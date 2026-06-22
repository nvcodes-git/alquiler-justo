# Guion del pitch — AlquilerJusto (7 min + 3 min Q&A)

> Deck: [pitch_deck.pdf](pitch_deck.pdf) · Demo: https://alquiler-justo.streamlit.app
> Estructura sugerida por el PDF: problema (1 min) · solución & demo (3-4 min) · mercado & modelo (1 min) · tracción & ask (1 min).
> **Ten un video de respaldo del demo por si falla internet.**

| Slide | Tiempo | Qué decir (idea central) |
|---|---|---|
| 1. Portada | 0:00–0:20 | "Soy Nicolás. AlquilerJusto te dice si tu próximo alquiler en Lima está mal preciado en 5 segundos." |
| 2. Problema | 0:20–1:20 | Buscar depto toma semanas; nadie te dice si *ese* aviso está bien preciado; decides a ciegas y pagas de más. |
| 3. Insight | 1:20–2:00 | El golpe: los portales **no pueden** decírtelo sin matar su negocio de ads (incumbent's dilemma). Nuestro incentivo está alineado. |
| 4. Solución + **DEMO** | 2:00–4:30 | **Abre la app en vivo.** Pega un aviso → veredicto 🟢🟡🔴 + comparables. Muestra también el lado propietario y el desglose "por qué". |
| 5. Producto (dos lados) | (dentro del demo) | Recalca: mismo motor, inquilino + propietario. Marketplace de dos lados. |
| 6. Modelo | 4:30–5:15 | Hedónico OLS, 1,475 avisos, R²=0.82. Menciona el rigor: vista al mar +10%, descarté parques por no significativo. |
| 7. Mercado | 5:15–5:45 | TAM/SAM/SOM con cifras. Proptech es categoría VC en LatAm. |
| 8. Negocio | 5:45–6:15 | Freemium **funcionando en el demo**; el dinero está en Pro corredores (S/90, ROI claro). Margen ~99%. |
| 9. Competencia & moat | 6:15–6:40 | Nadie da el veredicto; moat = dataset propio + incentivo no copiable. |
| 10. Tracción & ask | 6:40–7:00 | Producto vivo + entrevistas. The ask: USD 50K, 6 meses, milestone 500 pagados + 2 corredoras. |

## Posibles preguntas del Q&A y respuestas

- **"¿El precio de oferta no es distinto al de transacción?"** → Correcto; lo posicionamos como *precio justo de mercado abierto*, no tasación oficial. El spread oferta-transacción en Lima es ~5-10%, por eso el umbral de veredicto es ±10%.
- **"¿No es una caja negra?"** → No: la app desglosa cada precio por factor (distrito, m², amenidades). Modelo OLS interpretable, no red neuronal.
- **"¿De dónde salen los datos? ¿Es en vivo?"** → Scraping de Infocasas; hoy es un snapshot (DB incluida en el repo), y refrescarlo a diario es un job programado del roadmap. Infocasas bloquea IPs de data center, por eso scrapeamos local.
- **"¿Por qué no Urbania?"** → Cloudflare lo bloquea; está en el roadmap vía navegador real. Infocasas ya da 11 distritos limpios.
- **"¿Cuál es el moat real?"** → El incentivo: el incumbente no puede copiar sin canibalizar sus ads + dataset propio que crece con scraping diario.
- **"¿Validación?"** → N entrevistas (inquilinos + corredor); X dijeron que pagarían. *(completar con datos reales)*
