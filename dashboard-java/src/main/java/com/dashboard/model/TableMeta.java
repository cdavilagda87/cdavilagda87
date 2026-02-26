package com.dashboard.model;

/**
 * Representa una entrada de la tabla _metadata en SQLite.
 */
public record TableMeta(
    Long   id,
    String tableName,
    String sourceName,
    String fileName,
    String sheetName,
    Long   rowCount,
    Long   colCount,
    String createdAt
) {}
