"""
inclusion_financiera_app.py
============================
Dashboard de Inclusión Financiera — BCE Ecuador (III Trimestre 2025)
Inspirado en: https://app.powerbi.com/view?r=eyJrIjoiMWUxZTg5...

Ejecutar localmente:
    streamlit run inclusion_financiera_app.py

En Streamlit Cloud: el archivo descarga y procesa datos automáticamente.
"""

import os
import re
import sqlite3
import zipfile
import logging
from pathlib import Path

import requests
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ─── Configuración general ───────────────────────────────────────────────────
st.set_page_config(
    page_title="Inclusión Financiera — BCE Ecuador",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
)

ZIP_URL  = "https://contenido.bce.fin.ec/home1/economia/tasas/III2025.zip"
DATA_DIR = Path("downloads")
DB_PATH  = Path("database/inclusion_financiera.db")

# Paleta de colores BCE-Ecuador
COLORS = {
    "primary":   "#003366",   # azul BCE
    "secondary": "#0066CC",
    "accent":    "#FF6600",
    "green":     "#28A745",
    "red":       "#DC3545",
    "yellow":    "#FFC107",
    "bg":        "#F5F7FA",
}

COLOR_SEQ = [
    "#003366", "#0066CC", "#FF6600", "#28A745",
    "#FFC107", "#17A2B8", "#6F42C1", "#DC3545",
]

logging.basicConfig(level=logging.WARNING)


# ─── Descarga y procesamiento ─────────────────────────────────────────────────

def _sanitize_name(name: str) -> str:
    name = str(name).strip()
    name = re.sub(r"[\s\-/\\()]+", "_", name)
    name = re.sub(r"[^\w]", "", name)
    name = re.sub(r"_+", "_", name).strip("_")
    return name.lower() or "col"


def find_header_row(df_raw: pd.DataFrame, min_non_null: int = 3) -> int:
    for i, row in df_raw.iterrows():
        if row.notna().sum() >= min_non_null:
            return i
    return 0


def read_sheet_smart(excel_path: Path, sheet_name: str) -> pd.DataFrame | None:
    try:
        df_raw = pd.read_excel(excel_path, sheet_name=sheet_name,
                               header=None, dtype=str, nrows=60)
    except Exception:
        return None

    header_row = find_header_row(df_raw)

    try:
        df = pd.read_excel(excel_path, sheet_name=sheet_name,
                           header=header_row, dtype=str)
    except Exception:
        return None

    df = df.dropna(how="all").dropna(axis=1, how="all")
    if df.empty or len(df.columns) < 2:
        return None

    new_cols, seen = [], {}
    for col in df.columns:
        base = _sanitize_name(str(col))
        if not base or base.startswith("unnamed"):
            base = "col"
        if base in seen:
            seen[base] += 1
            base = f"{base}_{seen[base]}"
        else:
            seen[base] = 0
        new_cols.append(base)
    df.columns = new_cols

    threshold = max(1, len(df.columns) // 2)
    df = df.dropna(thresh=threshold)
    return df if len(df) >= 2 else None


def table_name_from(excel_file: str, sheet: str) -> str:
    return _sanitize_name(f"{Path(excel_file).stem}__{sheet}")[:64]


@st.cache_resource(show_spinner=False)
def build_database() -> bool:
    """Descarga ZIP, extrae Excels y construye SQLite. Retorna True si OK."""
    if DB_PATH.exists():
        return True

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    zip_local = DATA_DIR / "III2025.zip"

    # Descarga
    if not zip_local.exists():
        try:
            headers = {"User-Agent": "Mozilla/5.0 (compatible; BCE-Dashboard/1.0)"}
            resp = requests.get(ZIP_URL, headers=headers, timeout=180)
            resp.raise_for_status()
            zip_local.write_bytes(resp.content)
        except Exception as e:
            st.error(f"⚠️ No se pudo descargar el archivo: {e}")
            return False

    # Extracción
    with zipfile.ZipFile(zip_local) as zf:
        zf.extractall(DATA_DIR)

    excel_files = list(DATA_DIR.rglob("*.xlsx")) + list(DATA_DIR.rglob("*.xls"))
    if not excel_files:
        st.error("No se encontraron archivos Excel en el ZIP.")
        return False

    manifest = []
    with sqlite3.connect(DB_PATH) as conn:
        for ef in excel_files:
            try:
                xl = pd.ExcelFile(ef, engine="openpyxl" if ef.suffix == ".xlsx" else "xlrd")
            except Exception:
                continue
            for sheet in xl.sheet_names:
                df = read_sheet_smart(ef, sheet)
                if df is None:
                    continue
                tname = table_name_from(ef.name, sheet)
                df.to_sql(tname, conn, if_exists="replace", index=False)
                manifest.append({
                    "archivo": ef.name,
                    "hoja": sheet,
                    "tabla": tname,
                    "filas": len(df),
                    "columnas": len(df.columns),
                })
        if manifest:
            pd.DataFrame(manifest).to_sql("_manifest", conn, if_exists="replace", index=False)

    return True


@st.cache_data(ttl=3600)
def load_manifest() -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql("SELECT * FROM _manifest ORDER BY archivo, hoja", conn)


@st.cache_data(ttl=3600)
def load_table(table: str) -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql(f'SELECT * FROM "{table}"', conn)


def get_numeric_columns(df: pd.DataFrame) -> list[str]:
    """Devuelve columnas que pueden convertirse a numérico."""
    numeric = []
    for col in df.columns:
        try:
            pd.to_numeric(df[col].dropna(), errors="raise")
            numeric.append(col)
        except Exception:
            pass
    return numeric


def coerce_numeric(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    df = df.copy()
    for col in cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


# ─── Estilos CSS personalizados ───────────────────────────────────────────────

def apply_styles():
    st.markdown(
        f"""
        <style>
        /* Fondo general */
        .stApp {{
            background-color: {COLORS['bg']};
        }}
        /* Sidebar */
        [data-testid="stSidebar"] {{
            background: linear-gradient(180deg, {COLORS['primary']} 0%, {COLORS['secondary']} 100%);
        }}
        [data-testid="stSidebar"] * {{
            color: white !important;
        }}
        [data-testid="stSidebar"] .stSelectbox label,
        [data-testid="stSidebar"] .stMultiSelect label {{
            color: #CCE0FF !important;
            font-weight: 600;
        }}
        /* Métricas */
        [data-testid="stMetric"] {{
            background: white;
            border-radius: 12px;
            padding: 16px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            border-left: 4px solid {COLORS['secondary']};
        }}
        [data-testid="stMetricLabel"] {{
            color: {COLORS['primary']} !important;
            font-weight: 600;
        }}
        [data-testid="stMetricValue"] {{
            color: {COLORS['primary']} !important;
            font-size: 1.8rem !important;
        }}
        /* Título principal */
        .dashboard-title {{
            background: linear-gradient(90deg, {COLORS['primary']}, {COLORS['secondary']});
            color: white;
            padding: 20px 30px;
            border-radius: 12px;
            margin-bottom: 24px;
        }}
        /* Tarjetas de sección */
        .section-card {{
            background: white;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            margin-bottom: 20px;
        }}
        /* Divider */
        hr {{
            border: none;
            border-top: 2px solid #E9ECEF;
            margin: 20px 0;
        }}
        /* Tab activo */
        [data-baseweb="tab"][aria-selected="true"] {{
            border-bottom: 3px solid {COLORS['accent']} !important;
            color: {COLORS['primary']} !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# ─── Componentes de visualización ─────────────────────────────────────────────

def metric_card(label: str, value: str, delta: str = "", color: str = "secondary"):
    col_color = COLORS.get(color, COLORS["secondary"])
    st.markdown(
        f"""
        <div style="background:white; border-radius:12px; padding:16px 20px;
                    box-shadow:0 2px 8px rgba(0,0,0,0.08);
                    border-left:4px solid {col_color}; margin-bottom:8px;">
          <div style="color:#6B7280; font-size:0.85rem; font-weight:600;
                      text-transform:uppercase; letter-spacing:0.05em;">{label}</div>
          <div style="color:{COLORS['primary']}; font-size:1.7rem;
                      font-weight:700; margin:4px 0;">{value}</div>
          <div style="color:{'#28A745' if '+' in str(delta) else '#DC3545'};
                      font-size:0.8rem;">{delta}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_bar_chart(df: pd.DataFrame, x: str, y: str, title: str,
                     color_col: str = None, orientation: str = "v") -> go.Figure:
    fig = px.bar(
        df, x=x, y=y, title=title,
        color=color_col or y,
        color_continuous_scale=[[0, COLORS["secondary"]], [1, COLORS["accent"]]],
        orientation=orientation,
        template="plotly_white",
    )
    fig.update_layout(
        title_font_color=COLORS["primary"],
        title_font_size=15,
        plot_bgcolor="white",
        paper_bgcolor="white",
        coloraxis_showscale=False,
        margin=dict(l=10, r=10, t=40, b=10),
    )
    fig.update_traces(marker_line_width=0)
    return fig


def render_line_chart(df: pd.DataFrame, x: str, y_cols: list[str],
                      title: str) -> go.Figure:
    fig = go.Figure()
    for i, col in enumerate(y_cols):
        fig.add_trace(go.Scatter(
            x=df[x], y=df[col], mode="lines+markers",
            name=col, line=dict(color=COLOR_SEQ[i % len(COLOR_SEQ)], width=2.5),
            marker=dict(size=6),
        ))
    fig.update_layout(
        title=title, title_font_color=COLORS["primary"], title_font_size=15,
        plot_bgcolor="white", paper_bgcolor="white",
        xaxis=dict(gridcolor="#E9ECEF"),
        yaxis=dict(gridcolor="#E9ECEF"),
        legend=dict(orientation="h", y=-0.2),
        margin=dict(l=10, r=10, t=40, b=10),
        template="plotly_white",
    )
    return fig


def render_pie_chart(df: pd.DataFrame, names: str, values: str, title: str) -> go.Figure:
    fig = px.pie(
        df, names=names, values=values, title=title,
        color_discrete_sequence=COLOR_SEQ,
        hole=0.4,
    )
    fig.update_layout(
        title_font_color=COLORS["primary"], title_font_size=15,
        margin=dict(l=10, r=10, t=40, b=10),
        paper_bgcolor="white",
        legend=dict(orientation="h", y=-0.15),
    )
    return fig


# ─── Vista de tabla genérica ──────────────────────────────────────────────────

def render_table_explorer(df: pd.DataFrame, table_name: str):
    """Explorador interactivo de cualquier tabla del DB."""
    st.subheader(f"📋 {table_name}")

    num_cols = get_numeric_columns(df)
    cat_cols = [c for c in df.columns if c not in num_cols]

    col1, col2 = st.columns([3, 1])
    with col2:
        show_rows = st.slider("Filas a mostrar", 10, min(500, len(df)), 50, key=f"rows_{table_name}")

    with col1:
        if cat_cols:
            filter_col = st.selectbox("Filtrar por columna", ["— Ninguno —"] + cat_cols,
                                       key=f"filter_{table_name}")
            if filter_col != "— Ninguno —":
                vals = df[filter_col].dropna().unique().tolist()
                selected = st.multiselect("Valores", vals, default=vals[:5],
                                          key=f"vals_{table_name}")
                df = df[df[filter_col].isin(selected)]

    st.dataframe(df.head(show_rows), use_container_width=True)

    # Visualización automática
    if num_cols and cat_cols:
        st.markdown("---")
        st.markdown("**Visualización rápida**")
        vcol1, vcol2, vcol3 = st.columns(3)
        with vcol1:
            x_col = st.selectbox("Eje X (categoría)", cat_cols[:10],
                                  key=f"x_{table_name}")
        with vcol2:
            y_col = st.selectbox("Eje Y (valor)", num_cols[:10],
                                  key=f"y_{table_name}")
        with vcol3:
            chart_type = st.selectbox("Tipo", ["Barras", "Líneas", "Pastel"],
                                       key=f"chart_{table_name}")

        df_num = coerce_numeric(df, [y_col]).dropna(subset=[y_col])

        if chart_type == "Barras":
            agg = df_num.groupby(x_col)[y_col].sum().reset_index()
            agg = agg.nlargest(20, y_col)
            fig = render_bar_chart(agg, x_col, y_col,
                                   f"{y_col} por {x_col}",
                                   orientation="h" if len(agg) > 8 else "v")
            if len(agg) > 8:
                fig.update_layout(yaxis=dict(categoryorder="total ascending"))
            st.plotly_chart(fig, use_container_width=True)

        elif chart_type == "Líneas":
            agg = df_num.groupby(x_col)[y_col].sum().reset_index()
            fig = render_line_chart(agg, x_col, [y_col],
                                    f"{y_col} por {x_col}")
            st.plotly_chart(fig, use_container_width=True)

        else:
            agg = df_num.groupby(x_col)[y_col].sum().reset_index()
            agg = agg.nlargest(10, y_col)
            fig = render_pie_chart(agg, x_col, y_col,
                                   f"Distribución: {y_col}")
            st.plotly_chart(fig, use_container_width=True)


# ─── Resumen ejecutivo (cuando no hay categorías claras) ──────────────────────

def render_summary_dashboard(manifest: pd.DataFrame):
    """Dashboard de resumen con estadísticas de todas las tablas."""
    st.markdown(
        """
        <div style="background:white; border-radius:12px; padding:24px;
                    box-shadow:0 2px 8px rgba(0,0,0,0.06); margin-bottom:20px;">
          <h3 style="color:#003366; margin:0 0 8px 0;">
            📊 Resumen General — Base de Datos Inclusión Financiera BCE
          </h3>
          <p style="color:#6B7280; margin:0;">
            III Trimestre 2025 · Banco Central del Ecuador
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # KPIs generales
    total_filas = manifest["filas"].sum()
    total_tablas = len(manifest)
    archivos = manifest["archivo"].nunique()

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        metric_card("Total de Registros", f"{total_filas:,}", color="secondary")
    with c2:
        metric_card("Tablas Generadas", str(total_tablas), color="primary")
    with c3:
        metric_card("Archivos Excel", str(archivos), color="accent")
    with c4:
        metric_card("Fuente", "BCE Ecuador", color="green")

    st.markdown("<br>", unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        # Tabla de contenido
        fig = px.bar(
            manifest.sort_values("filas", ascending=True),
            x="filas", y="hoja",
            orientation="h",
            title="Registros por Hoja/Tabla",
            color="filas",
            color_continuous_scale=[[0, "#CCE0FF"], [1, "#003366"]],
            template="plotly_white",
        )
        fig.update_layout(
            coloraxis_showscale=False,
            yaxis_title="",
            xaxis_title="Número de registros",
            title_font_color=COLORS["primary"],
            plot_bgcolor="white",
            paper_bgcolor="white",
            margin=dict(l=10, r=10, t=40, b=10),
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        # Distribución por archivo
        arch_agg = manifest.groupby("archivo")["filas"].sum().reset_index()
        fig2 = render_pie_chart(arch_agg, "archivo", "filas",
                                "Distribución de registros por archivo")
        st.plotly_chart(fig2, use_container_width=True)

    # Catálogo completo
    st.markdown("### 📁 Catálogo de Tablas Disponibles")
    st.dataframe(
        manifest[["archivo", "hoja", "tabla", "filas", "columnas"]],
        use_container_width=True,
        height=300,
    )


# ─── Sidebar ──────────────────────────────────────────────────────────────────

def render_sidebar(manifest: pd.DataFrame) -> tuple[str, str]:
    with st.sidebar:
        st.markdown(
            """
            <div style="text-align:center; padding:20px 0 10px;">
              <div style="font-size:2.5rem;">🏦</div>
              <div style="font-size:1.1rem; font-weight:700; margin-top:8px;">
                Inclusión Financiera
              </div>
              <div style="font-size:0.8rem; opacity:0.8;">
                BCE Ecuador · III Trim 2025
              </div>
            </div>
            <hr style="border-color:rgba(255,255,255,0.2); margin:10px 0;">
            """,
            unsafe_allow_html=True,
        )

        view = st.radio(
            "Vista",
            ["📊 Resumen Ejecutivo", "🔍 Explorador de Datos"],
            label_visibility="collapsed",
        )

        selected_table = None
        if "Explorador" in view:
            st.markdown("**Seleccionar tabla:**")
            archivos = sorted(manifest["archivo"].unique())
            sel_archivo = st.selectbox("Archivo Excel", archivos)
            hojas = manifest[manifest["archivo"] == sel_archivo]["hoja"].tolist()
            sel_hoja = st.selectbox("Hoja", hojas)
            selected_table = manifest[
                (manifest["archivo"] == sel_archivo) &
                (manifest["hoja"] == sel_hoja)
            ]["tabla"].values[0]

        st.markdown(
            """
            <hr style="border-color:rgba(255,255,255,0.2);">
            <div style="font-size:0.75rem; opacity:0.7; padding:10px 0;">
              <b>Fuente:</b> Banco Central del Ecuador<br>
              <b>Período:</b> III Trimestre 2025<br>
              <b>Actualización:</b> Automática al iniciar
            </div>
            """,
            unsafe_allow_html=True,
        )

    return view, selected_table


# ─── Pantalla de carga inicial ────────────────────────────────────────────────

def show_loading_screen():
    st.markdown(
        f"""
        <div style="display:flex; flex-direction:column; align-items:center;
                    justify-content:center; min-height:60vh; text-align:center;">
          <div style="font-size:4rem; margin-bottom:20px;">🏦</div>
          <h2 style="color:{COLORS['primary']};">Preparando Dashboard...</h2>
          <p style="color:#6B7280; max-width:500px;">
            Descargando y procesando datos de Inclusión Financiera del
            <b>Banco Central del Ecuador</b>. Esto tomará unos momentos.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    apply_styles()

    # Header
    st.markdown(
        f"""
        <div class="dashboard-title">
          <div style="display:flex; align-items:center; gap:16px;">
            <div style="font-size:2.5rem;">🏦</div>
            <div>
              <div style="font-size:1.6rem; font-weight:700;">
                Dashboard de Inclusión Financiera
              </div>
              <div style="opacity:0.85; font-size:0.95rem;">
                Banco Central del Ecuador · III Trimestre 2025
              </div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Verificar / construir DB
    if not DB_PATH.exists():
        show_loading_screen()
        with st.spinner("Descargando y procesando datos del BCE..."):
            ok = build_database()
        if not ok:
            st.error(
                "⚠️ No se pudo obtener la base de datos. "
                "Ejecuta `python download_and_build_db.py` localmente y "
                "sube el archivo `database/inclusion_financiera.db` al repositorio."
            )
            st.stop()
        st.rerun()

    # Cargar manifiesto
    try:
        manifest = load_manifest()
    except Exception as e:
        st.error(f"Error al leer la base de datos: {e}")
        st.stop()

    if manifest.empty:
        st.warning("La base de datos no contiene tablas. Verifica el archivo ZIP.")
        st.stop()

    # Sidebar y navegación
    view, selected_table = render_sidebar(manifest)

    # Contenido principal
    if "Resumen" in view:
        render_summary_dashboard(manifest)

        # Análisis automático de cada tabla
        st.markdown("---")
        st.markdown("### 📈 Análisis por Tabla")

        tabs = st.tabs([f"📋 {row['hoja']}" for _, row in manifest.iterrows()])
        for tab, (_, row) in zip(tabs, manifest.iterrows()):
            with tab:
                df = load_table(row["tabla"])
                num_cols = get_numeric_columns(df)
                cat_cols = [c for c in df.columns if c not in num_cols]

                # Estadísticas rápidas
                sc1, sc2, sc3 = st.columns(3)
                with sc1:
                    st.metric("Registros", f"{len(df):,}")
                with sc2:
                    st.metric("Columnas numéricas", len(num_cols))
                with sc3:
                    st.metric("Columnas texto", len(cat_cols))

                if num_cols and cat_cols:
                    # Gráfico automático: top categoría × primera métrica
                    cat = cat_cols[0]
                    num = num_cols[0]
                    df_plot = coerce_numeric(df, [num]).dropna(subset=[num])
                    agg = df_plot.groupby(cat)[num].sum().reset_index()
                    agg = agg.nlargest(15, num).sort_values(num, ascending=True)

                    fig = px.bar(
                        agg, x=num, y=cat, orientation="h",
                        title=f"{num} por {cat}",
                        color=num,
                        color_continuous_scale=[[0, "#CCE0FF"], [1, "#003366"]],
                        template="plotly_white",
                    )
                    fig.update_layout(
                        coloraxis_showscale=False,
                        yaxis_title="", xaxis_title=num,
                        title_font_color=COLORS["primary"],
                        plot_bgcolor="white", paper_bgcolor="white",
                        margin=dict(l=10, r=10, t=40, b=10),
                    )
                    st.plotly_chart(fig, use_container_width=True)

                # Muestra primeras filas
                with st.expander("Ver datos"):
                    st.dataframe(df.head(50), use_container_width=True)

    else:
        # Explorador detallado
        if selected_table:
            df = load_table(selected_table)
            render_table_explorer(df, selected_table)
        else:
            st.info("Selecciona una tabla en el panel lateral.")

    # Footer
    st.markdown(
        f"""
        <hr>
        <div style="text-align:center; color:#9CA3AF; font-size:0.8rem; padding:10px;">
          Datos: <a href="https://www.bce.fin.ec" target="_blank"
                    style="color:{COLORS['secondary']};">Banco Central del Ecuador</a> ·
          Elaborado con <b>Python + Streamlit + Plotly</b> ·
          III Trimestre 2025
        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
