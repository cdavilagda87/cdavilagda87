package com.dashboard.model;

import java.util.List;
import java.util.Map;

/**
 * Resultado de una consulta de datos con metainformación de columnas.
 */
public record TableData(
    String              tableName,
    long                total,
    int                 limit,
    int                 offset,
    List<String>        numericCols,
    List<String>        textCols,
    List<Map<String, Object>> rows
) {}
