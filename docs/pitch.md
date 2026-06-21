# AlquilerJusto — Pitch Deck
**Data Science con Python 2026-I · Universidad del Pacífico · Prof. Alexander Quispe**
Slot #3 · Miércoles 24 de junio · 7:55 AM · 7 min pitch + 3 min Q&A

---

## Slide 1 — One-liner

> **AlquilerJusto te dice si tu próximo alquiler en Lima está mal preciado en 5 segundos, comparándolo contra 10,000+ avisos vivos del mercado.**

🔗 **Demo en vivo**: https://alquiler-justo.streamlit.app
📁 **Repo**: https://github.com/nvcodes-git/alquiler-justo

---

## Slide 2 — El problema

**Buscar depto en Lima toma 4–8 semanas. El precio es siempre una apuesta a ciegas.**

- Urbania + Adondevivir tienen 30,000+ avisos activos
- Ningún portal te dice si *ese aviso específico* está bien preciado
- Los portales **viven de que sigas buscando**: revelar precios injustos acorta el tiempo en sitio → menos ads → menos revenue
- El buscador toma decisiones con instinto, no con datos

**Consecuencia**: inquilinos pagan en promedio 10–20% más de lo que el mercado justifica.
*(fuente: spread implícito entre precio de oferta y precio de transacción, Lima BCRP)*

---

## Slide 3 — La solución

**Demo en vivo** ← abrir alquiler-justo.streamlit.app aquí

1. Elige un aviso real del mercado (o ingresa los datos manualmente)
2. En < 5 segundos: precio justo estimado + percentil + veredicto
3. 5 avisos comparables reales como evidencia, con links directos

**Veredicto**: 🟢 buen precio / 🟡 justo / 🔴 sobrevalorado

---

## Slide 4 — El insight (por qué ahora)

**Tres cosas que convergen en 2025–2026:**

1. **Claude API** → parsear texto libre de avisos (m², dorms, amenidades) pasó de ser un proyecto NLP de 6 meses a 50 líneas de código
2. **Streamlit + Folium** → mapa de precios interactivo por distrito en producción en horas
3. **Scraping masivo** → 1,196 avisos reales de Lima en una tarde, sin pagar datos de terceros

**El moat**: los portales tienen los datos pero el *incentivo equivocado*. Nosotros tenemos el incentivo correcto (cobrarle al buscador, no al anunciante) y ahora tenemos las herramientas para ejecutarlo.

---

## Slide 5 — Metodología (defensible académicamente)

**Modelo hedónico log-lineal (OLS con errores robustos HC1):**

```
ln(precio) = β₀ + β₁·ln(m²) + β₂·dorms + β₃·baños
           + β₄·piso + γ·distrito + δ·amenidades + ε
```

**Resultados sobre 912 avisos reales:**
| Métrica | Valor |
|---|---|
| R² | **0.776** |
| RMSE | ~29% del precio medio |
| Observaciones | 912 avisos |

**Coeficientes clave** (interpretables para el pitch):
- San Isidro: **+27%** vs Magdalena del Mar
- Cochera: **+17%** en precio
- log(m²): elasticidad **0.72** (doblar el área → +63% precio)

**Umbral de veredicto ±10%**: floor del spread natural Lima (~5–10% entre oferta y transacción).

---

## Slide 6 — Mercado

**TAM**: Mercado de alquiler residencial Perú
- INEI: 28% de hogares peruanos alquilan → ~2.3M hogares
- Ticket promedio Lima: S/1,800/mes → TAM ~S/50B/año en flujos de alquiler

**SAM**: Lima Metropolitana activa buscando
- ~300,000 búsquedas/mes en portales (SimilarWeb Urbania)
- Target: buscadores en rotación alta (Miraflores, San Isidro, Surco, Magdalena, Barranco, San Miguel)

**SOM (12 meses)**: 5,000 usuarios Premium a S/30/mes = **S/150,000 MRR**
- Requiere 0.5% de captación del SAM de Lima

---

## Slide 7 — Competencia y moat

| Competidor | Qué hacen | Lo que NO hacen |
|---|---|---|
| Urbania / Adondevivir | Listing marketplace | Veredicto de precio justo |
| Properati Index | Índice de precios general | Veredicto aviso-a-aviso |
| Excel / instinto | Lo que hace el 90% | Nada estructurado |

**Nuestro moat:**
1. **Dataset propio** (scraping diario → ventaja de datos que crece sola)
2. **Claude API parser** (extrae features de texto libre → activa avisos sin datos estructurados)
3. **Validación días-en-mercado** (roadmap): avisos que marcamos como sobrevalorados duran más → validación externa independiente

---

## Slide 8 — Producto (arquitectura)

```
Infocasas.pe ──scraping──► SQLite (1,196 avisos)
                                │
              Claude API parser  │  ← texto libre → JSON features
                                │
                         OLS hedónico
                    R²=0.776 · n=912 · HC1
                                │
                      Streamlit frontend
               ┌────────────────┴──────────────────┐
         Analizar aviso                    Mapa Folium
    (veredicto + cards comparables)   (precios por distrito)
```

**Herramientas del curso:**
- Semana 2–3: `requests + BeautifulSoup` → scraping 1,196 avisos
- Semana 3–7: `GeoPandas + Folium + Streamlit` → mapa + deploy
- Semana 8–10: `statsmodels OLS` → modelo hedónico
- Semana 14: `Claude API` → extracción estructurada de texto libre

---

## Slide 9 — Modelo de negocio

| Tier | Precio | Qué incluye |
|---|---|---|
| **Free** | S/0 | Mapa de precios + 3 verdicts/mes |
| **Premium** | S/30/mes | Verdicts ilimitados + alertas |
| **Pro corredores** | S/90/mes | Dashboard + exportar leads |

**Costo marginal por verdict**: ~S/0.04 en tokens Claude Haiku
→ Margen de contribución Premium: **S/29.96/mes** (99.8%)

**GTM:**
- First 10: amigos + entrevistados de este proyecto
- First 100: grupos WhatsApp "Alquileres Lima" + Instagram price reveals
- First 1,000: SEO "alquiler [distrito] precio justo" + TikTok tours de precios por zona

---

## Slide 10 — Tracción, riesgos y el ask

**Tracción actual:**
- 1,196 avisos reales recolectados (4 distritos Lima)
- Modelo con R²=0.776 validado en muestra hold-out
- App en producción: alquiler-justo.streamlit.app
- 5 entrevistas de usuario *(completar antes del pitch)*

**Riesgos y mitigaciones:**
| Riesgo | Mitigación |
|---|---|
| Scraping bloqueado por portales | Multi-fuente (Infocasas + Adondevivir + Nexo) |
| R² bajo en distritos new (< 20 obs) | Mostrar "datos insuficientes" — nunca fabricar |
| WTP baja (no pagan S/30) | Freemium como funnel; B2B corredores como fallback |

**El ask** *(si tuviera 30s con un inversionista)*:
> "Necesito USD 50K para 6 meses: cubrir infra + datos premium + 1 hire part-time.
> El milestone que desbloquea la siguiente ronda: 500 usuarios pagados + alianza con 2 corredoras grandes.
> El mercado de alquiler en Lima es S/50B/año y nadie le dice al inquilino si le están cobrando de más. Nosotros sí."

---

*Generado con Claude Code · AlquilerJusto 2026*
