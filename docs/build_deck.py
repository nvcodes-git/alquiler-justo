"""
Genera el pitch deck (HTML → PDF) de AlquilerJusto.

Uso:
    python docs/build_deck.py            # escribe docs/pitch_deck.html
    # luego: chromium --headless --print-to-pdf=docs/pitch_deck.pdf docs/pitch_deck.html

Diseño 16:9, identidad de marca verde. 10 slides.
"""
from pathlib import Path

GREEN_900 = "#0b3d2c"
GREEN_700 = "#13794f"
EMERALD = "#2ecc71"
AMBER = "#f5a623"
INK = "#18241f"
CREAM = "#f5f8f4"

CSS = f"""
* {{ margin:0; padding:0; box-sizing:border-box; }}
@page {{ size: 13.333in 7.5in; margin: 0; }}
body {{ font-family:'Liberation Sans','DejaVu Sans',Arial,sans-serif; color:{INK}; }}
.slide {{
    width:13.333in; height:7.5in; padding:0.85in 1in; position:relative;
    page-break-after:always; overflow:hidden; background:{CREAM};
    display:flex; flex-direction:column;
}}
.slide:last-child {{ page-break-after:auto; }}
.bar {{ position:absolute; top:0; left:0; right:0; height:14px;
        background:linear-gradient(90deg,{GREEN_900},{EMERALD}); }}
.kicker {{ color:{GREEN_700}; font-weight:800; letter-spacing:2px;
           text-transform:uppercase; font-size:15px; margin-bottom:10px; }}
h1 {{ font-size:54px; font-weight:800; line-height:1.05; color:{INK}; }}
h2 {{ font-size:40px; font-weight:800; line-height:1.1; color:{INK}; margin-bottom:18px; }}
p.lead {{ font-size:24px; line-height:1.4; color:#2c3a34; max-width:10in; }}
ul {{ list-style:none; margin-top:10px; }}
li {{ font-size:23px; line-height:1.5; margin:12px 0; padding-left:34px; position:relative; color:#26332e; }}
li::before {{ content:"›"; position:absolute; left:0; color:{EMERALD}; font-weight:800; font-size:26px; }}
.big {{ font-size:30px; font-weight:800; color:{GREEN_700}; }}
.foot {{ position:absolute; bottom:0.45in; left:1in; right:1in; display:flex;
         justify-content:space-between; font-size:13px; color:#7b8a83; }}
.pill {{ display:inline-block; background:{GREEN_700}; color:#fff; font-weight:700;
         padding:8px 18px; border-radius:30px; font-size:18px; margin:6px 8px 0 0; }}
.metrics {{ display:flex; gap:26px; margin-top:24px; }}
.metric {{ background:#fff; border:1px solid rgba(11,61,44,.1); border-radius:16px;
           padding:22px 26px; box-shadow:0 6px 18px rgba(11,61,44,.08); }}
.metric .v {{ font-size:40px; font-weight:800; color:{GREEN_700}; }}
.metric .l {{ font-size:15px; color:#5a6b63; margin-top:4px; }}
table {{ border-collapse:collapse; margin-top:18px; font-size:19px; width:100%; }}
th,td {{ text-align:left; padding:11px 14px; border-bottom:1px solid #dde7e1; }}
th {{ color:{GREEN_700}; font-weight:800; }}
.demo {{ background:linear-gradient(135deg,{GREEN_900},{EMERALD}); color:#fff;
         border-radius:18px; padding:26px 32px; margin-top:24px; }}
.demo .t {{ font-size:26px; font-weight:800; }}
.demo .u {{ font-size:22px; margin-top:6px; opacity:.95; }}
/* slide de portada / cierre */
.cover {{ background:linear-gradient(135deg,{GREEN_900} 0%,{GREEN_700} 50%,{EMERALD} 120%);
          color:#fff; justify-content:center; }}
.cover h1 {{ color:#fff; font-size:72px; }}
.cover p.lead {{ color:rgba(255,255,255,.95); font-size:27px; margin-top:18px; }}
.cover .pill {{ background:rgba(255,255,255,.18); border:1px solid rgba(255,255,255,.35); }}
.cover .foot {{ color:rgba(255,255,255,.85); }}
.skyline {{ position:absolute; bottom:0; left:0; right:0; height:90px; opacity:.5; }}
.two {{ display:flex; gap:34px; }}
.col {{ flex:1; background:#fff; border:1px solid rgba(11,61,44,.1); border-radius:16px;
        padding:22px 26px; box-shadow:0 6px 18px rgba(11,61,44,.07); }}
.col h3 {{ font-size:24px; color:{GREEN_700}; margin-bottom:8px; }}
.col li {{ font-size:19px; margin:8px 0; }}
.note {{ color:{AMBER}; font-weight:800; }}
"""

SKYLINE = (
    '<svg class="skyline" viewBox="0 0 1200 90" preserveAspectRatio="none">'
    '<g fill="#ffffff">'
    + "".join(
        f'<rect x="{x}" y="{y}" width="{w}" height="{90-y}"/>'
        for x, y, w in [
            (20,40,46),(74,22,34),(116,52,48),(172,16,30),(210,46,44),(262,30,36),
            (306,56,50),(364,20,32),(404,48,46),(458,32,34),(500,12,28),(536,52,48),
            (592,38,38),(638,24,34),(680,56,50),(738,18,30),(778,48,46),(832,34,36),
            (876,58,48),(932,22,32),(972,46,44),(1024,30,36),(1068,54,50),(1126,18,30),
        ]
    )
    + "</g></svg>"
)


def footer(n):
    return f'<div class="foot"><span>AlquilerJusto · Data Science con Python 2026-I</span><span>{n} / 10</span></div>'


SLIDES = [
    # 1 — Portada
    f"""<div class="slide cover">
        <div style="font-size:30px;font-weight:800">🏠 AlquilerJusto</div>
        <h1 style="margin-top:14px">¿Tu próximo alquiler<br>está mal preciado?</h1>
        <p class="lead">Te lo decimos en 5 segundos, comparándolo contra miles de
        avisos reales del mercado limeño.</p>
        <div style="margin-top:22px">
            <span class="pill">🔗 alquiler-justo.streamlit.app</span>
            <span class="pill">Nicolás Villar · Economía UP</span>
        </div>
        {SKYLINE}
    </div>""",
    # 2 — Problema
    f"""<div class="slide"><div class="bar"></div>
        <div class="kicker">El problema</div>
        <h2>Buscar depto en Lima es una apuesta a ciegas</h2>
        <ul>
            <li>La búsqueda toma <b>4 a 8 semanas</b> y se ven decenas de avisos.</li>
            <li>Hay <b>30,000+ avisos activos</b>, pero ningún portal te dice si <i>ese</i> aviso está bien preciado.</li>
            <li>Decides con <b>instinto</b>, no con datos — y pagas de más sin saberlo.</li>
        </ul>
        <p class="lead" style="margin-top:22px"><b>¿S/2,500 por un 2 dorm de 70 m² en Miraflores
        es caro, justo o regalado?</b> Nadie te lo responde.</p>
        {footer(2)}</div>""",
    # 3 — Insight
    f"""<div class="slide"><div class="bar"></div>
        <div class="kicker">El insight</div>
        <h2>Los portales tienen los datos,<br>pero el incentivo equivocado</h2>
        <ul>
            <li>Urbania y Adondevivir ganan cuando <b>sigues navegando semanas</b>.</li>
            <li>Decirte "este aviso está sobrevalorado" <b>acorta tu tiempo en su sitio</b> → menos ads → menos ingresos.</li>
            <li><b>No pueden construir esto sin canibalizarse</b> (incumbent's dilemma).</li>
            <li class="note">Nosotros cobramos al que busca y al que publica, no al anunciante.</li>
        </ul>
        {footer(3)}</div>""",
    # 4 — Solución + demo
    f"""<div class="slide"><div class="bar"></div>
        <div class="kicker">La solución</div>
        <h2>Pega los datos → veredicto en 5 segundos</h2>
        <ul>
            <li><b>Precio justo</b> estimado + rango de confianza</li>
            <li><b>Percentil</b> vs avisos similares de la zona</li>
            <li>Veredicto claro: 🟢 buen precio · 🟡 justo · 🔴 sobrevalorado</li>
            <li>5 <b>comparables reales</b> como evidencia, con link directo</li>
        </ul>
        <div class="demo"><div class="t">▶ DEMO EN VIVO</div>
            <div class="u">alquiler-justo.streamlit.app</div></div>
        {footer(4)}</div>""",
    # 5 — Producto dos lados
    f"""<div class="slide"><div class="bar"></div>
        <div class="kicker">Producto</div>
        <h2>Un solo motor, dos lados del mercado</h2>
        <div class="two">
            <div class="col"><h3>🔍 Inquilino</h3><ul>
                <li>"¿Me están cobrando de más?"</li>
                <li>Veredicto + comparables</li>
                <li>Búsqueda conversacional: "2 dorm en Surco hasta S/4,000"</li>
            </ul></div>
            <div class="col"><h3>💰 Propietario</h3><ul>
                <li>"¿Cuánto pido por mi depto?"</li>
                <li>Precio óptimo de mercado</li>
                <li>3 estrategias: alquila rápido · equilibrado · maximiza</li>
            </ul></div>
        </div>
        <p class="lead" style="margin-top:20px">Mapa de precios por distrito + asistente, sobre la misma base de datos.</p>
        {footer(5)}</div>""",
    # 6 — Modelo
    f"""<div class="slide"><div class="bar"></div>
        <div class="kicker">El modelo</div>
        <h2>Regresión hedónica defendible</h2>
        <ul>
            <li>OLS log-lineal con errores robustos (HC1): precio ~ m², dorms, baños, piso, distrito, amenidades.</li>
            <li>Hallazgo: <b>vista al mar +10%</b> (p&lt;0.001). Probamos cercanía a parques → <b>no significativo</b>, lo descartamos.</li>
            <li>Transparente: la app <b>desglosa "por qué" cada precio</b> (no es caja negra).</li>
        </ul>
        <div class="metrics">
            <div class="metric"><div class="v">0.82</div><div class="l">R² (varianza explicada)</div></div>
            <div class="metric"><div class="v">1,475</div><div class="l">avisos reales</div></div>
            <div class="metric"><div class="v">11</div><div class="l">distritos de Lima</div></div>
            <div class="metric"><div class="v">~25%</div><div class="l">RMSE</div></div>
        </div>
        {footer(6)}</div>""",
    # 7 — Mercado
    f"""<div class="slide"><div class="bar"></div>
        <div class="kicker">Mercado</div>
        <h2>Un mercado grande y desatendido</h2>
        <ul>
            <li><b>TAM</b> — alquiler residencial Perú: ~2.3M hogares alquilan (INEI: 28% de hogares).</li>
            <li><b>SAM</b> — Lima Metropolitana: ~300k búsquedas/mes en portales.</li>
            <li><b>SOM (12 meses)</b> — 5,000 usuarios Pro × S/20 = <b>S/100k MRR</b> (0.5% del SAM).</li>
        </ul>
        <p class="lead" style="margin-top:20px">Proptech es categoría VC activa en LatAm (La Haus, Houm).
        Nuestro wedge: <b>inteligencia de precio justo</b>.</p>
        {footer(7)}</div>""",
    # 8 — Negocio
    f"""<div class="slide"><div class="bar"></div>
        <div class="kicker">Modelo de negocio · ya funciona en el demo</div>
        <h2>Freemium con un lado B2B fuerte</h2>
        <table>
            <tr><th>Plan</th><th>Precio</th><th>Incluye</th></tr>
            <tr><td>Free</td><td>S/0</td><td>Mapa + 2 análisis/mes</td></tr>
            <tr><td><b>Pago por uso</b></td><td><b>S/5 / análisis</b></td><td>Para el que decide rápido</td></tr>
            <tr><td>Pro</td><td>S/20/mes</td><td>Análisis ilimitados + alertas</td></tr>
            <tr><td>Corredores (próx.)</td><td>B2B</td><td>Dashboard + leads</td></tr>
        </table>
        <p class="lead" style="margin-top:18px"><b class="note">Validado en entrevistas:</b>
        2 de 3 prefieren pagar <b>por uso (S/5)</b> antes que suscripción — el inquilino es
        transaccional. Margen <b>~99%</b> (costo ~S/0.04 por análisis).</p>
        {footer(8)}</div>""",
    # 9 — Competencia & moat
    f"""<div class="slide"><div class="bar"></div>
        <div class="kicker">Competencia & moat</div>
        <h2>Nadie le dice al usuario si el precio es justo</h2>
        <table>
            <tr><th>Alternativa</th><th>Qué hacen</th><th>Qué NO hacen</th></tr>
            <tr><td>Urbania / Adondevivir</td><td>Marketplace de avisos</td><td>Veredicto de precio justo</td></tr>
            <tr><td>Properati Index</td><td>Índice general</td><td>Veredicto aviso por aviso</td></tr>
            <tr><td>Excel / instinto</td><td>Lo que hace el 90%</td><td>Nada estructurado</td></tr>
        </table>
        <ul style="margin-top:16px">
            <li><b>Moat:</b> dataset propio que se compone con scraping diario.</li>
            <li><b>Incentivo alineado</b> que el incumbente no puede copiar sin canibalizar sus ads.</li>
        </ul>
        {footer(9)}</div>""",
    # 10 — Tracción, roadmap, ask
    f"""<div class="slide cover">
        <div class="kicker" style="color:#d6ffe9">Tracción · Roadmap · The ask</div>
        <h1 style="font-size:46px">Producto vivo. Listo para crecer.</h1>
        <ul style="margin-top:10px">
            <li><b>Hoy:</b> app desplegada · 1,475 avisos · R²=0.82 · 3 entrevistas que validaron el pago por uso (S/5).</li>
            <li><b>Roadmap:</b> scraping diario + alertas WhatsApp (3m) → multi-fuente Urbania (6m) → dashboard corredores (12m).</li>
            <li><b>Riesgos:</b> WTP (freemium como funnel) · asking≠transacción (lo posicionamos) · scraping (multi-fuente).</li>
        </ul>
        <p class="lead" style="margin-top:18px"><b>The ask:</b> USD 50K · 6 meses de runway ·
        milestone: 500 usuarios pagados + 2 corredoras aliadas.</p>
        <div class="foot"><span>🔗 alquiler-justo.streamlit.app</span><span>10 / 10</span></div>
    </div>""",
]


def main():
    html = f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{''.join(SLIDES)}</body></html>"
    out = Path(__file__).parent / "pitch_deck.html"
    out.write_text(html, encoding="utf-8")
    print(f"escrito {out}")


if __name__ == "__main__":
    main()
