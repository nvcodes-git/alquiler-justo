# AlquilerJusto

> ¿Tu próximo alquiler en Lima está mal preciado? Te lo decimos en 5 segundos.

## El problema

Buscar departamento en Lima toma entre 4 y 8 semanas. No es por falta de oferta —Urbania, Adondevivir y Properati tienen más de 30,000 avisos activos— sino porque ningún portal te dice si el precio de un aviso específico es justo. Decidir se vuelve apuesta a ciegas: ¿1,200 USD por un 2 dorm de 65m² en Magdalena es caro, justo o regalado?

## La solución

AlquilerJusto scrapea diariamente avisos de los portales principales, los pasa por Claude para extraer features estructurados del texto libre del aviso (m², dormitorios, antigüedad, amenities, piso), y los compara contra un modelo hedónico entrenado sobre miles de avisos comparables. Pegás el URL de un aviso y devolvemos en 5 segundos: precio justo de mercado, percentil contra comparables de la zona, y veredicto: buen precio / justo / sobrevalorado.

## Demo

URL: https://alquiler-justo.streamlit.app *(deploy en progreso)*
Video: *(próximamente)*

## Arquitectura

- **Scraping**: `requests` + `BeautifulSoup` contra Urbania (Miraflores, Surco, San Isidro, Magdalena para v1)
- **Parsing**: Claude API (`claude-sonnet-4-6`) extrae JSON estructurado del texto libre
- **Modelo**: regresión hedónica log-lineal (OLS con error estándar robusto) + comparables por percentiles dentro de (distrito, bucket de m², dormitorios)
- **Validación externa**: correlación entre desvío predicho y días-en-mercado del aviso
- **Visualización**: GeoPandas + Folium → mapa coroplético por distrito en Streamlit
- **Frontend**: Streamlit desplegado en Streamlit Cloud

## Herramientas del curso utilizadas

| Herramienta | Lectura | Dónde en el código |
|---|---|---|
| Web scraping (requests + BeautifulSoup) | 2-3 | `scraping/urbania.py` |
| Geocoding + GeoPandas + Folium + Streamlit | 3-7 | `frontend/app.py` |
| Claude AI para extracción estructurada | 14 | `ai/parse_listing.py` |

## Cómo correrlo localmente

```bash
git clone https://github.com/nico-2010/alquiler-justo.git
cd alquiler-justo
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # completar ANTHROPIC_API_KEY
streamlit run frontend/app.py
```

## Estructura del repo

```
alquiler-justo/
├── frontend/         # Streamlit app
├── backend/          # lógica de modelo y API interna
├── scraping/         # scrapers por portal
├── ai/               # prompts y parsers basados en Claude
├── data/             # muestras chicas (datasets grandes ignorados)
├── notebooks/        # EDA y modelo hedónico
└── docs/             # arquitectura, investigación de usuarios, deck
```

## Roadmap

- [x] Scaffold inicial del repo
- [ ] Scraper Urbania para 4 distritos clave
- [ ] Parser con Claude API → JSON estructurado
- [ ] Modelo hedónico v1 (target: R² > 0.65)
- [ ] Streamlit con mapa por distrito
- [ ] Feature "¿está bien preciado este URL?" con veredicto en menos de 5s
- [ ] Validación del modelo contra días-en-mercado
- [ ] Expansión a Adondevivir y Properati

## Founder

Solo founder. Estudiante de Economía en la Universidad del Pacífico. Cubro los roles clásicos apoyándome en agentes: Claude Code como pair-programmer del backend y los scrapers, Codex para piezas de frontend, y un agente crewAI para automatizar la recolección diaria de avisos.

## Licencia

MIT
