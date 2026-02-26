#!/usr/bin/env python3
"""
export_to_html.py
=================
Exporta la base de datos SQLite generada por agent.py a un dashboard
HTML completamente autónomo (sin servidor).

El HTML resultante puede alojarse en cualquier hosting estático:
  - GitHub Pages  → https://<usuario>.github.io/<repo>/
  - Netlify Drop  → arrastra la carpeta docs/
  - Cualquier servidor web / hosting compartido

Uso:
    python export_to_html.py
    python export_to_html.py --db database/bce_data.db --out docs/index.html
    python export_to_html.py --max-rows 500
"""

import json
import sqlite3
import argparse
import sys
from datetime import datetime
from pathlib import Path

DB_PATH  = Path("database/bce_data.db")
OUT_PATH = Path("docs/index.html")
MAX_ROWS_PER_TABLE = 500   # máximo de filas embebidas por tabla


# ─────────────────────────────────────────────
#  Lectura de datos
# ─────────────────────────────────────────────
def load_all_tables(db_path: Path, max_rows: int) -> list[dict]:
    """Lee todas las tablas de _metadata y sus datos."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    metas = conn.execute(
        "SELECT * FROM _metadata ORDER BY created_at DESC"
    ).fetchall()

    tables = []
    for m in metas:
        table_name = m["table_name"]
        try:
            rows = conn.execute(
                f'SELECT * FROM "{table_name}" LIMIT ?', (max_rows,)
            ).fetchall()
        except Exception:
            continue

        if not rows:
            continue

        # Clasificar columnas
        cols        = rows[0].keys()
        pub_cols    = [c for c in cols if not c.startswith("_")]
        numeric_cols, text_cols = [], []
        for col in pub_cols:
            val = rows[0][col]
            if isinstance(val, (int, float)):
                numeric_cols.append(col)
            else:
                text_cols.append(col)

        tables.append({
            "tableName":   table_name,
            "sourceName":  m["source_name"],
            "fileName":    m["file_name"]  or "",
            "sheetName":   m["sheet_name"] or table_name,
            "rowCount":    m["row_count"],
            "colCount":    m["col_count"],
            "numericCols": numeric_cols,
            "textCols":    text_cols,
            "rows": [
                {c: row[c] for c in pub_cols}
                for row in rows
            ],
        })

    conn.close()
    return tables


# ─────────────────────────────────────────────
#  Generación del HTML
# ─────────────────────────────────────────────
def generate_html(tables: list[dict], generated_at: str) -> str:
    data_json = json.dumps(tables, ensure_ascii=False, default=str)

    total_tables = len(tables)
    total_rows   = sum(t["rowCount"] for t in tables)

    table_cards_html = ""
    for t in tables:
        table_cards_html += f"""
        <div class="card table-card mb-2 shadow-sm"
             onclick="selectTable('{t['tableName']}', this)"
             data-table="{t['tableName']}">
            <div class="card-body py-2 px-3">
                <div class="fw-semibold small text-truncate" title="{t['sheetName']}">{t['sheetName']}</div>
                <div class="d-flex justify-content-between align-items-center mt-1">
                    <small class="text-muted">{t['sourceName']}</small>
                    <span class="badge badge-rows text-white">{t['rowCount']:,}</span>
                </div>
            </div>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard BCE — Índices Financieros</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
    <style>
        :root {{--bce-blue:#003366;--bce-yellow:#F5A800;--bce-light:#f0f4f8;}}
        body         {{background:var(--bce-light);font-family:'Segoe UI',sans-serif;}}
        .stat-card   {{border-left:4px solid var(--bce-yellow);}}
        .stat-number {{font-size:2rem;font-weight:700;color:var(--bce-blue);}}
        .table-card  {{cursor:pointer;transition:transform .15s,box-shadow .15s;}}
        .table-card:hover {{transform:translateY(-2px);box-shadow:0 6px 20px rgba(0,0,0,.12);}}
        .table-card.active {{border:2px solid var(--bce-blue);}}
        .chart-container {{position:relative;height:320px;}}
        .badge-rows  {{background:var(--bce-blue);}}
        footer       {{background:var(--bce-blue);color:#cdd8e3;font-size:.85rem;}}
    </style>
</head>
<body>

<nav class="navbar navbar-dark py-2" style="background:var(--bce-blue)">
    <div class="container-fluid">
        <span class="navbar-brand">
            <i class="bi bi-bar-chart-fill me-2" style="color:var(--bce-yellow)"></i>
            Dashboard BCE · Índices Financieros
        </span>
        <small class="text-white-50">Generado: {generated_at}</small>
    </div>
</nav>

<div class="container-fluid py-4">

    <!-- Tarjetas resumen -->
    <div class="row g-3 mb-4">
        <div class="col-sm-6 col-lg-3">
            <div class="card stat-card shadow-sm h-100">
                <div class="card-body">
                    <div class="text-muted small">Tablas disponibles</div>
                    <div class="stat-number">{total_tables}</div>
                </div>
            </div>
        </div>
        <div class="col-sm-6 col-lg-3">
            <div class="card stat-card shadow-sm h-100">
                <div class="card-body">
                    <div class="text-muted small">Total de registros</div>
                    <div class="stat-number">{total_rows:,}</div>
                </div>
            </div>
        </div>
        <div class="col-sm-6 col-lg-3">
            <div class="card stat-card shadow-sm h-100">
                <div class="card-body">
                    <div class="text-muted small">Fuente</div>
                    <div class="stat-number" style="font-size:1.1rem;padding-top:.5rem">BCE Ecuador</div>
                </div>
            </div>
        </div>
        <div class="col-sm-6 col-lg-3">
            <div class="card stat-card shadow-sm h-100">
                <div class="card-body">
                    <div class="text-muted small">Tipo</div>
                    <div class="stat-number" style="font-size:1.1rem;padding-top:.5rem">
                        <i class="bi bi-github me-1"></i>GitHub Pages
                    </div>
                </div>
            </div>
        </div>
    </div>

    <div class="row g-4">
        <!-- Lista de tablas -->
        <div class="col-lg-3">
            <h6 class="text-uppercase text-muted fw-bold mb-2">
                <i class="bi bi-table me-1"></i>Conjuntos de datos
            </h6>
            {table_cards_html}
        </div>

        <!-- Área principal -->
        <div class="col-lg-9">
            <div id="dashboard-content" style="display:none">
                <div class="d-flex justify-content-between align-items-center mb-3">
                    <h5 id="dash-title" class="mb-0"></h5>
                    <div class="d-flex gap-2">
                        <select id="chart-type" class="form-select form-select-sm w-auto" onchange="updateChart()">
                            <option value="line">Línea</option>
                            <option value="bar">Barras</option>
                            <option value="area">Área</option>
                        </select>
                        <button class="btn btn-sm btn-outline-secondary" onclick="exportCSV()">
                            <i class="bi bi-download me-1"></i>CSV
                        </button>
                    </div>
                </div>

                <div class="row g-2 mb-3">
                    <div class="col-md-4">
                        <label class="form-label small fw-semibold">Eje X (categoría)</label>
                        <select id="x-col" class="form-select form-select-sm" onchange="updateChart()"></select>
                    </div>
                    <div class="col-md-8">
                        <label class="form-label small fw-semibold">Series (columnas numéricas)</label>
                        <div id="y-cols" class="d-flex flex-wrap gap-2"></div>
                    </div>
                </div>

                <div class="card shadow-sm mb-4">
                    <div class="card-body">
                        <div class="chart-container">
                            <canvas id="main-chart"></canvas>
                        </div>
                    </div>
                </div>

                <div class="card shadow-sm">
                    <div class="card-header d-flex justify-content-between align-items-center py-2">
                        <span class="fw-semibold small">Datos (<span id="row-count">0</span> registros)</span>
                        <div class="d-flex gap-2">
                            <button class="btn btn-sm btn-outline-primary" onclick="prevPage()">
                                <i class="bi bi-chevron-left"></i>
                            </button>
                            <span id="page-info" class="small align-self-center"></span>
                            <button class="btn btn-sm btn-outline-primary" onclick="nextPage()">
                                <i class="bi bi-chevron-right"></i>
                            </button>
                        </div>
                    </div>
                    <div class="card-body p-0">
                        <div class="table-responsive">
                            <table class="table table-sm table-hover mb-0">
                                <thead class="table-dark" id="data-thead"></thead>
                                <tbody id="data-tbody"></tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>

            <div id="placeholder" class="text-center py-5 text-muted">
                <i class="bi bi-mouse2 fs-1 d-block mb-3"></i>
                Seleccione un conjunto de datos de la lista
            </div>
        </div>
    </div>
</div>

<footer class="py-3 mt-4">
    <div class="container-fluid text-center">
        Dashboard BCE · Excel-to-Dashboard Agent · GitHub Pages · Chart.js
    </div>
</footer>

<script>
// ─── Datos embebidos (generados por export_to_html.py) ──────────
const ALL_TABLES = {data_json};

// ─── Estado ─────────────────────────────────────────────────────
const PAGE_SIZE    = 50;
let currentTable   = null;
let currentPage    = 0;
let chartInstance  = null;
let selectedSeries = new Set();

const PALETTE = [
    '#003366','#F5A800','#2196F3','#4CAF50','#E91E63',
    '#9C27B0','#FF5722','#009688','#607D8B','#795548',
];

// ─── Seleccionar tabla ───────────────────────────────────────────
function selectTable(tableName, el) {{
    document.querySelectorAll('.table-card').forEach(c => c.classList.remove('active'));
    el.classList.add('active');
    currentTable = ALL_TABLES.find(t => t.tableName === tableName);
    currentPage  = 0;
    document.getElementById('placeholder').style.display       = 'none';
    document.getElementById('dashboard-content').style.display = 'block';
    document.getElementById('dash-title').textContent =
        tableName.replace(/^data_/, '').replace(/_/g, ' ');
    document.getElementById('row-count').textContent = currentTable.rowCount.toLocaleString();
    buildAxisSelectors();
    renderPage();
    updateChart();
    updatePageInfo();
}}

// ─── Selectores de ejes ──────────────────────────────────────────
function buildAxisSelectors() {{
    const xSel = document.getElementById('x-col');
    xSel.innerHTML = '';
    [...currentTable.textCols, ...currentTable.numericCols].forEach(col => {{
        const opt = document.createElement('option');
        opt.value = opt.textContent = col;
        xSel.appendChild(opt);
    }});
    if (currentTable.textCols.length) xSel.value = currentTable.textCols[0];

    const yDiv = document.getElementById('y-cols');
    yDiv.innerHTML = '';
    selectedSeries = new Set(currentTable.numericCols.slice(0, 4));
    currentTable.numericCols.forEach((col, i) => {{
        const color = PALETTE[i % PALETTE.length];
        const lbl   = document.createElement('label');
        lbl.className = 'form-check-label small d-flex align-items-center gap-1 border rounded px-2 py-1';
        lbl.style.cursor = 'pointer';
        lbl.innerHTML = `<input class="form-check-input m-0" type="checkbox"
            ${{selectedSeries.has(col) ? 'checked' : ''}}
            onchange="toggleSeries('${{col}}', this.checked)">
            <span style="color:${{color}};font-weight:600">${{col}}</span>`;
        yDiv.appendChild(lbl);
    }});
}}

function toggleSeries(col, checked) {{
    if (checked) selectedSeries.add(col); else selectedSeries.delete(col);
    updateChart();
}}

// ─── Gráfico ─────────────────────────────────────────────────────
function updateChart() {{
    if (!currentTable) return;
    const xCol = document.getElementById('x-col').value;
    const ct   = document.getElementById('chart-type').value;
    const type = ct === 'area' ? 'line' : ct;
    const rows = currentTable.rows;
    const labels = rows.map(r => r[xCol] ?? '');
    const datasets = [];
    currentTable.numericCols.forEach((col, i) => {{
        if (!selectedSeries.has(col)) return;
        const color = PALETTE[i % PALETTE.length];
        datasets.push({{
            label: col, data: rows.map(r => r[col] ?? null),
            borderColor: color,
            backgroundColor: ct==='area' ? color+'33' : ct==='bar' ? color+'bb' : color,
            borderWidth: 2, fill: ct==='area', tension: 0.3,
            pointRadius: rows.length > 60 ? 0 : 3,
        }});
    }});
    if (chartInstance) chartInstance.destroy();
    chartInstance = new Chart(document.getElementById('main-chart').getContext('2d'), {{
        type, data: {{ labels, datasets }},
        options: {{
            responsive: true, maintainAspectRatio: false,
            interaction: {{ intersect: false, mode: 'index' }},
            plugins: {{
                legend: {{ position: 'top', labels: {{ boxWidth: 12 }} }},
                tooltip: {{ callbacks: {{ label: ctx =>
                    ` ${{ctx.dataset.label}}: ${{Number(ctx.parsed.y).toLocaleString('es-EC',{{minimumFractionDigits:2,maximumFractionDigits:2}})}}` }} }}
            }},
            scales: {{
                x: {{ ticks: {{ maxTicksLimit: 20, maxRotation: 45 }} }},
                y: {{ ticks: {{ callback: v => Number(v).toLocaleString('es-EC') }} }}
            }}
        }}
    }});
}}

// ─── Tabla paginada ──────────────────────────────────────────────
function renderPage() {{
    const cols = Object.keys(currentTable.rows[0] || {{}});
    document.getElementById('data-thead').innerHTML =
        '<tr>' + cols.map(c => `<th class="small">${{c}}</th>`).join('') + '</tr>';
    const start = currentPage * PAGE_SIZE;
    const page  = currentTable.rows.slice(start, start + PAGE_SIZE);
    const tbody = document.getElementById('data-tbody');
    tbody.innerHTML = '';
    page.forEach(row => {{
        const tr = document.createElement('tr');
        tr.innerHTML = cols.map(c => {{
            const v = row[c]; const isNum = typeof v === 'number';
            return `<td class="small ${{isNum ? 'text-end' : ''}}">${{
                isNum ? Number(v).toLocaleString('es-EC',{{minimumFractionDigits:2,maximumFractionDigits:2}}) : (v ?? '')
            }}</td>`;
        }}).join('');
        tbody.appendChild(tr);
    }});
}}

function prevPage() {{
    if (currentPage <= 0) return;
    currentPage--; renderPage(); updatePageInfo();
}}
function nextPage() {{
    if ((currentPage + 1) * PAGE_SIZE >= currentTable.rows.length) return;
    currentPage++; renderPage(); updatePageInfo();
}}
function updatePageInfo() {{
    const from = currentPage * PAGE_SIZE + 1;
    const to   = Math.min(from + PAGE_SIZE - 1, currentTable.rows.length);
    document.getElementById('page-info').textContent =
        `${{from}}–${{to}} de ${{currentTable.rows.length.toLocaleString()}}`;
}}

// ─── Exportar CSV ────────────────────────────────────────────────
function exportCSV() {{
    if (!currentTable) return;
    const rows = currentTable.rows;
    const cols = Object.keys(rows[0] || {{}});
    const lines = [cols.join(',')];
    rows.forEach(row => lines.push(cols.map(c => {{
        const v = row[c] ?? '';
        return String(v).includes(',') ? `"${{v}}"` : v;
    }}).join(',')));
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob(['\uFEFF' + lines.join('\\n')], {{type:'text/csv;charset=utf-8;'}}));
    a.download = currentTable.tableName + '.csv'; a.click();
}}

// ─── Autocargar primera tabla ────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {{
    const first = document.querySelector('.table-card');
    if (first) first.click();
}});
</script>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""


# ─────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Genera un dashboard HTML estático desde la base SQLite."
    )
    parser.add_argument("--db",       default=str(DB_PATH),  help="Ruta al archivo SQLite")
    parser.add_argument("--out",      default=str(OUT_PATH), help="Ruta del HTML de salida")
    parser.add_argument("--max-rows", type=int, default=MAX_ROWS_PER_TABLE,
                        help="Máximo de filas por tabla embebidas en el HTML")
    args = parser.parse_args()

    db_path  = Path(args.db)
    out_path = Path(args.out)

    if not db_path.exists():
        print(f"ERROR: Base de datos no encontrada: {db_path}", file=sys.stderr)
        print("Ejecute primero: python agent.py --demo", file=sys.stderr)
        sys.exit(1)

    print(f"Leyendo datos de: {db_path}")
    tables = load_all_tables(db_path, args.max_rows)

    if not tables:
        print("ERROR: No hay tablas en la base de datos.", file=sys.stderr)
        sys.exit(1)

    total_rows = sum(t["rowCount"] for t in tables)
    print(f"  {len(tables)} tablas, {total_rows:,} registros en total")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now().strftime("%d/%m/%Y %H:%M")
    html = generate_html(tables, generated_at)
    out_path.write_text(html, encoding="utf-8")

    size_kb = out_path.stat().st_size // 1024
    print(f"HTML generado: {out_path}  ({size_kb} KB)")
    print(f"Listo para GitHub Pages: https://<usuario>.github.io/<repo>/")


if __name__ == "__main__":
    main()
