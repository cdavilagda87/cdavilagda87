# Agente Clasificación IPX — Índice de Precios de Exportación

## Objetivo
Clasificar productos de comercio exterior mensualmente usando
TF-IDF + KMeans (Fase 1) y Claude CLI como fallback (Fase 2).

## Arquitectura
- agente_fase2_mensual.py  → pipeline principal
- Fase 1 (automático):     TF-IDF + KMeans por subpartida
- Fase 2 (IA):             Claude CLI vía subprocess para REVISAR_MANUAL
- Umbral auto-asignar:     0.85 (UMBRAL_AUTOASIGNAR)
- Umbral confianza:        0.70 (argumento --umbral)

## Rutas clave
- BASE_DIR:        D:/crdavila/Índice de precios/IPX/
- MODELOS_DIR:     BASE_DIR/modelos_fase1/
- TFIDF_DIR:       MODELOS_DIR/tfidf_kmeans/
- VOCAB_PATH:      MODELOS_DIR/vocabulario_global.pkl
- BASE_GRUPOS:     BASE_DIR/base_grupos_fase1.csv
- MAPA_VU:         MODELOS_DIR/mapa_subgrupos_vu.csv
- SALIDAS:         BASE_DIR/salidas_mensuales/

## Flujo del pipeline
1. cargar_y_preprocesar()          → limpia texto, calcula VU
2. asignar_grupos_base()           → TF-IDF + KMeans por subpartida
3. asignar_grupos_finales()        → mapa VU multicriterio
4. detectar_descripciones_nuevas() → distancia al centroide P95
5. procesar_con_ia()               → Claude CLI en lotes de 5
6. guardar_resultados()            → CSV + JSON + TXT

## Convenciones
- Grupos: formato TF_{subpartida}_{número}
- Períodos: YYYY-MM
- Encoding salidas: utf-8-sig
- Lotes Claude: BATCH_SIZE = 5 productos
- Estados posibles: TF_*, REVISAR_MANUAL, NO_MAPEADO,
  NUEVO_GRUPO_POTENCIAL, ERROR_IA

## Comandos frecuentes
- python agente_fase2_mensual.py base_mes_2025_12.csv
- python agente_fase2_mensual.py base_mes_2025_12.csv --umbral 0.8
- python agente_fase2_mensual.py base_mes_2025_12.csv --sin-ia
- python agente_fase2_mensual.py base_mes_2025_12.csv --percentil-novedad 90

## NUNCA modificar
- modelos_fase1/  (modelos entrenados en Fase 1)
- base_grupos_fase1.csv  (histórico base)