"""
inclusion_financiera_app.py
============================
Dashboard de Inclusión Financiera — BCE Ecuador (III Trimestre 2025)

Ejecutar localmente:
    streamlit run inclusion_financiera_app.py
"""

from __future__ import annotations

import os
import re
import sqlite3
import zipfile
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
from plotly.subplots import make_subplots

# ─── Config ──────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Inclusión Financiera — BCE Ecuador",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
)

ZIP_URL  = "https://contenido.bce.fin.ec/home1/economia/tasas/III2025.zip"
DATA_DIR = Path("downloads")
DB_PATH  = Path("database/inclusion_financiera.db")

C = {
    "primary":   "#003366",
    "blue":      "#0066CC",
    "orange":    "#E8530A",
    "green":     "#1A7340",
    "red":       "#C0392B",
    "yellow":    "#D4A017",
    "gray":      "#6B7280",
    "bg":        "#F0F4FA",
    "white":     "#FFFFFF",
}
PALETTE = ["#003366","#0066CC","#E8530A","#1A7340","#D4A017",
           "#17A2B8","#6F42C1","#C0392B","#2ECC71","#F39C12"]

logging.basicConfig(level=logging.WARNING)


# ─── CSS ─────────────────────────────────────────────────────────────────────

def apply_css():
    st.markdown(f"""
    <style>
    .stApp {{ background:{C['bg']}; }}
    [data-testid="stSidebar"] {{
        background: linear-gradient(180deg,{C['primary']} 0%,{C['blue']} 100%);
    }}
    [data-testid="stSidebar"] * {{ color:white !important; }}
    [data-testid="stSidebar"] hr {{ border-color:rgba(255,255,255,.25)!important; }}

    .card {{
        background:{C['white']}; border-radius:14px; padding:20px 24px;
        box-shadow:0 2px 10px rgba(0,51,102,.08);
        margin-bottom:18px;
    }}
    .kpi-card {{
        background:{C['white']}; border-radius:14px; padding:18px 20px;
        box-shadow:0 2px 10px rgba(0,51,102,.08);
        border-left:5px solid {C['blue']};
        text-align:center;
    }}
    .kpi-label {{
        font-size:.78rem; font-weight:700; text-transform:uppercase;
        letter-spacing:.06em; color:{C['gray']}; margin-bottom:6px;
    }}
    .kpi-value {{
        font-size:1.9rem; font-weight:800; color:{C['primary']}; line-height:1.1;
    }}
    .kpi-delta {{
        font-size:.82rem; margin-top:4px;
    }}
    .section-title {{
        font-size:1.05rem; font-weight:700; color:{C['primary']};
        border-bottom:2px solid {C['blue']}; padding-bottom:6px;
        margin-bottom:16px;
    }}
    .header-band {{
        background:linear-gradient(90deg,{C['primary']},{C['blue']});
        color:white; border-radius:14px; padding:22px 28px;
        margin-bottom:24px;
    }}
    </style>
    """, unsafe_allow_html=True)


# ─── Build / Load Database ────────────────────────────────────────────────────

@st.cache_resource(show_spinner=False)
def build_database() -> bool:
    if DB_PATH.exists():
        return True

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    zip_local = DATA_DIR / "III2025.zip"
    if not zip_local.exists():
        try:
            headers = {"User-Agent": "Mozilla/5.0 (compatible; BCE-Dashboard/2.0)"}
            r = requests.get(ZIP_URL, headers=headers, timeout=180)
            r.raise_for_status()
            zip_local.write_bytes(r.content)
        except Exception as e:
            st.error(f"No se pudo descargar el archivo: {e}")
            return False

    with zipfile.ZipFile(zip_local) as zf:
        zf.extractall(DATA_DIR)

    excels = list(DATA_DIR.rglob("*.xlsx")) + list(DATA_DIR.rglob("*.xls"))
    if not excels:
        st.error("No se encontraron archivos Excel en el ZIP.")
        return False

    # Usar el cleaner robusto
    try:
        from data_cleaner import process_excel_to_sqlite
        import sqlite3 as _sqlite3

        all_manifest = []
        for ef in excels:
            records = process_excel_to_sqlite(ef, DB_PATH)
            all_manifest.extend(records)

        with _sqlite3.connect(DB_PATH) as conn:
            pd.DataFrame(all_manifest).to_sql(
                "_manifest", conn, if_exists="replace", index=False
            )
        return True
    except Exception as e:
        st.error(f"Error al procesar Excel: {e}")
        return False


@st.cache_data(ttl=3600, show_spinner=False)
def load_manifest() -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql("SELECT * FROM _manifest ORDER BY archivo, hoja", conn)


@st.cache_data(ttl=3600, show_spinner=False)
def load_table(table: str) -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql(f'SELECT * FROM "{table}"', conn)


def numeric_cols(df: pd.DataFrame) -> list[str]:
    cols = []
    for c in df.columns:
        s = pd.to_numeric(df[c], errors="coerce").dropna()
        if len(s) >= 2:
            cols.append(c)
    return cols


def text_cols(df: pd.DataFrame) -> list[str]:
    nc = set(numeric_cols(df))
    return [c for c in df.columns if c not in nc and not c.startswith("_")]


def to_num(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    df = df.copy()
    for c in cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


# ─── Helpers de gráficos ─────────────────────────────────────────────────────

_CHART_CFG = dict(
    plot_bgcolor="white", paper_bgcolor="white",
    margin=dict(l=8, r=8, t=44, b=8),
    font=dict(color=C["primary"], size=12),
    title_font=dict(color=C["primary"], size=14),
    hoverlabel=dict(bgcolor="white", bordercolor=C["primary"]),
)


def line_chart(df: pd.DataFrame, x: str, y_cols: list[str],
               title: str = "") -> go.Figure:
    fig = go.Figure()
    for i, col in enumerate(y_cols):
        y = pd.to_numeric(df[col], errors="coerce")
        fig.add_trace(go.Scatter(
            x=df[x], y=y, mode="lines+markers", name=col,
            line=dict(color=PALETTE[i % len(PALETTE)], width=2.4),
            marker=dict(size=7, symbol="circle"),
        ))
    fig.update_layout(
        title=title,
        xaxis=dict(gridcolor="#E4EAF3", title=""),
        yaxis=dict(gridcolor="#E4EAF3"),
        legend=dict(orientation="h", y=-0.22, x=0),
        **_CHART_CFG,
    )
    return fig


def bar_chart(df: pd.DataFrame, x: str, y: str,
              title: str = "", orientation: str = "v",
              color_col: str | None = None) -> go.Figure:
    df_plot = to_num(df, [y]).dropna(subset=[y])
    fig = px.bar(
        df_plot, x=x, y=y, title=title,
        orientation=orientation,
        color=color_col or y,
        color_continuous_scale=[[0, "#9EC8FF"], [1, C["primary"]]],
        template="plotly_white",
    )
    fig.update_layout(coloraxis_showscale=False, **_CHART_CFG)
    fig.update_traces(marker_line_width=0)
    return fig


def pie_chart(df: pd.DataFrame, names: str, values: str,
              title: str = "") -> go.Figure:
    df_plot = to_num(df, [values]).dropna(subset=[values])
    fig = px.pie(
        df_plot, names=names, values=values, title=title,
        color_discrete_sequence=PALETTE, hole=0.42,
    )
    fig.update_layout(
        legend=dict(orientation="h", y=-0.18),
        **_CHART_CFG,
    )
    return fig


def grouped_bar(df: pd.DataFrame, x: str, y_cols: list[str],
                title: str = "") -> go.Figure:
    fig = go.Figure()
    df_num = to_num(df, y_cols)
    for i, col in enumerate(y_cols):
        fig.add_trace(go.Bar(
            name=col, x=df_num[x], y=df_num[col],
            marker_color=PALETTE[i % len(PALETTE)],
        ))
    fig.update_layout(
        title=title, barmode="group",
        xaxis=dict(gridcolor="#E4EAF3"),
        yaxis=dict(gridcolor="#E4EAF3"),
        legend=dict(orientation="h", y=-0.22),
        **_CHART_CFG,
    )
    return fig


# ─── KPI Cards ───────────────────────────────────────────────────────────────

def kpi_card(label: str, value: str, delta: str = "",
             color: str = C["blue"]) -> str:
    delta_color = C["green"] if "+" in delta else (C["red"] if "-" in delta else C["gray"])
    return f"""
    <div class="kpi-card" style="border-left-color:{color}">
      <div class="kpi-label">{label}</div>
      <div class="kpi-value">{value}</div>
      <div class="kpi-delta" style="color:{delta_color}">{delta or "&nbsp;"}</div>
    </div>"""


def fmt_big(n) -> str:
    try:
        n = float(n)
        if n >= 1_000_000:
            return f"{n/1_000_000:.2f}M"
        if n >= 1_000:
            return f"{n/1_000:.1f}K"
        return f"{n:,.0f}"
    except Exception:
        return str(n)


# ─── Vista: Serie de Tiempo (Nacional) ───────────────────────────────────────

def render_timeseries_view(df_nac: pd.DataFrame, sheet_name: str):
    """
    Visualiza la sección Nacional de una hoja con estructura de serie de tiempo.
    Detecta automáticamente los grupos de indicadores y los grafica.
    """
    st.markdown(f'<div class="section-title">📈 Serie de Tiempo · Nacional — {sheet_name}</div>',
                unsafe_allow_html=True)

    # Identificar columna de período/fecha/etiqueta
    cols_num = numeric_cols(df_nac)
    cols_txt = text_cols(df_nac)

    # Intentar detectar columna de período
    period_col = None
    for c in df_nac.columns:
        sample = df_nac[c].dropna().astype(str).head(10)
        # patrón: año o trimestre (2019, 2020T1, I-2025, etc.)
        if sample.str.match(r".*\b(19|20)\d{2}\b.*").mean() > 0.3:
            period_col = c
            break
    if period_col is None and cols_txt:
        period_col = cols_txt[0]

    if not cols_num:
        st.info("No se encontraron columnas numéricas en la sección Nacional.")
        st.dataframe(df_nac, use_container_width=True)
        return

    # Si hay período, graficar series de tiempo
    if period_col and period_col in df_nac.columns:
        df_plot = to_num(df_nac, cols_num).dropna(how="all", subset=cols_num)
        df_plot[period_col] = df_plot[period_col].astype(str)

        # Agrupar columnas por su prefijo (INDICADOR USO 1, USO 2, etc.)
        # Detectar grupos por el primer segmento del nombre de columna
        groups: dict[str, list[str]] = {}
        for col in cols_num:
            # El nombre tiene forma: "indicador_uso_1 | num_clientes | prod_fin"
            # tomamos el primer segmento como grupo
            parts = col.split("_|_") if "_|_" in col else col.split("|")
            group_key = parts[0].strip() if parts else col
            # Limpiar: tomar solo los primeros 40 chars del grupo
            group_key = re.sub(r"\s+", " ", group_key)[:60]
            groups.setdefault(group_key, []).append(col)

        if len(groups) <= 1:
            # Sin grupos claros: mostrar todas las columnas en un gráfico
            fig = line_chart(df_plot, period_col, cols_num[:8],
                             f"Evolución Nacional — {sheet_name}")
            st.plotly_chart(fig, use_container_width=True)
        else:
            # Mostrar un gráfico por grupo de indicadores
            n_groups = len(groups)
            cols_layout = 2 if n_groups > 1 else 1
            cols_ui = st.columns(cols_layout)

            for idx, (group_name, group_cols) in enumerate(groups.items()):
                display_cols = [c for c in group_cols if c in df_plot.columns][:6]
                if not display_cols:
                    continue
                with cols_ui[idx % cols_layout]:
                    fig = line_chart(
                        df_plot, period_col, display_cols,
                        title=group_name[:60],
                    )
                    st.plotly_chart(fig, use_container_width=True)

        # KPIs del último período
        last_row = df_plot.tail(1).iloc[0] if not df_plot.empty else None
        if last_row is not None:
            st.markdown("**Último período disponible**")
            kpi_cols = st.columns(min(4, len(cols_num)))
            for i, col in enumerate(cols_num[:4]):
                with kpi_cols[i]:
                    val = last_row[col]
                    st.markdown(
                        kpi_card(col[:35].replace("_", " "), fmt_big(val)),
                        unsafe_allow_html=True,
                    )

    else:
        # Sin columna de período clara: tabla + barras
        df_plot = to_num(df_nac, cols_num)
        col_y = cols_num[0]
        col_x = df_nac.columns[0] if df_nac.columns[0] != col_y else (cols_txt[0] if cols_txt else df_nac.columns[0])
        fig = bar_chart(
            df_plot.head(30), col_x, col_y,
            title=f"{col_y} — {sheet_name}",
            orientation="h",
        )
        st.plotly_chart(fig, use_container_width=True)

    # Tabla de datos
    with st.expander("🔎 Ver datos brutos"):
        st.dataframe(df_nac, use_container_width=True)


# ─── Vista: Geográfico (Provincial / Cantonal) ───────────────────────────────

def render_geo_view(df: pd.DataFrame, level: str, sheet_name: str):
    """
    Visualiza datos provinciales o cantonales.
    """
    icon = "🗺️" if level == "provincial" else "📍"
    st.markdown(
        f'<div class="section-title">{icon} Distribución {level.title()} — {sheet_name}</div>',
        unsafe_allow_html=True,
    )

    cols_num = numeric_cols(df)
    cols_txt = text_cols(df)

    if not cols_num:
        st.info(f"No se encontraron columnas numéricas en la sección {level}.")
        st.dataframe(df, use_container_width=True)
        return

    # Detectar columna de etiqueta geográfica
    geo_col = "_geo_label" if "_geo_label" in df.columns else (cols_txt[0] if cols_txt else df.columns[0])

    # Detectar columna de período si existe
    period_col = None
    for c in df.columns:
        if c == geo_col:
            continue
        sample = df[c].dropna().astype(str).head(8)
        if sample.str.match(r".*\b(19|20)\d{2}\b.*").mean() > 0.4:
            period_col = c
            break

    # Selector de métrica
    col_y = st.selectbox(
        "Métrica a visualizar",
        cols_num[:10],
        key=f"geo_metric_{level}_{sheet_name}",
    )

    df_plot = to_num(df, [col_y]).dropna(subset=[col_y])

    # Si hay período: tabla pivote geo × período → heat o líneas
    if period_col and period_col in df_plot.columns and geo_col in df_plot.columns:
        pivot = (
            df_plot.groupby([geo_col, period_col])[col_y]
            .sum()
            .reset_index()
        )
        c1, c2 = st.columns([2, 1])
        with c1:
            # Barras agrupadas o líneas por área geográfica
            top_geos = (
                pivot.groupby(geo_col)[col_y].sum()
                .nlargest(10).index.tolist()
            )
            df_top = pivot[pivot[geo_col].isin(top_geos)]
            fig = px.line(
                df_top, x=period_col, y=col_y, color=geo_col,
                title=f"{col_y} — Top {len(top_geos)} {level}es",
                color_discrete_sequence=PALETTE,
                markers=True,
                template="plotly_white",
            )
            fig.update_layout(**_CHART_CFG,
                              legend=dict(orientation="h", y=-0.3))
            st.plotly_chart(fig, use_container_width=True)

        with c2:
            # Ranking total
            rank = pivot.groupby(geo_col)[col_y].sum().reset_index()
            rank = rank.sort_values(col_y, ascending=False).head(15)
            fig2 = bar_chart(rank, col_y, geo_col,
                             f"Ranking {level} — {col_y}",
                             orientation="h")
            fig2.update_layout(yaxis=dict(categoryorder="total ascending"))
            st.plotly_chart(fig2, use_container_width=True)

    else:
        # Sin período: ranking puro
        rank = (
            df_plot.groupby(geo_col)[col_y].sum()
            .reset_index()
            .sort_values(col_y, ascending=False)
            .head(20)
        )
        c1, c2 = st.columns([3, 2])
        with c1:
            fig = bar_chart(
                rank.sort_values(col_y), col_y, geo_col,
                f"Ranking {level} — {col_y}", orientation="h",
            )
            fig.update_layout(yaxis=dict(categoryorder="total ascending"))
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            fig2 = pie_chart(rank.head(10), geo_col, col_y,
                             f"Top 10 {level}es")
            st.plotly_chart(fig2, use_container_width=True)

    with st.expander("🔎 Ver datos brutos"):
        st.dataframe(df, use_container_width=True)


# ─── Vista: Plana (flat) ─────────────────────────────────────────────────────

def render_flat_view(df: pd.DataFrame, sheet_name: str):
    """
    Explorador interactivo para hojas con estructura plana.
    """
    st.markdown(f'<div class="section-title">📋 Datos — {sheet_name}</div>',
                unsafe_allow_html=True)

    cols_num = numeric_cols(df)
    cols_txt = text_cols(df)

    # KPIs rápidos
    if cols_num:
        kpi_cols = st.columns(min(4, len(cols_num)))
        for i, col in enumerate(cols_num[:4]):
            with kpi_cols[i]:
                total = pd.to_numeric(df[col], errors="coerce").sum()
                st.markdown(kpi_card(col[:30].replace("_"," "), fmt_big(total)),
                            unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Controles de visualización
    c1, c2, c3, c4 = st.columns([2, 2, 2, 1])
    with c1:
        chart_type = st.selectbox("Gráfico", ["Barras", "Líneas", "Pastel", "Agrupado"],
                                  key=f"chart_{sheet_name}")
    with c2:
        x_col = st.selectbox("Eje X / Categoría",
                             [c for c in df.columns if c not in cols_num][:10] or df.columns.tolist(),
                             key=f"x_{sheet_name}")
    with c3:
        if chart_type == "Agrupado":
            y_cols = st.multiselect("Métricas (Y)", cols_num[:8],
                                    default=cols_num[:2],
                                    key=f"ym_{sheet_name}")
        else:
            y_col = st.selectbox("Métrica (Y)", cols_num[:10] or df.columns.tolist(),
                                 key=f"y_{sheet_name}")
    with c4:
        top_n = st.number_input("Top N", 5, 100, 20, key=f"n_{sheet_name}")

    df_plot = to_num(df, cols_num).copy()
    if x_col in df_plot.columns:
        agg_col = y_col if chart_type != "Agrupado" else y_cols[0] if y_cols else cols_num[0]
        df_agg = (df_plot.groupby(x_col)[agg_col].sum()
                  .reset_index().nlargest(int(top_n), agg_col))

        if chart_type == "Barras":
            fig = bar_chart(df_agg.sort_values(agg_col), agg_col, x_col,
                            f"{agg_col} por {x_col}", orientation="h")
            fig.update_layout(yaxis=dict(categoryorder="total ascending"))

        elif chart_type == "Líneas":
            df_line = df_plot.groupby(x_col)[agg_col].sum().reset_index()
            fig = line_chart(df_line, x_col, [agg_col], f"{agg_col} por {x_col}")

        elif chart_type == "Pastel":
            fig = pie_chart(df_agg, x_col, agg_col, f"Distribución de {agg_col}")

        else:  # Agrupado
            if y_cols:
                df_grp = df_plot.groupby(x_col)[y_cols].sum().reset_index()
                df_grp = df_grp.nlargest(int(top_n), y_cols[0])
                fig = grouped_bar(df_grp, x_col, y_cols,
                                  f"Comparativa: {', '.join(y_cols)}")
            else:
                st.warning("Selecciona al menos una métrica.")
                fig = go.Figure()

        st.plotly_chart(fig, use_container_width=True)

    with st.expander("🔎 Ver datos"):
        rows = st.slider("Filas", 10, min(500, len(df)), 50,
                         key=f"rows_{sheet_name}")
        st.dataframe(df.head(rows), use_container_width=True)


# ─── Panel lateral ───────────────────────────────────────────────────────────

def render_sidebar(manifest: pd.DataFrame):
    with st.sidebar:
        st.markdown("""
        <div style="text-align:center;padding:18px 0 8px">
          <div style="font-size:2.8rem">🏦</div>
          <div style="font-size:1.05rem;font-weight:700;margin-top:6px">
            Inclusión Financiera
          </div>
          <div style="font-size:.78rem;opacity:.8">
            BCE Ecuador · III Trim 2025
          </div>
        </div>
        <hr style="border-color:rgba(255,255,255,.25);margin:10px 0">
        """, unsafe_allow_html=True)

        archivos = sorted(manifest["archivo"].unique())
        sel_archivo = st.selectbox("📂 Archivo Excel", archivos)

        hojas = (manifest[manifest["archivo"] == sel_archivo]["hoja"]
                 .unique().tolist())
        sel_hoja = st.selectbox("📄 Hoja", hojas)

        # Obtener todas las tablas de esa hoja
        mask = (manifest["archivo"] == sel_archivo) & (manifest["hoja"] == sel_hoja)
        rows_mask = manifest[mask]

        estructuras = rows_mask["estructura"].tolist()
        tablas = rows_mask["tabla"].tolist()

        st.markdown("""
        <hr style="border-color:rgba(255,255,255,.25)">
        <div style="font-size:.72rem;opacity:.7;padding:6px 0">
          <b>Fuente:</b> BCE Ecuador<br>
          <b>Período:</b> III Trim 2025<br>
          <b>Tablas disponibles:</b><br>
        """, unsafe_allow_html=True)
        for e, t in zip(estructuras, tablas):
            st.markdown(
                f"<div style='font-size:.68rem;opacity:.65'>· {e}</div>",
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)

    return sel_archivo, sel_hoja, rows_mask


# ─── Vista principal de una hoja ─────────────────────────────────────────────

def render_sheet_view(rows_mask: pd.DataFrame):
    """Decide cómo renderizar según las estructuras disponibles de la hoja."""
    estructuras = rows_mask["estructura"].tolist()
    tablas = rows_mask["tabla"].tolist()
    hoja = rows_mask["hoja"].iloc[0]

    # Separar por tipo
    ts_nacional   = [(e, t) for e, t in zip(estructuras, tablas) if "timeseries_nacional" in e]
    ts_provincial = [(e, t) for e, t in zip(estructuras, tablas) if "timeseries_provincial" in e]
    ts_cantonal   = [(e, t) for e, t in zip(estructuras, tablas) if "timeseries_cantonal" in e]
    flat_tabs     = [(e, t) for e, t in zip(estructuras, tablas) if e == "flat"]
    other_tabs    = [(e, t) for e, t in zip(estructuras, tablas)
                     if e not in ("flat",) and "timeseries" not in e]

    # Construir tabs dinámicas
    tab_labels = []
    tab_content = []  # (type, df or list)

    if ts_nacional:
        tab_labels.append("📈 Nacional (Serie)")
        df_nac = load_table(ts_nacional[0][1])
        tab_content.append(("ts_nacional", df_nac))

    if ts_provincial:
        tab_labels.append("🗺️ Provincial")
        df_prov = load_table(ts_provincial[0][1])
        tab_content.append(("ts_provincial", df_prov))

    if ts_cantonal:
        tab_labels.append("📍 Cantonal")
        df_cant = load_table(ts_cantonal[0][1])
        tab_content.append(("ts_cantonal", df_cant))

    for e, t in flat_tabs + other_tabs:
        tab_labels.append(f"📋 {e.replace('_',' ').title()}")
        tab_content.append(("flat", load_table(t)))

    if not tab_labels:
        st.warning("No hay datos disponibles para esta hoja.")
        return

    if len(tab_labels) == 1:
        _render_tab(tab_labels[0], tab_content[0], hoja)
    else:
        tabs = st.tabs(tab_labels)
        for tab, label, content in zip(tabs, tab_labels, tab_content):
            with tab:
                _render_tab(label, content, hoja)


def _render_tab(label: str, content: tuple, hoja: str):
    kind, df = content
    if "ts_nacional" in kind:
        render_timeseries_view(df, hoja)
    elif "ts_provincial" in kind:
        render_geo_view(df, "provincial", hoja)
    elif "ts_cantonal" in kind:
        render_geo_view(df, "cantonal", hoja)
    else:
        render_flat_view(df, hoja)


# ─── Resumen general ─────────────────────────────────────────────────────────

def render_overview(manifest: pd.DataFrame):
    st.markdown('<div class="section-title">📊 Resumen del Conjunto de Datos</div>',
                unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(kpi_card("Registros Totales",
                             f"{manifest['filas'].sum():,}", color=C["blue"]),
                    unsafe_allow_html=True)
    with c2:
        st.markdown(kpi_card("Tablas Generadas",
                             str(len(manifest)), color=C["orange"]),
                    unsafe_allow_html=True)
    with c3:
        st.markdown(kpi_card("Archivos Excel",
                             str(manifest["archivo"].nunique()), color=C["green"]),
                    unsafe_allow_html=True)
    with c4:
        n_ts = manifest[manifest["estructura"].str.startswith("timeseries")]["hoja"].nunique()
        st.markdown(kpi_card("Hojas con Serie Tiempo", str(n_ts), color=C["yellow"]),
                    unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)

    with col1:
        # Barras por hoja
        df_plot = (manifest.groupby("hoja")["filas"].sum()
                   .reset_index().sort_values("filas", ascending=True))
        fig = px.bar(
            df_plot, x="filas", y="hoja", orientation="h",
            title="Registros por Hoja",
            color="filas",
            color_continuous_scale=[[0, "#9EC8FF"], [1, C["primary"]]],
            template="plotly_white",
        )
        fig.update_layout(coloraxis_showscale=False, **_CHART_CFG,
                          yaxis_title="", xaxis_title="Registros")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        # Pie por tipo de estructura
        struct_counts = (manifest.groupby("estructura")["filas"].sum()
                         .reset_index())
        fig2 = pie_chart(struct_counts, "estructura", "filas",
                         "Distribución por Tipo de Estructura")
        st.plotly_chart(fig2, use_container_width=True)

    # Catálogo
    st.markdown('<div class="section-title">📁 Catálogo de Tablas</div>',
                unsafe_allow_html=True)
    st.dataframe(
        manifest[["archivo","hoja","estructura","filas","columnas"]],
        use_container_width=True, height=320,
    )


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    apply_css()

    # Header
    st.markdown("""
    <div class="header-band">
      <div style="display:flex;align-items:center;gap:18px">
        <div style="font-size:2.8rem">🏦</div>
        <div>
          <div style="font-size:1.55rem;font-weight:800">
            Dashboard de Inclusión Financiera
          </div>
          <div style="opacity:.85;font-size:.93rem">
            Banco Central del Ecuador · III Trimestre 2025
          </div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Construir / verificar DB
    if not DB_PATH.exists():
        with st.spinner("⏳ Descargando y procesando datos del BCE... (puede tardar ~1 min)"):
            ok = build_database()
        if not ok:
            st.stop()
        st.rerun()

    # Cargar manifiesto
    try:
        manifest = load_manifest()
    except Exception as e:
        st.error(f"Error al leer la base de datos: {e}")
        st.stop()

    if manifest.empty:
        st.warning("La base de datos no tiene tablas.")
        st.stop()

    # Sidebar
    sel_archivo, sel_hoja, rows_mask = render_sidebar(manifest)

    # Tabs de navegación principal
    tab_resumen, tab_hoja = st.tabs(["🏠 Resumen General", f"📄 {sel_hoja}"])

    with tab_resumen:
        render_overview(manifest)

    with tab_hoja:
        if rows_mask.empty:
            st.info("Selecciona un archivo y hoja en el panel lateral.")
        else:
            render_sheet_view(rows_mask)

    # Footer
    st.markdown(f"""
    <div style="text-align:center;color:{C['gray']};font-size:.78rem;
                padding:24px 0 8px;border-top:1px solid #E4EAF3;margin-top:32px">
      Datos: <a href="https://www.bce.fin.ec" target="_blank"
               style="color:{C['blue']}">Banco Central del Ecuador</a> ·
      Procesado con Python · Streamlit · Plotly
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
