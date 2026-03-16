"""
areas_intervencion_app.py
==========================
Dashboard ENIF — Áreas de Intervención en Inclusión Financiera
Banco Central del Ecuador
Fuente: D:/crdavila/Inclusión Financiera/Areas intervencion.xlsx

Ejecutar:
    streamlit run areas_intervencion_app.py
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import openpyxl
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ─── Config ──────────────────────────────────────────────────────────────────

EXCEL_PATH = Path(__file__).parent / "data" / "areas_intervencion.xlsx"

st.set_page_config(
    page_title="BCE · ENIF — Áreas de Intervención",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Paleta institucional BCE
C = {
    "navy":  "#002855",
    "blue":  "#004C97",
    "gold":  "#C8A84B",
    "green": "#1B5E20",
    "red":   "#8B0000",
    "gray":  "#546E7A",
    "lgray": "#ECEFF1",
    "text":  "#1A1A2E",
    "white": "#FFFFFF",
    "bg":    "#F3F5F8",
}

PALETTE = [
    "#004C97", "#C8A84B", "#1B5E20", "#8B0000", "#546E7A",
    "#0277BD", "#E65100", "#4A148C", "#00695C", "#827717",
]

AREA_COLORS = [C["blue"], "#1B5E20", "#E65100", C["navy"]]
AREA_LABELS = [
    "Área 1 — Puntos de Atención",
    "Área 2 — Oferta de Servicios Financieros",
    "Área 3 — Financiamiento y Crédito",
    "Área 4 — Protección al Consumidor",
]

_CHART_CFG = dict(
    plot_bgcolor="white",
    paper_bgcolor="white",
    margin=dict(l=10, r=10, t=48, b=10),
    font=dict(color=C["navy"], size=11, family="Arial, sans-serif"),
    title_font=dict(color=C["navy"], size=13, family="Arial, sans-serif"),
    hoverlabel=dict(bgcolor="white", bordercolor=C["blue"], font_size=11),
)


# ─── CSS Institucional BCE ────────────────────────────────────────────────────

def apply_css():
    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Source+Sans+Pro:wght@400;600;700&display=swap');

    .stApp {{
        background: {C['bg']};
        font-family: 'Source Sans Pro', Arial, sans-serif;
    }}

    /* ── Header institucional ── */
    .bce-header {{
        background: linear-gradient(135deg, {C['navy']} 0%, {C['blue']} 100%);
        color: white;
        border-radius: 4px;
        padding: 22px 32px;
        margin-bottom: 20px;
        border-bottom: 5px solid {C['gold']};
    }}
    .bce-header-title {{
        font-size: 1.45rem;
        font-weight: 700;
        letter-spacing: .02em;
        margin-bottom: 4px;
    }}
    .bce-header-sub {{
        font-size: .85rem;
        opacity: .85;
        letter-spacing: .04em;
    }}
    .bce-logo-text {{
        font-size: .72rem;
        font-weight: 700;
        letter-spacing: .12em;
        text-transform: uppercase;
        opacity: .7;
        margin-bottom: 8px;
    }}

    /* ── Línea dorada separadora ── */
    .gold-divider {{
        height: 2px;
        background: {C['gold']};
        border: none;
        margin: 18px 0 14px 0;
    }}

    /* ── Tarjeta KPI ── */
    .kpi-card {{
        background: {C['white']};
        border-radius: 3px;
        padding: 16px 18px 12px;
        box-shadow: 0 1px 6px rgba(0,40,85,.10);
        border-top: 4px solid {C['blue']};
        min-height: 108px;
    }}
    .kpi-label {{
        font-size: .70rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: .08em;
        color: {C['gray']};
        margin-bottom: 8px;
        line-height: 1.3;
    }}
    .kpi-value {{
        font-size: 1.55rem;
        font-weight: 800;
        color: {C['navy']};
        line-height: 1.1;
    }}
    .kpi-unit {{
        font-size: .80rem;
        font-weight: 600;
        color: {C['gold']};
        margin-left: 5px;
    }}
    .kpi-delta-up   {{ font-size:.76rem; color:{C['green']}; margin-top:5px; }}
    .kpi-delta-down {{ font-size:.76rem; color:{C['red']};   margin-top:5px; }}
    .kpi-delta-neu  {{ font-size:.76rem; color:{C['gray']};  margin-top:5px; }}

    /* ── Sección título ── */
    .section-title {{
        font-size: .92rem;
        font-weight: 700;
        color: {C['navy']};
        text-transform: uppercase;
        letter-spacing: .06em;
        border-left: 4px solid {C['gold']};
        padding-left: 10px;
        margin-bottom: 14px;
    }}

    /* ── Badge de área ── */
    .area-badge {{
        display: inline-block;
        border-radius: 2px;
        padding: 3px 14px;
        font-size: .76rem;
        font-weight: 700;
        color: white;
        letter-spacing: .05em;
        text-transform: uppercase;
        margin-bottom: 14px;
    }}

    /* ── Panel de filtros ── */
    .filter-panel-header {{
        background: white;
        border-radius: 3px 3px 0 0;
        border: 1px solid #D0D9E8;
        border-left: 4px solid {C['gold']};
        padding: 10px 16px 6px;
        margin-bottom: -1px;
    }}
    .filter-panel-title {{
        font-size: .70rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: .09em;
        color: {C['navy']};
    }}
    .filter-range-info {{
        font-size: .78rem;
        color: {C['gray']};
        padding: 6px 0 2px;
    }}

    /* Estilo de inputs de fecha */
    [data-testid="stDateInput"] label {{
        font-size: .70rem !important;
        font-weight: 700 !important;
        text-transform: uppercase !important;
        letter-spacing: .07em !important;
        color: {C['navy']} !important;
    }}

    /* ── Pie de página ── */
    .bce-footer {{
        text-align: center;
        color: {C['gray']};
        font-size: .72rem;
        padding: 18px 0 6px;
        border-top: 2px solid {C['lgray']};
        margin-top: 32px;
        letter-spacing: .03em;
    }}

    /* ── Tabs más formales ── */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 2px;
        background: {C['lgray']};
        padding: 4px;
        border-radius: 3px;
    }}
    .stTabs [data-baseweb="tab"] {{
        font-size: .80rem;
        font-weight: 600;
        letter-spacing: .04em;
        color: {C['navy']};
        padding: 8px 16px;
    }}
    </style>
    """, unsafe_allow_html=True)


# ─── Formatters por tipo de variable ────────────────────────────────────────

def fmt_entero(n) -> tuple[str, str]:
    """Conteo entero, sin abreviatura."""
    try:
        return f"{int(float(n)):,}", ""
    except Exception:
        return "—", ""


def fmt_millones_usd(n) -> tuple[str, str]:
    """Valor ya expresado en millones de USD."""
    try:
        return f"{float(n):,.2f}", "mill. USD"
    except Exception:
        return "—", ""


def fmt_pct_proporcion(n) -> tuple[str, str]:
    """Proporción 0–1 → porcentaje."""
    try:
        return f"{float(n) * 100:.1f}", "%"
    except Exception:
        return "—", ""


def fmt_pct_directa(n) -> tuple[str, str]:
    """Valor ya en puntos porcentuales (e.g. 5.5 → '5.5 %')."""
    try:
        return f"{float(n):.2f}", "%"
    except Exception:
        return "—", ""


def _fmt_for_col3(col: str):
    """Selecciona formatter para Intervención 3 según nombre de columna."""
    c = col.lower()
    if "mora" in c or "(%)" in c or "porcentaje" in c or "tasa" in c:
        return fmt_pct_directa
    return fmt_millones_usd


def _delta_str(val, prev, fmt_fn) -> tuple[str, str]:
    """Retorna (texto_delta, clase_css)."""
    try:
        if prev == 0 or pd.isna(prev) or pd.isna(val):
            return "", "kpi-delta-neu"
        pct = (float(val) - float(prev)) / abs(float(prev)) * 100
        texto = f"{'▲' if pct >= 0 else '▼'} {abs(pct):.1f}% vs período anterior"
        clase = "kpi-delta-up" if pct >= 0 else "kpi-delta-down"
        return texto, clase
    except Exception:
        return "", "kpi-delta-neu"


# ─── Componente KPI ──────────────────────────────────────────────────────────

def kpi_card(label: str, value: str, unit: str = "",
             delta: str = "", delta_cls: str = "kpi-delta-neu",
             color: str = C["blue"]) -> str:
    unit_html = f'<span class="kpi-unit">{unit}</span>' if unit else ""
    delta_html = f'<div class="{delta_cls}">{delta}</div>' if delta else ""
    return f"""
    <div class="kpi-card" style="border-top-color:{color}">
      <div class="kpi-label">{label}</div>
      <div class="kpi-value">{value}{unit_html}</div>
      {delta_html}
    </div>"""


# ─── Gráficos ─────────────────────────────────────────────────────────────────

def line_fig(df: pd.DataFrame, x: str, y_cols: list[str],
             title: str, labels: dict | None = None,
             color: str | None = None) -> go.Figure:
    fig = go.Figure()
    for i, col in enumerate(y_cols):
        lbl = (labels or {}).get(col, col.replace("_", " "))
        clr = color if (color and len(y_cols) == 1) else PALETTE[i % len(PALETTE)]
        y = pd.to_numeric(df[col], errors="coerce")
        fig.add_trace(go.Scatter(
            x=df[x], y=y, mode="lines+markers", name=lbl,
            line=dict(color=clr, width=2.2),
            marker=dict(size=5),
            hovertemplate=f"<b>{lbl}</b><br>%{{x}}: %{{y:,.3f}}<extra></extra>",
        ))
    fig.update_layout(
        title=title,
        xaxis=dict(gridcolor="#E8EDF3", title="", linecolor=C["lgray"]),
        yaxis=dict(gridcolor="#E8EDF3", linecolor=C["lgray"]),
        legend=dict(orientation="h", y=-0.28, x=0, font_size=10),
        **_CHART_CFG,
    )
    return fig


def bar_fig(df: pd.DataFrame, x: str, y_cols: list[str],
            title: str, labels: dict | None = None,
            pct_axis: bool = False) -> go.Figure:
    fig = go.Figure()
    for i, col in enumerate(y_cols):
        lbl = (labels or {}).get(col, col.replace("_", " "))
        y = pd.to_numeric(df[col], errors="coerce")
        if pct_axis:
            y = y * 100  # convertir proporción a %
        fig.add_trace(go.Bar(
            x=df[x], y=y, name=lbl,
            marker_color=PALETTE[i % len(PALETTE)],
            hovertemplate=f"<b>{lbl}</b><br>%{{x}}: %{{y:.1f}}{'%' if pct_axis else ''}<extra></extra>",
        ))
    y_cfg = dict(gridcolor="#E8EDF3", linecolor=C["lgray"])
    if pct_axis:
        y_cfg["ticksuffix"] = "%"
    fig.update_layout(
        title=title, barmode="group",
        xaxis=dict(gridcolor="#E8EDF3", linecolor=C["lgray"]),
        yaxis=y_cfg,
        legend=dict(orientation="h", y=-0.28, x=0, font_size=10),
        **_CHART_CFG,
    )
    return fig


# ─── Carga de datos ───────────────────────────────────────────────────────────

@st.cache_data(ttl=600, show_spinner=False)
def load_intervencion1() -> pd.DataFrame:
    """Puntos de Atención — trimestral, header multinivel (filas 2-4)."""
    wb = openpyxl.load_workbook(EXCEL_PATH, data_only=True, read_only=True)
    ws = wb["Intervención 1"]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    h2_raw = [str(v).strip() if v else "" for v in rows[1]]
    h3_raw = [str(v).strip() if v else "" for v in rows[2]]
    h4_raw = [str(v).strip() if v else "" for v in rows[3]]

    def ffill(lst):
        last, result = "", []
        for v in lst:
            if v and v not in ("None", "nan"):
                last = v
            result.append(last)
        return result

    h2 = ffill(h2_raw)
    h3 = ffill(h3_raw)
    h4 = h4_raw  # sin ffill: evitar arrastre incorrecto entre grupos

    col_names = []
    for i in range(len(h2)):
        parts = []
        for h in (h2, h3, h4):
            v = h[i].strip() if h[i] not in ("None", "nan") else ""
            if v and (not parts or parts[-1] != v):
                parts.append(v)
        col_names.append(" · ".join(parts) if parts else f"col_{i}")

    data = [r for r in rows[4:] if r[0] is not None]
    n_cols = len(data[0]) if data else len(col_names)
    names = col_names[:n_cols]

    seen: dict[str, int] = {}
    unique_names = []
    for name in names:
        if name in seen:
            seen[name] += 1
            unique_names.append(f"{name}_{seen[name]}")
        else:
            seen[name] = 0
            unique_names.append(name)

    df = pd.DataFrame(data, columns=unique_names)
    df.rename(columns={df.columns[0]: "periodo"}, inplace=True)
    df["periodo"] = df["periodo"].astype(str).str.strip()

    def sort_key(p):
        m = re.match(r"(\d{4})\s*-\s*(I{1,3}V?|IV)", str(p))
        if not m:
            return 0
        roman = {"I": 1, "II": 2, "III": 3, "IV": 4}.get(m.group(2), 0)
        return int(m.group(1)) * 10 + roman

    df["_k"] = df["periodo"].apply(sort_key)
    df = df[df["_k"] > 0].sort_values("_k").drop(columns=["_k"]).reset_index(drop=True)
    for c in df.columns[1:]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.dropna(axis=1, how="all")


@st.cache_data(ttl=600, show_spinner=False)
def load_intervencion1_anual() -> pd.DataFrame:
    """SPI/PIB — anual."""
    wb = openpyxl.load_workbook(EXCEL_PATH, data_only=True, read_only=True)
    ws = wb["Intervención 1 - Anual"]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    data = [r for r in rows[2:] if r[0] is not None]
    df = pd.DataFrame(data, columns=["año", "SPI / PIB"])
    df["año"] = df["año"].apply(lambda x: str(int(float(x))) if x is not None else None)
    df["SPI / PIB"] = pd.to_numeric(df["SPI / PIB"], errors="coerce")
    return df.dropna(subset=["año"]).sort_values("año").reset_index(drop=True)


@st.cache_data(ttl=600, show_spinner=False)
def load_intervencion2() -> pd.DataFrame:
    """Oferta de servicios — anual (Global Findex), valores proporción 0-1."""
    wb = openpyxl.load_workbook(EXCEL_PATH, data_only=True, read_only=True)
    ws = wb["Intervención 2"]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    headers = [str(v).strip() if v else f"col_{i}" for i, v in enumerate(rows[1])]
    data = [r for r in rows[2:] if r[0] is not None]
    df = pd.DataFrame(data, columns=headers[:len(data[0])])
    df.rename(columns={df.columns[0]: "año"}, inplace=True)
    df["año"] = df["año"].apply(lambda x: str(int(float(x))) if x is not None else None)
    for c in df.columns[1:]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.dropna(subset=["año"]).sort_values("año").reset_index(drop=True)


@st.cache_data(ttl=600, show_spinner=False)
def load_intervencion3() -> pd.DataFrame:
    """Financiamiento/Crédito — mensual."""
    wb = openpyxl.load_workbook(EXCEL_PATH, data_only=True, read_only=True)
    ws = wb["Intervención 3"]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    headers = [str(v).strip() if v else f"col_{i}" for i, v in enumerate(rows[1])]
    data = [r for r in rows[2:] if r[0] is not None]
    df = pd.DataFrame(data, columns=headers[:len(data[0])])
    df.rename(columns={df.columns[0]: "fecha"}, inplace=True)
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    for c in df.columns[1:]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.dropna(subset=["fecha"]).sort_values("fecha").reset_index(drop=True)


@st.cache_data(ttl=600, show_spinner=False)
def load_intervencion4() -> pd.DataFrame:
    """Protección al consumidor — mensual."""
    wb = openpyxl.load_workbook(EXCEL_PATH, data_only=True, read_only=True)
    ws = wb["Intervención 4"]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    headers = [str(v).strip() if v else f"col_{i}" for i, v in enumerate(rows[1])]
    data = [r for r in rows[2:] if r[0] is not None]
    df = pd.DataFrame(data, columns=headers[:len(data[0])])
    df.rename(columns={df.columns[0]: "fecha"}, inplace=True)
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    for c in df.columns[1:]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.dropna(subset=["fecha"]).sort_values("fecha").reset_index(drop=True)


# ─── Renders por área ─────────────────────────────────────────────────────────

def _label(col: str) -> str:
    """Nombre legible corto: último segmento del nombre de columna."""
    parts = col.split(" · ")
    return parts[-1][:50] if len(parts) > 1 else col[:50]


def render_intervencion1(df: pd.DataFrame, df_anual: pd.DataFrame):
    st.markdown(
        f'<span class="area-badge" style="background:{AREA_COLORS[0]}">'
        f'{AREA_LABELS[0]}</span>',
        unsafe_allow_html=True,
    )
    metricas = [c for c in df.columns if c != "periodo"]
    ultimo = df.iloc[-1]
    penultimo = df.iloc[-2] if len(df) > 1 else None

    # KPIs: conteos enteros sin abreviatura
    cols = st.columns(min(4, len(metricas)))
    for i, col in enumerate(metricas[:4]):
        with cols[i]:
            val, unit = fmt_entero(ultimo[col])
            dt, dt_cls = _delta_str(ultimo[col],
                                    penultimo[col] if penultimo is not None else None,
                                    fmt_entero)
            st.markdown(
                kpi_card(_label(col), val, unit, dt, dt_cls, AREA_COLORS[0]),
                unsafe_allow_html=True,
            )

    st.markdown('<div class="gold-divider"></div>', unsafe_allow_html=True)

    st.markdown('<div class="section-title">Evolución trimestral</div>',
                unsafe_allow_html=True)

    sel = st.multiselect(
        "Métricas a visualizar",
        metricas, default=metricas[:4],
        key="int1_metricas",
        format_func=_label,
    )
    if sel:
        labels = {c: _label(c) for c in sel}
        fig = line_fig(
            df, "periodo", sel,
            f"Puntos de Atención — {df['periodo'].iloc[0]} a {df['periodo'].iloc[-1]}",
            labels=labels,
            color=AREA_COLORS[0] if len(sel) == 1 else None,
        )
        fig.update_yaxes(title_text="Unidades")
        fig.update_xaxes(tickangle=-40)
        st.plotly_chart(fig, use_container_width=True)

    with st.expander("Ver datos tabulares"):
        st.dataframe(df, use_container_width=True)

    # ── SPI / PIB anual ──────────────────────────────────────────────────────
    if not df_anual.empty:
        st.markdown('<div class="gold-divider"></div>', unsafe_allow_html=True)
        st.markdown('<div class="section-title">SPI / PIB — Anual</div>',
                    unsafe_allow_html=True)

        ultimo_val = df_anual["SPI / PIB"].iloc[-1]
        penultimo_val = df_anual["SPI / PIB"].iloc[-2] if len(df_anual) > 1 else None
        val, unit = fmt_pct_directa(ultimo_val)
        dt, dt_cls = _delta_str(ultimo_val, penultimo_val, fmt_pct_directa)

        c1, _ = st.columns([1, 3])
        with c1:
            st.markdown(
                kpi_card(f"SPI / PIB ({df_anual['año'].iloc[-1]})",
                         val, unit, dt, dt_cls, AREA_COLORS[0]),
                unsafe_allow_html=True,
            )

        fig = bar_fig(df_anual, "año", ["SPI / PIB"],
                      "Índice SPI como porcentaje del PIB — 2010 a 2024")
        fig.update_yaxes(title_text="%", ticksuffix="%")
        fig.update_xaxes(tickmode="array", tickvals=df_anual["año"].tolist())
        st.plotly_chart(fig, use_container_width=True)

        with st.expander("Ver datos SPI / PIB"):
            st.dataframe(df_anual, use_container_width=True)


def render_intervencion2(df: pd.DataFrame):
    st.markdown(
        f'<span class="area-badge" style="background:{AREA_COLORS[1]}">'
        f'{AREA_LABELS[1]}</span>',
        unsafe_allow_html=True,
    )
    metricas = [c for c in df.columns if c != "año"]
    ultimo = df.iloc[-1]
    penultimo = df.iloc[-2] if len(df) > 1 else None

    # KPIs: proporciones → porcentaje
    cols = st.columns(min(3, len(metricas)))
    for i, col in enumerate(metricas[:3]):
        with cols[i]:
            val, unit = fmt_pct_proporcion(ultimo[col])
            dt, dt_cls = _delta_str(ultimo[col],
                                    penultimo[col] if penultimo is not None else None,
                                    fmt_pct_proporcion)
            st.markdown(
                kpi_card(col[:45], val, unit, dt, dt_cls, AREA_COLORS[1]),
                unsafe_allow_html=True,
            )

    st.markdown('<div class="gold-divider"></div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-title">Evolución por año de encuesta — Global Findex</div>',
        unsafe_allow_html=True,
    )

    sel = st.multiselect(
        "Indicadores",
        metricas, default=metricas,
        key="int2_metricas",
        format_func=lambda c: c[:60],
    )
    if sel:
        labels = {c: c[:50] for c in sel}
        fig = bar_fig(df, "año", sel,
                      "Indicadores de Acceso Financiero (Global Findex)",
                      labels=labels, pct_axis=True)
        st.plotly_chart(fig, use_container_width=True)

    with st.expander("Ver datos tabulares"):
        disp = df.copy()
        for c in metricas:
            disp[c] = disp[c].apply(
                lambda x: f"{float(x)*100:.1f} %" if pd.notna(x) else "—"
            )
        st.dataframe(disp, use_container_width=True)


def render_intervencion3(df: pd.DataFrame):
    st.markdown(
        f'<span class="area-badge" style="background:{AREA_COLORS[2]}">'
        f'{AREA_LABELS[2]}</span>',
        unsafe_allow_html=True,
    )
    metricas = [c for c in df.columns if c != "fecha"]
    ultimo = df.iloc[-1]
    penultimo = df.iloc[-2] if len(df) > 1 else None

    # KPIs: detecta si es millones USD o porcentaje
    kpi_cols = st.columns(min(len(metricas), 5))
    for i, col in enumerate(metricas):
        with kpi_cols[i]:
            fn = _fmt_for_col3(col)
            val, unit = fn(ultimo[col])
            dt, dt_cls = _delta_str(ultimo[col],
                                    penultimo[col] if penultimo is not None else None,
                                    fn)
            st.markdown(
                kpi_card(col[:45], val, unit, dt, dt_cls, AREA_COLORS[2]),
                unsafe_allow_html=True,
            )

    st.markdown('<div class="gold-divider"></div>', unsafe_allow_html=True)

    # ── BLOQUE DE CONTROLES (primero todos los selectores) ───────────────────
    st.markdown('<div class="section-title">Filtros y selección de series</div>',
                unsafe_allow_html=True)

    # Filtro de período
    min_f, max_f = df["fecha"].min(), df["fecha"].max()
    st.markdown(
        f'<div class="filter-panel-header">'
        f'<span class="filter-panel-title">Período de análisis</span></div>',
        unsafe_allow_html=True,
    )
    fc1, fc2, fc3 = st.columns([2, 2, 3])
    with fc1:
        desde = st.date_input("Fecha inicio", min_f, min_value=min_f, max_value=max_f,
                              key="int3_desde")
    with fc2:
        hasta = st.date_input("Fecha fin", max_f, min_value=min_f, max_value=max_f,
                              key="int3_hasta")
    with fc3:
        n_meses = max(
            0,
            (pd.Timestamp(hasta).year - pd.Timestamp(desde).year) * 12
            + (pd.Timestamp(hasta).month - pd.Timestamp(desde).month) + 1,
        )
        st.markdown(
            f'<div class="filter-range-info" style="padding-top:28px">'
            f'Rango seleccionado: <strong>{n_meses} meses</strong> '
            f'({desde.strftime("%b %Y")} — {hasta.strftime("%b %Y")})</div>',
            unsafe_allow_html=True,
        )

    df_f = df[
        (df["fecha"] >= pd.Timestamp(desde)) & (df["fecha"] <= pd.Timestamp(hasta))
    ]

    # Selectores de series — separados por tipo de eje
    cols_mill = [c for c in metricas if _fmt_for_col3(c) is fmt_millones_usd]
    cols_pct  = [c for c in metricas if _fmt_for_col3(c) is fmt_pct_directa]

    sc1, sc2 = st.columns(2)
    with sc1:
        sel_mill = st.multiselect(
            "Series de volumen de crédito (mill. USD)",
            cols_mill, default=cols_mill,
            key="int3_mill",
            format_func=lambda c: c[:65],
        )
    with sc2:
        sel_pct = st.multiselect(
            "Series de cartera en mora (%)",
            cols_pct, default=cols_pct,
            key="int3_pct",
            format_func=lambda c: c[:65],
        )

    # ── GRÁFICOS ─────────────────────────────────────────────────────────────
    st.markdown('<div class="gold-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Visualización</div>',
                unsafe_allow_html=True)

    if sel_mill and not df_f.empty:
        fig = line_fig(df_f, "fecha", sel_mill,
                       f"Volumen de Crédito — {desde.strftime('%b %Y')} a {hasta.strftime('%b %Y')}",
                       labels={c: c[:50] for c in sel_mill})
        fig.update_yaxes(title_text="Millones USD")
        st.plotly_chart(fig, use_container_width=True)

    if sel_pct and not df_f.empty:
        fig = line_fig(df_f, "fecha", sel_pct,
                       f"Cartera en Mora — {desde.strftime('%b %Y')} a {hasta.strftime('%b %Y')}",
                       labels={c: c[:50] for c in sel_pct})
        fig.update_yaxes(title_text="%", ticksuffix="%")
        st.plotly_chart(fig, use_container_width=True)

    with st.expander("Ver datos tabulares"):
        st.dataframe(df_f, use_container_width=True)


def render_intervencion4(df: pd.DataFrame):
    st.markdown(
        f'<span class="area-badge" style="background:{AREA_COLORS[3]}">'
        f'{AREA_LABELS[3]}</span>',
        unsafe_allow_html=True,
    )
    metricas = [c for c in df.columns if c != "fecha"]
    ultimo = df.iloc[-1]
    penultimo = df.iloc[-2] if len(df) > 1 else None

    cols = st.columns(min(4, len(metricas)))
    for i, col in enumerate(metricas[:4]):
        with cols[i]:
            val, unit = fmt_entero(ultimo[col])
            dt, dt_cls = _delta_str(ultimo[col],
                                    penultimo[col] if penultimo is not None else None,
                                    fmt_entero)
            st.markdown(
                kpi_card(col[:45], val, unit, dt, dt_cls, AREA_COLORS[3]),
                unsafe_allow_html=True,
            )

    st.markdown('<div class="gold-divider"></div>', unsafe_allow_html=True)

    min_f, max_f = df["fecha"].min(), df["fecha"].max()
    st.markdown(
        f'<div class="filter-panel-header">'
        f'<span class="filter-panel-title">Período de análisis</span></div>',
        unsafe_allow_html=True,
    )
    fc1, fc2, fc3 = st.columns([2, 2, 3])
    with fc1:
        desde = st.date_input("Fecha inicio", min_f, min_value=min_f, max_value=max_f,
                              key="int4_desde")
    with fc2:
        hasta = st.date_input("Fecha fin", max_f, min_value=min_f, max_value=max_f,
                              key="int4_hasta")
    with fc3:
        n_meses = max(
            0,
            (pd.Timestamp(hasta).year - pd.Timestamp(desde).year) * 12
            + (pd.Timestamp(hasta).month - pd.Timestamp(desde).month) + 1,
        )
        st.markdown(
            f'<div class="filter-range-info" style="padding-top:28px">'
            f'Rango seleccionado: <strong>{n_meses} meses</strong> '
            f'({desde.strftime("%b %Y")} — {hasta.strftime("%b %Y")})</div>',
            unsafe_allow_html=True,
        )
    st.markdown('<div class="gold-divider"></div>', unsafe_allow_html=True)

    df_f = df[
        (df["fecha"] >= pd.Timestamp(desde)) & (df["fecha"] <= pd.Timestamp(hasta))
    ]

    if not df_f.empty:
        fig = go.Figure()
        for i, col in enumerate(metricas):
            fig.add_trace(go.Bar(
                x=df_f["fecha"], y=df_f[col],
                name=col[:50],
                marker_color=PALETTE[i % len(PALETTE)],
                hovertemplate=f"<b>{col[:45]}</b><br>%{{x|%b %Y}}: %{{y:,.0f}} casos<extra></extra>",
            ))
        fig.update_layout(
            title=f"Quejas y Reclamos — {desde.strftime('%b %Y')} a {hasta.strftime('%b %Y')}",
            barmode="group",
            xaxis=dict(gridcolor="#E8EDF3", tickformat="%b %Y"),
            yaxis=dict(gridcolor="#E8EDF3", title="Casos"),
            legend=dict(orientation="h", y=-0.22, font_size=10),
            **_CHART_CFG,
        )
        st.plotly_chart(fig, use_container_width=True)

    with st.expander("Ver datos tabulares"):
        st.dataframe(df_f, use_container_width=True)


# ─── Resumen general ──────────────────────────────────────────────────────────

def render_overview(d1, d2, d3, d4):
    st.markdown('<div class="section-title">Estado Actual por Área de Intervención</div>',
                unsafe_allow_html=True)

    area_data = [
        (d1, "periodo", [c for c in d1.columns if c != "periodo"][0], fmt_entero, ""),
        (d2, "año",     [c for c in d2.columns if c != "año"][0],     fmt_pct_proporcion, ""),
        (d3, "fecha",   [c for c in d3.columns if c != "fecha"][0],   fmt_millones_usd, ""),
        (d4, "fecha",   [c for c in d4.columns if c != "fecha"][0],   fmt_entero, "casos"),
    ]

    cols = st.columns(4)
    for i, (df, x_col, metric, fn, extra_unit) in enumerate(area_data):
        with cols[i]:
            val_raw = df[metric].iloc[-1]
            val, unit = fn(val_raw)
            if extra_unit:
                unit = extra_unit
            periodo = df[x_col].iloc[-1]
            if hasattr(periodo, "strftime"):
                periodo = periodo.strftime("%b %Y")
            prev_raw = df[metric].iloc[-2] if len(df) > 1 else None
            dt, dt_cls = _delta_str(val_raw, prev_raw, fn)
            n = len(df)
            freq = ["trimestres", "años encuesta", "meses", "meses"][i]
            nota = f"Último: {periodo} · {n} {freq}"
            st.markdown(
                kpi_card(AREA_LABELS[i][:35], val, unit, nota, "kpi-delta-neu",
                         AREA_COLORS[i]),
                unsafe_allow_html=True,
            )

    st.markdown('<div class="gold-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Tendencias por Área</div>',
                unsafe_allow_html=True)

    # Mini-gráficos 2×2
    col1, col2 = st.columns(2)
    col3, col4 = st.columns(2)

    with col1:
        m = [c for c in d1.columns if c != "periodo"][-1]
        fig = line_fig(d1, "periodo", [m],
                       f"Área 1 — {_label(m)}", color=AREA_COLORS[0])
        fig.update_xaxes(tickangle=-40, nticks=8)
        fig.update_yaxes(title_text="Unidades")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        m2 = [c for c in d2.columns if c != "año"]
        fig = bar_fig(d2, "año", m2[:3],
                      "Área 2 — Indicadores Findex",
                      labels={c: c[:35] for c in m2[:3]},
                      pct_axis=True)
        st.plotly_chart(fig, use_container_width=True)

    with col3:
        cols_mill = [c for c in d3.columns if c != "fecha" and
                     _fmt_for_col3(c) is fmt_millones_usd]
        if cols_mill:
            fig = line_fig(d3, "fecha", [cols_mill[0]],
                           f"Área 3 — {cols_mill[0][:40]}", color=AREA_COLORS[2])
            fig.update_yaxes(title_text="Mill. USD")
            st.plotly_chart(fig, use_container_width=True)

    with col4:
        m4 = [c for c in d4.columns if c != "fecha"][0]
        fig = go.Figure(go.Bar(
            x=d4["fecha"], y=d4[m4],
            marker_color=AREA_COLORS[3],
            hovertemplate="%{x|%b %Y}: %{y:,.0f} casos<extra></extra>",
        ))
        fig.update_layout(
            title=f"Área 4 — {m4[:45]}",
            xaxis=dict(gridcolor="#E8EDF3", tickformat="%Y"),
            yaxis=dict(gridcolor="#E8EDF3", title="Casos"),
            **_CHART_CFG,
        )
        st.plotly_chart(fig, use_container_width=True)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    apply_css()

    st.markdown(f"""
    <div class="bce-header" style="display:flex;justify-content:space-between;align-items:center;gap:24px">
      <div style="flex:1">
        <div class="bce-logo-text">Banco Central del Ecuador</div>
        <div class="bce-header-title">
          Estrategia Nacional de Inclusión Financiera — ENIF
        </div>
        <div class="bce-header-sub">
          Dashboard de Áreas de Intervención &nbsp;|&nbsp;
          Junta de Política y Regulación Financiera y Monetaria &nbsp;|&nbsp;
          Información de carácter oficial
        </div>
      </div>
      <div style="flex-shrink:0;display:flex;align-items:center">
        <img src="https://www.bce.fin.ec/storage/elementor/thumbs/logo_bce_web-r45ldpnnqydo243f8ra5t93zx51bvhmqodcf53viwi.png"
             style="height:56px;display:block"
             alt="Banco Central del Ecuador" />
        <div style="width:1px;height:44px;background:rgba(200,168,75,0.5);margin:0 16px"></div>
        <img src="https://www.bce.fin.ec/storage/2025/10/jprmf.png"
             style="height:48px;display:block"
             alt="Junta de Política y Regulación Financiera y Monetaria" />
      </div>
    </div>
    """, unsafe_allow_html=True)

    if not EXCEL_PATH.exists():
        st.error(f"Archivo no encontrado: {EXCEL_PATH}")
        st.stop()

    with st.spinner("Cargando datos..."):
        d1 = load_intervencion1()
        d1_anual = load_intervencion1_anual()
        d2 = load_intervencion2()
        d3 = load_intervencion3()
        d4 = load_intervencion4()

    tabs = st.tabs([
        "Resumen General",
        "Área 1 — Puntos de Atención",
        "Área 2 — Oferta de Servicios",
        "Área 3 — Financiamiento y Crédito",
        "Área 4 — Protección al Consumidor",
    ])

    with tabs[0]:
        render_overview(d1, d2, d3, d4)

    with tabs[1]:
        render_intervencion1(d1, d1_anual)

    with tabs[2]:
        render_intervencion2(d2)

    with tabs[3]:
        render_intervencion3(d3)

    with tabs[4]:
        render_intervencion4(d4)

    # Fecha de última actualización
    ultimo_d3 = d3["fecha"].max().strftime("%B %Y") if not d3.empty else "—"
    st.markdown(f"""
    <div class="bce-footer">
      Banco Central del Ecuador &nbsp;·&nbsp;
      Estrategia Nacional de Inclusión Financiera (ENIF) &nbsp;·&nbsp;
      Datos al: {ultimo_d3} &nbsp;·&nbsp;
      Procesado con Python · Streamlit · Plotly
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
