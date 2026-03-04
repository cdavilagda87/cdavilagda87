#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
"""
Agente Fase 2 Mensual - IPX
============================================================
Clasifica los productos del nuevo mes usando los modelos de
Fase 1 y usa Claude Opus para resolver los casos REVISAR_MANUAL.

Uso:
    python agente_fase2_mensual.py base_mes_2025_12.csv
    python agente_fase2_mensual.py base_mes_2025_12.csv --umbral 0.8
    python agente_fase2_mensual.py base_mes_2025_12.csv --sin-ia

Requisitos:
    Claude Code CLI instalado y autenticado (suscripcion Pro)
    El ejecutable 'claude' debe estar en el PATH del sistema

Salidas (en salidas_mensuales/):
    clasificacion_<timestamp>.csv          — Todo el mes con grupos asignados
    revision_ia_<timestamp>.csv            — Productos con sugerencias de Claude
    diagnostico_<timestamp>.json           — Métricas del proceso
    resumen_<timestamp>.txt                — Resumen ejecutivo
"""

import os
import re
import sys
import json
import shutil
import subprocess
import joblib
import argparse
import numpy as np
import pandas as pd

from tqdm import tqdm
from pathlib import Path
from datetime import datetime
from scipy import stats
from unidecode import unidecode
from difflib import get_close_matches

tqdm.pandas()


def _encontrar_claude() -> str:
    """
    Devuelve la ruta al ejecutable claude.
    Primero busca en el PATH; si no lo encuentra, busca el bundled
    que viene dentro de claude-agent-sdk.
    """
    # 1. Buscar en el PATH del sistema
    ruta = shutil.which("claude")
    if ruta:
        return ruta

    # 2. Buscar en el paquete claude-agent-sdk (bundled)
    try:
        import claude_agent_sdk
        bundled = Path(claude_agent_sdk.__file__).parent / "_bundled" / "claude.exe"
        if bundled.exists():
            return str(bundled)
    except ImportError:
        pass

    return ""  # No encontrado


# ══════════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ══════════════════════════════════════════════════════════════

BASE_DIR     = Path("D:/crdavila/Índice de precios/IPX")
MODELOS_DIR  = BASE_DIR / "modelos_fase1"
TFIDF_DIR    = MODELOS_DIR / "tfidf_kmeans"
VOCAB_PATH   = MODELOS_DIR / "vocabulario_global.pkl"
BASE_GRUPOS_PATH = BASE_DIR / "base_grupos_fase1.csv"
MAPA_VU_PATH = MODELOS_DIR / "mapa_subgrupos_vu.csv"
OUT_DIR      = BASE_DIR / "salidas_mensuales"

MODEL_CLAUDE = "claude-opus-4-6"

# Umbral de confianza para auto-asignar sin revisión humana
UMBRAL_AUTOASIGNAR = 0.85


# ══════════════════════════════════════════════════════════════
# FUNCIONES DE LIMPIEZA (idénticas a Fase 1)
# ══════════════════════════════════════════════════════════════

def limpiar_texto(texto):
    if pd.isna(texto):
        return ""
    texto = str(texto).lower()
    texto = unidecode(texto)
    texto = re.sub(r"[^a-z0-9\s]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def autocorregir_texto(texto, vocabulario):
    def _corregir(palabra):
        if palabra in vocabulario:
            return palabra
        sug = get_close_matches(palabra, vocabulario, n=1, cutoff=0.8)
        return sug[0] if sug else palabra
    return " ".join(_corregir(p) for p in texto.split())


# ══════════════════════════════════════════════════════════════
# PASO 1: CARGA Y PREPROCESAMIENTO
# ══════════════════════════════════════════════════════════════

def cargar_y_preprocesar(data_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Carga el CSV mensual, limpia y autocorrige descripciones.
    Retorna (df_mes, df_base) donde df_base es el histórico de Fase 1.
    """
    print(f"\n📥 Cargando archivo mensual: {data_path.name}")
    df = pd.read_csv(
        data_path,
        dtype={
            "cod_nandina": str,
            "cod_identificacion": str,
            "Subpartida_Destino_2022": str,
        },
    )
    print(f"   Registros cargados: {len(df):,}")

    vocabulario = joblib.load(VOCAB_PATH)

    print("🧹 Limpiando texto...")
    df["desc_comercial_limpia"] = df["nom_desc_comer"].progress_apply(limpiar_texto)

    print("🔠 Autocorrigiendo...")
    df["desc_comercial_limpia"] = df["desc_comercial_limpia"].progress_apply(
        lambda x: autocorregir_texto(x, vocabulario)
    )

    df["vu"] = df["val_fob_ajustado"] / df["val_unid_fisic_ajustado"].replace(0, np.nan)
    df = df[df["vu"].notna() & (df["vu"] > 0)].copy()
    print(f"   Registros válidos (VU > 0): {len(df):,}")

    print("📂 Cargando histórico de Fase 1...")
    df_base = pd.read_csv(BASE_GRUPOS_PATH)

    return df, df_base


# ══════════════════════════════════════════════════════════════
# PASO 2: ASIGNACIÓN DE GRUPO BASE (TF-IDF + KMeans)
# ══════════════════════════════════════════════════════════════

def asignar_grupos_base(df: pd.DataFrame) -> pd.DataFrame:
    """Aplica los vectorizadores y KMeans de Fase 1 al nuevo mes."""
    print("\n🔖 Asignando grupos base (TF-IDF + KMeans)...")
    df = df.copy()
    df["grupo_base"] = None

    subpartidas = list(df.groupby("Subpartida_Destino_2022"))
    nuevas = 0

    for subp, bloque in tqdm(subpartidas, desc="Subpartidas"):
        vec_path = TFIDF_DIR / f"vectorizer_{subp}.pkl"
        km_path  = TFIDF_DIR / f"kmeans_{subp}.pkl"

        if not (vec_path.exists() and km_path.exists()):
            df.loc[bloque.index, "grupo_base"] = f"TF_{subp}_1"
            nuevas += 1
            continue

        vectorizer = joblib.load(vec_path)
        kmeans     = joblib.load(km_path)
        X_new      = vectorizer.transform(bloque["desc_comercial_limpia"])
        labels     = kmeans.predict(X_new)
        df.loc[bloque.index, "grupo_base"] = [f"TF_{subp}_{i+1}" for i in labels]

    print(f"   Subpartidas sin modelo (nuevas): {nuevas}")
    return df


# ══════════════════════════════════════════════════════════════
# PASO 3: ASIGNACIÓN DE GRUPO FINAL (mapa VU multicriterio)
# ══════════════════════════════════════════════════════════════

def _score_candidato(vu_nuevo, candidato, vu_historico, max_obs):
    """Calcula score multicriterio para un candidato de grupo."""
    rango = candidato["vu_max"] - candidato["vu_min"]
    dist_norm = (
        abs(vu_nuevo - candidato["vu_mediana"]) / rango
        if rango > 0
        else abs(vu_nuevo - candidato["vu_mediana"])
    )
    s_dist = np.exp(-dist_norm)

    if len(vu_historico) > 1:
        mean_vu, std_vu = vu_historico.mean(), vu_historico.std()
        z = abs((vu_nuevo - mean_vu) / std_vu) if std_vu > 0 else 0
        s_prob = stats.norm.pdf(z, 0, 1) / stats.norm.pdf(0, 0, 1)
    else:
        s_prob = 0.5

    s_tam = candidato["n_obs"] / max_obs if max_obs > 0 else 0

    if vu_nuevo < candidato["vu_min"]:
        desv = (candidato["vu_min"] - vu_nuevo) / candidato["vu_min"]
    elif vu_nuevo > candidato["vu_max"]:
        desv = (vu_nuevo - candidato["vu_max"]) / candidato["vu_max"]
    else:
        desv = 0
    s_rango = np.exp(-5 * desv)

    return 0.35 * s_dist + 0.25 * s_prob + 0.20 * s_tam + 0.20 * s_rango


def _asignar_fila(row, mapa, df_base, umbral):
    candidatos = mapa[
        (mapa["Subpartida_Destino_2022"] == row["Subpartida_Destino_2022"])
        & (mapa["grupo_base"] == row["grupo_base"])
    ].copy()

    if candidatos.empty:
        return {"grupo_final": "NO_MAPEADO", "score_confianza": 0.0, "metodo": "sin_candidatos"}

    # Intento directo: dentro del rango
    dentro = candidatos[
        (row["vu"] >= candidatos["vu_min"]) & (row["vu"] <= candidatos["vu_max"])
    ]
    if not dentro.empty:
        mejor = dentro.loc[dentro["n_obs"].idxmax()]
        return {"grupo_final": mejor["grupo_final"], "score_confianza": 1.0, "metodo": "rango_directo"}

    # Fallback multicriterio
    max_obs = candidatos["n_obs"].max()
    scores = []
    for _, cand in candidatos.iterrows():
        hist = df_base[df_base["grupo_final"] == cand["grupo_final"]]["vu"]
        score = _score_candidato(row["vu"], cand, hist, max_obs)
        scores.append({"grupo_final": cand["grupo_final"], "score": score})

    mejor = max(scores, key=lambda x: x["score"])

    if mejor["score"] < umbral:
        return {
            "grupo_final": "REVISAR_MANUAL",
            "score_confianza": mejor["score"],
            "metodo": "baja_confianza",
            "sugerencia": mejor["grupo_final"],
        }
    return {"grupo_final": mejor["grupo_final"], "score_confianza": mejor["score"], "metodo": "fallback_multicriterio"}


def asignar_grupos_finales(df: pd.DataFrame, mapa_vu: pd.DataFrame, df_base: pd.DataFrame, umbral: float = 0.7) -> pd.DataFrame:
    """Asigna grupo_final con el método multicriterio de Fase 2."""
    print(f"\n📊 Asignando grupos finales (umbral confianza={umbral})...")
    df = df.copy()

    resultados = df.apply(lambda row: _asignar_fila(row, mapa_vu, df_base, umbral), axis=1)
    df["grupo_final"]        = resultados.apply(lambda x: x["grupo_final"])
    df["score_confianza"]    = resultados.apply(lambda x: x["score_confianza"])
    df["metodo_asignacion"]  = resultados.apply(lambda x: x["metodo"])

    asignados  = df["grupo_final"].str.startswith("TF_").sum()
    revisar    = (df["grupo_final"] == "REVISAR_MANUAL").sum()
    no_mapeado = (df["grupo_final"] == "NO_MAPEADO").sum()

    print(f"   ✅ Asignados automáticamente : {asignados:,} ({asignados/len(df)*100:.1f}%)")
    print(f"   ⚠️  Para revisión manual     : {revisar:,} ({revisar/len(df)*100:.1f}%)")
    print(f"   ❌ Sin mapa (subpartida nueva): {no_mapeado:,}")
    return df


# ══════════════════════════════════════════════════════════════
# PASO 3B: DETECCIÓN DE DESCRIPCIONES NUEVAS
# ══════════════════════════════════════════════════════════════

def detectar_descripciones_nuevas(df: pd.DataFrame, percentil: float = 95) -> pd.DataFrame:
    """
    Detecta productos cuya descripción es inusual dentro de su grupo asignado.
    Calcula la distancia euclidiana al centroide KMeans para cada producto
    ya clasificado; los que superan el percentil indicado se marcan como
    'descripcion_nueva = True' para revisión con Claude.
    Solo aplica a productos con grupo_final que comienza con 'TF_'.
    """
    print(f"\n🔍 Detectando descripciones inusuales (umbral=P{int(percentil)})...")
    df = df.copy()
    df["descripcion_nueva"] = False
    df["dist_centroide"]    = np.nan

    mask_asignados  = df["grupo_final"].str.startswith("TF_", na=False)
    total_asignados = int(mask_asignados.sum())

    for subp, bloque in tqdm(
        df[mask_asignados].groupby("Subpartida_Destino_2022"),
        desc="Calculando distancias",
    ):
        vec_path = TFIDF_DIR / f"vectorizer_{subp}.pkl"
        km_path  = TFIDF_DIR / f"kmeans_{subp}.pkl"
        if not (vec_path.exists() and km_path.exists()):
            continue

        vectorizer = joblib.load(vec_path)
        kmeans     = joblib.load(km_path)
        X          = vectorizer.transform(bloque["desc_comercial_limpia"])
        labels     = kmeans.predict(X)

        dists = [
            np.linalg.norm(X[i].toarray().flatten() - kmeans.cluster_centers_[labels[i]])
            for i in range(X.shape[0])
        ]
        dists_s = pd.Series(dists, index=bloque.index)
        df.loc[bloque.index, "dist_centroide"] = dists_s

        umbral_subp = np.percentile(dists, percentil)
        df.loc[dists_s[dists_s > umbral_subp].index, "descripcion_nueva"] = True

    n_nuevas = int(df["descripcion_nueva"].sum())
    pct = n_nuevas / total_asignados * 100 if total_asignados > 0 else 0
    print(f"   🆕 Descripciones potencialmente nuevas: {n_nuevas:,}  ({pct:.1f}% de los asignados)")
    return df


# ══════════════════════════════════════════════════════════════
# PASO 4: INTEGRACIÓN CON CLAUDE (VÍA CLI / SUSCRIPCIÓN PRO)
# ══════════════════════════════════════════════════════════════

def _procesar_lote(
    lote: list,
    mapa_vu: pd.DataFrame,
    df_base: pd.DataFrame,
) -> list:
    """Clasifica un lote de productos llamando al CLI de claude (--print)."""
    secciones = []
    for p in lote:
        grupos = mapa_vu[
            mapa_vu["Subpartida_Destino_2022"] == p["subpartida"]
        ][["grupo_base", "grupo_final", "vu_min", "vu_max", "vu_mediana", "n_obs"]]

        hist = df_base[
            df_base["Subpartida_Destino_2022"] == p["subpartida"]
        ]["vu"]

        grupos_str = grupos.to_string(index=False) if not grupos.empty else "Sin grupos previos"
        vu_min_h = f"{hist.min():.2f}" if len(hist) > 0 else "N/D"
        vu_max_h = f"{hist.max():.2f}" if len(hist) > 0 else "N/D"
        vu_med_h = f"{hist.median():.2f}" if len(hist) > 0 else "N/D"

        secciones.append(
            f"[PRODUCTO index={p['index']}]\n"
            f"Descripcion  : {p['descripcion']}\n"
            f"Subpartida   : {p['subpartida']}\n"
            f"Valor unit.  : {p['vu']:.4f} USD\n"
            f"Grupo base   : {p['grupo_base']}\n"
            f"Rango VU hist: {vu_min_h} - {vu_max_h} USD  (mediana: {vu_med_h})\n"
            f"Grupos disponibles:\n{grupos_str}"
        )

    prompt = (
        "Eres un experto en clasificacion de productos para el IPX "
        "(Indice de Precios de Exportacion de Guatemala).\n\n"
        f"TAREA: Clasifica los {len(lote)} productos listados. "
        "El sistema automatico no pudo asignarlos con suficiente confianza.\n\n"
        "Para cada producto determina:\n"
        "  - accion='asignar_grupo' si puede incluirse en un grupo existente\n"
        "  - accion='nuevo_grupo'   si es una variedad nueva sin equivalente\n"
        "  - accion='revisar_datos' si el VU parece un error de datos\n\n"
        "CRITERIOS:\n"
        "1. Elige el grupo cuyo rango VU sea mas compatible con el valor unitario.\n"
        "2. Considera similitud entre la descripcion y los grupos disponibles.\n"
        "3. Con varios grupos compatibles, prefiere el de mayor n_obs.\n"
        "4. Usa NUEVO_GRUPO si la variedad es claramente nueva.\n"
        "5. Usa ERROR_DATOS solo si el VU es ~1000x mayor que la mediana historica.\n\n"
        "PRODUCTOS:\n"
        + "\n\n".join(secciones)
        + "\n\nRESPUESTA:\n"
        "Responde UNICAMENTE con un JSON array valido. Sin texto antes ni despues.\n"
        "[\n"
        "  {\n"
        '    "index": <numero entero exacto del index>,\n'
        '    "grupo_sugerido": "<codigo_grupo_final o NUEVO_GRUPO o ERROR_DATOS>",\n'
        '    "accion": "<asignar_grupo|nuevo_grupo|revisar_datos>",\n'
        '    "razon": "<maximo 2 oraciones>",\n'
        '    "confianza": <numero 0.0-1.0>\n'
        "  }\n"
        "]\n"
        f"El array debe tener exactamente {len(lote)} elementos."
    )

    claude_exe = _encontrar_claude()
    if not claude_exe:
        raise RuntimeError("No se encontro el ejecutable claude en el PATH ni en claude-agent-sdk")

    # Pasamos el prompt por stdin para evitar límites de longitud de argumento
    result = subprocess.run(
        [claude_exe, "--print"],
        input=prompt,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"CLI claude salio con codigo {result.returncode}. "
            f"STDERR: {result.stderr[:500]}"
        )

    resultado = result.stdout.strip()
    start = resultado.find("[")
    if start == -1:
        raise ValueError(f"No se encontro '[' en la respuesta: {resultado[:300]}")

    # Buscar el cierre correcto contando corchetes (evita confundir con texto extra)
    depth = 0
    end = -1
    in_string = False
    escape_next = False
    for i, ch in enumerate(resultado[start:], start):
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                end = i
                break

    if end == -1:
        raise ValueError(f"No se encontro cierre del JSON array: {resultado[:300]}")
    return json.loads(resultado[start:end + 1])


def procesar_con_ia(
    df_mes: pd.DataFrame,
    mapa_vu: pd.DataFrame,
    df_base: pd.DataFrame,
) -> pd.DataFrame:
    """
    Para cada producto REVISAR_MANUAL / NO_MAPEADO, consulta a Claude via CLI
    (usa la suscripcion Pro, sin API key de creditos) y:
    - Agrega columnas: grupo_sugerido_ia, accion_ia, razon_ia, confianza_ia
    - Auto-asigna los que tengan confianza >= UMBRAL_AUTOASIGNAR
    """
    # Inicializar columnas IA siempre (aunque no haya productos que revisar)
    for col in ["grupo_sugerido_ia", "accion_ia", "razon_ia", "confianza_ia"]:
        df_mes[col] = None

    mask_revisar = df_mes["grupo_final"].isin(["REVISAR_MANUAL", "NO_MAPEADO"])
    df_revisar   = df_mes[mask_revisar].copy()

    if len(df_revisar) == 0:
        print("\n✅ No hay productos para revision IA — saltando paso")
        return df_mes

    print(f"\n🤖 Claude analizando {len(df_revisar)} productos (via CLI / suscripcion Pro)...")
    print(f"   Objetivo : identificar variedades nuevas vs. asignar a grupo existente")
    print(f"   Auto-asignacion si confianza >= {UMBRAL_AUTOASIGNAR:.0%}\n")

    # Preparar lista de productos y dividir en lotes
    BATCH_SIZE = 5
    productos = []
    for idx, row in df_revisar.iterrows():
        productos.append({
            "index":       idx,
            "descripcion": str(row.get("nom_desc_comer", "")),
            "subpartida":  str(row.get("Subpartida_Destino_2022", "")),
            "vu":          float(row["vu"]) if pd.notna(row.get("vu")) else 0.0,
            "grupo_base":  str(row.get("grupo_base", "")),
        })

    lotes = [productos[i:i + BATCH_SIZE] for i in range(0, len(productos), BATCH_SIZE)]
    print(f"   Procesando en {len(lotes)} lotes de hasta {BATCH_SIZE} productos c/u\n")

    # Procesar lotes de forma sincrona
    resultados_lotes = []
    for i, lote in enumerate(lotes):
        print(f"  Lote {i + 1}/{len(lotes)} ({len(lote)} productos)...", end=" ", flush=True)
        try:
            resultados = _procesar_lote(lote, mapa_vu, df_base)
            resultados_lotes.append((lote, resultados, None))
            print("OK")
        except Exception as e:
            resultados_lotes.append((lote, [], e))
            print(f"ERROR: {e}")

    # Aplicar resultados al DataFrame
    auto_asignados = 0
    nuevos_grupos  = 0
    errores_ia     = 0

    for lote, resultados, error in resultados_lotes:
        if error is not None:
            for prod in lote:
                idx = prod["index"]
                df_mes.at[idx, "grupo_sugerido_ia"] = "ERROR_IA"
                df_mes.at[idx, "accion_ia"]         = "revisar_datos"
                df_mes.at[idx, "razon_ia"]          = f"Error en lote: {error}"
                df_mes.at[idx, "confianza_ia"]      = 0.0
            errores_ia += len(lote)
            continue

        res_map = {r["index"]: r for r in resultados}

        for prod in lote:
            idx = prod["index"]
            r   = res_map.get(idx)

            if r is None:
                df_mes.at[idx, "grupo_sugerido_ia"] = "ERROR_IA"
                df_mes.at[idx, "accion_ia"]         = "revisar_datos"
                df_mes.at[idx, "razon_ia"]          = "Sin resultado para este producto"
                df_mes.at[idx, "confianza_ia"]      = 0.0
                errores_ia += 1
                continue

            df_mes.at[idx, "grupo_sugerido_ia"] = r.get("grupo_sugerido", "ERROR_IA")
            df_mes.at[idx, "accion_ia"]         = r.get("accion", "revisar_datos")
            df_mes.at[idx, "razon_ia"]          = r.get("razon", "")
            df_mes.at[idx, "confianza_ia"]      = float(r.get("confianza", 0.0))

            accion    = r.get("accion", "")
            confianza = float(r.get("confianza", 0.0))

            if accion == "asignar_grupo" and confianza >= UMBRAL_AUTOASIGNAR:
                df_mes.at[idx, "grupo_final"]       = r.get("grupo_sugerido")
                df_mes.at[idx, "metodo_asignacion"] = "ia_alta_confianza"
                auto_asignados += 1
            elif accion == "nuevo_grupo":
                df_mes.at[idx, "grupo_final"]       = "NUEVO_GRUPO_POTENCIAL"
                df_mes.at[idx, "metodo_asignacion"] = "ia_nuevo_grupo"
                nuevos_grupos += 1

    aun_manual = df_mes["grupo_final"].isin(["REVISAR_MANUAL", "NO_MAPEADO"]).sum()

    print(f"\n   ✅ Asignados a grupo existente (confianza >= {UMBRAL_AUTOASIGNAR:.0%}): {auto_asignados}")
    print(f"   🆕 Variedades nuevas detectadas                                   : {nuevos_grupos}")
    print(f"   📋 Pendientes de revision humana (baja confianza)                 : {aun_manual}")
    if errores_ia:
        print(f"   ❌ Errores en consulta a IA                                       : {errores_ia}")

    return df_mes


# ══════════════════════════════════════════════════════════════
# PASO 5: GUARDAR RESULTADOS
# ══════════════════════════════════════════════════════════════

def guardar_resultados(df_mes: pd.DataFrame, usar_ia: bool) -> dict:
    """Guarda CSVs, JSON de diagnóstico y resumen de texto."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    archivos = {}

    # 1. Clasificación completa
    arch_completo = OUT_DIR / f"clasificacion_{ts}.csv"
    df_mes.to_csv(arch_completo, index=False, encoding="utf-8-sig")
    archivos["completo"] = arch_completo
    print(f"\n✅ Clasificación completa : {arch_completo.name}")

    # 2. Productos pendientes de revisión humana
    mask_revisar = df_mes["grupo_final"].isin(["REVISAR_MANUAL", "NO_MAPEADO"])
    if mask_revisar.any():
        arch_revisar = OUT_DIR / f"revision_pendiente_{ts}.csv"
        df_mes[mask_revisar].to_csv(arch_revisar, index=False, encoding="utf-8-sig")
        archivos["revision"] = arch_revisar
        print(f"⚠️  Revisión pendiente      : {arch_revisar.name}  ({mask_revisar.sum()} registros)")

    # 3. Sugerencias de IA (si aplica)
    if usar_ia:
        arch_ia = OUT_DIR / f"revision_ia_{ts}.csv"
        cols_ia = [c for c in [
            "Subpartida_Destino_2022", "nom_desc_comer", "desc_comercial_limpia",
            "vu", "grupo_base", "grupo_final", "score_confianza", "metodo_asignacion",
            "grupo_sugerido_ia", "accion_ia", "razon_ia", "confianza_ia",
        ] if c in df_mes.columns]
        df_ia = df_mes[df_mes["grupo_sugerido_ia"].notna()][cols_ia]
        df_ia.to_csv(arch_ia, index=False, encoding="utf-8-sig")
        archivos["ia"] = arch_ia
        print(f"🤖 Sugerencias IA          : {arch_ia.name}  ({len(df_ia)} registros)")

    # 4. Diagnóstico JSON
    asignados      = df_mes["grupo_final"].str.startswith("TF_", na=False).sum()
    revisar        = (df_mes["grupo_final"] == "REVISAR_MANUAL").sum()
    no_mapeado     = (df_mes["grupo_final"] == "NO_MAPEADO").sum()
    nuevo_potencial= (df_mes["grupo_final"] == "NUEVO_GRUPO_POTENCIAL").sum()
    ia_alta        = (df_mes.get("metodo_asignacion", pd.Series()) == "ia_alta_confianza").sum()

    diagnostico = {
        "timestamp": ts,
        "total_productos": len(df_mes),
        "cobertura": {
            "asignados_automaticos": int(asignados),
            "asignados_ia_alta_confianza": int(ia_alta),
            "nuevo_grupo_potencial": int(nuevo_potencial),
            "revision_humana_pendiente": int(revisar + no_mapeado),
        },
        "confianza_promedio": float(
            df_mes[df_mes["grupo_final"].str.startswith("TF_", na=False)]["score_confianza"].mean()
        ),
        "metodos_asignacion": df_mes["metodo_asignacion"].value_counts().to_dict(),
    }
    if usar_ia and "confianza_ia" in df_mes.columns:
        ia_validas = df_mes["confianza_ia"].dropna()
        diagnostico["ia"] = {
            "total_procesados": int(ia_validas.notna().sum()),
            "confianza_promedio_ia": float(ia_validas.mean()) if len(ia_validas) > 0 else None,
            "auto_asignados": int(ia_alta),
        }

    arch_diag = OUT_DIR / f"diagnostico_{ts}.json"
    with open(arch_diag, "w", encoding="utf-8") as f:
        json.dump(diagnostico, f, indent=2, ensure_ascii=False, default=str)
    archivos["diagnostico"] = arch_diag
    print(f"📊 Diagnóstico             : {arch_diag.name}")

    # 5. Resumen texto
    arch_res = OUT_DIR / f"resumen_{ts}.txt"
    with open(arch_res, "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write("RESUMEN DE CLASIFICACIÓN MENSUAL — IPX\n")
        f.write("=" * 70 + "\n\n")
        f.write(f"Fecha de proceso : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total productos  : {len(df_mes):,}\n\n")
        f.write("COBERTURA:\n")
        f.write(f"  Asignados automáticamente : {asignados:,} ({asignados/len(df_mes)*100:.1f}%)\n")
        if ia_alta:
            f.write(f"  Asignados por IA          : {ia_alta:,} ({ia_alta/len(df_mes)*100:.1f}%)\n")
        if nuevo_potencial:
            f.write(f"  Nuevo grupo potencial     : {nuevo_potencial:,} ({nuevo_potencial/len(df_mes)*100:.1f}%)\n")
        pend = revisar + no_mapeado
        f.write(f"  Revisión humana pendiente : {pend:,} ({pend/len(df_mes)*100:.1f}%)\n\n")
        f.write(f"Confianza promedio (asignados): {diagnostico['confianza_promedio']:.2%}\n\n")
        f.write("MÉTODOS DE ASIGNACIÓN:\n")
        for metodo, cnt in diagnostico["metodos_asignacion"].items():
            f.write(f"  {metodo:<30}: {cnt:,}\n")
        if pend == 0:
            f.write("\n✅ Todos los productos fueron clasificados exitosamente.\n")
        else:
            f.write(f"\n⚠️  {pend} productos requieren revisión manual.\n")
            f.write(f"   Ver: revision_pendiente_{ts}.csv\n")
    archivos["resumen"] = arch_res
    print(f"📄 Resumen ejecutivo       : {arch_res.name}")

    return diagnostico


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Agente Fase 2 Mensual IPX — Clasificación con IA"
    )
    parser.add_argument(
        "archivo_mes",
        help="Nombre del CSV mensual (ej: base_mes_2025_12.csv)",
    )
    parser.add_argument(
        "--umbral",
        type=float,
        default=0.7,
        help="Umbral de confianza para asignación automática (default: 0.7)",
    )
    parser.add_argument(
        "--sin-ia",
        action="store_true",
        help="Omitir el paso de clasificación con Claude (útil para pruebas)",
    )
    parser.add_argument(
        "--percentil-novedad",
        type=float,
        default=95.0,
        help="Percentil de distancia al centroide para detectar descripciones inusuales (default: 95)",
    )
    args = parser.parse_args()

    data_path = BASE_DIR / args.archivo_mes
    if not data_path.exists():
        print(f"❌ Archivo no encontrado: {data_path}")
        sys.exit(1)

    usar_ia = not args.sin_ia

    if usar_ia and not _encontrar_claude():
        print("❌ No se encontro el ejecutable claude")
        print("   Opciones:")
        print("   1. Instala claude-agent-sdk: pip install claude-agent-sdk")
        print("   2. Instala Claude Code CLI y agrega al PATH")
        print("   3. Usa --sin-ia para omitir la clasificacion con Claude")
        sys.exit(1)

    print("=" * 70)
    print("AGENTE FASE 2 MENSUAL — IPX")
    print("=" * 70)
    print(f"Archivo    : {args.archivo_mes}")
    print(f"Umbral     : {args.umbral}")
    print(f"P-novedad  : {args.percentil_novedad}")
    print(f"Modo IA    : {'✅ Claude (CLI / Pro)' if usar_ia else '❌ Desactivado'}")
    print("=" * 70)

    # Cargar artefactos de Fase 1
    mapa_vu = pd.read_csv(MAPA_VU_PATH)
    mapa_vu["Subpartida_Destino_2022"] = (
        mapa_vu["Subpartida_Destino_2022"].astype(str).str.zfill(10)
    )

    # Pipeline
    df_mes, df_base = cargar_y_preprocesar(data_path)
    df_mes = asignar_grupos_base(df_mes)
    df_mes = asignar_grupos_finales(df_mes, mapa_vu, df_base, umbral=args.umbral)

    if usar_ia:
        df_mes = procesar_con_ia(df_mes, mapa_vu, df_base)

    print("\n" + "=" * 70)
    print("GUARDANDO RESULTADOS")
    print("=" * 70)
    guardar_resultados(df_mes, usar_ia)

    print("\n" + "=" * 70)
    print("✅ PROCESO COMPLETADO")
    print("=" * 70)


if __name__ == "__main__":
    main()
