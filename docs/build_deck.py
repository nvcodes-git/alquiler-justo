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
.cover li {{ color:rgba(255,255,255,.94); }}
.cover li::before {{ color:#9ff5c4; }}
.cover strong, .cover b {{ color:#ffffff; }}
.cover .note {{ color:#ffe08a; }}
.cover .kicker {{ color:#bff3d6; }}
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
        <h2>Alquilar en Lima es una apuesta a ciegas</h2>
        <ul>
            <li><b>4 a 8 semanas</b> revisando avisos a mano.</li>
            <li><b>30,000+ avisos</b>, pero nada con qué comparar de forma objetiva.</li>
            <li>Terminas decidiendo <b>sin saber si pagas de más</b>.</li>
        </ul>
        <p class="lead" style="margin-top:30px"><b>¿S/2,500 por 70 m² en Miraflores
        es caro o justo?</b></p>
        {footer(2)}</div>""",
    # 3 — Insight
    f"""<div class="slide"><div class="bar"></div>
        <div class="kicker">El insight</div>
        <h2>Los portales no quieren decírtelo</h2>
        <ul>
            <li>Ganan con tu <b>tiempo navegando</b>.</li>
            <li>El veredicto <b>mataría su negocio de ads</b>.</li>
            <li class="note">Un incentivo que el incumbente no puede copiar.</li>
        </ul>
        {footer(3)}</div>""",
    # 4 — Solución + demo
    f"""<div class="slide"><div class="bar"></div>
        <div class="kicker">La solución</div>
        <h2>El precio justo, en 5 segundos</h2>
        <ul>
            <li>Precio justo + veredicto 🟢 🟡 🔴</li>
            <li>Dónde cae tu aviso vs el mercado</li>
            <li>Comparables reales con link</li>
        </ul>
        <div class="demo"><div class="t">▶ DEMO EN VIVO</div>
            <div class="u">alquiler-justo.streamlit.app</div></div>
        {footer(4)}</div>""",
    # 5 — Producto dos lados
    f"""<div class="slide"><div class="bar"></div>
        <div class="kicker">Producto</div>
        <h2>Un motor, dos lados del mercado</h2>
        <div class="two">
            <div class="col"><h3>🔍 Inquilino</h3><ul>
                <li>¿Me cobran de más?</li>
                <li>Veredicto + comparables</li>
                <li>Búsqueda conversacional</li>
            </ul></div>
            <div class="col"><h3>💰 Propietario</h3><ul>
                <li>¿Cuánto pido?</li>
                <li>Precio óptimo</li>
                <li>3 estrategias de publicación</li>
            </ul></div>
        </div>
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
        <h2>Grande y desatendido</h2>
        <ul>
            <li><b>TAM</b> · 2.3M hogares alquilan en Perú</li>
            <li><b>SAM</b> · Lima: ~300k búsquedas/mes</li>
            <li><b>SOM</b> · 5,000 Pro = <b>S/100k MRR</b></li>
        </ul>
        <p class="lead" style="margin-top:24px">Proptech: categoría VC activa en LatAm.</p>
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
        <div class="kicker">Tracción · Roadmap · The ask</div>
        <h1 style="font-size:48px">Producto vivo.<br>Listo para crecer.</h1>
        <ul style="margin-top:16px">
            <li><b>Hoy:</b> app desplegada · R²=0.82 · pago por uso validado en entrevistas.</li>
            <li><b>Roadmap:</b> scraping diario → multi-fuente → dashboard corredores.</li>
        </ul>
        <p class="lead" style="margin-top:20px"><b>The ask:</b> USD 50K · 6 meses ·
        500 usuarios pagados + 2 corredoras.</p>
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
