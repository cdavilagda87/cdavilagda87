# Dashboard PHP — BCE Ecuador

## Requisitos
- PHP >= 8.0 con extensiones: `pdo_sqlite`, `sqlite3`

## Uso

```bash
# 1. Ejecutar el agente Python para generar la DB
cd ..
python agent.py          # descarga real del BCE
python agent.py --demo   # datos de prueba

# 2. Iniciar servidor PHP
cd dashboard-php
php -S 0.0.0.0:8080

# 3. Abrir en el navegador
http://localhost:8080
```

## Deploy en hosting compartido
1. Subir toda la carpeta `dashboard-php/` y `database/` al hosting
2. Asegurarse de que la ruta en `config.php → DB_PATH` es correcta
3. Acceder vía el dominio del hosting

## API Endpoints
| Endpoint | Descripción |
|---|---|
| `api.php?action=tables` | Lista de tablas disponibles |
| `api.php?action=data&table=NAME` | Datos de una tabla |
| `api.php?action=stats` | Estadísticas generales |
