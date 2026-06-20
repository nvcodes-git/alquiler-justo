# CLAUDE.md — AlquilerJusto

> Project memory for Claude Code. Auto-loaded at session start.
> Last updated: 2026-06-20 (sábado).
> Project deadline: miércoles 24 de junio de 2026, 7:55 AM (slot #3).

---

## What this is

Final project for *Data Science con Python 2026-I* at Universidad del Pacífico (course: Alexander Quispe). Deliverable is a working startup MVP, demoed LIVE during a 10-minute pitch slot (7 min + 3 min Q&A). Grading is 0-20 vigesimal. **Solo founder**: no teammates, all roles covered by me + AI agents (Claude Code = pair programmer, this file = project memory).

---

## The product (one-liner — defend this verbatim in the pitch)

> **AlquilerJusto te dice si tu próximo alquiler en Lima está mal preciado en 5 segundos, comparándolo contra 10,000+ avisos vivos del mercado.**

**User flow**: paste a Urbania URL → in <5s return:
1. Predicted fair price (`X soles/mes`)
2. Percentile vs comparables within `(distrito, m² bucket ±20%, bedrooms)`
3. Verdict: 🟢 buen precio / 🟡 justo / 🔴 sobrevalorado
4. 5 comparable listings as evidence

---

## The insight (the non-obvious bit — Q&A gold)

Existing portals (Urbania, Adondevivir, Properati) live off keeping users browsing for weeks. They have zero incentive to tell users if a specific listing is overpriced — that would shorten time-on-site. We combine large-scale scraping + Claude API parsing free-text fields + a hedonic regression to give the verdict portals refuse to give. We validate externally against listing days-on-market: overpriced listings sit ~3x longer.

**This is the killer talking point**: "Validamos nuestro modelo contra tiempo-en-mercado. Los avisos que marcamos como sobrevalorados se quedan en promedio 47 días publicados; los justos, 18." If we can produce that stat from real data, the pitch is gold.

---

## Methodology decisions (LOCKED — do not change without strong reason)

### Pricing model: hybrid hedonic + percentile

**Engine** (defensible academically): hedonic OLS log-linear regression.

```
ln(Precio) = β₀ + β₁·log(m²) + β₂·dormitorios + β₃·baños
           + β₄·antigüedad + β₅·piso + Σγ_d·distrito_d + Σδ_a·amenity_a + ε
```

- Robust standard errors (HC1).
- Minimum 20 observations per distrito for stable dummy coefficient.
- Target R² > 0.5 minimum, stretch goal 0.7+. Report RMSE alongside.
- Use `statsmodels.api.OLS` with `cov_type='HC1'`.

**UI display layer** (intuitive for the user): percentile rank within `(distrito, m² bucket ±20%, # bedrooms)`. Show "estás más caro que el X% de avisos similares en tu zona".

**Mispricing thresholds**:
- Deviation < −10% OR percentile < 25 → **buen precio** (verde)
- Deviation within ±10% → **justo** (amarillo)
- Deviation > +10% OR percentile > 75 → **sobrevalorado** (rojo)

**Why ±10%**: floor of natural asking-vs-transaction spread in Lima (~5-10%). Below 10% we can't claim mispricing with confidence.

### Caveats to address proactively in Q&A

1. **Asking price ≠ transaction price**: position explicitly as "precio justo de mercado abierto", not valuación oficial.
2. **Endogeneity** between amenities and distrito (cochera/piscina correlate with rich barrios). Acknowledge: model is descriptive, not causal.
3. **Selection bias**: only see still-listed properties. Mitigation: scrape daily.
4. **Small-sample distritos**: if <20 obs, show "data insuficiente" — never fabricate.

---

## Tech stack

| Layer | Tool | File |
|---|---|---|
| Frontend | Streamlit + streamlit-folium | `frontend/app.py` |
| Scraping | requests + BeautifulSoup | `scraping/urbania.py` |
| AI parsing | Claude API (`claude-sonnet-4-6`) | `ai/parse_listing.py` |
| Modeling | statsmodels OLS | `backend/app/model.py` |
| Comparables | pandas percentile groupby | `backend/app/comparables.py` |
| Maps | GeoPandas + Folium | inline in `app.py` |
| Storage | SQLite (samples) + Parquet (raw) | `data/` |
| Geocoding | distrito centroid for v1, Nominatim if time | `scraping/utils.py` |
| Deploy | Streamlit Community Cloud (free) | — |

**V1 scope**: scrape only Miraflores, Surco, San Isidro, Magdalena (high listing density). Expansion to other distritos in roadmap.

---

## Course tools used (rubric requires ≥2; we have 3)

| Tool | Course lecture | Where in code |
|---|---|---|
| Web scraping (requests + BeautifulSoup) | 2-3 | `scraping/urbania.py` |
| GeoPandas + Folium + Streamlit | 3-7 | `frontend/app.py` |
| Claude AI document AI (free text → JSON) | 14 | `ai/parse_listing.py` |

Optional 4th: crewAI agent for daily monitoring + WhatsApp alerts via OpenClaw. **DO NOT BUILD until everything else works** — sell it in the roadmap section.

---

## Commit schedule (rubric: 3 puntos for "commits distribuidos")

**Saturday 2026-06-20** — scaffolding
- [x] README.md, .gitignore, .env.example, requirements.txt
- [x] Directory structure scaffold
- [ ] First Urbania scraper for single listing detail page
- [ ] Pagination + collect 500+ listings to SQLite

**Sunday 2026-06-21** — data + model + first deploy
- [ ] EDA notebook over scraped sample
- [ ] Claude API parser (free text → JSON features)
- [ ] Hedonic OLS notebook v1
- [ ] Streamlit skeleton + Folium distrito map
- [ ] **First deploy to Streamlit Cloud** (public URL live, even if rough)

**Monday 2026-06-22** — killer feature + polish
- [ ] "Paste this URL" verdict feature
- [ ] Comparable listings panel
- [ ] Days-on-market external validation chart
- [ ] UX pass: empty states, loading, error handling
- [ ] 3 user tests with interview participants
- [ ] README final + architecture diagram + screenshots
- [ ] 2-3 min Loom demo video
- [ ] Pitch deck (10 slides max)

**Wednesday 2026-06-24 07:55**: present (slot #3, day 2).

---

## User research (rubric: 3 puntos for "validación")

5 interviews minimum. Document in `docs/research/entrevistas.md` with date, name or pseudonym, and **literal quotes**.

**Target mix**:
- 2-3 people apartment-hunting now (find via Facebook groups "Departamentos Lima", "Alquileres Miraflores")
- 1-2 real estate brokers (same groups, search "agente inmobiliario")
- Optional: 1 landlord

**Three questions only**:
1. ¿Cuánto tiempo te tomó tu última búsqueda y cuántos departamentos viste?
2. ¿Cómo decides si un precio es justo?
3. ¿Pagarías 30 PEN/mes por una herramienta que te diga si un aviso está bien preciado vs el mercado?

---

## Pitch dossier — 14 YC sections (fill in `docs/pitch.md`)

1. One-liner — (above)
2. Founder + founder-market fit (economics student in Lima, lives the rental market reality)
3. Problem — specific segment: people hunting apartments in metropolitan Lima
4. Solution & insight — (above)
5. Why now? — Claude API made free-text parsing trivial; Streamlit + Folium = production web maps in hours; previously this would have been a 6-month NLP+frontend project
6. Market: TAM (mercado de alquiler residencial Peru via INEI/BCRP), SAM (Lima Metropolitana), SOM (zonas de alta rotación: Miraflores, San Isidro, Surco, Magdalena, San Miguel, Pueblo Libre, Barranco — first 12 months target)
7. Competition + moat: Urbania/Adondevivir/Properati (no fair-price), Properati index (basic), do-nothing (Excel/instinct). Moat: dataset propio + parser tuneado + validación días-en-mercado.
8. Product: demo URL, screenshots, architecture diagram, repo link
9. Business model: freemium (mapa gratis + 3 verdicts/mes), Premium 30 PEN/mes (verdicts ilimitados + alertas), Pro corredores 90 PEN/mes (dashboard + leads). Contribution margin per user: ~0.50 PEN/mes en tokens Claude (verify).
10. GTM: first 10 (amigos + Facebook groups), first 100 (alianzas con grupos WhatsApp de búsqueda + Instagram con price reveals semanales), first 1000 (SEO "alquiler [distrito] precio justo" + TikTok tours de zonas)
11. Tracción: interview quotes + beta users count + waitlist
12. Roadmap 3/6/12 months
13. Risks: regulatorio (scraping), técnico (model calibration en distritos low-density), mercado (willingness to pay) + mitigations
14. The ask: "Si tuviera 30s con un inversionista: 50K USD para 6 meses runway + datos premium + 1 hire part-time, milestone que desbloquea = 500 usuarios pagados + alianza con 2 corredoras grandes"

---

## Rubric weights (total 20)

| Criterion | Weight |
|---|---|
| Problema & validación | 3 |
| Solución & insight | 2 |
| Mercado & modelo de negocio | 3 |
| **Prototipo / demo funcional** | **5** — heaviest |
| Repositorio GitHub | 3 |
| Uso de herramientas IA del curso | 2 |
| Pitch & sustentación | 2 |

Oral defense swings ±2 individual points.

---

## What NOT to do (PDF rules)

- ✗ No private repo (evaluator can't read)
- ✗ No secrets committed — check `git log -p | grep -iE 'api_key|secret|token'` before push
- ✗ No single giant commit the day before
- ✗ No `.env` file committed (only `.env.example`)
- ✗ No demo that requires evaluator to clone and configure
- ✗ No README copied from default template

---

## Conventions for Claude Code in this project

- Code comments in English; user-facing strings in Spanish
- Type hints on public functions
- Rate-limit scrapers: 1-2s between requests, respect `robots.txt`
- Keep scraped data samples small in repo (`data/samples/`, max ~50 rows); full datasets in `data/raw/` which is gitignored
- Use `python-dotenv` to load `ANTHROPIC_API_KEY`; never hardcode
- Streamlit: keep `frontend/app.py` thin (UI only), push business logic to `backend/app/`
- For any model decision (thresholds, features, transformations), default to what's locked in above; flag changes for confirmation
- When in doubt about a numerical claim (R², spread, market size), say "verify before pitch" rather than fabricating

---

## Open questions / TODO before pitch

- [ ] Verify INEI / BCRP have public stats on rental market size for TAM slide
- [ ] Decide if we ship Adondevivir scraper or keep it as roadmap (depends on Urbania output quality)
- [ ] Validate that hedonic R² is acceptable on real data (if <0.5, simplify model + lean harder on percentile approach in UI)
- [ ] Confirm Claude API per-listing cost ≤ 0.01 PEN to keep contribution margin honest
- [ ] Find 2 backup pitch participants in case main interviewees flake
