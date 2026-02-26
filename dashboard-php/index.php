<?php
require_once __DIR__ . '/config.php';

$db_exists = file_exists(DB_PATH);
$error_msg = '';
$stats     = ['total_tables' => 0, 'total_rows' => 0];
$tables    = [];

if ($db_exists) {
    try {
        $pdo    = get_db();
        $stats  = $pdo->query("SELECT COUNT(*) AS total_tables, SUM(row_count) AS total_rows FROM _metadata")->fetch();
        $tables = $pdo->query("SELECT * FROM _metadata ORDER BY created_at DESC")->fetchAll();
    } catch (Exception $e) {
        $error_msg = $e->getMessage();
    }
}
?>
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard BCE — Índices Financieros</title>
    <!-- Bootstrap 5 -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <!-- Bootstrap Icons -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css" rel="stylesheet">
    <!-- Chart.js -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
    <style>
        :root {
            --bce-blue:   #003366;
            --bce-yellow: #F5A800;
            --bce-light:  #f0f4f8;
        }
        body          { background: var(--bce-light); font-family: 'Segoe UI', sans-serif; }
        .navbar-brand  { font-weight: 700; letter-spacing: .5px; }
        .stat-card     { border-left: 4px solid var(--bce-yellow); }
        .stat-number   { font-size: 2rem; font-weight: 700; color: var(--bce-blue); }
        .table-card    { cursor: pointer; transition: transform .15s, box-shadow .15s; }
        .table-card:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(0,0,0,.12); }
        .table-card.active { border: 2px solid var(--bce-blue); }
        .chart-container { position: relative; height: 320px; }
        #loading { display: none; }
        .badge-rows { background: var(--bce-blue); }
        footer { background: var(--bce-blue); color: #cdd8e3; font-size: .85rem; }
    </style>
</head>
<body>

<!-- Navbar -->
<nav class="navbar navbar-dark py-2" style="background:var(--bce-blue)">
    <div class="container-fluid">
        <span class="navbar-brand">
            <i class="bi bi-bar-chart-fill me-2" style="color:var(--bce-yellow)"></i>
            Dashboard BCE · Índices Financieros
        </span>
        <small class="text-white-50">Actualizado: <?= date('d/m/Y H:i') ?></small>
    </div>
</nav>

<div class="container-fluid py-4">

    <?php if (!$db_exists): ?>
    <!-- Sin base de datos -->
    <div class="alert alert-warning d-flex align-items-center">
        <i class="bi bi-exclamation-triangle-fill me-3 fs-4"></i>
        <div>
            <strong>Base de datos no encontrada.</strong><br>
            Ejecute el agente primero:<br>
            <code>python agent.py</code> &nbsp;o&nbsp; <code>python agent.py --demo</code>
        </div>
    </div>
    <?php elseif ($error_msg): ?>
    <div class="alert alert-danger"><?= htmlspecialchars($error_msg) ?></div>
    <?php else: ?>

    <!-- Tarjetas de resumen -->
    <div class="row g-3 mb-4">
        <div class="col-sm-6 col-lg-3">
            <div class="card stat-card shadow-sm h-100">
                <div class="card-body">
                    <div class="text-muted small">Tablas disponibles</div>
                    <div class="stat-number"><?= (int)($stats['total_tables'] ?? 0) ?></div>
                </div>
            </div>
        </div>
        <div class="col-sm-6 col-lg-3">
            <div class="card stat-card shadow-sm h-100">
                <div class="card-body">
                    <div class="text-muted small">Total de registros</div>
                    <div class="stat-number"><?= number_format((int)($stats['total_rows'] ?? 0)) ?></div>
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
                    <div class="text-muted small">Tecnología</div>
                    <div class="stat-number" style="font-size:1.1rem;padding-top:.5rem">PHP + SQLite</div>
                </div>
            </div>
        </div>
    </div>

    <div class="row g-4">
        <!-- Columna izquierda: lista de tablas -->
        <div class="col-lg-3">
            <h6 class="text-uppercase text-muted fw-bold mb-2">
                <i class="bi bi-table me-1"></i>Conjuntos de datos
            </h6>
            <div id="table-list">
                <?php foreach ($tables as $t): ?>
                <div class="card table-card mb-2 shadow-sm"
                     onclick="loadTable('<?= htmlspecialchars($t['table_name']) ?>', this)"
                     data-table="<?= htmlspecialchars($t['table_name']) ?>">
                    <div class="card-body py-2 px-3">
                        <div class="fw-semibold small text-truncate" title="<?= htmlspecialchars($t['sheet_name']) ?>">
                            <?= htmlspecialchars($t['sheet_name']) ?>
                        </div>
                        <div class="d-flex justify-content-between align-items-center mt-1">
                            <small class="text-muted"><?= htmlspecialchars($t['source_name']) ?></small>
                            <span class="badge badge-rows text-white"><?= number_format((int)$t['row_count']) ?></span>
                        </div>
                    </div>
                </div>
                <?php endforeach; ?>
            </div>
        </div>

        <!-- Columna derecha: gráfico + tabla -->
        <div class="col-lg-9">
            <div id="loading" class="text-center py-5">
                <div class="spinner-border text-primary"></div>
                <div class="mt-2 text-muted">Cargando datos…</div>
            </div>

            <div id="dashboard-content" style="display:none">
                <!-- Título y controles -->
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

                <!-- Selector de ejes -->
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

                <!-- Gráfico -->
                <div class="card shadow-sm mb-4">
                    <div class="card-body">
                        <div class="chart-container">
                            <canvas id="main-chart"></canvas>
                        </div>
                    </div>
                </div>

                <!-- Tabla de datos -->
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
                            <table class="table table-sm table-hover mb-0" id="data-table">
                                <thead class="table-dark" id="data-thead"></thead>
                                <tbody id="data-tbody"></tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Placeholder inicial -->
            <div id="placeholder" class="text-center py-5 text-muted">
                <i class="bi bi-mouse2 fs-1 d-block mb-3"></i>
                Seleccione un conjunto de datos de la lista
            </div>
        </div>
    </div>

    <?php endif; ?>
</div>

<footer class="py-3 mt-4">
    <div class="container-fluid text-center">
        Dashboard BCE · Excel-to-Dashboard Agent · PHP + SQLite + Chart.js
    </div>
</footer>

<script>
// ─── Estado global ─────────────────────────────────────────────
const PAGE_SIZE     = 50;
let currentTable    = '';
let currentData     = [];
let currentNumCols  = [];
let currentTextCols = [];
let currentPage     = 0;
let totalRows       = 0;
let chartInstance   = null;
let selectedSeries  = new Set();

// ─── Paleta de colores ──────────────────────────────────────────
const PALETTE = [
    '#003366','#F5A800','#2196F3','#4CAF50','#E91E63',
    '#9C27B0','#FF5722','#009688','#607D8B','#795548',
];

// ─── Carga de tabla ─────────────────────────────────────────────
function loadTable(tableName, el) {
    document.querySelectorAll('.table-card').forEach(c => c.classList.remove('active'));
    el.classList.add('active');

    currentTable = tableName;
    currentPage  = 0;

    document.getElementById('placeholder').style.display      = 'none';
    document.getElementById('dashboard-content').style.display = 'none';
    document.getElementById('loading').style.display           = 'block';

    fetchData(tableName, 0);
}

function fetchData(tableName, offset) {
    const url = `api.php?action=data&table=${encodeURIComponent(tableName)}&limit=${PAGE_SIZE}&offset=${offset}`;
    fetch(url)
        .then(r => r.json())
        .then(json => {
            if (json.status !== 'ok') { alert(json.message); return; }
            currentData     = json.rows;
            currentNumCols  = json.numeric_cols;
            currentTextCols = json.text_cols;
            totalRows       = json.total;

            document.getElementById('loading').style.display           = 'none';
            document.getElementById('dashboard-content').style.display = 'block';

            document.getElementById('dash-title').textContent = tableName.replace(/^data_/, '').replace(/_/g,' ');
            document.getElementById('row-count').textContent  = totalRows.toLocaleString();

            buildAxisSelectors();
            buildTable();
            updateChart();
            updatePageInfo();
        })
        .catch(err => {
            document.getElementById('loading').style.display = 'none';
            alert('Error: ' + err.message);
        });
}

// ─── Selectores de ejes ─────────────────────────────────────────
function buildAxisSelectors() {
    // Eje X
    const xSel = document.getElementById('x-col');
    xSel.innerHTML = '';
    const allCols = currentTextCols.concat(currentNumCols);
    allCols.forEach(col => {
        const opt      = document.createElement('option');
        opt.value      = col;
        opt.textContent = col;
        xSel.appendChild(opt);
    });
    // Prefer first text col as X
    if (currentTextCols.length) xSel.value = currentTextCols[0];

    // Checkboxes para series Y
    const yDiv = document.getElementById('y-cols');
    yDiv.innerHTML = '';
    selectedSeries = new Set(currentNumCols.slice(0, 4)); // seleccionar primeros 4

    currentNumCols.forEach((col, i) => {
        const color  = PALETTE[i % PALETTE.length];
        const id     = `chk_${col}`;
        const label  = document.createElement('label');
        label.className    = 'form-check-label small d-flex align-items-center gap-1 border rounded px-2 py-1';
        label.style.cursor = 'pointer';
        label.style.borderColor = color + ' !important';
        label.innerHTML = `
            <input class="form-check-input m-0" type="checkbox" id="${id}"
                   ${selectedSeries.has(col) ? 'checked' : ''}
                   onchange="toggleSeries('${col}', this.checked)">
            <span style="color:${color}; font-weight:600">${col}</span>
        `;
        yDiv.appendChild(label);
    });
}

function toggleSeries(col, checked) {
    if (checked) selectedSeries.add(col);
    else         selectedSeries.delete(col);
    updateChart();
}

// ─── Gráfico ────────────────────────────────────────────────────
function updateChart() {
    const xCol     = document.getElementById('x-col').value;
    const chartType = document.getElementById('chart-type').value;
    const labels   = currentData.map(r => r[xCol] ?? '');
    const type     = chartType === 'area' ? 'line' : chartType;

    const datasets = [];
    let colorIdx   = 0;
    currentNumCols.forEach(col => {
        if (!selectedSeries.has(col)) { colorIdx++; return; }
        const color = PALETTE[colorIdx % PALETTE.length];
        datasets.push({
            label:           col,
            data:            currentData.map(r => r[col] ?? null),
            borderColor:     color,
            backgroundColor: chartType === 'area'
                ? color + '33'
                : chartType === 'bar' ? color + 'bb' : color,
            borderWidth: 2,
            fill:        chartType === 'area',
            tension:     0.3,
            pointRadius: currentData.length > 60 ? 0 : 3,
        });
        colorIdx++;
    });

    if (chartInstance) chartInstance.destroy();

    const ctx = document.getElementById('main-chart').getContext('2d');
    chartInstance = new Chart(ctx, {
        type,
        data: { labels, datasets },
        options: {
            responsive:          true,
            maintainAspectRatio: false,
            interaction:  { intersect: false, mode: 'index' },
            plugins: {
                legend:  { position: 'top', labels: { boxWidth: 12 } },
                tooltip: { callbacks: {
                    label: ctx => ` ${ctx.dataset.label}: ${Number(ctx.parsed.y).toLocaleString('es-EC', {minimumFractionDigits:2, maximumFractionDigits:2})}`
                }}
            },
            scales: {
                x: { ticks: { maxTicksLimit: 20, maxRotation: 45 } },
                y: { ticks: { callback: v => Number(v).toLocaleString('es-EC') } }
            }
        }
    });
}

// ─── Tabla de datos ─────────────────────────────────────────────
function buildTable() {
    if (!currentData.length) return;
    const cols = Object.keys(currentData[0]).filter(c => !c.startsWith('_'));

    // Encabezado
    document.getElementById('data-thead').innerHTML =
        '<tr>' + cols.map(c => `<th class="small">${c}</th>`).join('') + '</tr>';

    // Filas
    const tbody = document.getElementById('data-tbody');
    tbody.innerHTML = '';
    currentData.forEach(row => {
        const tr = document.createElement('tr');
        tr.innerHTML = cols.map(c => {
            const val = row[c];
            const display = val === null || val === undefined ? '' : val;
            const isNum   = typeof val === 'number';
            return `<td class="small ${isNum ? 'text-end' : ''}">${
                isNum ? Number(val).toLocaleString('es-EC', {minimumFractionDigits:2,maximumFractionDigits:2}) : display
            }</td>`;
        }).join('');
        tbody.appendChild(tr);
    });
}

// ─── Paginación ─────────────────────────────────────────────────
function prevPage() {
    if (currentPage <= 0) return;
    currentPage--;
    fetchData(currentTable, currentPage * PAGE_SIZE);
}
function nextPage() {
    if ((currentPage + 1) * PAGE_SIZE >= totalRows) return;
    currentPage++;
    fetchData(currentTable, currentPage * PAGE_SIZE);
}
function updatePageInfo() {
    const from  = currentPage * PAGE_SIZE + 1;
    const to    = Math.min(from + PAGE_SIZE - 1, totalRows);
    document.getElementById('page-info').textContent = `${from}–${to} de ${totalRows.toLocaleString()}`;
}

// ─── Exportar CSV ───────────────────────────────────────────────
function exportCSV() {
    if (!currentData.length) return;
    const cols = Object.keys(currentData[0]).filter(c => !c.startsWith('_'));
    const lines = [cols.join(',')];
    currentData.forEach(row => {
        lines.push(cols.map(c => {
            const v = row[c] ?? '';
            return String(v).includes(',') ? `"${v}"` : v;
        }).join(','));
    });
    const blob = new Blob(['\uFEFF' + lines.join('\n')], { type: 'text/csv;charset=utf-8;' });
    const a    = document.createElement('a');
    a.href     = URL.createObjectURL(blob);
    a.download = currentTable + '.csv';
    a.click();
}

// ─── Cargar primera tabla automáticamente ──────────────────────
document.addEventListener('DOMContentLoaded', () => {
    const first = document.querySelector('.table-card');
    if (first) first.click();
});
</script>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
