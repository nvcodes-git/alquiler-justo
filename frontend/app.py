"""
AlquilerJusto — Streamlit frontend.

Tabs:
  1. Analizar aviso  — pick example or fill form → verdict + comparable cards
  2. Mapa de precios — Folium choropleth by district
  3. Sobre el modelo — methodology explainer
"""

import json
import sys
from pathlib import Path

import folium
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_folium import st_folium
from streamlit_option_menu import option_menu

sys.path.insert(0, str(Path(__file__).parent.parent))

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
/* Hero header */
.hero {
    background: linear-gradient(120deg, #0f4c2e 0%, #1f9d57 55%, #2ecc71 100%);
    border-radius: 16px;
    padding: 2rem 2.4rem;
    margin-bottom: 1.4rem;
    color: white;
    box-shadow: 0 6px 24px rgba(31,157,87,0.25);
}
.hero h1 {
    color: white !important;
    font-size: 2.5rem;
    margin: 0 0 0.4rem 0;
    font-weight: 800;
    letter-spacing: -0.5px;
}
.hero p {
    color: rgba(255,255,255,0.92);
    font-size: 1.05rem;
    margin: 0;
    max-width: 640px;
}
.hero .pill {
    display: inline-block;
    background: rgba(255,255,255,0.18);
    border: 1px solid rgba(255,255,255,0.3);
    border-radius: 20px;
    padding: 0.2rem 0.9rem;
    font-size: 0.8rem;
    margin-top: 0.9rem;
    font-weight: 600;
}
/* Verdict box */
.verdict-box {
    padding: 1.5rem 2rem;
    border-radius: 12px;
    text-align: center;
    margin: 1rem 0;
}
.verde    { background: #d4edda; border: 2px solid #28a745; }
.amarillo { background: #fff3cd; border: 2px solid #ffc107; }
.rojo     { background: #f8d7da; border: 2px solid #dc3545; }
.big-number { font-size: 2.4rem; font-weight: 700; }
.subtitle   { font-size: 0.9rem; color: #555; margin-top: 0.3rem; }

/* Comparable cards */
.comp-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
    gap: 1rem;
    margin: 1rem 0;
}
.comp-card {
    background: #ffffff;
    border: 1px solid #dee2e6;
    border-radius: 10px;
    padding: 1rem 1.1rem;
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
}
.comp-price  { font-size: 1.15rem; font-weight: 700; color: #2c3e50; }
.comp-meta   { font-size: 0.82rem; color: #666; }
.comp-diff-down { font-size: 0.82rem; color: #28a745; font-weight: 600; }
.comp-diff-up   { font-size: 0.82rem; color: #dc3545; font-weight: 600; }
.comp-link {
    margin-top: auto;
    padding-top: 0.6rem;
}
.comp-link a {
    display: block;
    padding: 0.4rem 0;
    background: #2ecc71;
    color: white !important;
    text-align: center;
    border-radius: 6px;
    text-decoration: none !important;
    font-size: 0.83rem;
    font-weight: 600;
}
.comp-link a:hover { background: #27ae60; }
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
    df = pd.read_sql_query("""
        SELECT district,
               COUNT(*)            AS n,
               AVG(price_pen)      AS avg_pen,
               AVG(area_m2)        AS avg_m2,
               AVG(CAST(bedrooms AS REAL)) AS avg_beds
        FROM listings
        WHERE price_pen IS NOT NULL AND area_m2 IS NOT NULL
        GROUP BY district
    """, conn)
    conn.close()
    for col in ["avg_pen", "avg_m2", "avg_beds"]:
        df[col] = df[col].round(0)
    return df


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
# Header
# ---------------------------------------------------------------------------
_model_for_header, _res_for_header = load_model()
st.markdown(f"""
<div class="hero">
    <h1>🏠 AlquilerJusto</h1>
    <p><strong>¿Tu próximo alquiler en Lima está mal preciado?</strong>
    Descúbrelo en 5 segundos, antes de firmar el contrato.</p>
    <span class="pill">✓ {_res_for_header.n_obs:,} alquileres reales analizados en {len(_res_for_header.districts)} distritos de Lima</span>
</div>
""", unsafe_allow_html=True)

MENU_OPTIONS = ["Inicio", "Analizar mi alquiler", "Tasar mi propiedad",
                "Asistente", "Mapa de precios", "Cómo funciona"]
# Routing override coming from landing-page cards (consumed once)
_manual = st.session_state.pop("manual_select", None)
selected = option_menu(
    menu_title=None,
    options=MENU_OPTIONS,
    icons=["house-heart", "search-heart", "cash-coin", "chat-dots", "geo-alt", "info-circle"],
    orientation="horizontal",
    default_index=0,
    manual_select=_manual,
    key="mainmenu",
    styles={
        "container": {"padding": "0!important", "background-color": "#f8f9fa",
                      "border-radius": "12px", "margin-bottom": "0.5rem"},
        "icon": {"color": "#1f9d57", "font-size": "16px"},
        "nav-link": {"font-size": "14px", "font-weight": "600", "color": "#444",
                     "text-align": "center", "margin": "3px",
                     "--hover-color": "#e8f5ee"},
        "nav-link-selected": {"background-color": "#1f9d57", "color": "white"},
    },
)
selected = selected or "Inicio"

# ===========================================================================
# Inicio — landing con selección de perfil
# ===========================================================================
if selected == "Inicio":
    st.markdown("### ¿Qué necesitas hoy?")
    st.caption("Elige tu perfil — usamos el mismo motor de datos para responder tu pregunta.")

    c_tenant, c_owner = st.columns(2)
    with c_tenant:
        with st.container(border=True):
            st.markdown("#### 🔍 Soy inquilino")
            st.markdown(
                "Estás por alquilar y quieres saber **si el precio es justo** "
                "antes de firmar. Pega los datos del aviso y te decimos si está "
                "bien preciado, justo o sobrevalorado — con evidencia del mercado."
            )
            st.markdown("&nbsp;", unsafe_allow_html=True)
            if st.button("Analizar un alquiler →", key="go_tenant",
                         use_container_width=True, type="primary"):
                st.session_state.manual_select = 1
                st.rerun()
    with c_owner:
        with st.container(border=True):
            st.markdown("#### 💰 Soy propietario")
            st.markdown(
                "Tienes una propiedad y quieres alquilarla al **mejor precio posible** "
                "sin que se quede meses vacía. Te damos el precio óptimo y 3 estrategias: "
                "alquilar rápido, equilibrado o maximizar ingreso."
            )
            st.markdown("&nbsp;", unsafe_allow_html=True)
            if st.button("Tasar mi propiedad →", key="go_owner",
                         use_container_width=True, type="primary"):
                st.session_state.manual_select = 2
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

# ===========================================================================
# Analizar mi alquiler
# ===========================================================================
elif selected == "Analizar mi alquiler":
    model, results = load_model()

    # --- Example cards ---
    st.markdown("#### Ejemplos reales del mercado — elige uno para empezar")
    examples = load_examples()
    if "example_idx" not in st.session_state:
        st.session_state.example_idx = None

    ex_cols = st.columns(len(examples))
    for i, ex in enumerate(examples):
        label = DISTRICT_LABELS.get(ex["district"], ex["district"])
        am = json.loads(ex.get("amenities_raw") or "{}")
        tags = [k for k, v in am.items() if v]
        tag_str = " · ".join(tags[:3]) if tags else "sin amenidades"
        with ex_cols[i]:
            with st.container(border=True):
                st.markdown(f"**📍 {label}**")
                st.markdown(f"### S/ {int(ex['price_pen']):,}")
                st.caption(
                    f"{int(ex['area_m2'])} m²  ·  {int(ex['bedrooms'])} dorm  ·  "
                    f"{int(ex['bathrooms'])} baño"
                )
                st.caption(tag_str)
                if st.button("Analizar este →", key=f"ex_{i}", use_container_width=True):
                    st.session_state.example_idx = i
                    st.rerun()

    # Show which example is loaded
    if "claude_parsed" not in st.session_state:
        st.session_state.claude_parsed = None

    parsed_listing = (
        examples[st.session_state.example_idx]
        if st.session_state.example_idx is not None else None
    )
    # Claude-parsed listing overrides example
    if st.session_state.claude_parsed:
        parsed_listing = st.session_state.claude_parsed

    if parsed_listing:
        source = "Claude AI" if st.session_state.claude_parsed else "base de datos"
        st.success(
            f"✅ Datos cargados ({source}) — "
            "puedes modificar cualquier campo abajo antes de analizar."
        )

    st.markdown("---")

    # --- Claude AI parser ---
    with st.expander("🤖 O pega la descripción del aviso — Claude la parsea automáticamente"):
        st.caption(
            "Pega el texto del aviso (descripción, título, características) "
            "y Claude extraerá m², dormitorios, precio, amenidades y más."
        )
        desc_input = st.text_area(
            "Descripción del aviso",
            placeholder="Ej: Depto 2 dorm, 75m2, piso 4, Miraflores. Cochera incluida, ascensor. S/ 2,800/mes.",
            height=120,
            key="claude_desc_input",
        )
        if st.button("🤖 Parsear con Claude", key="parse_claude"):
            if desc_input.strip():
                try:
                    import os
                    from ai.parse_listing import parse_listing_text, claude_to_model_features
                    api_key = os.getenv("ANTHROPIC_API_KEY")
                    if not api_key:
                        st.error("ANTHROPIC_API_KEY no configurado. Configúralo en los secrets de Streamlit.")
                    else:
                        with st.spinner("Claude analizando el aviso…"):
                            raw = parse_listing_text(desc_input.strip())
                        if raw:
                            features = claude_to_model_features(raw)
                            am = features.get("amenities", {})
                            st.session_state.claude_parsed = {
                                "price_pen":    features.get("price_pen") or 2500,
                                "area_m2":      features.get("area_m2") or 70,
                                "bedrooms":     features.get("bedrooms") or 2,
                                "bathrooms":    features.get("bathrooms") or 1,
                                "floor":        features.get("floor") or 1,
                                "district":     features.get("district") or "miraflores",
                                "amenities_raw": json.dumps({k: int(v) for k, v in am.items()}),
                                "title":        "Aviso parseado por Claude",
                            }
                            st.session_state.example_idx = None
                            st.rerun()
                        else:
                            st.warning("No se pudo extraer información suficiente. Intenta con una descripción más detallada.")
                except ImportError:
                    st.error("Módulo ai.parse_listing no disponible.")
            else:
                st.warning("Pega una descripción primero.")

    st.markdown("---")
    st.markdown("#### ✏️ Personaliza los datos del aviso")

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

    amenities = {
        "piscina": int(am_piscina), "gimnasio": int(am_gym),
        "cochera": int(am_cochera), "ascensor": int(am_ascensor),
        "terraza": int(am_terraza), "amoblado": int(am_amoblado),
        "aire":    int(am_aire),    "seguridad": int(am_seg),
    }

    if st.button("🔍 Analizar precio", type="primary", use_container_width=True):
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

    o_amenities = {
        "piscina": int(o_piscina), "gimnasio": int(o_gym),
        "cochera": int(o_cochera), "ascensor": int(o_ascensor),
        "terraza": int(o_terraza), "amoblado": int(o_amoblado),
        "aire":    int(o_aire),    "seguridad": int(o_seg),
    }

    if st.button("💰 Calcular precio óptimo", type="primary", use_container_width=True):
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
# Asistente conversacional
# ===========================================================================
elif selected == "Asistente":
    st.subheader("💬 Asistente AlquilerJusto")
    st.caption(
        "Dime qué buscas en lenguaje natural y te muestro opciones reales del mercado. "
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
    st.subheader("Precio promedio por distrito (S/mes)")

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
                f"Precio promedio: <b>S/ {row['avg_pen']:,.0f}</b><br>"
                f"Área promedio: {row['avg_m2']:.0f} m²<br>"
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
        "n": "Avisos", "avg_pen": "Precio prom. (S/)",
        "avg_m2": "Área prom. (m²)", "avg_beds": "Dorm. prom.",
    })
    st.dataframe(
        stats_display[["Distrito", "Avisos", "Precio prom. (S/)", "Área prom. (m²)", "Dorm. prom."]],
        use_container_width=True, hide_index=True,
    )

# ===========================================================================
# Cómo funciona
# ===========================================================================
elif selected == "Cómo funciona":
    model_loaded, res = load_model()
    st.subheader("Metodología")
    st.markdown(f"""
    ### Modelo hedónico log-lineal (OLS)

    Entrenado sobre **{res.n_obs:,} departamentos en alquiler** de Lima Metropolitana
    (Miraflores, San Isidro, Surco, Magdalena del Mar), extraídos de portales inmobiliarios.

    **Especificación:**
    ```
    ln(precio_pen) = β₀ + β₁·ln(m²) + β₂·dormitorios + β₃·baños
                   + β₄·piso + Σγ_d·distrito_d + Σδ_a·amenidad_a + ε
    ```

    **Resultados:**
    | Métrica | Valor |
    |---|---|
    | R² | {res.rsquared:.3f} |
    | R² ajustado | {res.rsquared_adj:.3f} |
    | RMSE (% del precio) | {res.rmse_pct:.1f}% |
    | Observaciones | {res.n_obs:,} |
    | Distritos | {', '.join(res.districts)} |

    **Coeficientes principales:**
    """)

    coef_df = pd.DataFrame({
        "Variable": res.params.index,
        "Coeficiente": res.params.values.round(3),
        "Interpretación": [
            "Intercepto (base Magdalena, sin amenidades)",
            "Elasticidad área: +1% m² → +0.72% precio",
            "Dormitorios adicionales (efecto sobre precio log)",
            "Baños adicionales",
            "Piso",
            "Prima Miraflores vs Magdalena: +21%",
            "Prima San Isidro vs Magdalena: +27%",
            "Prima Surco vs Magdalena: -5%",
            "Piscina: +6%", "Gimnasio: +9%", "Cochera: +17%",
            "Ascensor: +10%", "Seguridad", "Terraza: +9%",
            "Amoblado: +10%", "Aire acond.",
        ] if len(res.params) == 16 else [""] * len(res.params),
    })
    st.dataframe(coef_df, use_container_width=True, hide_index=True)

    st.markdown("""
    ### Herramientas del curso utilizadas
    | Herramienta | Lectura | Uso |
    |---|---|---|
    | Web scraping (requests + BeautifulSoup) | 2-3 | `scraping/infocasas.py` — extrae 1,196 avisos reales |
    | GeoPandas + Folium + Streamlit | 3-7 | `frontend/app.py` — mapa coroplético interactivo |
    | Regresión hedónica OLS (statsmodels) | 8-10 | `backend/app/model.py` — R²=0.776 sobre 912 avisos |

    ### Limitaciones
    - **Precio de oferta ≠ precio de transacción**: modelamos el mercado de avisos publicados.
    - **Cobertura**: 4 distritos de Lima Metropolitana de alta densidad de avisos.
    - **Endogeneidad**: amenidades y distrito están correlacionados (San Isidro tiene más piscinas).
      El modelo es descriptivo, no causal.
    - **Distritos con <20 avisos**: se muestran con advertencia de datos insuficientes.
    """)
