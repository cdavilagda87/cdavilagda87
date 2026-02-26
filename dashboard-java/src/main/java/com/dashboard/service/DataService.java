package com.dashboard.service;

import com.dashboard.model.TableData;
import com.dashboard.model.TableMeta;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.util.*;

@Service
public class DataService {

    private static final Logger log = LoggerFactory.getLogger(DataService.class);
    private static final int DEFAULT_LIMIT = 100;
    private static final int MAX_LIMIT     = 1000;

    private final JdbcTemplate jdbc;

    public DataService(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    // ─── Lista de tablas ──────────────────────────────────────────
    public List<TableMeta> listTables() {
        return jdbc.query(
            "SELECT id, table_name, source_name, file_name, sheet_name, " +
            "row_count, col_count, created_at FROM _metadata ORDER BY created_at DESC",
            (rs, n) -> new TableMeta(
                rs.getLong("id"),
                rs.getString("table_name"),
                rs.getString("source_name"),
                rs.getString("file_name"),
                rs.getString("sheet_name"),
                rs.getLong("row_count"),
                rs.getLong("col_count"),
                rs.getString("created_at")
            )
        );
    }

    // ─── Estadísticas ─────────────────────────────────────────────
    public Map<String, Object> getStats() {
        Map<String, Object> row = jdbc.queryForMap(
            "SELECT COUNT(*) AS total_tables, COALESCE(SUM(row_count),0) AS total_rows FROM _metadata"
        );
        Map<String, Object> stats = new LinkedHashMap<>();
        stats.put("totalTables", row.get("total_tables"));
        stats.put("totalRows",   row.get("total_rows"));
        stats.put("tables",      listTables());
        return stats;
    }

    // ─── Datos de una tabla ───────────────────────────────────────
    public TableData getTableData(String tableName, int limit, int offset) {
        validateTableName(tableName);

        int safeLimit  = Math.min(limit  > 0 ? limit  : DEFAULT_LIMIT, MAX_LIMIT);
        int safeOffset = Math.max(offset, 0);

        // Total de filas
        long total = Optional.ofNullable(
            jdbc.queryForObject("SELECT COUNT(*) FROM \"" + tableName + "\"", Long.class)
        ).orElse(0L);

        // Filas paginadas
        List<Map<String, Object>> rows = jdbc.queryForList(
            "SELECT * FROM \"" + tableName + "\" LIMIT ? OFFSET ?",
            safeLimit, safeOffset
        );

        // Clasificar columnas (numéricas vs texto)
        List<String> numericCols = new ArrayList<>();
        List<String> textCols    = new ArrayList<>();

        if (!rows.isEmpty()) {
            rows.get(0).forEach((col, val) -> {
                if (col.startsWith("_")) return;
                if (val instanceof Number) numericCols.add(col);
                else                       textCols.add(col);
            });
        }

        return new TableData(tableName, total, safeLimit, safeOffset, numericCols, textCols, rows);
    }

    // ─── Seguridad: validar nombre de tabla ───────────────────────
    private void validateTableName(String tableName) {
        // Verifica en _metadata para evitar inyección SQL
        Integer count = jdbc.queryForObject(
            "SELECT COUNT(*) FROM _metadata WHERE table_name = ?",
            Integer.class, tableName
        );
        if (count == null || count == 0) {
            throw new NoSuchElementException("Tabla no encontrada: " + tableName);
        }
    }
}
