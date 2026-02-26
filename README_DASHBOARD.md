# Excel-to-Dashboard Agent — BCE Ecuador

Agente que descarga archivos Excel/ZIP desde el sitio del Banco Central del Ecuador,
los procesa y genera una base de datos SQLite lista para ser consumida por dos
dashboards interactivos (PHP y Java).

```
┌──────────────────────────────────────────────────────────────────┐
│                      FLUJO DEL AGENTE                            │
│                                                                  │
│  Página BCE  →  ZIP descargado  →  Excel extraído               │
│       ↓                                                          │
│  agent.py (Python)                                               │
│       ↓                                                          │
│  database/bce_data.db  (SQLite)                                  │
│       ↓                    ↓                                     │
│  dashboard-php/         dashboard-java/                          │
│  (PHP + Chart.js)       (Spring Boot + Chart.js)                 │
│  puerto 8080            puerto 8081                              │
└──────────────────────────────────────────────────────────────────┘
```

## Instalación rápida

### 1. Dependencias Python

```bash
pip install -r requirements.txt
```

### 2. Ejecutar el agente

```bash
# Descarga real desde el BCE (requiere acceso a internet)
python agent.py

# Limitar a los primeros 3 archivos
python agent.py --max-files 3

# Modo demo (sin descargas, usa datos generados)
python agent.py --demo

# URL personalizada
python agent.py --url https://otro-sitio.com/pagina-excel
```

### 3. Dashboard PHP

```bash
cd dashboard-php
php -S 0.0.0.0:8080
# Abrir: http://localhost:8080
```

### 4. Dashboard Java (Spring Boot)

```bash
cd dashboard-java
mvn spring-boot:run
# Abrir: http://localhost:8081
```

## Estructura del proyecto

```
.
├── agent.py                    # Agente principal (Python)
├── requirements.txt            # Dependencias Python
├── database/
│   └── bce_data.db             # SQLite generado por el agente
├── downloads/                  # Archivos ZIP/Excel descargados
├── dashboard-php/
│   ├── index.php               # Dashboard web interactivo
│   ├── api.php                 # API REST (JSON)
│   └── config.php              # Configuración (ruta DB)
└── dashboard-java/
    ├── pom.xml                 # Maven
    └── src/main/
        ├── java/com/dashboard/
        │   ├── DashboardApplication.java
        │   ├── controller/DashboardController.java
        │   ├── service/DataService.java
        │   └── model/{TableMeta,TableData}.java
        └── resources/
            ├── application.properties
            └── templates/index.html
```

## Características del Dashboard

- **Gráficos interactivos**: línea, barras, área (Chart.js 4)
- **Selector de ejes**: escoge qué columnas graficar
- **Tabla paginada**: 50 filas por página con navegación
- **Exportar CSV**: descarga los datos actuales
- **API REST**: consumible por cualquier cliente externo
- **Responsive**: funciona en móvil y escritorio

## API REST

Ambos dashboards exponen la misma API:

| PHP                                         | Java                              | Descripción          |
|---------------------------------------------|-----------------------------------|----------------------|
| `GET /api.php?action=tables`                | `GET /api/tables`                 | Lista de tablas      |
| `GET /api.php?action=data&table=NAME`       | `GET /api/data/{name}`            | Datos de una tabla   |
| `GET /api.php?action=stats`                 | `GET /api/stats`                  | Estadísticas         |

## Fuente de datos

- **URL**: https://contenido.bce.fin.ec/documentos/informacioneconomica/MonetarioFinanciero/indiceINCFIN_InfTrimestral.htm
- **Formato**: Archivos `.zip` con Excel `.xls`/`.xlsx` dentro
- **Contenido**: Índices monetarios y financieros trimestrales del Ecuador
