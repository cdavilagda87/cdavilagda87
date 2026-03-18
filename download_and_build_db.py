"""
download_and_build_db.py
========================
Descarga III2025.zip del BCE, extrae los Excel y construye una SQLite
con datos limpios (encabezados multinivel, secciones geográficas).

Uso:
    python download_and_build_db.py
"""

import logging
import zipfile
from pathlib import Path

import requests

from data_cleaner import process_excel_to_sqlite

ZIP_URL  = "https://contenido.bce.fin.ec/home1/economia/tasas/III2025.zip"
DATA_DIR = Path("downloads")
DB_PATH  = Path("database/inclusion_financiera.db")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def download_zip(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    local = dest.parent / url.split("/")[-1]
    if local.exists():
        log.info("ZIP ya existe: %s", local)
        return local
    log.info("Descargando %s …", url)
    headers = {"User-Agent": "Mozilla/5.0 (compatible; BCE-Dashboard/2.0)"}
    r = requests.get(url, headers=headers, timeout=180)
    r.raise_for_status()
    local.write_bytes(r.content)
    log.info("Guardado (%d KB)", len(r.content) // 1024)
    return local


def extract_zip(zip_path: Path, dest_dir: Path) -> list[Path]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(dest_dir)
    return list(dest_dir.rglob("*.xlsx")) + list(dest_dir.rglob("*.xls"))


def run():
    log.info("=" * 60)
    log.info("PIPELINE BCE — Inclusión Financiera III2025")
    log.info("=" * 60)

    zip_path = download_zip(ZIP_URL, DATA_DIR)
    excels = extract_zip(zip_path, DATA_DIR)
    log.info("Archivos Excel: %d", len(excels))

    if DB_PATH.exists():
        DB_PATH.unlink()

    all_manifest = []
    for ef in excels:
        records = process_excel_to_sqlite(ef, DB_PATH)
        all_manifest.extend(records)

    # Guardar manifiesto
    import sqlite3, pandas as pd
    with sqlite3.connect(DB_PATH) as conn:
        pd.DataFrame(all_manifest).to_sql("_manifest", conn,
                                           if_exists="replace", index=False)

    log.info("=" * 60)
    log.info("Completado. Tablas: %d  DB: %s", len(all_manifest), DB_PATH)
    for r in all_manifest:
        log.info("  %-40s  %d f × %d c  [%s]",
                 r["tabla"], r["filas"], r["columnas"], r["estructura"])
    log.info("=" * 60)


if __name__ == "__main__":
    run()
