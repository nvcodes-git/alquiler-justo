# AlquilerJusto

> ¿Tu próximo alquiler en Lima está mal preciado? Te lo decimos en 5 segundos.

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://alquiler-justo.streamlit.app)

---

## El problema

Buscar departamento en Lima toma entre 4 y 8 semanas. No es por falta de oferta — Urbania, Adondevivir y Properati tienen más de 30,000 avisos activos — sino porque ningún portal te dice si el precio de un aviso específico es justo. Decidir se vuelve apuesta a ciegas: ¿2,500 soles por un 2 dorm de 70 m² en Miraflores es caro, justo o regalado?

## La solución

AlquilerJusto scrapea avisos de Infocasas.pe, los normaliza automáticamente (m², dormitorios, amenities, piso, distrito), y los compara contra un modelo hedónico entrenado sobre 1,196 avisos reales de Lima. Pegás el URL o completás el formulario y en menos de 5 segundos obtenés:

- **Precio justo de mercado** estimado por el modelo
- **Percentil** contra avisos similares en la misma zona
- **Veredicto**: 🟢 buen precio / 🟡 justo / 🔴 sobrevalorado
- **5 comparables reales** como evidencia

## Demo

**URL**: https://alquiler-justo.streamlit.app

## Arquitectura

```
Infocasas.pe ──scraping──► SQLite (1,196 avisos)
                                │
                          OLS hedónico
                     ln(precio) ~ ln(m²) + dorms + baños
                     + piso + distrito + amenities
                          R² = 0.776  n = 912
                                │
                        Streamlit frontend
                    ┌───────────┴──────────────┐
              Analizar aviso           Mapa Folium
           (veredicto + comparables)  (precios por distrito)
```

## Herramientas del curso utilizadas

| Herramienta | Lectura | Dónde en el código |
|---|---|---|
| Web scraping (requests + BeautifulSoup) | 2-3 | `scraping/infocasas.py` |
| GeoPandas + Folium + Streamlit | 3-7 | `frontend/app.py` |
| Regresión hedónica (statsmodels OLS) | 8-10 | `backend/app/model.py` |

## Resultados del modelo

| Métrica | Valor |
|---|---|
| R² | 0.792 |
| R² ajustado | 0.788 |
| RMSE | ~27% del precio medio |
| Observaciones | 1,433 avisos |
| Distritos | 11 distritos de Lima Metropolitana |

**Coeficientes principales** (log-lineal, errores robustos HC1):
- `log(m²)` → +0.72 (elasticidad precio-área)
- San Isidro → +24% vs Magdalena (referencia)
- Miraflores → +19%
- Cochera → +16%
- Ascensor → +9%

## Estructura del repo

```
alquiler-justo/
├── frontend/app.py          # Streamlit UI (3 tabs)
├── backend/app/
│   ├── model.py             # OLS hedónico + predicción
│   └── comparables.py       # top-5 avisos similares
├── scraping/
│   ├── infocasas.py         # scraper principal (1,196 avisos)
│   ├── listing_parser.py    # fetch de URL individual
│   └── utils.py             # SQLite helpers + rate limiter
├── data/
│   ├── listings.db          # 1,196 avisos (SQLite, ~1.8 MB)
│   └── samples/             # muestra 60 filas para el repo
├── notebooks/
│   └── 01_eda.ipynb         # EDA: distribuciones, correlaciones, residuos
└── docs/                    # pitch deck, entrevistas, arquitectura
```

## Cómo correrlo localmente

```bash
git clone https://github.com/nvcodes-git/alquiler-justo.git
cd alquiler-justo
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run frontend/app.py
```

No requiere API key para el flujo principal. La DB (`data/listings.db`) ya está incluida en el repo.

## Roadmap

- [x] Scraper Infocasas (1,196 avisos, 4 distritos)
- [x] Modelo hedónico OLS — R² = 0.776
- [x] Streamlit con formulario + mapa Folium
- [x] Deploy público en Streamlit Cloud
- [ ] Parser de URL para cualquier aviso de Infocasas
- [ ] Alertas diarias por WhatsApp (crewAI + OpenClaw)
- [ ] Expansión a Adondevivir y Properati
- [ ] Seguimiento días-en-mercado (validación externa del modelo)
- [ ] Dashboard para corredores inmobiliarios

## Founder

Nicolás Villar — Economía, Universidad del Pacífico. Proyecto final *Data Science con Python 2026-I* (Prof. Alexander Quispe).

## Licencia

MIT
