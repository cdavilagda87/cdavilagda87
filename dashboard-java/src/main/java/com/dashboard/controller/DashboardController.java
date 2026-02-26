package com.dashboard.controller;

import com.dashboard.model.TableData;
import com.dashboard.service.DataService;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.*;

import java.util.Map;
import java.util.NoSuchElementException;

@Controller
public class DashboardController {

    private final DataService dataService;

    public DashboardController(DataService dataService) {
        this.dataService = dataService;
    }

    // ─── Página principal ────────────────────────────────────────
    @GetMapping("/")
    public String index(Model model) {
        try {
            model.addAttribute("stats",  dataService.getStats());
            model.addAttribute("tables", dataService.listTables());
            model.addAttribute("dbOk",   true);
        } catch (Exception e) {
            model.addAttribute("dbOk",  false);
            model.addAttribute("error", e.getMessage());
        }
        return "index";
    }

    // ─── API: lista de tablas ─────────────────────────────────────
    @GetMapping("/api/tables")
    @ResponseBody
    public ResponseEntity<?> apiTables() {
        try {
            return ResponseEntity.ok(Map.of(
                "status", "ok",
                "tables", dataService.listTables()
            ));
        } catch (Exception e) {
            return ResponseEntity.internalServerError()
                .body(Map.of("status", "error", "message", e.getMessage()));
        }
    }

    // ─── API: datos de tabla ──────────────────────────────────────
    @GetMapping("/api/data/{table}")
    @ResponseBody
    public ResponseEntity<?> apiData(
        @PathVariable String table,
        @RequestParam(defaultValue = "100") int limit,
        @RequestParam(defaultValue = "0")   int offset
    ) {
        try {
            TableData data = dataService.getTableData(table, limit, offset);
            return ResponseEntity.ok(Map.of(
                "status",      "ok",
                "tableName",   data.tableName(),
                "total",       data.total(),
                "limit",       data.limit(),
                "offset",      data.offset(),
                "numericCols", data.numericCols(),
                "textCols",    data.textCols(),
                "rows",        data.rows()
            ));
        } catch (NoSuchElementException e) {
            return ResponseEntity.notFound().build();
        } catch (Exception e) {
            return ResponseEntity.internalServerError()
                .body(Map.of("status", "error", "message", e.getMessage()));
        }
    }

    // ─── API: estadísticas ────────────────────────────────────────
    @GetMapping("/api/stats")
    @ResponseBody
    public ResponseEntity<?> apiStats() {
        try {
            Map<String, Object> stats = dataService.getStats();
            stats.put("status", "ok");
            return ResponseEntity.ok(stats);
        } catch (Exception e) {
            return ResponseEntity.internalServerError()
                .body(Map.of("status", "error", "message", e.getMessage()));
        }
    }
}
