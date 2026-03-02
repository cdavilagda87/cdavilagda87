"""
download_and_build_db.py
========================
Descarga el archivo III2025.zip del BCE, extrae los archivos Excel,
detecta automáticamente dónde empiezan los datos en cada hoja,
y construye una base de datos SQLite con toda la información.

Uso:
    python download_and_build_db.py
"""

import os
import io
import re
import zipfile
import sqlite3
import logging
import requests
import pandas as pd
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------
ZIP_URL    = "https://contenido.bce.fin.ec/home1/economia/tasas/III2025.zip"
DATA_DIR   = Path("downloads")
DB_PATH    = Path("database/inclusion_financiera.db")
LOG_LEVEL  = logging.INFO

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. Descarga
# ---------------------------------------------------------------------------

def download_zip(url: str, dest_dir: Path) -> Path:
    """Descarga el ZIP y lo guarda en dest_dir. Devuelve la ruta local."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    filename = url.split("/")[-1]
    local_path = dest_dir / filename

    if local_path.exists():
        log.info("ZIP ya existe: %s — omitiendo descarga.", local_path)
        return local_path

    log.info("Descargando %s …", url)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    resp = requests.get(url, headers=headers, timeout=120)
    resp.raise_for_status()
    local_path.write_bytes(resp.content)
    log.info("Guardado en %s (%d KB)", local_path, len(resp.content) // 1024)
    return local_path


# ---------------------------------------------------------------------------
# 2. Extracción
# ---------------------------------------------------------------------------

def extract_zip(zip_path: Path, dest_dir: Path) -> list[Path]:
    """Extrae todos los archivos del ZIP y devuelve la lista de rutas."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    extracted = []
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            out = dest_dir / name
            if not out.exists():
                zf.extract(name, dest_dir)
            extracted.append(dest_dir / name)
    log.info("Archivos extraídos: %d", len(extracted))
    return extracted


# ---------------------------------------------------------------------------
# 3. Detección inteligente del encabezado en hojas de Excel
# ---------------------------------------------------------------------------

def _sanitize_name(name: str) -> str:
    """Convierte un nombre a snake_case apto para SQL."""
    name = str(name).strip()
    name = re.sub(r"[\s\-/\\()]+", "_", name)
    name = re.sub(r"[^\w]", "", name)
    name = re.sub(r"_+", "_", name).strip("_")
    return name.lower() or "col"


def find_header_row(df_raw: pd.DataFrame, min_non_null: int = 3) -> int:
    """
    Recorre filas buscando la primera con al menos `min_non_null` celdas
    no vacías — esa es la fila de encabezados.
    """
    for i, row in df_raw.iterrows():
        non_null = row.notna().sum()
        if non_null >= min_non_null:
            return i
    return 0


def read_sheet_smart(excel_path: Path, sheet_name: str) -> pd.DataFrame | None:
    """
    Lee una hoja de Excel saltando filas vacías antes de los encabezados.
    Devuelve None si la hoja no tiene datos útiles.
    """
    try:
        # Primera lectura sin encabezado para detectar dónde empiezan los datos
        df_raw = pd.read_excel(
            excel_path,
            sheet_name=sheet_name,
            header=None,
            dtype=str,
            nrows=60,          # sólo las primeras 60 filas para detectar header
        )
    except Exception as exc:
        log.warning("No se pudo leer hoja '%s': %s", sheet_name, exc)
        return None

    header_row = find_header_row(df_raw, min_non_null=3)

    # Segunda lectura con el encabezado real
    try:
        df = pd.read_excel(
            excel_path,
            sheet_name=sheet_name,
            header=header_row,
            dtype=str,
        )
    except Exception as exc:
        log.warning("Error leyendo hoja '%s' con header=%d: %s", sheet_name, header_row, exc)
        return None

    # Eliminar filas/columnas completamente vacías
    df = df.dropna(how="all").dropna(axis=1, how="all")

    if df.empty or len(df.columns) < 2:
        log.debug("Hoja '%s' descartada (sin datos)", sheet_name)
        return None

    # Renombrar columnas duplicadas / sin nombre
    new_cols = []
    seen: dict[str, int] = {}
    for col in df.columns:
        base = _sanitize_name(str(col))
        if not base or base.startswith("unnamed"):
            base = "col"
        if base in seen:
            seen[base] += 1
            base = f"{base}_{seen[base]}"
        else:
            seen[base] = 0
        new_cols.append(base)
    df.columns = new_cols

    # Eliminar filas que son sub-encabezados (>50 % vacías) o totalmente NaN
    threshold = max(1, len(df.columns) // 2)
    df = df.dropna(thresh=threshold)

    if len(df) < 2:
        log.debug("Hoja '%s' descartada (menos de 2 filas de datos)", sheet_name)
        return None

    log.info("  ✓ Hoja '%-30s'  → %d filas × %d cols", sheet_name, len(df), len(df.columns))
    return df


# ---------------------------------------------------------------------------
# 4. Escritura en SQLite
# ---------------------------------------------------------------------------

def table_name_from(excel_file: str, sheet: str) -> str:
    """Genera un nombre de tabla único a partir del archivo + hoja."""
    base_file = Path(excel_file).stem
    return _sanitize_name(f"{base_file}__{sheet}")[:64]


def write_to_sqlite(db_path: Path, table: str, df: pd.DataFrame) -> None:
    """Escribe (o reemplaza) una tabla en SQLite."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        df.to_sql(table, conn, if_exists="replace", index=False)


def save_manifest(db_path: Path, manifest: list[dict]) -> None:
    """Guarda un catálogo de tablas disponibles."""
    df_manifest = pd.DataFrame(manifest)
    with sqlite3.connect(db_path) as conn:
        df_manifest.to_sql("_manifest", conn, if_exists="replace", index=False)
    log.info("Manifiesto guardado (%d entradas)", len(manifest))


# ---------------------------------------------------------------------------
# 5. Pipeline principal
# ---------------------------------------------------------------------------

def process_excel_file(excel_path: Path, db_path: Path) -> list[dict]:
    """Procesa un archivo Excel y escribe todas sus hojas válidas en SQLite."""
    records = []
    try:
        xl = pd.ExcelFile(excel_path, engine="openpyxl")
        sheets = xl.sheet_names
    except Exception:
        try:
            xl = pd.ExcelFile(excel_path, engine="xlrd")
            sheets = xl.sheet_names
        except Exception as exc:
            log.error("No se pudo abrir %s: %s", excel_path.name, exc)
            return records

    log.info("Procesando '%s'  (%d hojas) …", excel_path.name, len(sheets))

    for sheet in sheets:
        df = read_sheet_smart(excel_path, sheet)
        if df is None:
            continue
        tname = table_name_from(excel_path.name, sheet)
        write_to_sqlite(db_path, tname, df)
        records.append({
            "archivo": excel_path.name,
            "hoja":    sheet,
            "tabla":   tname,
            "filas":   len(df),
            "columnas": len(df.columns),
        })

    return records


def run_pipeline():
    log.info("=" * 60)
    log.info("PIPELINE: Inclusión Financiera BCE — III2025")
    log.info("=" * 60)

    # 1. Descargar
    zip_path = download_zip(ZIP_URL, DATA_DIR)

    # 2. Extraer
    files = extract_zip(zip_path, DATA_DIR)
    excel_files = [f for f in files if f.suffix.lower() in (".xlsx", ".xls")]
    log.info("Archivos Excel encontrados: %d", len(excel_files))

    if not excel_files:
        log.error("No se encontraron archivos Excel en el ZIP.")
        return

    # 3. Procesar y escribir en SQLite
    if DB_PATH.exists():
        DB_PATH.unlink()
        log.info("Base de datos anterior eliminada.")

    all_manifest = []
    for excel_path in excel_files:
        records = process_excel_file(excel_path, DB_PATH)
        all_manifest.extend(records)

    # 4. Manifiesto
    save_manifest(DB_PATH, all_manifest)

    log.info("=" * 60)
    log.info("Proceso completado. Base de datos: %s", DB_PATH)
    log.info("Tablas creadas: %d", len(all_manifest))
    for r in all_manifest:
        log.info("  %s → %s  (%d f × %d c)", r["archivo"], r["tabla"], r["filas"], r["columnas"])
    log.info("=" * 60)


if __name__ == "__main__":
    run_pipeline()
