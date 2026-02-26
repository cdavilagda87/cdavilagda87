<?php
/**
 * API REST simple para el dashboard BCE
 *
 * Endpoints:
 *   GET /api.php?action=tables           → lista de tablas disponibles
 *   GET /api.php?action=data&table=NAME  → datos de una tabla (JSON)
 *   GET /api.php?action=stats            → estadísticas generales
 */

header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');

require_once __DIR__ . '/config.php';

$action = $_GET['action'] ?? '';

try {
    $pdo = get_db();

    switch ($action) {

        // ── Lista de tablas ──────────────────────────────────────────
        case 'tables':
            $rows = $pdo->query("
                SELECT table_name, source_name, file_name, sheet_name,
                       row_count, col_count, created_at
                FROM   _metadata
                ORDER  BY created_at DESC
            ")->fetchAll();
            echo json_encode(['status' => 'ok', 'tables' => $rows], JSON_UNESCAPED_UNICODE);
            break;

        // ── Datos de una tabla ───────────────────────────────────────
        case 'data':
            $table = $_GET['table'] ?? '';
            // Validar que la tabla existe en _metadata para evitar inyección
            $check = $pdo->prepare("SELECT 1 FROM _metadata WHERE table_name = ?");
            $check->execute([$table]);
            if (!$check->fetch()) {
                http_response_code(404);
                echo json_encode(['status' => 'error', 'message' => 'Tabla no encontrada']);
                break;
            }
            $limit  = min((int)($_GET['limit'] ?? MAX_ROWS_PREVIEW), 1000);
            $offset = max((int)($_GET['offset'] ?? 0), 0);
            // Nombre de tabla ya validado — seguro para interpolación
            $stmt = $pdo->prepare("SELECT * FROM \"$table\" LIMIT :limit OFFSET :offset");
            $stmt->bindValue(':limit',  $limit,  PDO::PARAM_INT);
            $stmt->bindValue(':offset', $offset, PDO::PARAM_INT);
            $stmt->execute();
            $rows = $stmt->fetchAll();

            $count = (int)$pdo->query("SELECT COUNT(*) FROM \"$table\"")->fetchColumn();

            // Detectar columnas numéricas para sugerencia de gráfico
            $numeric_cols = [];
            $text_cols    = [];
            if (!empty($rows)) {
                foreach (array_keys($rows[0]) as $col) {
                    if (str_starts_with($col, '_')) continue;
                    $sample = $rows[0][$col];
                    if (is_numeric($sample)) {
                        $numeric_cols[] = $col;
                    } else {
                        $text_cols[] = $col;
                    }
                }
            }

            echo json_encode([
                'status'       => 'ok',
                'table'        => $table,
                'total'        => $count,
                'limit'        => $limit,
                'offset'       => $offset,
                'numeric_cols' => $numeric_cols,
                'text_cols'    => $text_cols,
                'rows'         => $rows,
            ], JSON_UNESCAPED_UNICODE | JSON_NUMERIC_CHECK);
            break;

        // ── Estadísticas generales ───────────────────────────────────
        case 'stats':
            $meta   = $pdo->query("SELECT COUNT(*) AS total_tables, SUM(row_count) AS total_rows FROM _metadata")->fetch();
            $tables = $pdo->query("SELECT table_name, source_name, sheet_name, row_count FROM _metadata ORDER BY row_count DESC")->fetchAll();
            echo json_encode([
                'status'       => 'ok',
                'total_tables' => (int)($meta['total_tables'] ?? 0),
                'total_rows'   => (int)($meta['total_rows']   ?? 0),
                'tables'       => $tables,
            ], JSON_UNESCAPED_UNICODE);
            break;

        default:
            http_response_code(400);
            echo json_encode(['status' => 'error', 'message' => 'Acción no válida. Use: tables, data, stats']);
    }

} catch (RuntimeException $e) {
    http_response_code(503);
    echo json_encode(['status' => 'error', 'message' => $e->getMessage()]);
} catch (Exception $e) {
    http_response_code(500);
    echo json_encode(['status' => 'error', 'message' => 'Error interno: ' . $e->getMessage()]);
}
