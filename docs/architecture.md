# AlquilerJusto — Arquitectura del Sistema

## Diagrama de flujo

```
┌─────────────────────────────────────────────────────────────────┐
│                     FUENTE DE DATOS                             │
│                                                                 │
│  Infocasas.pe  ──── __NEXT_DATA__ JSON ────►  scraping/        │
│  (11 distritos)      (sin JS rendering)        infocasas.py    │
└────────────────────────────────┬────────────────────────────────┘
                                 │ 1,475 avisos
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                     ALMACENAMIENTO                              │
│                                                                 │
│  data/listings.db  (SQLite)                                     │
│  ├── listings: price_pen, area_m2, bedrooms, bathrooms,        │
│  │             floor, district, amenities_raw, ...             │
│  └── data/samples/: muestra 60 filas (en repo)                 │
└────────────────────────────────┬────────────────────────────────┘
                                 │
              ┌──────────────────┴──────────────────┐
              │                                     │
              ▼                                     ▼
┌─────────────────────────┐           ┌─────────────────────────┐
│   MODELO HEDÓNICO       │           │   CLAUDE API PARSER     │
│   backend/app/model.py  │           │   ai/parse_listing.py   │
│                         │           │                         │
│  OLS log-lineal (HC1)   │           │  Texto libre → JSON     │
│  ln(P) = f(m², dorms,   │           │  "2 dorm, cochera,      │
│  baños, piso, distrito, │           │   piso 5, S/2200"       │
│  amenidades)            │           │        ↓                │
│                         │           │  {bedrooms: 2,          │
│  R² = 0.824 · n = 1,445   │           │   cochera: true, ...}   │
│  RMSE ≈ 25%             │           │                         │
└────────────┬────────────┘           └────────────┬────────────┘
             │                                     │
             │         features estructurados      │
             └────────────────┬────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     PREDICCIÓN + VEREDICTO                      │
│                                                                 │
│  1. Fair price = exp(OLS prediction)                            │
│  2. Deviation % = (listed - fair) / fair × 100                 │
│  3. Percentile vs comparables (mismo distrito, m² ±25%, dorms) │
│  4. Veredicto:                                                  │
│     🟢 buen precio   → deviation < −10% OR percentile < 25     │
│     🟡 justo         → deviation dentro de ±10%                │
│     🔴 sobrevalorado → deviation > +10% OR percentile > 75     │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FRONTEND (Streamlit)                        │
│                     frontend/app.py                             │
│                                                                 │
│  Tab 1: Analizar aviso                                          │
│  ├── Cards de ejemplos reales (4 distritos)                    │
│  ├── Parser Claude (texto libre → form pre-llenado)            │
│  ├── Formulario editable (precio, m², dorms, amenidades...)    │
│  └── Resultado: veredicto + 5 cards comparables con links      │
│                                                                 │
│  Tab 2: Mapa de precios                                         │
│  └── Folium CircleMarker por distrito (precio promedio)        │
│                                                                 │
│  Tab 3: Sobre el modelo                                         │
│  └── Coeficientes OLS + metodología + limitaciones            │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
                  https://alquiler-justo.streamlit.app
                  (Streamlit Community Cloud · free tier)
```

## Stack tecnológico

| Capa | Tecnología | Archivo |
|---|---|---|
| Scraping | `requests` + `BeautifulSoup` | `scraping/infocasas.py` |
| AI parsing | Claude API (`claude-haiku-4-5`) | `ai/parse_listing.py` |
| Storage | SQLite + Parquet (gitignored) | `data/listings.db` |
| Modelo | `statsmodels` OLS (HC1) | `backend/app/model.py` |
| Comparables | `pandas` percentile groupby | `backend/app/comparables.py` |
| Mapa | `folium` + `streamlit-folium` | `frontend/app.py` |
| Frontend | `Streamlit` | `frontend/app.py` |
| Deploy | Streamlit Community Cloud | — |

## Flujo de datos (detalle)

```
Infocasas HTML
      │
      ├─► BeautifulSoup parse
      │         │
      │         └─► script#__NEXT_DATA__ → JSON
      │                   │
      │                   └─► props.pageProps.fetchResult.searchFast.data[]
      │                               │
      │                               └─► normalize_listing() → dict
      │                                           │
      │                                           └─► SQLite INSERT OR IGNORE
      │
      └─► [texto libre de descripción]
                │
                └─► Claude Haiku API
                          │
                          └─► JSON estructurado
                                    │
                                    └─► claude_to_model_features()
                                                │
                                                └─► OLSModel.predict()
```

## Coeficientes del modelo (referencia rápida)

```
ln(precio) = ≈8.3                    ← base (Barranco = referencia, sin amenidades)
           + 0.716 · ln(m²)          ← elasticidad área
           + 0.042 · dormitorios
           + 0.085 · baños
           + 0.003 · piso
           + 0.000 · [Miraflores]    ← ~referencia (Barranco)
           + 0.013 · [San Isidro]    ← distrito top por mediana
           - 0.047 · [Surco]
           + 0.053 · cochera         ← +5%
           + 0.079 · ascensor        ← +8%
           + 0.074 · amoblado        ← +8%
           + 0.088 · terraza
           + 0.087 · gimnasio
           + ...
```
