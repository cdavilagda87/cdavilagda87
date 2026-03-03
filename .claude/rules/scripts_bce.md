---
description: Reglas para scripts de procesamiento BCE
globs: "*.py"
---
- Siempre manejar ZipFile con context manager (with ZipFile)
- requests: usar timeout=30 y manejar ConnectionError
- pandas: leer Excel con engine='openpyxl' para .xlsx, engine='xlrd' para .xls
- SQLite: usar context manager (with sqlite3.connect) para commits seguros
- Logging: usar print con timestamp f"[{datetime.now():%H:%M:%S}]"