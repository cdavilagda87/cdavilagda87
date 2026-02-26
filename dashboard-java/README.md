# Dashboard Java — BCE Ecuador (Spring Boot)

## Requisitos
- Java 17+
- Maven 3.8+

## Uso

```bash
# 1. Generar la base de datos con el agente Python
cd ..
python agent.py          # descarga real del BCE
python agent.py --demo   # datos de prueba

# 2. Compilar y ejecutar
cd dashboard-java
mvn spring-boot:run

# 3. Abrir en el navegador
http://localhost:8081
```

## Empaquetar como JAR ejecutable

```bash
mvn clean package -DskipTests
java -jar target/bce-dashboard-1.0.0.jar
```

## Variables de entorno

| Variable  | Descripción                  | Default                     |
|-----------|------------------------------|-----------------------------|
| `DB_PATH` | Ruta a la base SQLite        | `../database/bce_data.db`   |
| `PORT`    | Puerto del servidor (server.port) | `8081`                 |

```bash
DB_PATH=/ruta/a/bce_data.db java -jar bce-dashboard-1.0.0.jar
```

## API Endpoints

| Endpoint               | Descripción                      |
|------------------------|----------------------------------|
| `GET /`                | Dashboard web                    |
| `GET /api/tables`      | Lista de tablas (JSON)           |
| `GET /api/data/{table}?limit=100&offset=0` | Datos paginados |
| `GET /api/stats`       | Estadísticas generales           |
