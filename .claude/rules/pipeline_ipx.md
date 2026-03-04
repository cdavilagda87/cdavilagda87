---
description: Reglas para el agente IPX
globs: "*.py"
---
- Claude se llama via subprocess con --print, nunca directamente
- Prompt siempre en español, respuesta esperada en JSON puro sin backticks
- Lotes de máximo 5 productos para evitar timeout (300s)
- VU = val_fob_ajustado / val_unid_fisic_ajustado
- Encoding de salidas: siempre utf-8-sig
- Subpartidas: str con zfill(10) para consistencia
- Al modificar _procesar_lote(): mantener el parser de JSON
  que cuenta corchetes (evita romper con texto extra de Claude)