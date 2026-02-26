#!/usr/bin/env python3
"""
export_to_html.py
=================
Exporta la base de datos SQLite a un dashboard HTML completamente
autónomo, con diseño moderno inspirado en dashboards financieros
gubernamentales (estilo FI Dashboard).

Sin servidor requerido. Desplegable en Netlify, Surge, GitHub Pages, etc.

Uso:
    python export_to_html.py
    python export_to_html.py --db database/bce_data.db --out docs/index.html
    python export_to_html.py --max-rows 500 --title "Mi Dashboard"
"""

import json
import sqlite3
import argparse
import sys
from datetime import datetime
from pathlib import Path

DB_PATH  = Path("database/bce_data.db")
OUT_PATH = Path("docs/index.html")
MAX_ROWS_PER_TABLE = 500


# ─────────────────────────────────────────────
#  Lectura de datos
# ─────────────────────────────────────────────
def load_all_tables(db_path: Path, max_rows: int) -> list[dict]:
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

        cols        = rows[0].keys()
        pub_cols    = [c for c in cols if not c.startswith("_")]
        numeric_cols, text_cols = [], []
        for col in pub_cols:
            val = rows[0][col]
            if isinstance(val, (int, float)):
                numeric_cols.append(col)
            else:
                text_cols.append(col)

        # Estadísticas rápidas para KPIs
        stats = {}
        for nc in numeric_cols[:6]:
            vals = [r[nc] for r in rows if r[nc] is not None]
            if vals:
                stats[nc] = {
                    "last":   round(vals[-1], 2),
                    "prev":   round(vals[-2], 2) if len(vals) > 1 else None,
                    "max":    round(max(vals), 2),
                    "min":    round(min(vals), 2),
                    "avg":    round(sum(vals) / len(vals), 2),
                }

        tables.append({
            "tableName":   table_name,
            "sourceName":  m["source_name"],
            "fileName":    m["file_name"]  or "",
            "sheetName":   m["sheet_name"] or table_name,
            "rowCount":    m["row_count"],
            "colCount":    m["col_count"],
            "numericCols": numeric_cols,
            "textCols":    text_cols,
            "stats":       stats,
            "rows": [
                {c: row[c] for c in pub_cols}
                for row in rows
            ],
        })

    conn.close()
    return tables


# ─────────────────────────────────────────────
#  HTML generation
# ─────────────────────────────────────────────
def generate_html(tables: list[dict], generated_at: str, title: str) -> str:
    data_json    = json.dumps(tables, ensure_ascii=False, default=str)
    total_tables = len(tables)
    total_rows   = sum(t["rowCount"] for t in tables)

    # Sidebar nav items
    nav_items = ""
    for i, t in enumerate(tables):
        label = t["sheetName"]
        src   = t["sourceName"]
        rows  = t["rowCount"]
        nav_items += f"""
        <li class="nav-item" onclick="selectTable({i})" id="nav-{i}">
            <div class="nav-label">{label}</div>
            <div class="nav-meta">{src} &middot; {rows:,} reg.</div>
        </li>"""

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>

<!-- Chart.js -->
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<!-- ApexCharts para el gauge (donut) extra -->
<script src="https://cdn.jsdelivr.net/npm/apexcharts@3.46.0/dist/apexcharts.min.js"></script>

<style>
/* ═══════════════════════════════════════════════════
   CSS Variables & Reset
═══════════════════════════════════════════════════ */
:root {{
  --navy:   #0d1b2a;
  --navy2:  #1b2a3b;
  --navy3:  #243447;
  --teal:   #00c4a7;
  --teal2:  #00a98e;
  --gold:   #f5a623;
  --rose:   #e05c97;
  --blue:   #4a90d9;
  --white:  #ffffff;
  --light:  #f0f4f8;
  --muted:  #8ea0b5;
  --border: rgba(255,255,255,0.08);
  --card-bg:#1e2f42;
  --sidebar-w: 270px;
  --header-h:  64px;
  --radius: 12px;
  --shadow: 0 4px 24px rgba(0,0,0,0.25);
}}
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
body{{
  font-family:'Segoe UI',system-ui,sans-serif;
  background:var(--navy);
  color:var(--white);
  display:flex;
  flex-direction:column;
  min-height:100vh;
  overflow-x:hidden;
}}

/* ═══════════════════════════════════════════════════
   Header
═══════════════════════════════════════════════════ */
header {{
  position:fixed;top:0;left:0;right:0;
  height:var(--header-h);
  background:var(--navy2);
  border-bottom:1px solid var(--border);
  display:flex;align-items:center;
  padding:0 24px;
  z-index:100;
  gap:16px;
}}
.header-brand {{
  display:flex;align-items:center;gap:10px;
  font-size:1.1rem;font-weight:700;letter-spacing:-.3px;
}}
.header-brand .dot {{
  width:10px;height:10px;border-radius:50%;
  background:var(--teal);
  box-shadow:0 0 8px var(--teal);
}}
.header-badge {{
  background:var(--teal);color:var(--navy);
  font-size:.65rem;font-weight:700;
  padding:2px 8px;border-radius:99px;
  letter-spacing:.5px;text-transform:uppercase;
  margin-left:4px;
}}
.header-right {{
  margin-left:auto;display:flex;align-items:center;gap:16px;
}}
.header-ts {{color:var(--muted);font-size:.8rem;}}

/* ═══════════════════════════════════════════════════
   Layout: Sidebar + Main
═══════════════════════════════════════════════════ */
.layout {{
  display:flex;
  margin-top:var(--header-h);
  flex:1;
}}
.sidebar {{
  position:fixed;
  top:var(--header-h);bottom:0;left:0;
  width:var(--sidebar-w);
  background:var(--navy2);
  border-right:1px solid var(--border);
  overflow-y:auto;
  padding:20px 0;
  z-index:90;
}}
.sidebar-section {{
  padding:0 16px;
  margin-bottom:8px;
}}
.sidebar-title {{
  font-size:.65rem;font-weight:700;
  text-transform:uppercase;letter-spacing:1px;
  color:var(--muted);padding:0 4px 8px;
}}
ul.nav-list {{list-style:none;}}
li.nav-item {{
  padding:10px 12px;margin-bottom:2px;
  border-radius:8px;cursor:pointer;
  transition:background .15s,border-left .15s;
  border-left:3px solid transparent;
}}
li.nav-item:hover {{
  background:var(--navy3);
}}
li.nav-item.active {{
  background:rgba(0,196,167,.12);
  border-left-color:var(--teal);
}}
.nav-label {{font-size:.875rem;font-weight:600;}}
.nav-meta  {{font-size:.72rem;color:var(--muted);margin-top:2px;}}

main {{
  margin-left:var(--sidebar-w);
  flex:1;
  padding:28px 32px;
  min-width:0;
}}

/* ═══════════════════════════════════════════════════
   Page title bar
═══════════════════════════════════════════════════ */
.page-header {{
  display:flex;align-items:flex-start;
  justify-content:space-between;flex-wrap:wrap;
  gap:12px;margin-bottom:24px;
}}
.page-title {{font-size:1.5rem;font-weight:700;}}
.page-subtitle {{font-size:.85rem;color:var(--muted);margin-top:2px;}}
.btn-group {{display:flex;gap:8px;flex-wrap:wrap;}}
.btn {{
  display:inline-flex;align-items:center;gap:6px;
  padding:8px 16px;border-radius:8px;
  font-size:.8rem;font-weight:600;cursor:pointer;
  border:none;transition:all .15s;
}}
.btn-teal  {{background:var(--teal);color:var(--navy);}}
.btn-teal:hover{{background:var(--teal2);}}
.btn-ghost {{background:var(--navy3);color:var(--white);border:1px solid var(--border);}}
.btn-ghost:hover{{background:var(--navy2);}}

/* ═══════════════════════════════════════════════════
   KPI Cards
═══════════════════════════════════════════════════ */
.kpi-grid {{
  display:grid;
  grid-template-columns:repeat(auto-fill,minmax(180px,1fr));
  gap:16px;margin-bottom:28px;
}}
.kpi-card {{
  background:var(--card-bg);
  border-radius:var(--radius);
  padding:20px;
  border:1px solid var(--border);
  position:relative;overflow:hidden;
  transition:transform .15s,box-shadow .15s;
}}
.kpi-card:hover{{transform:translateY(-2px);box-shadow:var(--shadow);}}
.kpi-card::before {{
  content:'';position:absolute;top:0;left:0;right:0;height:3px;
}}
.kpi-card.c0::before{{background:var(--teal);}}
.kpi-card.c1::before{{background:var(--gold);}}
.kpi-card.c2::before{{background:var(--rose);}}
.kpi-card.c3::before{{background:var(--blue);}}
.kpi-card.c4::before{{background:#a78bfa;}}
.kpi-card.c5::before{{background:#fb923c;}}
.kpi-label  {{font-size:.72rem;font-weight:600;text-transform:uppercase;letter-spacing:.6px;color:var(--muted);margin-bottom:8px;}}
.kpi-value  {{font-size:1.75rem;font-weight:800;line-height:1;}}
.kpi-trend  {{margin-top:8px;display:flex;align-items:center;gap:4px;font-size:.78rem;}}
.kpi-trend.up   {{color:#34d399;}}
.kpi-trend.down {{color:#f87171;}}
.kpi-trend.flat {{color:var(--muted);}}
.kpi-sub    {{margin-top:6px;font-size:.72rem;color:var(--muted);}}

/* ═══════════════════════════════════════════════════
   Charts grid
═══════════════════════════════════════════════════ */
.charts-grid {{
  display:grid;
  grid-template-columns:2fr 1fr;
  gap:20px;margin-bottom:28px;
}}
@media(max-width:1100px){{.charts-grid{{grid-template-columns:1fr;}}}}

.chart-card {{
  background:var(--card-bg);
  border-radius:var(--radius);
  border:1px solid var(--border);
  padding:20px;
}}
.chart-card-header {{
  display:flex;align-items:center;
  justify-content:space-between;
  margin-bottom:16px;
}}
.chart-card-title {{font-size:.9rem;font-weight:700;}}
.chart-toolbar {{display:flex;gap:6px;flex-wrap:wrap;}}
.chart-type-btn {{
  padding:4px 10px;border-radius:6px;font-size:.72rem;font-weight:600;
  cursor:pointer;border:1px solid var(--border);
  background:transparent;color:var(--muted);
  transition:all .15s;
}}
.chart-type-btn.active,
.chart-type-btn:hover {{background:var(--teal);color:var(--navy);border-color:var(--teal);}}
.chart-wrap {{position:relative;height:280px;}}
.chart-wrap-sm {{position:relative;height:280px;}}

/* Series checkboxes */
.series-bar {{
  display:flex;flex-wrap:wrap;gap:6px;
  margin-bottom:12px;
}}
.series-chip {{
  display:inline-flex;align-items:center;gap:5px;
  padding:3px 10px;border-radius:99px;
  font-size:.72rem;font-weight:600;
  cursor:pointer;border:none;
  opacity:.45;transition:opacity .15s;
}}
.series-chip.on {{opacity:1;}}
.series-chip .dot {{width:8px;height:8px;border-radius:50%;}}

/* Axis selector */
.axis-row {{
  display:flex;align-items:center;gap:10px;margin-bottom:12px;flex-wrap:wrap;
}}
.axis-label {{font-size:.72rem;font-weight:600;color:var(--muted);white-space:nowrap;}}
.axis-select {{
  background:var(--navy3);color:var(--white);
  border:1px solid var(--border);border-radius:6px;
  padding:4px 8px;font-size:.78rem;
  cursor:pointer;
}}

/* ═══════════════════════════════════════════════════
   Data Table
═══════════════════════════════════════════════════ */
.table-card {{
  background:var(--card-bg);
  border-radius:var(--radius);
  border:1px solid var(--border);
  overflow:hidden;margin-bottom:28px;
}}
.table-card-header {{
  display:flex;align-items:center;
  justify-content:space-between;
  padding:16px 20px;border-bottom:1px solid var(--border);
  flex-wrap:wrap;gap:10px;
}}
.table-card-title {{font-size:.9rem;font-weight:700;}}
.search-box {{
  background:var(--navy3);border:1px solid var(--border);
  border-radius:8px;padding:6px 12px;
  color:var(--white);font-size:.8rem;width:220px;
}}
.search-box::placeholder{{color:var(--muted);}}
.table-wrap {{overflow-x:auto;}}
table {{width:100%;border-collapse:collapse;}}
thead th {{
  background:var(--navy3);
  padding:10px 14px;
  font-size:.72rem;font-weight:700;
  text-transform:uppercase;letter-spacing:.4px;
  color:var(--muted);
  text-align:left;white-space:nowrap;
  position:sticky;top:0;
}}
tbody tr {{border-bottom:1px solid rgba(255,255,255,.04);}}
tbody tr:hover{{background:rgba(255,255,255,.03);}}
tbody td {{
  padding:9px 14px;
  font-size:.8rem;white-space:nowrap;
}}
td.num {{text-align:right;font-variant-numeric:tabular-nums;}}
.pagination {{
  display:flex;align-items:center;gap:8px;
  padding:12px 20px;border-top:1px solid var(--border);
}}
.pg-btn {{
  background:var(--navy3);border:1px solid var(--border);
  color:var(--white);border-radius:6px;
  padding:5px 12px;font-size:.78rem;cursor:pointer;
}}
.pg-btn:disabled{{opacity:.35;cursor:default;}}
.pg-info {{font-size:.78rem;color:var(--muted);margin-left:auto;}}

/* ═══════════════════════════════════════════════════
   Placeholder / empty state
═══════════════════════════════════════════════════ */
.empty-state {{
  display:flex;flex-direction:column;align-items:center;
  justify-content:center;min-height:60vh;
  color:var(--muted);gap:16px;text-align:center;
}}
.empty-icon {{font-size:4rem;opacity:.3;}}

/* ═══════════════════════════════════════════════════
   Footer
═══════════════════════════════════════════════════ */
footer {{
  background:var(--navy2);
  border-top:1px solid var(--border);
  padding:16px 32px;
  font-size:.75rem;color:var(--muted);
  display:flex;justify-content:space-between;
  flex-wrap:wrap;gap:8px;
  margin-left:var(--sidebar-w);
}}

/* ═══════════════════════════════════════════════════
   Scrollbar
═══════════════════════════════════════════════════ */
::-webkit-scrollbar{{width:6px;height:6px;}}
::-webkit-scrollbar-track{{background:transparent;}}
::-webkit-scrollbar-thumb{{background:var(--navy3);border-radius:99px;}}

/* ═══════════════════════════════════════════════════
   Responsive
═══════════════════════════════════════════════════ */
@media(max-width:768px){{
  .sidebar{{display:none;}}
  main{{margin-left:0;padding:16px;}}
  footer{{margin-left:0;}}
}}
</style>
</head>

<body>

<!-- ─── HEADER ─── -->
<header>
  <div class="header-brand">
    <div class="dot"></div>
    <span>{title}</span>
    <span class="header-badge">Live</span>
  </div>
  <div class="header-right">
    <span class="header-ts">Actualizado: {generated_at}</span>
  </div>
</header>

<!-- ─── SIDEBAR ─── -->
<div class="layout">
  <nav class="sidebar">
    <div class="sidebar-section">
      <div class="sidebar-title">Conjuntos de datos</div>
      <ul class="nav-list" id="nav-list">
        {nav_items}
      </ul>
    </div>
  </nav>

  <!-- ─── MAIN ─── -->
  <main id="main">
    <div class="empty-state" id="empty-state">
      <div class="empty-icon">📊</div>
      <div>
        <div style="font-size:1.1rem;font-weight:700;color:#fff;margin-bottom:6px">Selecciona un conjunto de datos</div>
        <div style="font-size:.85rem">Haz clic en cualquier ítem del panel izquierdo</div>
      </div>
    </div>

    <div id="dashboard" style="display:none">

      <!-- Page header -->
      <div class="page-header">
        <div>
          <div class="page-title" id="page-title">—</div>
          <div class="page-subtitle" id="page-subtitle">—</div>
        </div>
        <div class="btn-group">
          <button class="btn btn-ghost" onclick="exportCSV()">↓ CSV</button>
          <button class="btn btn-ghost" onclick="copyLink()">🔗 Link</button>
        </div>
      </div>

      <!-- KPI Cards -->
      <div class="kpi-grid" id="kpi-grid"></div>

      <!-- Charts -->
      <div class="charts-grid">
        <!-- Main chart -->
        <div class="chart-card">
          <div class="chart-card-header">
            <div class="chart-card-title">Evolución temporal</div>
            <div class="chart-toolbar">
              <button class="chart-type-btn active" data-type="line"  onclick="setChartType('line',this)">Línea</button>
              <button class="chart-type-btn"        data-type="bar"   onclick="setChartType('bar',this)">Barras</button>
              <button class="chart-type-btn"        data-type="area"  onclick="setChartType('area',this)">Área</button>
            </div>
          </div>
          <div class="axis-row">
            <span class="axis-label">Eje X:</span>
            <select class="axis-select" id="x-col" onchange="updateMainChart()"></select>
          </div>
          <div class="series-bar" id="series-bar"></div>
          <div class="chart-wrap"><canvas id="main-chart"></canvas></div>
        </div>

        <!-- Donut chart -->
        <div class="chart-card">
          <div class="chart-card-header">
            <div class="chart-card-title">Distribución (último)</div>
          </div>
          <div class="axis-row">
            <span class="axis-label">Columna:</span>
            <select class="axis-select" id="donut-col" onchange="updateDonut()"></select>
          </div>
          <div class="chart-wrap-sm" id="donut-wrap"></div>
        </div>
      </div>

      <!-- Data Table -->
      <div class="table-card">
        <div class="table-card-header">
          <div class="table-card-title">Datos (<span id="row-count">0</span> registros)</div>
          <input class="search-box" id="search-box" type="text" placeholder="Buscar…" oninput="onSearch()">
        </div>
        <div class="table-wrap">
          <table>
            <thead id="tbl-head"></thead>
            <tbody id="tbl-body"></tbody>
          </table>
        </div>
        <div class="pagination">
          <button class="pg-btn" id="btn-prev" onclick="prevPage()">← Anterior</button>
          <button class="pg-btn" id="btn-next" onclick="nextPage()">Siguiente →</button>
          <span class="pg-info" id="pg-info"></span>
        </div>
      </div>

    </div><!-- /dashboard -->
  </main>
</div><!-- /layout -->

<footer>
  <span>{title} · Datos embebidos · Chart.js + ApexCharts</span>
  <span>Generado: {generated_at}</span>
</footer>

<!-- ═══════════════════════════════════════════════════
     JavaScript — datos + lógica completa
═══════════════════════════════════════════════════ -->
<script>
// ── Datos ────────────────────────────────────────────
const ALL_TABLES = {data_json};

// ── Paleta ───────────────────────────────────────────
const PALETTE = [
  '#00c4a7','#f5a623','#e05c97','#4a90d9',
  '#a78bfa','#fb923c','#34d399','#60a5fa',
  '#fbbf24','#f472b6',
];

// ── Estado ───────────────────────────────────────────
const PAGE_SIZE  = 50;
let cur          = null;   // tabla activa
let curPage      = 0;
let filteredRows = [];
let selectedSeries = new Set();
let chartInst    = null;
let donutInst    = null;
let chartType    = 'line';
let searchQ      = '';

// ── Utilidades ───────────────────────────────────────
function fmt(v) {{
  if (v === null || v === undefined) return '—';
  if (typeof v === 'number') return Number(v).toLocaleString('es-EC',{{minimumFractionDigits:2,maximumFractionDigits:2}});
  return v;
}}
function fmtShort(v) {{
  if (v === null || v === undefined) return '—';
  if (Math.abs(v) >= 1e9) return (v/1e9).toFixed(1)+'B';
  if (Math.abs(v) >= 1e6) return (v/1e6).toFixed(1)+'M';
  if (Math.abs(v) >= 1e3) return (v/1e3).toFixed(1)+'K';
  return Number(v).toLocaleString('es-EC',{{minimumFractionDigits:2,maximumFractionDigits:2}});
}}

// ── Seleccionar tabla ─────────────────────────────────
function selectTable(idx) {{
  cur = ALL_TABLES[idx];
  curPage = 0; searchQ = '';
  document.getElementById('search-box').value = '';

  // Nav highlight
  document.querySelectorAll('li.nav-item').forEach((el,i) => {{
    el.classList.toggle('active', i === idx);
  }});

  document.getElementById('empty-state').style.display = 'none';
  document.getElementById('dashboard').style.display   = 'block';

  document.getElementById('page-title').textContent =
    cur.sheetName.replace(/_/g,' ');
  document.getElementById('page-subtitle').textContent =
    `Fuente: ${{cur.sourceName}} · ${{cur.fileName}} · ${{cur.rowCount.toLocaleString()}} registros`;
  document.getElementById('row-count').textContent = cur.rowCount.toLocaleString();

  buildKPIs();
  buildAxisSelectors();
  buildSeriesBar();
  filteredRows = [...cur.rows];
  renderPage();
  updateMainChart();
  updateDonut();
  updatePagination();
}}

// ── KPI Cards ─────────────────────────────────────────
function buildKPIs() {{
  const grid = document.getElementById('kpi-grid');
  grid.innerHTML = '';
  const entries = Object.entries(cur.stats).slice(0,6);
  if (!entries.length) return;
  entries.forEach(([col,s],i) => {{
    let trendHtml = '';
    let trendCls  = 'flat';
    if (s.prev !== null) {{
      const d = s.last - s.prev;
      const pct = s.prev !== 0 ? ((d/Math.abs(s.prev))*100).toFixed(1) : 0;
      trendCls  = d > 0 ? 'up' : d < 0 ? 'down' : 'flat';
      const arrow = d > 0 ? '▲' : d < 0 ? '▼' : '─';
      trendHtml = `<span class="kpi-trend ${{trendCls}}">${{arrow}} ${{Math.abs(pct)}}% vs anterior</span>`;
    }}
    const label = col.replace(/_/g,' ');
    grid.innerHTML += `
      <div class="kpi-card c${{i}}">
        <div class="kpi-label">${{label}}</div>
        <div class="kpi-value">${{fmtShort(s.last)}}</div>
        ${{trendHtml}}
        <div class="kpi-sub">máx ${{fmtShort(s.max)}} · mín ${{fmtShort(s.min)}}</div>
      </div>`;
  }});
}}

// ── Axis selectors ────────────────────────────────────
function buildAxisSelectors() {{
  const xSel = document.getElementById('x-col');
  xSel.innerHTML = '';
  [...cur.textCols, ...cur.numericCols].forEach(col => {{
    const o = document.createElement('option');
    o.value = o.textContent = col.replace(/_/g,' '); o.value = col;
    xSel.appendChild(o);
  }});
  if (cur.textCols.length) xSel.value = cur.textCols[0];

  const dSel = document.getElementById('donut-col');
  dSel.innerHTML = '';
  cur.numericCols.forEach(col => {{
    const o = document.createElement('option');
    o.value = col; o.textContent = col.replace(/_/g,' ');
    dSel.appendChild(o);
  }});
}}

// ── Series checkboxes ─────────────────────────────────
function buildSeriesBar() {{
  const bar = document.getElementById('series-bar');
  bar.innerHTML = '';
  selectedSeries = new Set(cur.numericCols.slice(0,5));
  cur.numericCols.forEach((col,i) => {{
    const color = PALETTE[i % PALETTE.length];
    const chip  = document.createElement('button');
    chip.className = 'series-chip on';
    chip.style.background = color + '22';
    chip.style.color = color;
    chip.style.border = `1px solid ${{color}}`;
    chip.innerHTML = `<span class="dot" style="background:${{color}}"></span>${{col.replace(/_/g,' ')}}`;
    chip.onclick = () => {{
      if (selectedSeries.has(col)) {{
        selectedSeries.delete(col);
        chip.classList.remove('on');
      }} else {{
        selectedSeries.add(col);
        chip.classList.add('on');
      }}
      updateMainChart();
    }};
    bar.appendChild(chip);
  }});
}}

// ── Chart type ────────────────────────────────────────
function setChartType(type, btn) {{
  chartType = type;
  document.querySelectorAll('.chart-type-btn').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  updateMainChart();
}}

// ── Main Chart ────────────────────────────────────────
function updateMainChart() {{
  if (!cur) return;
  const xCol = document.getElementById('x-col').value;
  const rows = cur.rows;
  const labels = rows.map(r => r[xCol] ?? '');
  const type   = chartType === 'area' ? 'line' : chartType;
  const datasets = [];
  cur.numericCols.forEach((col,i) => {{
    if (!selectedSeries.has(col)) return;
    const color = PALETTE[i % PALETTE.length];
    datasets.push({{
      label: col.replace(/_/g,' '),
      data: rows.map(r => r[col] ?? null),
      borderColor: color,
      backgroundColor: chartType==='area' ? color+'33' : chartType==='bar' ? color+'bb' : color,
      borderWidth: 2,
      fill: chartType==='area',
      tension: 0.35,
      pointRadius: rows.length > 80 ? 0 : 3,
      pointHoverRadius: 5,
    }});
  }});
  if (chartInst) chartInst.destroy();
  Chart.defaults.color = '#8ea0b5';
  chartInst = new Chart(document.getElementById('main-chart').getContext('2d'), {{
    type,
    data: {{ labels, datasets }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      interaction: {{ intersect: false, mode: 'index' }},
      plugins: {{
        legend: {{ position: 'top', labels: {{ boxWidth: 10, font: {{ size: 11 }} }} }},
        tooltip: {{ callbacks: {{
          label: ctx => ` ${{ctx.dataset.label}}: ${{fmt(ctx.parsed.y)}}`
        }} }},
      }},
      scales: {{
        x: {{
          ticks: {{ maxTicksLimit: 20, maxRotation: 45, font: {{ size: 10 }} }},
          grid: {{ color: 'rgba(255,255,255,.05)' }},
        }},
        y: {{
          ticks: {{ callback: v => fmtShort(v), font: {{ size: 10 }} }},
          grid: {{ color: 'rgba(255,255,255,.05)' }},
        }},
      }},
    }},
  }});
}}

// ── Donut Chart ───────────────────────────────────────
function updateDonut() {{
  if (!cur || !cur.numericCols.length) return;
  const col  = document.getElementById('donut-col').value;
  const rows = cur.rows.slice(-20);  // últimos 20
  const labels = rows.map((_,i) => `#${{i+1}}`);
  const xCol = cur.textCols[0] || null;
  const labelsX = xCol ? rows.map(r => String(r[xCol] ?? '')) : labels;
  const vals = rows.map(r => r[col] ?? 0).map(v => Math.abs(Number(v)));
  const wrap = document.getElementById('donut-wrap');
  if (donutInst) {{ donutInst.destroy(); donutInst = null; }}
  wrap.innerHTML = '<canvas id="donut-canvas"></canvas>';

  Chart.defaults.color = '#8ea0b5';
  donutInst = new Chart(document.getElementById('donut-canvas').getContext('2d'), {{
    type: 'doughnut',
    data: {{
      labels: labelsX,
      datasets: [{{
        data: vals,
        backgroundColor: PALETTE.map(c => c + 'cc'),
        borderColor: PALETTE,
        borderWidth: 1,
        hoverOffset: 8,
      }}],
    }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      plugins: {{
        legend: {{ position:'right', labels: {{ boxWidth:10, font:{{ size:10 }} }} }},
        tooltip: {{ callbacks: {{ label: ctx => ` ${{ctx.label}}: ${{fmt(ctx.parsed)}}` }} }},
      }},
    }},
  }});
}}

// ── Tabla + búsqueda ──────────────────────────────────
function onSearch() {{
  searchQ = document.getElementById('search-box').value.toLowerCase();
  curPage = 0;
  filteredRows = searchQ
    ? cur.rows.filter(row => Object.values(row).some(v => String(v).toLowerCase().includes(searchQ)))
    : [...cur.rows];
  renderPage();
  updatePagination();
  document.getElementById('row-count').textContent = filteredRows.length.toLocaleString();
}}

function renderPage() {{
  if (!cur || !cur.rows.length) return;
  const cols = Object.keys(cur.rows[0]);
  const thead = document.getElementById('tbl-head');
  const tbody = document.getElementById('tbl-body');
  thead.innerHTML = '<tr>' + cols.map(c =>
    `<th>${{c.replace(/_/g,' ')}}</th>`).join('') + '</tr>';

  const start = curPage * PAGE_SIZE;
  const page  = filteredRows.slice(start, start + PAGE_SIZE);
  tbody.innerHTML = '';
  page.forEach(row => {{
    const tr = document.createElement('tr');
    tr.innerHTML = cols.map(c => {{
      const v = row[c];
      const isNum = typeof v === 'number';
      return `<td class="${{isNum ? 'num' : ''}}">${{fmt(v)}}</td>`;
    }}).join('');
    tbody.appendChild(tr);
  }});
}}

function prevPage() {{ if (curPage > 0) {{ curPage--; renderPage(); updatePagination(); }} }}
function nextPage() {{
  if ((curPage+1)*PAGE_SIZE < filteredRows.length) {{ curPage++; renderPage(); updatePagination(); }}
}}
function updatePagination() {{
  const from = curPage * PAGE_SIZE + 1;
  const to   = Math.min(from + PAGE_SIZE - 1, filteredRows.length);
  const total = filteredRows.length;
  document.getElementById('pg-info').textContent  = `${{from.toLocaleString()}}–${{to.toLocaleString()}} de ${{total.toLocaleString()}}`;
  document.getElementById('btn-prev').disabled = curPage === 0;
  document.getElementById('btn-next').disabled = to >= total;
}}

// ── Exportar CSV ──────────────────────────────────────
function exportCSV() {{
  if (!cur) return;
  const cols = Object.keys(filteredRows[0] || {{}});
  const lines = [cols.join(',')];
  filteredRows.forEach(row => lines.push(cols.map(c => {{
    const v = row[c] ?? '';
    return String(v).includes(',') ? `"${{v}}"` : v;
  }}).join(',')));
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob(['\uFEFF'+lines.join('\\n')],{{type:'text/csv;charset=utf-8;'}}));
  a.download = cur.tableName+'.csv'; a.click();
}}

function copyLink() {{
  navigator.clipboard.writeText(location.href).then(() => alert('Link copiado al portapapeles'));
}}

// ── Auto-select primera tabla ─────────────────────────
document.addEventListener('DOMContentLoaded', () => {{
  if (ALL_TABLES.length) selectTable(0);
}});
</script>
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
    parser.add_argument("--title",    default="Dashboard BCE · Índices Financieros",
                        help="Título del dashboard")
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
    html = generate_html(tables, generated_at, args.title)
    out_path.write_text(html, encoding="utf-8")

    size_kb = out_path.stat().st_size // 1024
    print(f"HTML generado: {out_path}  ({size_kb} KB)")


if __name__ == "__main__":
    main()
