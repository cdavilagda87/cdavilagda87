# CLAUDE.md — Excel-to-Dashboard Agent (BCE Ecuador)

This file provides guidance for AI assistants working in this repository.

## Project Overview

This project is an **Excel-to-Dashboard Agent** that:
1. Downloads ZIP/Excel files from the Banco Central del Ecuador (BCE) website
2. Parses and stores the data in a SQLite database
3. Serves the data through interactive dashboards (PHP or Java)
4. Exports a static standalone HTML dashboard for GitHub Pages

**Primary language:** Python 3.11+
**Secondary languages:** PHP, Java 17 (Spring Boot 3.2), HTML/JS

---

## Repository Structure

```
.
├── agent.py                  # Main agent: download → extract → SQLite
├── export_to_html.py         # Static HTML exporter for GitHub Pages
├── trade_price_indices.py    # Standalone trade price index calculator module
├── demo.py                   # Demo runner (no network required)
├── requirements.txt          # Python dependencies
├── database/
│   └── bce_data.db           # SQLite DB (git-ignored, generated at runtime)
├── downloads/                # Downloaded ZIP/Excel files (git-ignored)
├── docs/
│   └── index.html            # Static HTML export (served by GitHub Pages)
├── dashboard-php/
│   ├── index.php             # Interactive web dashboard
│   ├── api.php               # REST API (JSON)
│   └── config.php            # DB path configuration
├── dashboard-java/
│   ├── pom.xml               # Maven build (Java 17, Spring Boot 3.2)
│   └── src/main/
│       ├── java/com/dashboard/
│       │   ├── DashboardApplication.java
│       │   ├── controller/DashboardController.java
│       │   ├── service/DataService.java
│       │   └── model/{TableMeta,TableData}.java
│       └── resources/
│           ├── application.properties
│           └── templates/index.html   # Thymeleaf template
└── .github/workflows/
    ├── pages.yml             # CI: build agent → export HTML → deploy Pages
    └── jekyll-gh-pages.yml   # Alternative Jekyll Pages workflow
```

---

## Development Workflows

### Python Setup

```bash
pip install -r requirements.txt
```

**Dependencies:** `requests>=2.31`, `beautifulsoup4>=4.12`, `pandas>=2.1`, `openpyxl>=3.1`, `xlrd>=2.0`, `lxml>=4.9`

### Running the Agent

```bash
# Download real data from BCE (requires internet)
python agent.py

# Limit to first N files (useful for testing)
python agent.py --max-files 3

# Demo mode — no network, generates synthetic data
python agent.py --demo

# Process a local ZIP or Excel file
python agent.py --file path/to/file.zip

# Process all ZIP/Excel files in a folder
python agent.py --dir ./my_excels/

# Custom source URL
python agent.py --url https://other-site.com/page
```

The agent writes to `database/bce_data.db`. If the BCE site is unreachable it **automatically falls back to demo data** — no special handling needed.

### Exporting to Static HTML

```bash
# Default: reads database/bce_data.db, writes docs/index.html
python export_to_html.py

# With options
python export_to_html.py --db database/bce_data.db --out docs/index.html --max-rows 500
```

### PHP Dashboard

```bash
cd dashboard-php
php -S 0.0.0.0:8080
# Open: http://localhost:8080
```

### Java Dashboard (Spring Boot)

```bash
cd dashboard-java
mvn spring-boot:run
# Open: http://localhost:8081
```

Requires Java 17+ and Maven 3.x installed.

---

## Key Modules

### `agent.py`

Core pipeline with these sections (marked by `# ────` banners):

| Section | Functions | Purpose |
|---|---|---|
| HTTP helpers | `make_session()`, `fetch_with_retry()` | Session with BCE headers; 4-attempt exponential backoff |
| Link discovery | `find_downloadable_links()` | Scrapes `.zip`/`.xls`/`.xlsx` links from HTML |
| Download/extract | `download_file()`, `extract_excel_from_zip()` | Downloads and unzips files |
| Excel → SQLite | `sanitize()`, `excel_to_sqlite()` | Converts all Excel sheets to SQLite tables |
| Demo data | `create_demo_data()` | Generates synthetic financial data (2020–2025) |
| CLI entry | `run_agent()`, `process_local_files()` | Top-level orchestration |

**SQLite schema:** Each Excel sheet becomes a table named `data_{source}_{sheet}` (max 60 chars). A `_metadata` table tracks provenance. Columns starting with `_` are internal metadata (`_source_name`, `_sheet_name`, `_file_name`).

### `trade_price_indices.py`

Standalone economics module — no external dependencies beyond stdlib. Implements:
- `Producto` dataclass — a tradeable good with base/current price & quantity
- `Canasta` dataclass — basket of products (exports or imports)
- `CalculadoraIndices` — computes Laspeyres, Paasche, Fisher indices, Terms of Trade, and Unit Value Variation

### `export_to_html.py`

Reads SQLite data and embeds it as JSON inside a self-contained HTML file with Chart.js. The output has zero server dependencies.

---

## REST API Reference

Both dashboards expose identical endpoints:

| PHP | Java | Description |
|---|---|---|
| `GET /api.php?action=tables` | `GET /api/tables` | List all tables |
| `GET /api.php?action=data&table=NAME` | `GET /api/data/{name}` | Table data (paginated) |
| `GET /api.php?action=stats` | `GET /api/stats` | Row/table counts |

PHP also supports `limit` and `offset` query params on the `data` action.

---

## CI/CD — GitHub Actions

**`pages.yml`** runs on pushes to `main` that touch `agent.py`, `export_to_html.py`, `requirements.txt`, or itself:

1. Checkout + Python 3.11 + pip cache
2. `pip install -r requirements.txt`
3. `python agent.py --max-files 5` (falls back to demo if BCE unreachable)
4. `python export_to_html.py --max-rows 500`
5. Verify `docs/index.html` exists
6. Upload `docs/` as GitHub Pages artifact and deploy

Deployed URL: `https://<user>.github.io/<repo>/`

---

## Coding Conventions

### Python

- **Docstrings:** module-level and function-level, in Spanish
- **Logging:** use the module-level `logger = logging.getLogger(__name__)` with `logger.info/warning/error/debug`. Format: `HH:MM:SS [LEVEL] message`
- **Path handling:** use `pathlib.Path` throughout — no raw string paths
- **SQL safety:** table names are validated against `_metadata` before use (PHP: PDO prepared statements; Python: `sanitize()` + whitelist check)
- **Retry pattern:** `fetch_with_retry()` — 4 attempts, exponential backoff `2^attempt` seconds
- **Column naming:** `sanitize(name)` → alphanumeric + underscore, max 60 chars, deduped with `_N` suffix
- **Type hints:** used on function signatures (Python 3.10+ union syntax `X | Y`)

### PHP

- PDO with prepared statements for all user-supplied values
- Table names validated against `_metadata` whitelist before interpolation
- CORS header `Access-Control-Allow-Origin: *` on API responses
- Errors returned as `{'status': 'error', 'message': '...'}` JSON

### Java

- Spring Boot 3.2, Java 17
- Package root: `com.dashboard`
- Thymeleaf for server-rendered HTML templates
- Same REST contract as the PHP API

### General

- **No committing generated files:** `downloads/*`, `database/*.db`, `__pycache__/`, `*.pyc`, Java `target/`
- **Demo fallback:** all network-dependent code must handle failures gracefully by falling back to `--demo` data
- **Language:** code comments and docs are in **Spanish** (project convention)

---

## Git Conventions

- Feature branches: `claude/<description>-<session-id>` (e.g., `claude/excel-to-dashboard-agent-DFzNy`)
- Push with: `git push -u origin <branch-name>`
- Retry pushes up to 4 times on network failure (exponential backoff: 2s, 4s, 8s, 16s)

---

## Data Source

- **URL:** `https://contenido.bce.fin.ec/documentos/informacioneconomica/MonetarioFinanciero/indiceINCFIN_InfTrimestral.htm`
- **Format:** `.zip` files containing `.xls`/`.xlsx` Excel workbooks
- **Content:** Quarterly monetary and financial indices of Ecuador
- **Access:** The BCE site can be intermittently unreachable; always code with the demo fallback in mind
