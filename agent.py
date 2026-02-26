#!/usr/bin/env python3
"""
Excel-to-Dashboard Agent
========================
Descarga archivos ZIP/Excel/CSV desde el BCE (Banco Central del Ecuador),
extrae y parsea los datos, y los almacena en SQLite para ser
consumidos por los dashboards PHP, Java y estático (GitHub Pages / Netlify).

Uso:
    python agent.py                          # Procesa URL del BCE
    python agent.py --url <URL>              # URL personalizada
    python agent.py --max-files 3            # Limita archivos a procesar
    python agent.py --demo                   # Genera datos demo sin descargar
    python agent.py --csv datos.csv          # Procesa un CSV directamente
    python agent.py --csv a.csv b.csv        # Múltiples CSV
    python agent.py --file datos.zip         # ZIP o Excel local
    python agent.py --dir ./mis_datos/       # Carpeta con CSV/ZIP/Excel
"""

import os
import re
import sys
import time
import zipfile
import sqlite3
import logging
import argparse
import requests
import pandas as pd
from io import BytesIO
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

# ─────────────────────────────────────────────
#  Configuración
# ─────────────────────────────────────────────
BASE_URL = (
    "https://contenido.bce.fin.ec/documentos/informacioneconomica/"
    "MonetarioFinanciero/indiceINCFIN_InfTrimestral.htm"
)
DB_PATH      = Path("database/bce_data.db")
DOWNLOAD_DIR = Path("downloads")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-EC,es;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": "https://contenido.bce.fin.ec/",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
#  HTTP helpers
# ─────────────────────────────────────────────
def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def fetch_with_retry(session: requests.Session, url: str, **kwargs) -> requests.Response:
    """GET con hasta 4 reintentos y backoff exponencial."""
    for attempt in range(4):
        try:
            resp = session.get(url, timeout=30, **kwargs)
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            if attempt == 3:
                raise
            wait = 2 ** attempt
            logger.warning("Intento %d falló (%s). Reintentando en %ds…", attempt + 1, exc, wait)
            time.sleep(wait)


# ─────────────────────────────────────────────
#  Descubrimiento de enlaces
# ─────────────────────────────────────────────
def find_downloadable_links(html: str, base_url: str) -> list[dict]:
    """Encuentra todos los enlaces .zip / .xls / .xlsx en la página."""
    soup = BeautifulSoup(html, "html.parser")
    links = []
    seen = set()

    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        lower = href.lower()
        if not any(ext in lower for ext in (".zip", ".xls", ".xlsx")):
            continue
        full_url = urljoin(base_url, href)
        if full_url in seen:
            continue
        seen.add(full_url)
        text = tag.get_text(strip=True) or Path(urlparse(href).path).name
        links.append({"url": full_url, "text": text})
        logger.info("  Enlace encontrado: %s → %s", text, full_url)

    return links


# ─────────────────────────────────────────────
#  Descarga y extracción
# ─────────────────────────────────────────────
def download_file(session: requests.Session, url: str, dest: Path) -> bool:
    """Descarga un archivo. Retorna True si tuvo éxito."""
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        resp = fetch_with_retry(session, url, stream=True)
        with open(dest, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=8192):
                fh.write(chunk)
        logger.info("  Descargado → %s (%d KB)", dest.name, dest.stat().st_size // 1024)
        return True
    except Exception as exc:
        logger.error("  Error descargando %s: %s", url, exc)
        return False


def extract_excel_from_zip(zip_path: Path, extract_dir: Path) -> list[Path]:
    """Extrae archivos Excel de un ZIP. Retorna lista de rutas."""
    excel_files = []
    extract_dir.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            for name in zf.namelist():
                if "__MACOSX" in name:
                    continue
                if name.lower().endswith((".xls", ".xlsx")):
                    zf.extract(name, extract_dir)
                    path = extract_dir / name
                    excel_files.append(path)
                    logger.info("  Extraído: %s", name)
    except zipfile.BadZipFile as exc:
        logger.error("  ZIP inválido %s: %s", zip_path.name, exc)
    return excel_files


# ─────────────────────────────────────────────
#  Procesamiento Excel → SQLite
# ─────────────────────────────────────────────
def sanitize(name: str) -> str:
    """Convierte un string en identificador SQL válido."""
    s = re.sub(r"[^a-zA-Z0-9_]", "_", str(name).strip())
    s = re.sub(r"_+", "_", s).strip("_")
    return s[:60] or "col"


def ensure_metadata_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS _metadata (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            table_name  TEXT    UNIQUE,
            source_name TEXT,
            file_name   TEXT,
            sheet_name  TEXT,
            row_count   INTEGER,
            col_count   INTEGER,
            created_at  TEXT    DEFAULT (datetime('now'))
        )
    """)
    conn.commit()


def excel_to_sqlite(excel_path: Path, db_path: Path, source_name: str) -> int:
    """
    Lee todas las hojas de un Excel y las guarda como tablas en SQLite.
    Retorna el número de tablas creadas.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    tables_created = 0

    try:
        xl = pd.ExcelFile(excel_path, engine="openpyxl" if excel_path.suffix == ".xlsx" else "xlrd")
    except Exception as exc:
        logger.error("  No se pudo leer %s: %s", excel_path.name, exc)
        return 0

    conn = sqlite3.connect(db_path)
    ensure_metadata_table(conn)

    for sheet in xl.sheet_names:
        try:
            df = pd.read_excel(excel_path, sheet_name=sheet, header=0)
            df.dropna(how="all", inplace=True)
            df.dropna(axis=1, how="all", inplace=True)

            if df.empty:
                logger.debug("  Hoja vacía omitida: %s", sheet)
                continue

            # Limpiar nombres de columnas
            clean_cols = {}
            seen_cols: dict[str, int] = {}
            for i, col in enumerate(df.columns):
                base = sanitize(str(col)) if str(col).strip() else f"col_{i}"
                if base in seen_cols:
                    seen_cols[base] += 1
                    base = f"{base}_{seen_cols[base]}"
                else:
                    seen_cols[base] = 0
                clean_cols[col] = base
            df.rename(columns=clean_cols, inplace=True)

            # Metadatos de origen
            df["_source_name"] = source_name
            df["_sheet_name"]  = sheet
            df["_file_name"]   = excel_path.name

            table_name = f"data_{sanitize(source_name)}_{sanitize(sheet)}"[:60]
            df.to_sql(table_name, conn, if_exists="replace", index=False)

            conn.execute("""
                INSERT OR REPLACE INTO _metadata
                    (table_name, source_name, file_name, sheet_name, row_count, col_count)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (table_name, source_name, excel_path.name, sheet, len(df), len(df.columns)))
            conn.commit()

            logger.info("  ✔ Tabla '%s': %d filas × %d columnas", table_name, len(df), len(df.columns))
            tables_created += 1

        except Exception as exc:
            logger.warning("  Error en hoja '%s': %s", sheet, exc)

    conn.close()
    return tables_created


# ─────────────────────────────────────────────
#  Procesamiento CSV → SQLite
# ─────────────────────────────────────────────
def csv_to_sqlite(csv_path: Path, db_path: Path, source_name: str | None = None) -> int:
    """
    Lee un CSV y lo guarda como tabla en SQLite.
    Detecta automáticamente el separador (coma, punto y coma, tabulador).
    Retorna 1 si tuvo éxito, 0 si falló.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)

    if source_name is None:
        source_name = sanitize(csv_path.stem)[:40]

    # Detectar separador
    separador = ","
    try:
        sample = csv_path.read_text(encoding="utf-8", errors="replace")[:4096]
        counts = {sep: sample.count(sep) for sep in [",", ";", "\t", "|"]}
        separador = max(counts, key=counts.get)
        logger.debug("  CSV separador detectado: %r", separador)
    except Exception:
        pass

    try:
        df = pd.read_csv(
            csv_path,
            sep=separador,
            encoding="utf-8",
            on_bad_lines="skip",
            dtype_backend="numpy_nullable",
        )
    except UnicodeDecodeError:
        try:
            df = pd.read_csv(
                csv_path,
                sep=separador,
                encoding="latin-1",
                on_bad_lines="skip",
                dtype_backend="numpy_nullable",
            )
        except Exception as exc:
            logger.error("  No se pudo leer %s: %s", csv_path.name, exc)
            return 0
    except Exception as exc:
        logger.error("  No se pudo leer %s: %s", csv_path.name, exc)
        return 0

    df.dropna(how="all", inplace=True)
    df.dropna(axis=1, how="all", inplace=True)

    if df.empty:
        logger.warning("  CSV vacío o sin datos: %s", csv_path.name)
        return 0

    # Limpiar nombres de columnas
    clean_cols: dict = {}
    seen_cols: dict[str, int] = {}
    for i, col in enumerate(df.columns):
        base = sanitize(str(col)) if str(col).strip() else f"col_{i}"
        if base in seen_cols:
            seen_cols[base] += 1
            base = f"{base}_{seen_cols[base]}"
        else:
            seen_cols[base] = 0
        clean_cols[col] = base
    df.rename(columns=clean_cols, inplace=True)

    # Convertir columnas numéricas que quedaron como texto
    for col in df.columns:
        if df[col].dtype == object:
            try:
                converted = pd.to_numeric(
                    df[col].astype(str).str.replace(",", ".").str.strip(),
                    errors="coerce",
                )
                if converted.notna().mean() > 0.5:   # >50% convertibles → numérica
                    df[col] = converted
            except Exception:
                pass

    # Metadatos de origen
    df["_source_name"] = source_name
    df["_sheet_name"]  = csv_path.stem
    df["_file_name"]   = csv_path.name

    table_name = f"data_{sanitize(source_name)}_{sanitize(csv_path.stem)}"[:60]

    conn = sqlite3.connect(db_path)
    ensure_metadata_table(conn)
    df.to_sql(table_name, conn, if_exists="replace", index=False)
    conn.execute("""
        INSERT OR REPLACE INTO _metadata
            (table_name, source_name, file_name, sheet_name, row_count, col_count)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (table_name, source_name, csv_path.name, csv_path.stem, len(df), len(df.columns)))
    conn.commit()
    conn.close()

    logger.info("  ✔ CSV '%s': %d filas × %d columnas → tabla '%s'",
                csv_path.name, len(df), len(df.columns), table_name)
    return 1


# ─────────────────────────────────────────────
#  Datos de demostración
# ─────────────────────────────────────────────
def create_demo_data(db_path: Path) -> None:
    """Crea datos de demostración si no se puede descargar el Excel real."""
    import random
    logger.info("Generando datos de demostración…")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    ensure_metadata_table(conn)

    # Tabla de índices financieros demo
    periodos = [f"{y}T{t}" for y in range(2020, 2026) for t in range(1, 5)]
    rows = []
    base = {"credito": 100, "depositos": 100, "tasas": 8.5}
    for p in periodos:
        base["credito"]  *= 1 + random.uniform(0.01, 0.04)
        base["depositos"] *= 1 + random.uniform(0.005, 0.03)
        base["tasas"]     += random.uniform(-0.2, 0.3)
        rows.append({
            "periodo": p,
            "indice_credito": round(base["credito"], 2),
            "indice_depositos": round(base["depositos"], 2),
            "tasa_activa": round(base["tasas"], 2),
            "tasa_pasiva": round(base["tasas"] * 0.4, 2),
            "_source_name": "demo",
            "_sheet_name": "IndicesFinancieros",
            "_file_name": "demo_data.xlsx",
        })

    df = pd.DataFrame(rows)
    df.to_sql("data_demo_IndicesFinancieros", conn, if_exists="replace", index=False)

    # Tabla de liquidez demo
    liq_rows = []
    liq = 2_500_000
    for p in periodos:
        liq *= 1 + random.uniform(-0.02, 0.05)
        liq_rows.append({
            "periodo": p,
            "liquidez_total_miles_usd": round(liq, 2),
            "reservas_miles_usd": round(liq * 0.15, 2),
            "_source_name": "demo",
            "_sheet_name": "Liquidez",
            "_file_name": "demo_data.xlsx",
        })

    df2 = pd.DataFrame(liq_rows)
    df2.to_sql("data_demo_Liquidez", conn, if_exists="replace", index=False)

    # Metadata
    for tbl, sheet, rows_n, cols_n in [
        ("data_demo_IndicesFinancieros", "IndicesFinancieros", len(rows), 7),
        ("data_demo_Liquidez", "Liquidez", len(liq_rows), 4),
    ]:
        conn.execute("""
            INSERT OR REPLACE INTO _metadata
                (table_name, source_name, file_name, sheet_name, row_count, col_count)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (tbl, "demo", "demo_data.xlsx", sheet, rows_n, cols_n))
    conn.commit()
    conn.close()
    logger.info("Datos demo creados en %s", db_path)


# ─────────────────────────────────────────────
#  Agente principal
# ─────────────────────────────────────────────
def process_local_files(paths: list[Path]) -> bool:
    """Procesa archivos ZIP/Excel locales directamente (sin descargar)."""
    logger.info("=" * 60)
    logger.info("Excel-to-Dashboard Agent — Modo archivos locales")
    logger.info("=" * 60)
    total_tables = 0

    for i, path in enumerate(paths, 1):
        if not path.exists():
            logger.warning("[%d/%d] No encontrado: %s", i, len(paths), path)
            continue

        source = f"bce_{i:03d}_{sanitize(path.stem)}"[:40]
        logger.info("[%d/%d] Procesando: %s", i, len(paths), path.name)

        if path.suffix.lower() == ".zip":
            extract_dir = DOWNLOAD_DIR / f"ex_local_{i:03d}"
            excel_files = extract_excel_from_zip(path, extract_dir)
        else:
            excel_files = [path]

        for xls in excel_files:
            if xls.exists():
                total_tables += excel_to_sqlite(xls, DB_PATH, source)

    logger.info("=" * 60)
    logger.info("¡Completado! %d tablas creadas en %s", total_tables, DB_PATH)
    return True


def run_agent(url: str = BASE_URL, max_files: int | None = None, demo: bool = False) -> bool:
    logger.info("=" * 60)
    logger.info("Excel-to-Dashboard Agent")
    logger.info("=" * 60)

    if demo:
        create_demo_data(DB_PATH)
        return True

    logger.info("Fuente: %s", url)
    session = make_session()

    # 1. Descargar página
    logger.info("Paso 1/3 — Descargando página…")
    try:
        response = fetch_with_retry(session, url)
        logger.info("  HTTP %d — %d bytes", response.status_code, len(response.content))
    except Exception as exc:
        logger.error("No se pudo obtener la página: %s", exc)
        logger.info("Usando datos de demostración como fallback…")
        create_demo_data(DB_PATH)
        return True

    # 2. Encontrar enlaces
    logger.info("Paso 2/3 — Buscando enlaces descargables…")
    links = find_downloadable_links(response.text, url)

    if not links:
        logger.warning("No se encontraron enlaces ZIP/Excel. Usando datos demo.")
        create_demo_data(DB_PATH)
        return True

    if max_files:
        links = links[:max_files]
    logger.info("  %d archivo(s) a procesar", len(links))

    # 3. Descargar, extraer y procesar
    logger.info("Paso 3/3 — Descargando y procesando archivos…")
    DOWNLOAD_DIR.mkdir(exist_ok=True)
    total_tables = 0

    for i, link in enumerate(links, 1):
        file_url = link["url"]
        source   = f"bce_{i:03d}"
        filename = Path(urlparse(file_url).path).name
        dest     = DOWNLOAD_DIR / filename

        logger.info("[%d/%d] %s", i, len(links), link["text"])

        if not download_file(session, file_url, dest):
            continue

        if filename.lower().endswith(".zip"):
            excel_files = extract_excel_from_zip(dest, DOWNLOAD_DIR / f"ex_{i:03d}")
        else:
            excel_files = [dest]

        for xls in excel_files:
            if xls.exists():
                total_tables += excel_to_sqlite(xls, DB_PATH, source)

        time.sleep(0.5)

    logger.info("=" * 60)
    logger.info("¡Agente completado! %d tablas creadas en %s", total_tables, DB_PATH)
    return True


# ─────────────────────────────────────────────
#  CLI
# ─────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Descarga Excel del BCE y lo convierte en base de datos SQLite.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python agent.py                          # descarga real desde el BCE
  python agent.py --max-files 3            # solo los primeros 3 archivos
  python agent.py --demo                   # datos de prueba (sin internet)
  python agent.py --file datos.zip         # procesa un ZIP local
  python agent.py --dir ./mis_excels/      # procesa todos los ZIP/Excel en carpeta
  python agent.py --url https://otro.com   # URL personalizada
        """,
    )
    parser.add_argument("--url", default=BASE_URL, help="URL de la página fuente")
    parser.add_argument("--max-files", type=int, default=None, metavar="N",
                        help="Máximo de archivos a procesar (modo URL)")
    parser.add_argument("--demo", action="store_true",
                        help="Genera datos de demostración (sin descarga real)")
    parser.add_argument("--file", metavar="RUTA",
                        help="Procesa un archivo ZIP, Excel o CSV local directamente")
    parser.add_argument("--csv", metavar="CSV", nargs="+",
                        help="Uno o más archivos CSV a procesar directamente")
    parser.add_argument("--dir", metavar="CARPETA",
                        help="Procesa todos los ZIP/Excel/CSV en una carpeta local")
    args = parser.parse_args()

    if args.csv:
        # Modo CSV directo
        logger.info("=" * 60)
        logger.info("Excel-to-Dashboard Agent — Modo CSV directo")
        logger.info("=" * 60)
        total = 0
        for csv_file in args.csv:
            p = Path(csv_file)
            if not p.exists():
                logger.warning("Archivo no encontrado: %s", p)
                continue
            if p.suffix.lower() == ".csv":
                total += csv_to_sqlite(p, DB_PATH, sanitize(p.stem)[:40])
            else:
                # Si pasan un XLS/ZIP por --csv por error, procesarlo igual
                total += excel_to_sqlite(p, DB_PATH, sanitize(p.stem)[:40])
        logger.info("¡Completado! %d tablas creadas en %s", total, DB_PATH)
        success = total > 0
    elif args.file:
        p = Path(args.file)
        if p.suffix.lower() == ".csv":
            success = csv_to_sqlite(p, DB_PATH) > 0
        else:
            success = process_local_files([p])
    elif args.dir:
        folder = Path(args.dir)
        files = sorted(
            list(folder.glob("*.zip")) +
            list(folder.glob("*.xls")) +
            list(folder.glob("*.xlsx")) +
            list(folder.glob("*.csv"))
        )
        if not files:
            logger.error("No se encontraron ZIP/Excel/CSV en: %s", folder)
            sys.exit(1)
        logger.info("Archivos encontrados en '%s': %d", folder, len(files))
        csv_files   = [f for f in files if f.suffix.lower() == ".csv"]
        other_files = [f for f in files if f.suffix.lower() != ".csv"]
        total = 0
        for csv_f in csv_files:
            total += csv_to_sqlite(csv_f, DB_PATH, sanitize(csv_f.stem)[:40])
        if other_files:
            process_local_files(other_files)
        success = True
    else:
        success = run_agent(url=args.url, max_files=args.max_files, demo=args.demo)

    sys.exit(0 if success else 1)
