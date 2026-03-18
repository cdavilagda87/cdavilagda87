# Excel-to-Dashboard BCE Ecuador — Inclusión Financiera

## Arquitectura
- agent.py → descarga ZIP desde BCE → extrae Excel → SQLite
- database/bce_data.db → dashboard-php (puerto 8080) + dashboard-java (8081)
- inclusion_financiera_app.py → app Streamlit alternativa
- export_to_html.py → exportación HTML standalone

## Fuente de datos
- URL BCE: https://contenido.bce.fin.ec/documentos/informacioneconomica/MonetarioFinanciero/indiceINCFIN_InfTrimestral.htm
- Formato: ZIP con Excel .xls/.xlsx adentro
- Contenido: índices monetarios y financieros trimestrales

## Comandos frecuentes
- python agent.py --demo              # prueba sin descargar
- python agent.py --max-files 3       # limitar descarga
- python agent.py                     # descarga completa desde BCE
- streamlit run inclusion_financiera_app.py
- cd dashboard-php && php -S 0.0.0.0:8080

## Archivos clave
- agent.py              → agente principal de descarga y procesamiento
- data_cleaner.py       → limpieza de datos Excel del BCE
- download_and_build_db.py → construcción de SQLite
- inclusion_financiera_app.py → dashboard Streamlit
- export_to_html.py     → exportación HTML

## Convenciones
- Nombres de tablas SQLite: snake_case
- Períodos: YYYY-MM o YYYY-QN (trimestral)
- No modificar database/*.db directamente (generado por agent.py)
- No modificar downloads/ (generado automáticamente)