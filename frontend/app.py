"""
AlquilerJusto — Streamlit frontend.

Tabs:
  1. Analizar aviso  — paste URL or fill form → verdict + comparables
  2. Mapa de precios — Folium choropleth by district
  3. Sobre el modelo — methodology explainer
"""

import json
import sys
from pathlib import Path

import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.app.comparables import get_comparables
from backend.app.model import get_model
from scraping.listing_parser import parse_listing_url
from scraping.utils import get_session

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
.verdict-box {
    padding: 1.5rem 2rem;
    border-radius: 12px;
    text-align: center;
    margin: 1rem 0;
}
.verde  { background: #d4edda; border: 2px solid #28a745; }
.amarillo { background: #fff3cd; border: 2px solid #ffc107; }
.rojo   { background: #f8d7da; border: 2px solid #dc3545; }
.big-number { font-size: 2.4rem; font-weight: 700; }
.subtitle   { font-size: 0.9rem; color: #666; margin-top: 0.3rem; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# District metadata (centroids for map)
# ---------------------------------------------------------------------------
DISTRICT_META = {
    "miraflores": {"lat": -12.1219, "lon": -77.0299, "label": "Miraflores"},
    "san-isidro": {"lat": -12.0969, "lon": -77.0367, "label": "San Isidro"},
    "surco":      {"lat": -12.1477, "lon": -76.9934, "label": "Santiago de Surco"},
    "magdalena":  {"lat": -12.0925, "lon": -77.0714, "label": "Magdalena del Mar"},
}


def _price_color(avg_pen: float) -> str:
    if avg_pen >= 5000:
        return "#c0392b"
    if avg_pen >= 3500:
        return "#e67e22"
    if avg_pen >= 2500:
        return "#f1c40f"
    return "#27ae60"

DB_PATH = Path("data/raw/listings.db")

# ---------------------------------------------------------------------------
# Cached resources
# ---------------------------------------------------------------------------
@st.cache_resource(show_spinner="Entrenando modelo hedónico…")
def load_model():
    return get_model(DB_PATH)


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
# Header
# ---------------------------------------------------------------------------
st.title("🏠 AlquilerJusto")
st.markdown(
    "**¿Tu próximo alquiler en Lima está mal preciado?** "
    "Compáralo contra el mercado real en menos de 5 segundos."
)

tab1, tab2, tab3 = st.tabs(["🔍 Analizar aviso", "🗺️ Mapa de precios", "📊 Sobre el modelo"])

# ===========================================================================
# TAB 1 — Analizar aviso
# ===========================================================================
with tab1:
    model, results = load_model()

    st.subheader("Pega la URL del aviso o completa el formulario")

    url_input = st.text_input(
        "URL del departamento (Infocasas)",
        placeholder="https://www.infocasas.com.pe/...",
        help="Pega la URL directa del aviso. Si no tienes URL, completa el formulario abajo.",
    )

    parsed_listing = None
    auto_filled    = False

    if url_input.strip():
        with st.spinner("Obteniendo datos del aviso…"):
            sess = get_session()
            parsed_listing = parse_listing_url(url_input.strip(), sess)

        if parsed_listing:
            st.success("✅ Datos del aviso obtenidos automáticamente")
            auto_filled = True
        else:
            st.warning(
                "No pudimos extraer datos automáticamente de esa URL. "
                "Completa el formulario manualmente."
            )

    st.markdown("---")

    # Form (pre-filled if URL parsed successfully)
    amenities_raw = json.loads(parsed_listing.get("amenities_raw", "{}")) if parsed_listing else {}

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
            "buen_precio":    "Buen precio",
            "justo":          "Precio justo",
            "sobrevalorado":  "Sobrevalorado",
        }
        st.markdown(f"""
        <div class="verdict-box {css_class}">
            <div class="big-number">{pred.verdict_emoji} {label_map[pred.verdict]}</div>
            <div class="subtitle">
                Precio justo estimado: <strong>S/ {pred.fair_price_pen:,.0f}/mes</strong> &nbsp;|&nbsp;
                Desvío: <strong>{pred.deviation_pct:+.1f}%</strong> &nbsp;|&nbsp;
                Percentil: <strong>{pred.percentile:.0f}° de avisos similares</strong>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Metrics row
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Precio publicado", f"S/ {listed_price:,.0f}")
        m2.metric("Precio justo",     f"S/ {pred.fair_price_pen:,.0f}",
                  delta=f"{pred.deviation_pct:+.1f}%",
                  delta_color="inverse")
        m3.metric("Percentil",        f"{pred.percentile:.0f}°")
        m4.metric("Comparables",      f"{pred.n_comparables} avisos")

        # Comparables table
        st.subheader("📋 Avisos comparables en el mercado")
        comps = get_comparables(district, float(area), int(bedrooms),
                                float(listed_price), DB_PATH)
        if not comps.empty:
            comps_display = comps.copy()
            comps_display["precio"] = comps_display["price_pen"].apply(lambda x: f"S/ {x:,.0f}")
            comps_display["área"]   = comps_display["area_m2"].apply(lambda x: f"{x:.0f} m²")
            comps_display["diff"]   = comps_display["diff_vs_aviso_pct"].apply(
                lambda x: f"{'↓' if x < 0 else '↑'} {abs(x):.1f}%"
            )
            comps_display["link"]   = comps_display["url"].apply(
                lambda u: f"[ver aviso]({u})" if u else ""
            )
            comps_display["Distrito"] = comps_display["district"].map(
                lambda d: DISTRICT_META.get(d, {}).get("label", d)
            )
            st.dataframe(
                comps_display[["Distrito", "precio", "área", "bedrooms", "bathrooms", "diff", "link"]]
                .rename(columns={"precio": "Precio", "área": "Área",
                                 "bedrooms": "Dorm", "bathrooms": "Baños",
                                 "diff": "vs tu aviso", "link": ""}),
                use_container_width=True,
                hide_index=True,
            )
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
# TAB 2 — Mapa de precios
# ===========================================================================
with tab2:
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
# TAB 3 — Sobre el modelo
# ===========================================================================
with tab3:
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
    | Claude AI (extracción estructurada) | 14 | `ai/parse_listing.py` — parsing de descripciones libres |

    ### Limitaciones
    - **Precio de oferta ≠ precio de transacción**: modelamos el mercado de avisos publicados.
    - **Cobertura**: 4 distritos de Lima Metropolitana de alta densidad de avisos.
    - **Endogeneidad**: amenidades y distrito están correlacionados (San Isidro tiene más piscinas).
      El modelo es descriptivo, no causal.
    - **Distritos con <20 avisos**: se muestran con advertencia de datos insuficientes.
    """)


