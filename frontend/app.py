"""
AlquilerJusto — Streamlit frontend.

Tabs:
  1. Analizar aviso  — pick example or fill form → verdict + comparable cards
  2. Mapa de precios — Folium choropleth by district
  3. Sobre el modelo — methodology explainer
"""

import json
import os
import sys
from pathlib import Path

import folium
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_folium import st_folium
from streamlit_option_menu import option_menu

sys.path.insert(0, str(Path(__file__).parent.parent))

# Puente seguro: expone el secret de Streamlit como variable de entorno
# (lo usa ai/assistant.py para el parseo opcional con Claude, vía os.getenv).
try:
    if "ANTHROPIC_API_KEY" in st.secrets and not os.getenv("ANTHROPIC_API_KEY"):
        os.environ["ANTHROPIC_API_KEY"] = st.secrets["ANTHROPIC_API_KEY"]
except Exception:
    pass  # sin secrets.toml local no pasa nada; se usa .env o el fallback

from backend.app.comparables import get_comparables
from backend.app.model import get_model
from ai.assistant import parse_query, relax_search, DISTRICTS as ASSISTANT_DISTRICTS

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="AlquilerJusto",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;700;800&family=Inter:wght@400;500;600&display=swap');

:root {
    --aj-green-900: #0b3d2c;
    --aj-green-700: #13794f;
    --aj-green-500: #1f9d57;
    --aj-emerald:   #2ecc71;
    --aj-amber:     #f5a623;
    --aj-ink:       #18241f;
    --aj-muted:     #6b7c74;
    --aj-cream:     #f5f8f4;
    --aj-card-sh:   0 4px 18px rgba(11,61,44,0.08);
    --aj-card-sh-h: 0 12px 30px rgba(11,61,44,0.16);
}

/* Tipografía global */
html, body, [class*="css"], .stMarkdown, p, span, div, label, input, textarea {
    font-family: 'Inter', system-ui, sans-serif;
}
h1, h2, h3, h4, h5 {
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    letter-spacing: -0.4px;
    color: var(--aj-ink);
}

/* Fondo de la app */
[data-testid="stAppViewContainer"] {
    background:
        radial-gradient(900px 400px at 100% -5%, rgba(46,204,113,0.07), transparent 60%),
        radial-gradient(700px 350px at -5% 10%, rgba(245,166,35,0.06), transparent 55%),
        var(--aj-cream);
}

/* ───────── Hero ───────── */
.hero {
    position: relative;
    overflow: hidden;
    background: linear-gradient(125deg, #0b3d2c 0%, #13794f 48%, #2ecc71 115%);
    border-radius: 22px;
    padding: 2.4rem 2.6rem 3.2rem 2.6rem;
    margin-bottom: 1.5rem;
    color: white;
    box-shadow: 0 18px 44px rgba(11,61,44,0.30);
}
.hero::after {  /* brillo superior */
    content: "";
    position: absolute; top: -40%; right: -10%;
    width: 460px; height: 460px;
    background: radial-gradient(circle, rgba(255,255,255,0.18), transparent 65%);
    pointer-events: none;
}
.hero .skyline {
    position: absolute; left: 0; right: 0; bottom: 0;
    width: 100%; height: 70px; opacity: 0.55;
    pointer-events: none;
}
.hero h1 {
    color: #fff !important;
    font-size: 2.7rem;
    margin: 0 0 0.5rem 0;
    font-weight: 800;
    position: relative; z-index: 1;
}
.hero p {
    color: rgba(255,255,255,0.94);
    font-size: 1.08rem; margin: 0; max-width: 640px;
    position: relative; z-index: 1;
}
.hero .pill {
    display: inline-flex; align-items: center; gap: .4rem;
    background: rgba(255,255,255,0.16);
    border: 1px solid rgba(255,255,255,0.32);
    backdrop-filter: blur(6px);
    border-radius: 30px;
    padding: 0.35rem 1rem;
    font-size: 0.82rem; font-weight: 600;
    margin-top: 1rem; position: relative; z-index: 1;
}

/* ───────── Botones ───────── */
.stButton > button {
    border-radius: 12px;
    font-weight: 600;
    border: 1px solid rgba(11,61,44,0.12);
    transition: transform .15s ease, box-shadow .15s ease, background .15s ease;
}
.stButton > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 20px rgba(11,61,44,0.16);
}
.stButton > button[kind="primary"] {
    background: linear-gradient(120deg, var(--aj-green-700), var(--aj-emerald));
    border: none; color: #fff;
    box-shadow: 0 6px 16px rgba(31,157,87,0.30);
}
.stButton > button[kind="primary"]:hover {
    box-shadow: 0 12px 26px rgba(31,157,87,0.42);
}

/* ───────── Contenedores con borde (cards nativas) ───────── */
[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 16px !important;
    border: 1px solid rgba(11,61,44,0.08) !important;
    background: #fff;
    box-shadow: var(--aj-card-sh);
    overflow: hidden;
    transition: transform .18s ease, box-shadow .18s ease;
}
[data-testid="stVerticalBlockBorderWrapper"]:hover {
    transform: translateY(-3px);
    box-shadow: var(--aj-card-sh-h);
}

/* Banner de distrito (tope de las tarjetas de ejemplo) */
.dist-banner {
    margin: -1rem -1rem 0.7rem -1rem;
    height: 88px;
    display: flex; align-items: flex-end;
    padding: 0.6rem 0.9rem;
    position: relative; overflow: hidden;
}
.dist-banner .ico {
    position: absolute; right: -8px; top: -14px;
    font-size: 66px; opacity: 0.22;
}
.dist-banner::after {
    content: ""; position: absolute; inset: 0;
    background: linear-gradient(180deg, rgba(0,0,0,0) 35%, rgba(0,0,0,0.42));
}
.dist-banner .dn {
    position: relative; z-index: 2; color: #fff; font-weight: 800;
    font-family: 'Plus Jakarta Sans', sans-serif; font-size: 1.05rem;
    text-shadow: 0 1px 6px rgba(0,0,0,0.5);
}

/* ───────── Métricas ───────── */
[data-testid="stMetric"] {
    background: #fff;
    border: 1px solid rgba(11,61,44,0.08);
    border-radius: 14px;
    padding: 0.9rem 1.1rem;
    box-shadow: var(--aj-card-sh);
}
[data-testid="stMetricValue"] { color: var(--aj-green-700); font-weight: 800; }

/* ───────── Inputs ───────── */
[data-testid="stTextInput"] input, [data-testid="stNumberInput"] input,
[data-baseweb="select"] > div, .stTextArea textarea {
    border-radius: 10px !important;
}

/* ───────── Veredicto ───────── */
.verdict-box {
    padding: 1.7rem 2rem;
    border-radius: 18px;
    text-align: center;
    margin: 1.1rem 0;
    box-shadow: var(--aj-card-sh);
    animation: aj-pop .4s cubic-bezier(.2,.8,.2,1);
}
@keyframes aj-pop { from {opacity:0; transform: scale(.96) translateY(8px);} to {opacity:1; transform:none;} }
.verde    { background: linear-gradient(135deg,#eafaf0,#d3f3df); border: 1.5px solid #28a745; }
.amarillo { background: linear-gradient(135deg,#fff8e6,#ffefc2); border: 1.5px solid #f0b400; }
.rojo     { background: linear-gradient(135deg,#fdecee,#f9d6da); border: 1.5px solid #dc3545; }
.big-number { font-size: 2.6rem; font-weight: 800; font-family:'Plus Jakarta Sans',sans-serif; }
.subtitle   { font-size: 0.92rem; color: #4a5a53; margin-top: 0.4rem; }

/* ───────── Cards de avisos ───────── */
.comp-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
    gap: 1rem; margin: 1rem 0;
}
.comp-card {
    position: relative;
    background: #fff;
    border: 1px solid rgba(11,61,44,0.08);
    border-radius: 14px;
    padding: 1.1rem 1.15rem 1.1rem 1.25rem;
    display: flex; flex-direction: column; gap: 0.28rem;
    box-shadow: var(--aj-card-sh);
    transition: transform .18s ease, box-shadow .18s ease;
    overflow: hidden;
}
.comp-card::before {  /* barra de acento lateral */
    content:""; position:absolute; left:0; top:0; bottom:0; width:5px;
    background: linear-gradient(var(--aj-green-500), var(--aj-emerald));
}
.comp-card:hover { transform: translateY(-4px); box-shadow: var(--aj-card-sh-h); }
.comp-price  { font-size: 1.22rem; font-weight: 800; color: var(--aj-ink);
               font-family:'Plus Jakarta Sans',sans-serif; }
.comp-meta   { font-size: 0.82rem; color: var(--aj-muted); }
.comp-diff-down { font-size: 0.82rem; color: #1e9e54; font-weight: 700; }
.comp-diff-up   { font-size: 0.82rem; color: #dc3545; font-weight: 700; }
.comp-link { margin-top: auto; padding-top: 0.7rem; }
.comp-link a {
    display: block; padding: 0.5rem 0;
    background: linear-gradient(120deg, var(--aj-green-700), var(--aj-emerald));
    color: #fff !important; text-align: center; border-radius: 9px;
    text-decoration: none !important; font-size: 0.84rem; font-weight: 700;
    transition: filter .15s ease, transform .15s ease;
}
.comp-link a:hover { filter: brightness(1.08); transform: translateY(-1px); }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# District metadata (centroids for map)
# ---------------------------------------------------------------------------
DISTRICT_META = {
    "miraflores":  {"lat": -12.1219, "lon": -77.0299, "label": "Miraflores"},
    "san-isidro":  {"lat": -12.0969, "lon": -77.0367, "label": "San Isidro"},
    "surco":       {"lat": -12.1477, "lon": -76.9934, "label": "Santiago de Surco"},
    "magdalena":   {"lat": -12.0925, "lon": -77.0714, "label": "Magdalena del Mar"},
    "san-miguel":  {"lat": -12.0771, "lon": -77.0982, "label": "San Miguel"},
    "barranco":    {"lat": -12.1530, "lon": -77.0197, "label": "Barranco"},
    "san-borja":   {"lat": -12.0990, "lon": -76.9952, "label": "San Borja"},
    "la-molina":   {"lat": -12.0820, "lon": -76.9432, "label": "La Molina"},
    "jesus-maria": {"lat": -12.0703, "lon": -77.0469, "label": "Jesús María"},
    "lince":       {"lat": -12.0833, "lon": -77.0361, "label": "Lince"},
    "pueblo-libre":{"lat": -12.0742, "lon": -77.0630, "label": "Pueblo Libre"},
}
DISTRICT_LABELS = {d: m["label"] for d, m in DISTRICT_META.items()}

# Gradiente de marca por distrito (para banners de tarjetas)
DISTRICT_GRADIENTS = {
    "miraflores":  "linear-gradient(135deg,#0e7490,#06b6d4)",
    "san-isidro":  "linear-gradient(135deg,#1e3a8a,#3b82f6)",
    "barranco":    "linear-gradient(135deg,#7e22ce,#db2777)",
    "magdalena":   "linear-gradient(135deg,#0369a1,#0ea5e9)",
    "san-miguel":  "linear-gradient(135deg,#c2410c,#f97316)",
    "surco":       "linear-gradient(135deg,#15803d,#22c55e)",
    "san-borja":   "linear-gradient(135deg,#0f766e,#14b8a6)",
    "la-molina":   "linear-gradient(135deg,#a16207,#eab308)",
    "jesus-maria": "linear-gradient(135deg,#9f1239,#e11d48)",
    "lince":       "linear-gradient(135deg,#334155,#64748b)",
    "pueblo-libre":"linear-gradient(135deg,#9a3412,#c2410c)",
}
DEFAULT_GRADIENT = "linear-gradient(135deg,#13794f,#2ecc71)"


def _price_color(avg_pen: float) -> str:
    if avg_pen >= 5000:
        return "#c0392b"
    if avg_pen >= 3500:
        return "#e67e22"
    if avg_pen >= 2500:
        return "#f1c40f"
    return "#27ae60"


DB_PATH = Path("data/listings.db")

# ---------------------------------------------------------------------------
# Cached resources
# ---------------------------------------------------------------------------
@st.cache_resource(show_spinner="Entrenando modelo hedónico…")
def load_model():
    return get_model(DB_PATH)


@st.cache_data(show_spinner=False)
def load_examples() -> list[dict]:
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    rows = []
    for district in ["miraflores", "san-isidro", "barranco", "san-miguel"]:
        df = pd.read_sql_query("""
            SELECT district, price_pen, area_m2, bedrooms, bathrooms,
                   floor, amenities_raw, title, url
            FROM listings
            WHERE district = ?
              AND price_pen IS NOT NULL AND area_m2 IS NOT NULL
              AND bedrooms IS NOT NULL AND bedrooms > 0
            LIMIT 1 OFFSET 3
        """, conn, params=(district,))
        if not df.empty:
            rows.append(df.iloc[0].to_dict())
    conn.close()
    return rows


@st.cache_data(show_spinner=False)
def district_stats() -> pd.DataFrame:
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    # Filtra precios de venta/oficinas (300–30,000) y usa MEDIANA, robusta a outliers
    df = pd.read_sql_query("""
        SELECT district, price_pen, area_m2, bedrooms
        FROM listings
        WHERE price_pen IS NOT NULL AND price_pen BETWEEN 300 AND 30000
          AND area_m2 IS NOT NULL
    """, conn)
    conn.close()
    g = df.groupby("district").agg(
        n=("price_pen", "size"),
        avg_pen=("price_pen", "median"),
        avg_m2=("area_m2", "median"),
        avg_beds=("bedrooms", "mean"),
    ).reset_index()
    for col in ["avg_pen", "avg_m2", "avg_beds"]:
        g[col] = g[col].round(0)
    return g


# ---------------------------------------------------------------------------
# Chart builders
# ---------------------------------------------------------------------------
def build_gauge(deviation_pct: float, verdict: str) -> go.Figure:
    """Speedometer showing how far the listed price deviates from fair price."""
    color = {"buen_precio": "#28a745", "justo": "#f1c40f", "sobrevalorado": "#dc3545"}[verdict]
    val = max(-40, min(40, deviation_pct))
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=val,
        number={"suffix": "%", "font": {"size": 34, "color": color}},
        gauge={
            "axis": {"range": [-40, 40], "tickwidth": 1, "tickvals": [-40, -20, -10, 0, 10, 20, 40]},
            "bar": {"color": color, "thickness": 0.28},
            "borderwidth": 0,
            "steps": [
                {"range": [-40, -10], "color": "#d4edda"},
                {"range": [-10, 10],  "color": "#fff3cd"},
                {"range": [10, 40],   "color": "#f8d7da"},
            ],
            "threshold": {"line": {"color": "#222", "width": 3}, "thickness": 0.8, "value": val},
        },
    ))
    fig.update_layout(height=240, margin=dict(l=20, r=20, t=10, b=10),
                      paper_bgcolor="rgba(0,0,0,0)")
    return fig


def build_histogram(comp_prices, listed_price, fair_price) -> go.Figure:
    """Distribution of comparable listing prices with markers for this listing & fair price."""
    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=comp_prices, nbinsx=24, marker_color="#bdc3c7",
        opacity=0.85, name="Avisos comparables",
    ))
    fig.add_vline(x=fair_price, line_width=3, line_dash="dash", line_color="#1f9d57",
                  annotation_text="Precio justo", annotation_position="top",
                  annotation_font_color="#1f9d57")
    fig.add_vline(x=listed_price, line_width=3, line_color="#dc3545",
                  annotation_text="Tu aviso", annotation_position="top left",
                  annotation_font_color="#dc3545")
    fig.update_layout(
        height=300, margin=dict(l=20, r=20, t=40, b=30),
        xaxis_title="Precio (S/mes)", yaxis_title="N° de avisos",
        showlegend=False, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        bargap=0.05,
    )
    return fig


# ---------------------------------------------------------------------------
# Cuentas y freemium (demo: estado en sesión, sin persistencia real)
# ---------------------------------------------------------------------------
FREE_LIMIT = 2  # análisis gratis para usuarios anónimos

for _k, _v in {"user": None, "free_used": 0}.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v


def _gate_blocked() -> bool:
    """True si el usuario anónimo ya agotó sus análisis gratis."""
    return st.session_state.user is None and st.session_state.free_used >= FREE_LIMIT


def _register_use():
    """Cuenta un análisis si el usuario es anónimo."""
    if st.session_state.user is None:
        st.session_state.free_used += 1


@st.dialog("Crea tu cuenta")
def _signup_dialog():
    st.caption("Empieza gratis. Sin tarjeta.")
    email = st.text_input("Correo", key="su_email", placeholder="tu@correo.com")
    st.text_input("Contraseña", key="su_pass", type="password")
    plan = st.radio("Plan", ["Gratis", "Pago por uso (S/5 / análisis)", "Pro (S/20/mes)"],
                    key="su_plan")
    if st.button("Crear cuenta", type="primary", use_container_width=True):
        if email and "@" in email:
            if plan.startswith("Pro"):
                _plan = "Pro"
            elif plan.startswith("Pago"):
                _plan = "Pago por uso"
            else:
                _plan = "Gratis"
            st.session_state.user = {"email": email, "plan": _plan}
            st.rerun()
        else:
            st.error("Ingresa un correo válido.")


@st.dialog("Iniciar sesión")
def _login_dialog():
    email = st.text_input("Correo", key="li_email", placeholder="tu@correo.com")
    st.text_input("Contraseña", key="li_pass", type="password")
    if st.button("Entrar", type="primary", use_container_width=True):
        if email and "@" in email:
            st.session_state.user = {"email": email, "plan": "Pro"}
            st.rerun()
        else:
            st.error("Ingresa un correo válido.")
    st.caption("¿No tienes cuenta? Usa **Probar gratis** arriba.")


# ── Barra superior: marca + auth ──
_tb_l, _tb_r = st.columns([3, 2])
with _tb_l:
    st.markdown(
        "<div style='font-weight:800;font-family:Plus Jakarta Sans,sans-serif;"
        "font-size:1.15rem;color:#0b3d2c;padding-top:.3rem'>🏠 AlquilerJusto</div>",
        unsafe_allow_html=True,
    )
with _tb_r:
    if st.session_state.user is None:
        _b1, _b2 = st.columns(2)
        if _b1.button("Iniciar sesión", use_container_width=True, key="tb_login"):
            _login_dialog()
        if _b2.button("Probar gratis", type="primary", use_container_width=True, key="tb_signup"):
            _signup_dialog()
    else:
        _u = st.session_state.user
        _b1, _b2 = st.columns([3, 2])
        _b1.markdown(
            f"<div style='text-align:right;padding-top:.35rem;font-size:.86rem'>"
            f"👤 {_u['email']} · <b>{_u['plan']}</b></div>", unsafe_allow_html=True,
        )
        if _b2.button("Cerrar sesión", use_container_width=True, key="tb_logout"):
            st.session_state.user = None
            st.rerun()

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
_model_for_header, _res_for_header = load_model()
st.markdown(f"""
<div class="hero">
    <h1>🏠 AlquilerJusto</h1>
    <p><strong>¿Tu próximo alquiler en Lima está mal preciado?</strong>
    Descúbrelo en 5 segundos, antes de firmar el contrato.</p>
    <span class="pill">✓ {_res_for_header.n_obs:,} alquileres reales analizados en {len(_res_for_header.districts)} distritos de Lima</span>
    <svg class="skyline" viewBox="0 0 1200 70" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
        <g fill="#ffffff">
            <rect x="20"  y="34" width="42" height="36"/><rect x="70"  y="20" width="34" height="50"/>
            <rect x="112" y="42" width="48" height="28"/><rect x="168" y="14" width="30" height="56"/>
            <rect x="206" y="38" width="44" height="32"/><rect x="258" y="26" width="36" height="44"/>
            <rect x="302" y="46" width="50" height="24"/><rect x="360" y="18" width="32" height="52"/>
            <rect x="400" y="40" width="46" height="30"/><rect x="454" y="28" width="34" height="42"/>
            <rect x="496" y="10" width="28" height="60"/><rect x="532" y="44" width="48" height="26"/>
            <rect x="588" y="32" width="38" height="38"/><rect x="634" y="22" width="34" height="48"/>
            <rect x="676" y="46" width="50" height="24"/><rect x="734" y="16" width="30" height="54"/>
            <rect x="772" y="40" width="46" height="30"/><rect x="826" y="30" width="36" height="40"/>
            <rect x="870" y="48" width="48" height="22"/><rect x="926" y="20" width="32" height="50"/>
            <rect x="966" y="38" width="44" height="32"/><rect x="1018" y="26" width="36" height="44"/>
            <rect x="1062" y="44" width="50" height="26"/><rect x="1120" y="18" width="30" height="52"/>
        </g>
    </svg>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Navegación de dos niveles: perfil → herramientas específicas del perfil
# ---------------------------------------------------------------------------
if "profile" not in st.session_state:
    st.session_state.profile = None

MENU_STYLES = {
    "container": {"padding": "0!important", "background-color": "#f8f9fa",
                  "border-radius": "12px", "margin-bottom": "0.5rem"},
    "icon": {"color": "#1f9d57", "font-size": "16px"},
    "nav-link": {"font-size": "14px", "font-weight": "600", "color": "#444",
                 "text-align": "center", "margin": "3px", "--hover-color": "#e8f5ee"},
    "nav-link-selected": {"background-color": "#1f9d57", "color": "white"},
}

selected = None

if st.session_state.profile is None:
    # ── Nivel 1: elegir perfil ──
    st.markdown("### ¿Cómo podemos ayudarte hoy?")
    st.caption("Elige tu perfil y te llevamos a las herramientas pensadas para ti.")

    c_tenant, c_owner = st.columns(2)
    with c_tenant:
        with st.container(border=True):
            st.markdown("#### 🔍 Soy inquilino")
            st.markdown(
                "Quiero saber **si un alquiler está bien preciado** antes de firmar, "
                "o **buscar opciones** que se ajusten a lo que necesito."
            )
            st.markdown("&nbsp;", unsafe_allow_html=True)
            if st.button("Entrar como inquilino →", key="go_tenant",
                         use_container_width=True, type="primary"):
                st.session_state.profile = "inquilino"
                st.rerun()
    with c_owner:
        with st.container(border=True):
            st.markdown("#### 💰 Soy propietario")
            st.markdown(
                "Tengo una propiedad y quiero saber **cuánto pedir** para alquilarla "
                "al mejor precio posible, sin que se quede meses vacía."
            )
            st.markdown("&nbsp;", unsafe_allow_html=True)
            if st.button("Entrar como propietario →", key="go_owner",
                         use_container_width=True, type="primary"):
                st.session_state.profile = "propietario"
                st.rerun()

    st.markdown("---")
    h1, h2, h3 = st.columns(3)
    h1.metric("Avisos analizados", f"{_res_for_header.n_obs:,}")
    h2.metric("Distritos de Lima", f"{len(_res_for_header.districts)}")
    h3.metric("Respuesta en", "< 5 seg")
    st.caption(
        "AlquilerJusto compara cada propiedad contra miles de alquileres reales "
        "del mercado limeño usando un modelo de precios entrenado con datos vivos."
    )
else:
    # ── Nivel 2: sub-menú según el perfil ──
    back_col, _sp = st.columns([1, 4])
    with back_col:
        if st.button("← Cambiar perfil", key="change_profile", use_container_width=True):
            st.session_state.profile = None
            st.rerun()

    if st.session_state.profile == "inquilino":
        selected = option_menu(
            menu_title=None,
            options=["Analizar un alquiler", "Buscar departamento", "Mapa de precios"],
            icons=["clipboard-check", "search-heart", "geo-alt"],
            orientation="horizontal", default_index=0,
            key="menu_inquilino", styles=MENU_STYLES,
        )
    else:
        selected = option_menu(
            menu_title=None,
            options=["Tasar mi propiedad", "Mapa de precios"],
            icons=["cash-coin", "geo-alt"],
            orientation="horizontal", default_index=0,
            key="menu_propietario", styles=MENU_STYLES,
        )

# ===========================================================================
# Analizar un alquiler (inquilino)
# ===========================================================================
if selected == "Analizar un alquiler":
    model, results = load_model()

    # --- Intro ---
    st.markdown("### ¿Algún departamento en mente? Coloca sus datos y te digo si el precio es justo")
    st.markdown(
        "Llena los datos del departamento en el formulario y te decimos si está bien preciado. "
        "¿No tienes uno a la mano? Prueba con un ejemplo real del mercado 👇"
    )

    # --- Example cards ---
    st.markdown("##### Ejemplos reales del mercado")
    examples = load_examples()
    if "example_idx" not in st.session_state:
        st.session_state.example_idx = None

    ex_cols = st.columns(len(examples))
    for i, ex in enumerate(examples):
        label = DISTRICT_LABELS.get(ex["district"], ex["district"])
        am = json.loads(ex.get("amenities_raw") or "{}")
        tags = [k for k, v in am.items() if v]
        tag_str = " · ".join(tags[:3]) if tags else "sin amenidades"
        grad = DISTRICT_GRADIENTS.get(ex["district"], DEFAULT_GRADIENT)
        with ex_cols[i]:
            with st.container(border=True):
                st.markdown(
                    f'<div class="dist-banner" style="background:{grad}">'
                    f'<span class="ico">🏙️</span>'
                    f'<span class="dn">📍 {label}</span></div>',
                    unsafe_allow_html=True,
                )
                st.markdown(f"### S/ {int(ex['price_pen']):,}")
                st.caption(
                    f"{int(ex['area_m2'])} m²  ·  {int(ex['bedrooms'])} dorm  ·  "
                    f"{int(ex['bathrooms'])} baño"
                )
                st.caption(tag_str)
                if st.button("Analizar este →", key=f"ex_{i}", use_container_width=True):
                    st.session_state.example_idx = i
                    st.rerun()

    # Ejemplo cargado (si el usuario eligió uno)
    parsed_listing = (
        examples[st.session_state.example_idx]
        if st.session_state.example_idx is not None else None
    )
    if parsed_listing:
        st.success("✅ Ejemplo cargado — ajusta cualquier campo abajo antes de analizar.")

    st.markdown("---")
    st.markdown("#### ✏️ Completa los datos del departamento")
    st.caption("Llena los datos de tu depto (o ajusta el ejemplo cargado) "
               "y dale a *Analizar precio*.")

    amenities_raw = json.loads(parsed_listing.get("amenities_raw") or "{}") if parsed_listing else {}

    col1, col2 = st.columns(2)
    with col1:
        listed_price = st.number_input(
            "Precio publicado (S/)",
            min_value=300, max_value=50000, step=100,
            value=int(parsed_listing["price_pen"]) if parsed_listing and parsed_listing.get("price_pen") else 2500,
        )
        area = st.number_input(
            "Área (m²)",
            min_value=15, max_value=600, step=5,
            value=int(parsed_listing["area_m2"]) if parsed_listing and parsed_listing.get("area_m2") else 70,
        )
        bedrooms = st.selectbox(
            "Dormitorios",
            options=[0, 1, 2, 3, 4, 5],
            index=parsed_listing.get("bedrooms", 2) if parsed_listing else 2,
        )
        bathrooms = st.selectbox(
            "Baños",
            options=[1, 2, 3, 4],
            index=min((parsed_listing.get("bathrooms", 1) if parsed_listing else 1) - 1, 3),
        )

    with col2:
        district = st.selectbox(
            "Distrito",
            options=list(DISTRICT_META.keys()),
            format_func=lambda d: DISTRICT_META[d]["label"],
            index=list(DISTRICT_META.keys()).index(parsed_listing.get("district", "miraflores"))
                  if parsed_listing and parsed_listing.get("district") in DISTRICT_META else 0,
        )
        floor = st.number_input(
            "Piso",
            min_value=0, max_value=30, step=1,
            value=int(parsed_listing.get("floor") or 1) if parsed_listing else 1,
        )
        st.markdown("**Amenidades**")
        c1, c2 = st.columns(2)
        with c1:
            am_piscina  = st.checkbox("Piscina",   value=bool(amenities_raw.get("piscina")))
            am_gym      = st.checkbox("Gimnasio",  value=bool(amenities_raw.get("gimnasio")))
            am_cochera  = st.checkbox("Cochera",   value=bool(amenities_raw.get("cochera")))
            am_ascensor = st.checkbox("Ascensor",  value=bool(amenities_raw.get("ascensor")))
        with c2:
            am_terraza  = st.checkbox("Terraza",   value=bool(amenities_raw.get("terraza")))
            am_amoblado = st.checkbox("Amoblado",  value=bool(amenities_raw.get("amoblado")))
            am_aire     = st.checkbox("Aire acond.", value=bool(amenities_raw.get("aire")))
            am_seg      = st.checkbox("Seguridad", value=bool(amenities_raw.get("seguridad")))
            am_mar      = st.checkbox("Vista al mar", value=bool(amenities_raw.get("vista_mar")))

    amenities = {
        "piscina": int(am_piscina), "gimnasio": int(am_gym),
        "cochera": int(am_cochera), "ascensor": int(am_ascensor),
        "terraza": int(am_terraza), "amoblado": int(am_amoblado),
        "aire":    int(am_aire),    "seguridad": int(am_seg),
        "vista_mar": int(am_mar),
    }

    if st.session_state.user is None:
        _rem = max(0, FREE_LIMIT - st.session_state.free_used)
        st.caption(f"🎁 Tienes **{_rem}** de {FREE_LIMIT} análisis gratis. "
                   "Crea una cuenta para análisis ilimitados.")

    _do_analyze = st.button("🔍 Analizar precio", type="primary", use_container_width=True)
    if _do_analyze and _gate_blocked():
        st.warning("Llegaste al límite de análisis gratis. Para seguir: "
                   "**S/5 por análisis**, o **Pro S/20/mes** (ilimitado + alertas).")
        if st.button("✨ Crear cuenta gratis", key="gate_signup_analyze", type="primary"):
            _signup_dialog()
    elif _do_analyze:
        _register_use()
        pred = model.predict(
            area_m2=float(area),
            bedrooms=int(bedrooms),
            bathrooms=int(bathrooms),
            district=district,
            floor=int(floor),
            amenities=amenities,
            listed_price_pen=float(listed_price),
        )

        # Verdict box
        css_class = {"buen_precio": "verde", "justo": "amarillo", "sobrevalorado": "rojo"}[pred.verdict]
        label_map  = {
            "buen_precio":   "Buen precio",
            "justo":         "Precio justo",
            "sobrevalorado": "Sobrevalorado",
        }
        st.markdown(f"""
        <div class="verdict-box {css_class}">
            <div class="big-number">{pred.verdict_emoji} {label_map[pred.verdict]}</div>
            <div class="subtitle">
                Precio justo estimado: <strong>S/ {pred.fair_price_pen:,.0f}/mes</strong>
                <span style="opacity:0.8">(rango S/ {pred.fair_price_low:,.0f} – S/ {pred.fair_price_high:,.0f})</span>
                &nbsp;|&nbsp; Desvío: <strong>{pred.deviation_pct:+.1f}%</strong>
                &nbsp;|&nbsp; Percentil: <strong>{pred.percentile:.0f}° de avisos similares</strong>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Gauge + histogram side by side
        g_col, h_col = st.columns([1, 1.4])
        with g_col:
            st.caption("**Desvío vs precio justo**")
            st.plotly_chart(build_gauge(pred.deviation_pct, pred.verdict),
                            use_container_width=True, config={"displayModeBar": False})
        with h_col:
            st.caption("**¿Dónde cae tu aviso en el mercado?**")
            comp_prices_df = get_comparables(district, float(area), int(bedrooms),
                                             float(listed_price), DB_PATH, n=200)
            if not comp_prices_df.empty and len(comp_prices_df) >= 5:
                st.plotly_chart(
                    build_histogram(comp_prices_df["price_pen"].tolist(),
                                    float(listed_price), pred.fair_price_pen),
                    use_container_width=True, config={"displayModeBar": False})
            else:
                st.info("Pocos comparables para graficar la distribución.")

        # Metrics row
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Precio publicado", f"S/ {listed_price:,.0f}")
        m2.metric("Precio justo",     f"S/ {pred.fair_price_pen:,.0f}",
                  delta=f"{pred.deviation_pct:+.1f}%", delta_color="inverse")
        m3.metric("Percentil",        f"{pred.percentile:.0f}°")
        m4.metric("Comparables",      f"{pred.n_comparables} avisos")

        # Price decomposition — "¿Por qué este precio?"
        if pred.contributions:
            st.subheader("🧩 ¿Por qué este precio justo?")
            st.caption(
                "Cómo el modelo construye el precio justo a partir de cada característica "
                "(el distrito se mide vs el promedio de Lima)."
            )
            contrib_fig = go.Figure(go.Waterfall(
                orientation="v",
                measure=["relative"] * len(pred.contributions) + ["total"],
                x=list(pred.contributions.keys()) + ["Precio justo"],
                y=list(pred.contributions.values()) + [0],
                text=[f"S/ {v:+,.0f}" for v in pred.contributions.values()]
                     + [f"S/ {pred.fair_price_pen:,.0f}"],
                textposition="outside",
                connector={"line": {"color": "#bbb"}},
                increasing={"marker": {"color": "#2ecc71"}},
                decreasing={"marker": {"color": "#e67e22"}},
                totals={"marker": {"color": "#1f9d57"}},
            ))
            contrib_fig.update_layout(
                height=340, margin=dict(l=20, r=20, t=20, b=30),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                yaxis_title="Aporte al precio (S/)", showlegend=False,
            )
            st.plotly_chart(contrib_fig, use_container_width=True,
                            config={"displayModeBar": False})

        # Comparable cards
        st.subheader("📋 Avisos comparables en el mercado")
        comps = get_comparables(district, float(area), int(bedrooms),
                                float(listed_price), DB_PATH)
        if not comps.empty:
            cards_html = '<div class="comp-grid">'
            for _, row in comps.iterrows():
                diff = row["diff_vs_aviso_pct"]
                diff_cls  = "comp-diff-down" if diff < 0 else "comp-diff-up"
                diff_text = f"↓ {abs(diff):.0f}% más barato" if diff < 0 else f"↑ {diff:.0f}% más caro"
                url = row.get("url") or "#"
                bath = int(row["bathrooms"]) if pd.notna(row["bathrooms"]) else 1
                cards_html += f"""
                <div class="comp-card">
                    <div class="comp-price">S/ {row['price_pen']:,.0f}/mes</div>
                    <div class="comp-meta">
                        {row['area_m2']:.0f} m²&nbsp;·&nbsp;{int(row['bedrooms'])} dorm&nbsp;·&nbsp;{bath} baño
                    </div>
                    <div class="comp-meta">{DISTRICT_LABELS.get(row['district'], row['district'])}</div>
                    <div class="{diff_cls}">{diff_text}</div>
                    <div class="comp-link">
                        <a href="{url}" target="_blank" rel="noopener">Ver aviso →</a>
                    </div>
                </div>"""
            cards_html += "</div>"
            st.markdown(cards_html, unsafe_allow_html=True)
        else:
            st.info("No se encontraron avisos suficientemente similares en la base de datos.")

        # Methodology note
        with st.expander("¿Cómo se calcula el precio justo?"):
            st.markdown(f"""
            Usamos una **regresión hedónica log-lineal (OLS)** entrenada sobre
            **{results.n_obs:,} avisos reales** de Lima Metropolitana:

            ```
            ln(precio) = β₀ + β₁·ln(m²) + β₂·dormitorios + β₃·baños
                       + β₄·piso + γ·distrito + δ·amenidades + ε
            ```

            **Rendimiento del modelo:** R² = {results.rsquared:.3f} &nbsp;|&nbsp;
            R² ajustado = {results.rsquared_adj:.3f} &nbsp;|&nbsp;
            RMSE ≈ {results.rmse_pct:.1f}%

            Los umbrales de veredicto son ±10% de desvío respecto al precio justo estimado,
            consistentes con el spread natural entre precio de oferta y precio de transacción
            en Lima (~5-10%).
            """)

# ===========================================================================
# Tasar mi propiedad (propietario)
# ===========================================================================
elif selected == "Tasar mi propiedad":
    model, results = load_model()

    st.subheader("💰 ¿Cuánto deberías pedir por tu propiedad?")
    st.caption(
        "Ingresa las características de tu propiedad y te diremos el precio óptimo "
        "de mercado, con estrategias para alquilar rápido o maximizar tu ingreso."
    )

    o1, o2 = st.columns(2)
    with o1:
        o_area = st.number_input("Área (m²)", min_value=15, max_value=600,
                                 step=5, value=80, key="o_area")
        o_beds = st.selectbox("Dormitorios", [0, 1, 2, 3, 4, 5], index=2, key="o_beds")
        o_baths = st.selectbox("Baños", [1, 2, 3, 4], index=1, key="o_baths")
    with o2:
        o_dist = st.selectbox("Distrito", options=list(DISTRICT_META.keys()),
                              format_func=lambda d: DISTRICT_META[d]["label"], key="o_dist")
        o_floor = st.number_input("Piso", min_value=0, max_value=30, step=1,
                                  value=3, key="o_floor")
        st.markdown("**Amenidades de tu propiedad**")
        oc1, oc2 = st.columns(2)
        with oc1:
            o_piscina  = st.checkbox("Piscina", key="o_pisc")
            o_gym      = st.checkbox("Gimnasio", key="o_gym")
            o_cochera  = st.checkbox("Cochera", key="o_coch")
            o_ascensor = st.checkbox("Ascensor", key="o_asc")
        with oc2:
            o_terraza  = st.checkbox("Terraza", key="o_terr")
            o_amoblado = st.checkbox("Amoblado", key="o_amob")
            o_aire     = st.checkbox("Aire acond.", key="o_aire")
            o_seg      = st.checkbox("Seguridad", key="o_seg")
            o_mar      = st.checkbox("Vista al mar", key="o_mar")

    o_amenities = {
        "piscina": int(o_piscina), "gimnasio": int(o_gym),
        "cochera": int(o_cochera), "ascensor": int(o_ascensor),
        "terraza": int(o_terraza), "amoblado": int(o_amoblado),
        "aire":    int(o_aire),    "seguridad": int(o_seg),
        "vista_mar": int(o_mar),
    }

    if st.session_state.user is None:
        _rem = max(0, FREE_LIMIT - st.session_state.free_used)
        st.caption(f"🎁 Tienes **{_rem}** de {FREE_LIMIT} cálculos gratis. "
                   "Crea una cuenta para uso ilimitado.")

    _do_price = st.button("💰 Calcular precio óptimo", type="primary", use_container_width=True)
    if _do_price and _gate_blocked():
        st.warning("Llegaste al límite gratis. Para seguir: "
                   "**S/5 por tasación**, o **Pro S/20/mes** (ilimitado + alertas).")
        if st.button("✨ Crear cuenta gratis", key="gate_signup_price", type="primary"):
            _signup_dialog()
    elif _do_price:
        _register_use()
        pred = model.predict(
            area_m2=float(o_area), bedrooms=int(o_beds), bathrooms=int(o_baths),
            district=o_dist, floor=int(o_floor), amenities=o_amenities,
        )
        fair = pred.fair_price_pen

        # Comparable price distribution for percentile positioning
        comps = get_comparables(o_dist, float(o_area), int(o_beds), fair, DB_PATH, n=200)
        comp_prices = comps["price_pen"] if not comps.empty else pd.Series([fair])

        def _pct_at(price):
            return float((comp_prices < price).mean() * 100)

        # Three pricing strategies anchored on the fair price
        rapido     = round(fair * 0.93, 0)
        recomendado = fair
        premium    = round(fair * 1.10, 0)

        st.markdown(f"""
        <div class="verdict-box verde">
            <div class="big-number">💰 Precio de mercado: S/ {fair:,.0f}/mes</div>
            <div class="subtitle">
                Rango de confianza: S/ {pred.fair_price_low:,.0f} – S/ {pred.fair_price_high:,.0f}
                &nbsp;|&nbsp; basado en {pred.n_comparables or len(comp_prices)} propiedades comparables
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("#### Elige tu estrategia de publicación")
        s1, s2, s3 = st.columns(3)
        strategies = [
            (s1, "🟢 Alquila rápido", rapido,
             "Por debajo del mercado. Atrae interés de inmediato, ideal si necesitas alquilar pronto."),
            (s2, "🟡 Recomendado", recomendado,
             "Precio justo de mercado. El mejor balance entre ingreso y tiempo de alquiler."),
            (s3, "🔴 Maximiza ingreso", premium,
             "Premium sobre el mercado. Mayor ingreso mensual, pero puede tardar más en alquilarse."),
        ]
        for col, title, price, desc in strategies:
            with col:
                with st.container(border=True):
                    st.markdown(f"**{title}**")
                    st.markdown(f"### S/ {price:,.0f}")
                    st.caption(f"Más caro que el {_pct_at(price):.0f}% del mercado")
                    st.caption(desc)

        # Distribution chart with recommended price marked
        if len(comp_prices) >= 5:
            st.markdown("#### Tu propiedad vs el mercado")
            fig = go.Figure()
            fig.add_trace(go.Histogram(x=comp_prices.tolist(), nbinsx=24,
                                       marker_color="#bdc3c7", opacity=0.85))
            fig.add_vline(x=rapido, line_width=2, line_dash="dot", line_color="#28a745",
                          annotation_text="Rápido", annotation_position="top")
            fig.add_vline(x=recomendado, line_width=3, line_dash="dash", line_color="#1f9d57",
                          annotation_text="Recomendado", annotation_position="top")
            fig.add_vline(x=premium, line_width=2, line_dash="dot", line_color="#dc3545",
                          annotation_text="Premium", annotation_position="top")
            fig.update_layout(height=300, margin=dict(l=20, r=20, t=40, b=30),
                              xaxis_title="Precio (S/mes)", yaxis_title="N° de propiedades",
                              showlegend=False, paper_bgcolor="rgba(0,0,0,0)",
                              plot_bgcolor="rgba(0,0,0,0)", bargap=0.05)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        # Why this price — decomposition
        if pred.contributions:
            with st.expander("🧩 ¿Por qué este precio? Ver desglose"):
                contrib_fig = go.Figure(go.Waterfall(
                    orientation="v",
                    measure=["relative"] * len(pred.contributions) + ["total"],
                    x=list(pred.contributions.keys()) + ["Precio de mercado"],
                    y=list(pred.contributions.values()) + [0],
                    text=[f"S/ {v:+,.0f}" for v in pred.contributions.values()]
                         + [f"S/ {fair:,.0f}"],
                    textposition="outside",
                    connector={"line": {"color": "#bbb"}},
                    increasing={"marker": {"color": "#2ecc71"}},
                    decreasing={"marker": {"color": "#e67e22"}},
                    totals={"marker": {"color": "#1f9d57"}},
                ))
                contrib_fig.update_layout(height=320, margin=dict(l=20, r=20, t=20, b=30),
                                          paper_bgcolor="rgba(0,0,0,0)",
                                          plot_bgcolor="rgba(0,0,0,0)",
                                          yaxis_title="Aporte (S/)", showlegend=False)
                st.plotly_chart(contrib_fig, use_container_width=True,
                                config={"displayModeBar": False})

        # Competing listings
        if not comps.empty:
            st.markdown("#### Propiedades similares publicadas ahora")
            cards_html = '<div class="comp-grid">'
            for _, row in comps.head(5).iterrows():
                url = row.get("url") or "#"
                bath = int(row["bathrooms"]) if pd.notna(row["bathrooms"]) else 1
                cards_html += f"""
                <div class="comp-card">
                    <div class="comp-price">S/ {row['price_pen']:,.0f}/mes</div>
                    <div class="comp-meta">
                        {row['area_m2']:.0f} m²&nbsp;·&nbsp;{int(row['bedrooms'])} dorm&nbsp;·&nbsp;{bath} baño
                    </div>
                    <div class="comp-meta">{DISTRICT_LABELS.get(row['district'], row['district'])}</div>
                    <div class="comp-link">
                        <a href="{url}" target="_blank" rel="noopener">Ver aviso →</a>
                    </div>
                </div>"""
            cards_html += "</div>"
            st.markdown(cards_html, unsafe_allow_html=True)

# ===========================================================================
# Buscar departamento (inquilino) — asistente conversacional
# ===========================================================================
elif selected == "Buscar departamento":
    st.subheader("🔎 ¿Buscas un departamento? Dime qué necesitas")
    st.caption(
        "Escríbelo como hablarías normalmente y te muestro opciones reales del mercado. "
        "Ej: «2 dormitorios en Miraflores hasta S/ 3,500» o «depto en Barranco entre 70 y 90 m²»."
    )

    def _render_listing_cards(df):
        cards = '<div class="comp-grid">'
        for _, row in df.iterrows():
            url = row.get("url") or "#"
            bath = int(row["bathrooms"]) if pd.notna(row["bathrooms"]) else 1
            label = ASSISTANT_DISTRICTS.get(row["district"], row["district"])
            cards += f"""
            <div class="comp-card">
                <div class="comp-price">S/ {row['price_pen']:,.0f}/mes</div>
                <div class="comp-meta">{row['area_m2']:.0f} m²&nbsp;·&nbsp;{int(row['bedrooms'])} dorm&nbsp;·&nbsp;{bath} baño</div>
                <div class="comp-meta">{label}</div>
                <div class="comp-link"><a href="{url}" target="_blank" rel="noopener">Ver aviso →</a></div>
            </div>"""
        cards += "</div>"
        return cards

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = [{
            "role": "assistant",
            "text": "¡Hola! 👋 Cuéntame qué departamento buscas: distrito, dormitorios, "
                    "metraje y tu presupuesto. Yo te muestro las mejores opciones del mercado.",
            "df": None,
        }]

    # Render history
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"], avatar="🏠" if msg["role"] == "assistant" else None):
            st.markdown(msg["text"])
            if msg.get("df") is not None and not msg["df"].empty:
                st.markdown(_render_listing_cards(msg["df"]), unsafe_allow_html=True)

    prompt = st.chat_input("Ej: 2 dorm en Surco hasta S/ 4,000")
    if prompt:
        st.session_state.chat_history.append({"role": "user", "text": prompt, "df": None})

        filters = parse_query(prompt)
        if not filters:
            reply = ("No logré entender los criterios. Prueba indicando distrito, "
                     "dormitorios, metraje o presupuesto. Ej: «3 dorm en San Isidro hasta S/ 6,000».")
            df = None
        else:
            df, notes = relax_search(filters, DB_PATH, limit=6)
            crit = []
            if filters.get("district"):
                crit.append(ASSISTANT_DISTRICTS.get(filters["district"], filters["district"]))
            if filters.get("bedrooms") is not None:
                crit.append(f"{filters['bedrooms']} dorm")
            if filters.get("area_min") or filters.get("area_max"):
                lo = f"{filters.get('area_min', 0):.0f}" if filters.get("area_min") else "0"
                hi = f"{filters.get('area_max'):.0f}" if filters.get("area_max") else "∞"
                crit.append(f"{lo}–{hi} m²")
            if filters.get("price_min") or filters.get("price_max"):
                lo = f"S/{filters.get('price_min'):,.0f}" if filters.get("price_min") else "S/0"
                hi = f"S/{filters.get('price_max'):,.0f}" if filters.get("price_max") else "sin tope"
                crit.append(f"{lo}–{hi}")
            crit_str = ", ".join(crit) if crit else "tu búsqueda"

            if df is not None and not df.empty:
                reply = f"Encontré **{len(df)} opciones** para {crit_str}:"
                if notes:
                    reply += f"\n\n_Ajusté la búsqueda: {'; '.join(notes)}._"
            else:
                reply = (f"No encontré avisos para {crit_str} ni relajando los filtros. "
                         "Intenta ampliar el presupuesto o el distrito.")
                df = None

        st.session_state.chat_history.append({"role": "assistant", "text": reply, "df": df})
        st.rerun()

# ===========================================================================
# Mapa de precios
# ===========================================================================
elif selected == "Mapa de precios":
    st.subheader("Precio típico por distrito (S/mes)")
    st.caption("Mediana del alquiler por distrito (robusta a avisos atípicos).")

    stats = district_stats()

    m = folium.Map(location=[-12.11, -77.02], zoom_start=12, tiles="CartoDB positron")

    for _, row in stats.iterrows():
        d = row["district"]
        if d not in DISTRICT_META:
            continue
        meta  = DISTRICT_META[d]
        color = _price_color(row["avg_pen"])

        folium.CircleMarker(
            location=[meta["lat"], meta["lon"]],
            radius=max(18, min(40, row["avg_pen"] / 200)),
            color=color, fill=True, fill_color=color, fill_opacity=0.7,
            popup=folium.Popup(
                f"<b>{meta['label']}</b><br>"
                f"Precio típico: <b>S/ {row['avg_pen']:,.0f}</b><br>"
                f"Área típica: {row['avg_m2']:.0f} m²<br>"
                f"Avisos: {int(row['n'])}",
                max_width=200,
            ),
            tooltip=f"{meta['label']}: S/ {row['avg_pen']:,.0f}",
        ).add_to(m)

        folium.Marker(
            location=[meta["lat"], meta["lon"]],
            icon=folium.DivIcon(
                html=f'<div style="font-size:11px;font-weight:bold;color:#333;'
                     f'text-align:center;white-space:nowrap;">'
                     f'S/ {row["avg_pen"]:,.0f}</div>',
                icon_size=(120, 20),
                icon_anchor=(60, -18),
            ),
        ).add_to(m)

    st_folium(m, width="100%", height=480)

    st.markdown("---")
    st.subheader("Estadísticas por distrito")
    stats_display = stats.copy()
    stats_display["Distrito"] = stats_display["district"].map(
        lambda d: DISTRICT_META.get(d, {}).get("label", d)
    )
    stats_display = stats_display.rename(columns={
        "n": "Avisos", "avg_pen": "Precio típico (S/)",
        "avg_m2": "Área típica (m²)", "avg_beds": "Dorm. prom.",
    })
    st.dataframe(
        stats_display[["Distrito", "Avisos", "Precio típico (S/)", "Área típica (m²)", "Dorm. prom."]],
        use_container_width=True, hide_index=True,
    )
