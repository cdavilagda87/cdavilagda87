"""
areas_intervencion_app.py
==========================
Dashboard ENIF — Áreas de Intervención en Inclusión Financiera
Banco Central del Ecuador
Fuente: data/areas_intervencion.xlsx

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
from plotly.subplots import make_subplots
import streamlit as st

# ─── Config ──────────────────────────────────────────────────────────────────

EXCEL_PATH = Path(__file__).parent / "data" / "areas_intervencion.xlsx"

st.set_page_config(
    page_title="BCE · ENIF — Áreas de Intervención",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
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

    /* ── Sidebar ── */
    [data-testid="stSidebar"] {{
        background: {C['navy']};
    }}
    [data-testid="stSidebar"] * {{
        color: white !important;
    }}
    [data-testid="stSidebar"] .stSelectbox label,
    [data-testid="stSidebar"] .stSlider label {{
        color: {C['gold']} !important;
        font-size: .72rem !important;
        font-weight: 700 !important;
        text-transform: uppercase !important;
        letter-spacing: .08em !important;
    }}
    .sidebar-section {{
        border-top: 1px solid rgba(200,168,75,0.3);
        padding-top: 12px;
        margin-top: 12px;
    }}
    .sidebar-title {{
        font-size: .68rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: .10em;
        color: {C['gold']};
        margin-bottom: 8px;
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

    /* ── Tabla resumen ── */
    .resumen-table {{
        width: 100%;
        border-collapse: collapse;
        font-size: .82rem;
    }}
    .resumen-table th {{
        background: {C['navy']};
        color: white;
        padding: 8px 12px;
        text-align: left;
        font-weight: 600;
        letter-spacing: .04em;
    }}
    .resumen-table td {{
        padding: 7px 12px;
        border-bottom: 1px solid {C['lgray']};
        color: {C['text']};
    }}
    .resumen-table tr:nth-child(even) td {{
        background: {C['lgray']};
    }}
    </style>
    """, unsafe_allow_html=True)


# ─── Formatters ──────────────────────────────────────────────────────────────

def fmt_entero(n) -> tuple[str, str]:
    try:
        return f"{int(float(n)):,}", ""
    except Exception:
        return "—", ""


def fmt_millones_usd(n) -> tuple[str, str]:
    try:
        return f"{float(n):,.2f}", "mill. USD"
    except Exception:
        return "—", ""


def fmt_pct_proporcion(n) -> tuple[str, str]:
    try:
        return f"{float(n) * 100:.1f}", "%"
    except Exception:
        return "—", ""


def fmt_pct_directa(n) -> tuple[str, str]:
    try:
        return f"{float(n):.2f}", "%"
    except Exception:
        return "—", ""


def _fmt_for_col3(col: str):
    c = col.lower()
    if "mora" in c or "(%)" in c or "porcentaje" in c or "tasa" in c:
        return fmt_pct_directa
    return fmt_millones_usd


def _delta_str(val, prev, fmt_fn) -> tuple[str, str]:
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


def download_btn(df: pd.DataFrame, key: str, label: str = "Descargar CSV"):
    csv = df.to_csv(index=False, encoding="utf-8-sig")
    st.download_button(label, csv, file_name=f"{key}.csv",
                       mime="text/csv", key=f"dl_{key}")


# ─── Gráficos ─────────────────────────────────────────────────────────────────

def line_fig(df: pd.DataFrame, x: str, y_cols: list[str],
             title: str, labels: dict | None = None,
             color: str | None = None,
             rolling: int = 0) -> go.Figure:
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
        if rolling > 1 and len(y.dropna()) >= rolling:
            y_roll = y.rolling(rolling, min_periods=1).mean()
            fig.add_trace(go.Scatter(
                x=df[x], y=y_roll, mode="lines", name=f"{lbl} (media {rolling}p)",
                line=dict(color=clr, width=1.5, dash="dot"),
                hovertemplate=f"<b>Media {rolling}p</b><br>%{{x}}: %{{y:,.3f}}<extra></extra>",
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
            pct_axis: bool = False, stacked: bool = False) -> go.Figure:
    fig = go.Figure()
    for i, col in enumerate(y_cols):
        lbl = (labels or {}).get(col, col.replace("_", " "))
        y = pd.to_numeric(df[col], errors="coerce")
        if pct_axis:
            y = y * 100
        fig.add_trace(go.Bar(
            x=df[x], y=y, name=lbl,
            marker_color=PALETTE[i % len(PALETTE)],
            hovertemplate=f"<b>{lbl}</b><br>%{{x}}: %{{y:.1f}}{'%' if pct_axis else ''}<extra></extra>",
        ))
    y_cfg = dict(gridcolor="#E8EDF3", linecolor=C["lgray"])
    if pct_axis:
        y_cfg["ticksuffix"] = "%"
    fig.update_layout(
        title=title,
        barmode="stack" if stacked else "group",
        xaxis=dict(gridcolor="#E8EDF3", linecolor=C["lgray"]),
        yaxis=y_cfg,
        legend=dict(orientation="h", y=-0.28, x=0, font_size=10),
        **_CHART_CFG,
    )
    return fig


def dual_axis_fig(df: pd.DataFrame, x: str,
                  cols_left: list[str], cols_right: list[str],
                  title: str, y_left_title: str = "", y_right_title: str = "",
                  rolling: int = 0) -> go.Figure:
    """Gráfico de doble eje Y: izquierda (mill. USD) y derecha (%)."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    for i, col in enumerate(cols_left):
        y = pd.to_numeric(df[col], errors="coerce")
        fig.add_trace(go.Scatter(
            x=df[x], y=y, mode="lines+markers", name=col[:50],
            line=dict(color=PALETTE[i % 5], width=2.2),
            marker=dict(size=5),
            hovertemplate=f"<b>{col[:45]}</b><br>%{{x}}: %{{y:,.2f}} mill. USD<extra></extra>",
        ), secondary_y=False)
        if rolling > 1 and len(y.dropna()) >= rolling:
            y_roll = y.rolling(rolling, min_periods=1).mean()
            fig.add_trace(go.Scatter(
                x=df[x], y=y_roll, mode="lines", name=f"{col[:35]} (media {rolling}p)",
                line=dict(color=PALETTE[i % 5], width=1.4, dash="dot"),
                showlegend=False,
            ), secondary_y=False)

    for j, col in enumerate(cols_right):
        y = pd.to_numeric(df[col], errors="coerce")
        fig.add_trace(go.Scatter(
            x=df[x], y=y, mode="lines+markers", name=col[:50],
            line=dict(color=PALETTE[(j + 5) % len(PALETTE)], width=2, dash="dash"),
            marker=dict(size=4, symbol="diamond"),
            hovertemplate=f"<b>{col[:45]}</b><br>%{{x}}: %{{y:.2f}}%<extra></extra>",
        ), secondary_y=True)

    fig.update_layout(
        title=title,
        legend=dict(orientation="h", y=-0.28, x=0, font_size=10),
        **_CHART_CFG,
    )
    fig.update_yaxes(title_text=y_left_title, secondary_y=False,
                     gridcolor="#E8EDF3", linecolor=C["lgray"])
    fig.update_yaxes(title_text=y_right_title, secondary_y=True,
                     ticksuffix="%", gridcolor="#E8EDF3", showgrid=False)
    return fig


def area_fig(df: pd.DataFrame, x: str, y_cols: list[str],
             title: str, color: str) -> go.Figure:
    fig = go.Figure()
    for i, col in enumerate(y_cols):
        clr = color if len(y_cols) == 1 else PALETTE[i % len(PALETTE)]
        y = pd.to_numeric(df[col], errors="coerce")
        fig.add_trace(go.Scatter(
            x=df[x], y=y, mode="lines", name=col[:50],
            line=dict(color=clr, width=2),
            fill="tozeroy",
            fillcolor=clr.replace("#", "rgba(").rstrip(")") if clr.startswith("#") else clr,
            hovertemplate=f"<b>{col[:45]}</b><br>%{{x}}: %{{y:,.0f}} casos<extra></extra>",
        ))
    fig.update_layout(
        title=title,
        xaxis=dict(gridcolor="#E8EDF3", tickformat="%b %Y"),
        yaxis=dict(gridcolor="#E8EDF3", title="Casos"),
        legend=dict(orientation="h", y=-0.22, font_size=10),
        **_CHART_CFG,
    )
    return fig


def radar_fig(df: pd.DataFrame, year_col: str, metricas: list[str], title: str) -> go.Figure:
    """Radar comparativo para datos Global Findex."""
    fig = go.Figure()
    años = df[year_col].tolist()
    colors_radar = [C["blue"], C["gold"], "#1B5E20"]
    for i, (_, row) in enumerate(df.iterrows()):
        vals = [float(row[m]) * 100 if pd.notna(row[m]) else 0 for m in metricas]
        vals.append(vals[0])  # cerrar radar
        labs = [m[:35] for m in metricas] + [metricas[0][:35]]
        fig.add_trace(go.Scatterpolar(
            r=vals, theta=labs,
            name=str(años[i]),
            line=dict(color=colors_radar[i % len(colors_radar)], width=2),
            fill="toself",
            fillcolor=colors_radar[i % len(colors_radar)],
            opacity=0.15,
        ))
    fig.update_layout(
        title=title,
        polar=dict(
            radialaxis=dict(ticksuffix="%", gridcolor="#D0D9E8", range=[0, 100]),
            angularaxis=dict(gridcolor="#D0D9E8"),
            bgcolor="white",
        ),
        legend=dict(orientation="h", y=-0.12, font_size=10),
        **_CHART_CFG,
    )
    return fig


# ─── Carga de datos ───────────────────────────────────────────────────────────

@st.cache_data(ttl=600, show_spinner=False)
def load_intervencion1() -> pd.DataFrame:
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
    h4 = h4_raw

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
def load_intervencion2() -> pd.DataFrame:
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


# ─── Sidebar ──────────────────────────────────────────────────────────────────

def build_sidebar(d3: pd.DataFrame, d4: pd.DataFrame) -> dict:
    with st.sidebar:
        st.markdown("""
        <div style="padding:16px 0 8px">
          <div style="font-size:.68rem;font-weight:700;letter-spacing:.12em;
                      text-transform:uppercase;color:#C8A84B;margin-bottom:4px">
            BCE · ENIF
          </div>
          <div style="font-size:1rem;font-weight:700;line-height:1.3">
            Áreas de Intervención
          </div>
          <div style="font-size:.75rem;opacity:.7;margin-top:4px">
            Inclusión Financiera — Ecuador
          </div>
        </div>
        <div class="sidebar-section">
          <div class="sidebar-title">Filtro global (Áreas 3 y 4)</div>
        </div>
        """, unsafe_allow_html=True)

        min_f = min(d3["fecha"].min(), d4["fecha"].min())
        max_f = max(d3["fecha"].max(), d4["fecha"].max())

        desde = st.date_input("Desde", min_f, min_value=min_f, max_value=max_f,
                              key="sb_desde")
        hasta = st.date_input("Hasta", max_f, min_value=min_f, max_value=max_f,
                              key="sb_hasta")

        st.markdown('<div class="sidebar-section"><div class="sidebar-title">Opciones de gráficos</div></div>',
                    unsafe_allow_html=True)

        rolling = st.select_slider(
            "Media móvil (meses)",
            options=[0, 3, 6, 12],
            value=0,
            key="sb_rolling",
            format_func=lambda v: "Sin media" if v == 0 else f"{v} meses",
        )

        chart_type_a1 = st.radio(
            "Área 1 — tipo de gráfico",
            ["Línea", "Barras", "Barras apiladas"],
            key="sb_a1_chart",
            horizontal=False,
        )

        st.markdown('<div class="sidebar-section"></div>', unsafe_allow_html=True)
        st.caption("Datos: BCE Ecuador · Encuesta Global Findex")

    return {
        "desde": pd.Timestamp(desde),
        "hasta": pd.Timestamp(hasta),
        "rolling": rolling,
        "chart_type_a1": chart_type_a1,
    }


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _label(col: str) -> str:
    parts = col.split(" · ")
    return parts[-1][:50] if len(parts) > 1 else col[:50]


# ─── Renders por área ─────────────────────────────────────────────────────────

def render_intervencion1(df: pd.DataFrame, opts: dict):
    st.markdown(
        f'<span class="area-badge" style="background:{AREA_COLORS[0]}">'
        f'{AREA_LABELS[0]}</span>',
        unsafe_allow_html=True,
    )
    metricas = [c for c in df.columns if c != "periodo"]
    ultimo = df.iloc[-1]
    penultimo = df.iloc[-2] if len(df) > 1 else None

    # KPIs — todas las métricas disponibles, filas de 4
    for row_start in range(0, len(metricas), 4):
        chunk = metricas[row_start:row_start + 4]
        cols = st.columns(len(chunk))
        for i, col in enumerate(chunk):
            with cols[i]:
                val, unit = fmt_entero(ultimo[col])
                dt, dt_cls = _delta_str(ultimo[col],
                                        penultimo[col] if penultimo is not None else None,
                                        fmt_entero)
                st.markdown(
                    kpi_card(_label(col), val, unit, dt, dt_cls, AREA_COLORS[0]),
                    unsafe_allow_html=True,
                )
        st.markdown("")

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
        ct = opts["chart_type_a1"]
        if ct == "Línea":
            fig = line_fig(df, "periodo", sel,
                           f"Puntos de Atención — {df['periodo'].iloc[0]} a {df['periodo'].iloc[-1]}",
                           labels=labels,
                           color=AREA_COLORS[0] if len(sel) == 1 else None)
            fig.update_yaxes(title_text="Unidades")
            fig.update_xaxes(tickangle=-40)
        elif ct == "Barras":
            fig = bar_fig(df, "periodo", sel,
                          "Puntos de Atención", labels=labels)
            fig.update_xaxes(tickangle=-40)
        else:
            fig = bar_fig(df, "periodo", sel,
                          "Puntos de Atención (apilado)", labels=labels, stacked=True)
            fig.update_xaxes(tickangle=-40)
        st.plotly_chart(fig, use_container_width=True)

    with st.expander("Ver datos tabulares"):
        st.dataframe(df, use_container_width=True)
        download_btn(df, "area1_puntos_atencion")


def render_intervencion2(df: pd.DataFrame):
    st.markdown(
        f'<span class="area-badge" style="background:{AREA_COLORS[1]}">'
        f'{AREA_LABELS[1]}</span>',
        unsafe_allow_html=True,
    )
    metricas = [c for c in df.columns if c != "año"]
    ultimo = df.iloc[-1]
    penultimo = df.iloc[-2] if len(df) > 1 else None

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

    # Radar + barras en dos columnas
    col_radar, col_bar = st.columns([1, 1])

    with col_radar:
        st.markdown('<div class="section-title">Radar comparativo — Global Findex</div>',
                    unsafe_allow_html=True)
        sel_radar = st.multiselect(
            "Indicadores para radar",
            metricas, default=metricas[:min(6, len(metricas))],
            key="int2_radar",
            format_func=lambda c: c[:50],
        )
        if sel_radar and len(df) > 0:
            fig = radar_fig(df, "año", sel_radar,
                            "Comparación entre encuestas Global Findex")
            st.plotly_chart(fig, use_container_width=True)

    with col_bar:
        st.markdown('<div class="section-title">Evolución por año de encuesta</div>',
                    unsafe_allow_html=True)
        sel_bar = st.multiselect(
            "Indicadores para barras",
            metricas, default=metricas[:min(3, len(metricas))],
            key="int2_bar",
            format_func=lambda c: c[:50],
        )
        if sel_bar:
            fig = bar_fig(df, "año", sel_bar,
                          "Indicadores de Acceso Financiero",
                          labels={c: c[:40] for c in sel_bar},
                          pct_axis=True)
            st.plotly_chart(fig, use_container_width=True)

    # Tabla comparativa
    st.markdown('<div class="gold-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Tabla comparativa por año</div>',
                unsafe_allow_html=True)
    disp = df.copy()
    for c in metricas:
        disp[c] = disp[c].apply(
            lambda x: f"{float(x)*100:.1f} %" if pd.notna(x) else "—"
        )
    st.dataframe(disp, use_container_width=True)
    download_btn(df, "area2_oferta_servicios")


def render_intervencion3(df: pd.DataFrame, opts: dict):
    st.markdown(
        f'<span class="area-badge" style="background:{AREA_COLORS[2]}">'
        f'{AREA_LABELS[2]}</span>',
        unsafe_allow_html=True,
    )
    metricas = [c for c in df.columns if c != "fecha"]
    ultimo = df.iloc[-1]
    penultimo = df.iloc[-2] if len(df) > 1 else None

    kpi_cols = st.columns(min(len(metricas), 5))
    for i, col in enumerate(metricas):
        with kpi_cols[i % min(len(metricas), 5)]:
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

    # Filtro de período (usa sidebar global)
    df_f = df[
        (df["fecha"] >= opts["desde"]) & (df["fecha"] <= opts["hasta"])
    ]
    n_meses = max(0,
        (opts["hasta"].year - opts["desde"].year) * 12
        + (opts["hasta"].month - opts["desde"].month) + 1)
    st.markdown(
        f'<div class="filter-range-info" style="margin-bottom:10px">'
        f'Período: <strong>{opts["desde"].strftime("%b %Y")} — {opts["hasta"].strftime("%b %Y")}'
        f'</strong> ({n_meses} meses)</div>',
        unsafe_allow_html=True,
    )

    cols_mill = [c for c in metricas if _fmt_for_col3(c) is fmt_millones_usd]
    cols_pct  = [c for c in metricas if _fmt_for_col3(c) is fmt_pct_directa]

    # Selectores
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

    st.markdown('<div class="gold-divider"></div>', unsafe_allow_html=True)

    rolling = opts["rolling"]

    if not df_f.empty:
        if sel_mill and sel_pct:
            # Doble eje Y combinado
            st.markdown('<div class="section-title">Crédito y Mora — doble eje</div>',
                        unsafe_allow_html=True)
            fig = dual_axis_fig(
                df_f, "fecha", sel_mill, sel_pct,
                f"Crédito y Mora — {opts['desde'].strftime('%b %Y')} a {opts['hasta'].strftime('%b %Y')}",
                y_left_title="Millones USD", y_right_title="Mora %",
                rolling=rolling,
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            if sel_mill:
                fig = line_fig(df_f, "fecha", sel_mill,
                               f"Volumen de Crédito",
                               labels={c: c[:50] for c in sel_mill},
                               rolling=rolling)
                fig.update_yaxes(title_text="Millones USD")
                st.plotly_chart(fig, use_container_width=True)
            if sel_pct:
                fig = line_fig(df_f, "fecha", sel_pct,
                               f"Cartera en Mora",
                               labels={c: c[:50] for c in sel_pct},
                               rolling=rolling)
                fig.update_yaxes(title_text="%", ticksuffix="%")
                st.plotly_chart(fig, use_container_width=True)

    with st.expander("Ver datos tabulares"):
        st.dataframe(df_f, use_container_width=True)
        download_btn(df_f, "area3_credito")


def render_intervencion4(df: pd.DataFrame, opts: dict):
    st.markdown(
        f'<span class="area-badge" style="background:{AREA_COLORS[3]}">'
        f'{AREA_LABELS[3]}</span>',
        unsafe_allow_html=True,
    )
    metricas = [c for c in df.columns if c != "fecha"]
    ultimo = df.iloc[-1]
    penultimo = df.iloc[-2] if len(df) > 1 else None

    # KPI acumulado total + por columna
    total_acum = sum(df[c].sum() for c in metricas if pd.api.types.is_numeric_dtype(df[c]))
    kpi_list = [(f"Total acumulado", fmt_entero(total_acum), "casos", AREA_COLORS[3])]

    all_cols = st.columns(min(4, len(metricas) + 1))
    with all_cols[0]:
        val_t, unit_t = fmt_entero(total_acum)
        st.markdown(
            kpi_card("Total Acumulado", val_t, "casos", "", "kpi-delta-neu", AREA_COLORS[3]),
            unsafe_allow_html=True,
        )
    for i, col in enumerate(metricas[:3]):
        with all_cols[i + 1]:
            val, unit = fmt_entero(ultimo[col])
            dt, dt_cls = _delta_str(ultimo[col],
                                    penultimo[col] if penultimo is not None else None,
                                    fmt_entero)
            st.markdown(
                kpi_card(col[:45], val, unit, dt, dt_cls, AREA_COLORS[3]),
                unsafe_allow_html=True,
            )

    st.markdown('<div class="gold-divider"></div>', unsafe_allow_html=True)

    df_f = df[
        (df["fecha"] >= opts["desde"]) & (df["fecha"] <= opts["hasta"])
    ]
    n_meses = max(0,
        (opts["hasta"].year - opts["desde"].year) * 12
        + (opts["hasta"].month - opts["desde"].month) + 1)
    st.markdown(
        f'<div class="filter-range-info" style="margin-bottom:10px">'
        f'Período: <strong>{opts["desde"].strftime("%b %Y")} — {opts["hasta"].strftime("%b %Y")}'
        f'</strong> ({n_meses} meses)</div>',
        unsafe_allow_html=True,
    )

    if not df_f.empty:
        # Barras agrupadas
        st.markdown('<div class="section-title">Quejas y Reclamos — barras</div>',
                    unsafe_allow_html=True)
        fig = go.Figure()
        for i, col in enumerate(metricas):
            fig.add_trace(go.Bar(
                x=df_f["fecha"], y=df_f[col],
                name=col[:50],
                marker_color=PALETTE[i % len(PALETTE)],
                hovertemplate=f"<b>{col[:45]}</b><br>%{{x|%b %Y}}: %{{y:,.0f}} casos<extra></extra>",
            ))
        fig.update_layout(
            title=f"Quejas y Reclamos — {opts['desde'].strftime('%b %Y')} a {opts['hasta'].strftime('%b %Y')}",
            barmode="group",
            xaxis=dict(gridcolor="#E8EDF3", tickformat="%b %Y"),
            yaxis=dict(gridcolor="#E8EDF3", title="Casos"),
            legend=dict(orientation="h", y=-0.22, font_size=10),
            **_CHART_CFG,
        )
        st.plotly_chart(fig, use_container_width=True)

        # Área rellena — evolución acumulada
        st.markdown('<div class="section-title">Evolución acumulada — área</div>',
                    unsafe_allow_html=True)
        df_area = df_f.copy()
        df_area["total"] = df_area[metricas].sum(axis=1)
        fig2 = area_fig(df_area, "fecha", ["total"],
                        "Evolución mensual total de casos",
                        color=AREA_COLORS[3])
        # Ajuste de color de fill con opacidad
        fig2.data[0].fillcolor = "rgba(0,40,85,0.15)"
        st.plotly_chart(fig2, use_container_width=True)

    with st.expander("Ver datos tabulares"):
        st.dataframe(df_f, use_container_width=True)
        download_btn(df_f, "area4_proteccion")


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

    # Tabla resumen
    st.markdown('<div class="section-title">Tabla resumen por área</div>',
                unsafe_allow_html=True)

    resumen_rows = []
    for i, (df, x_col, metric, fn, extra_unit) in enumerate(area_data):
        val_raw = df[metric].iloc[-1]
        val, unit = fn(val_raw)
        if extra_unit:
            unit = extra_unit
        prev_raw = df[metric].iloc[-2] if len(df) > 1 else None
        dt, _ = _delta_str(val_raw, prev_raw, fn)
        periodo = df[x_col].iloc[-1]
        if hasattr(periodo, "strftime"):
            periodo = periodo.strftime("%b %Y")
        resumen_rows.append({
            "Área": AREA_LABELS[i],
            "Último período": periodo,
            "Métrica principal": metric[:50],
            "Valor": f"{val} {unit}".strip(),
            "Variación": dt or "—",
            "N° registros": len(df),
        })

    df_res = pd.DataFrame(resumen_rows)
    st.dataframe(df_res, use_container_width=True, hide_index=True)

    st.markdown('<div class="gold-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Tendencias por Área</div>',
                unsafe_allow_html=True)

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
        d4_area = d4.copy()
        d4_area["total"] = d4[[c for c in d4.columns if c != "fecha"]].sum(axis=1)
        fig = go.Figure(go.Scatter(
            x=d4_area["fecha"], y=d4_area["total"],
            mode="lines", fill="tozeroy",
            line=dict(color=AREA_COLORS[3], width=2),
            fillcolor="rgba(0,40,85,0.12)",
            hovertemplate="%{x|%b %Y}: %{y:,.0f} casos<extra></extra>",
        ))
        fig.update_layout(
            title="Área 4 — Total casos mensual",
            xaxis=dict(gridcolor="#E8EDF3", tickformat="%Y"),
            yaxis=dict(gridcolor="#E8EDF3", title="Casos"),
            **_CHART_CFG,
        )
        st.plotly_chart(fig, use_container_width=True)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    apply_css()

    if not EXCEL_PATH.exists():
        st.error(f"Archivo no encontrado: {EXCEL_PATH}")
        st.stop()

    with st.spinner("Cargando datos..."):
        d1 = load_intervencion1()
        d2 = load_intervencion2()
        d3 = load_intervencion3()
        d4 = load_intervencion4()

    opts = build_sidebar(d3, d4)

    ultimo_d3 = d3["fecha"].max().strftime("%B %Y") if not d3.empty else "—"

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
          Datos al: <strong>{ultimo_d3}</strong>
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
        render_intervencion1(d1, opts)

    with tabs[2]:
        render_intervencion2(d2)

    with tabs[3]:
        render_intervencion3(d3, opts)

    with tabs[4]:
        render_intervencion4(d4, opts)

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
