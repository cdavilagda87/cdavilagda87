<?php
/**
 * Configuración del Dashboard BCE
 */

// Ruta a la base de datos SQLite (relativa a este archivo)
define('DB_PATH', __DIR__ . '/../database/bce_data.db');

// Número de filas por tabla a mostrar en el dashboard
define('MAX_ROWS_PREVIEW', 100);

// Zona horaria
date_default_timezone_set('America/Guayaquil');

/**
 * Obtiene conexión PDO a SQLite.
 * Lanza excepción si la DB no existe.
 */
function get_db(): PDO {
    if (!file_exists(DB_PATH)) {
        throw new RuntimeException(
            'Base de datos no encontrada. Ejecute primero: python agent.py'
        );
    }
    $pdo = new PDO('sqlite:' . DB_PATH);
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
    $pdo->setAttribute(PDO::ATTR_DEFAULT_FETCH_MODE, PDO::FETCH_ASSOC);
    return $pdo;
}
