"""
Claude-powered parser for rental listing free text.

Takes raw description text from a listing and returns structured JSON
with all numeric and categorical features needed by the pricing model.

Used in lecture 14 (AI document extraction) — demonstrates how Claude
bridges the gap between unstructured portal text and structured features.
"""

import json
import logging
import os
from typing import Optional

import anthropic
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

CLIENT: Optional[anthropic.Anthropic] = None

SYSTEM_PROMPT = """Eres un asistente especializado en extracción de datos de avisos inmobiliarios en Lima, Perú.
Tu tarea es leer la descripción de un departamento en alquiler y devolver ÚNICAMENTE un JSON válido con los campos extraídos.
No incluyas texto antes ni después del JSON. Si un campo no está mencionado devuelve null.
Los precios deben ser numéricos (sin texto). Las amenidades son booleanos (true/false)."""

EXTRACTION_PROMPT = """Extrae los datos de este aviso inmobiliario de Lima y devuelve solo JSON:

<aviso>
{text}
</aviso>

Devuelve este JSON (completa todos los campos que puedas inferir del texto):
{{
  "precio_pen": <número en soles o null>,
  "precio_usd": <número en dólares o null>,
  "area_m2": <número o null>,
  "dormitorios": <entero o null>,
  "banos": <entero o null>,
  "piso": <entero o null>,
  "antiguedad_anos": <entero estimado o null>,
  "distrito": <"miraflores"|"san-isidro"|"surco"|"magdalena"|otro nombre o null>,
  "direccion": <string o null>,
  "amenidades": {{
    "piscina": <true|false>,
    "gimnasio": <true|false>,
    "cochera": <true|false>,
    "ascensor": <true|false>,
    "seguridad": <true|false>,
    "terraza": <true|false>,
    "amoblado": <true|false>,
    "aire_acondicionado": <true|false>
  }},
  "notas": <observaciones relevantes no capturadas arriba o null>
}}"""


def _get_client() -> anthropic.Anthropic:
    global CLIENT
    if CLIENT is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "ANTHROPIC_API_KEY no encontrado. "
                "Copia .env.example a .env y agrega tu API key."
            )
        CLIENT = anthropic.Anthropic(api_key=api_key)
    return CLIENT


def parse_listing_text(text: str) -> Optional[dict]:
    """
    Send listing description to Claude and return structured dict.

    Args:
        text: Raw description text from a rental listing.

    Returns:
        Dict with extracted fields, or None if parsing fails.

    Example:
        >>> result = parse_listing_text(
        ...     "Depto 2 dorm, 65m2, piso 4, Miraflores. "
        ...     "Cochera, ascensor. S/ 2,200/mes."
        ... )
        >>> result["dormitorios"]
        2
    """
    client = _get_client()
    prompt = EXTRACTION_PROMPT.format(text=text[:3000])

    try:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",  # cheapest model — cents per listing
            max_tokens=512,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()

        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        parsed = json.loads(raw)
        logger.info(f"Claude parsed listing: {list(parsed.keys())}")
        return parsed

    except json.JSONDecodeError as e:
        logger.warning(f"Claude returned invalid JSON: {e}")
        return None
    except anthropic.APIError as e:
        logger.error(f"Anthropic API error: {e}")
        return None


def parse_listing_batch(texts: list[str]) -> list[Optional[dict]]:
    """Parse multiple listing descriptions. Returns list of same length."""
    return [parse_listing_text(t) for t in texts]


def claude_to_model_features(parsed: dict) -> dict:
    """
    Convert Claude output dict to the schema expected by OLSModel.predict().
    Maps field names and normalizes types.
    """
    am = parsed.get("amenidades", {}) or {}
    return {
        "price_pen":       parsed.get("precio_pen"),
        "price_usd":       parsed.get("precio_usd"),
        "area_m2":         parsed.get("area_m2"),
        "bedrooms":        parsed.get("dormitorios"),
        "bathrooms":       parsed.get("banos"),
        "floor":           parsed.get("piso") or 1,
        "antiquity_years": parsed.get("antiguedad_anos"),
        "district":        parsed.get("distrito") or "miraflores",
        "address":         parsed.get("direccion"),
        "amenities": {
            "piscina":    bool(am.get("piscina")),
            "gimnasio":   bool(am.get("gimnasio")),
            "cochera":    bool(am.get("cochera")),
            "ascensor":   bool(am.get("ascensor")),
            "seguridad":  bool(am.get("seguridad")),
            "terraza":    bool(am.get("terraza")),
            "amoblado":   bool(am.get("amoblado")),
            "aire":       bool(am.get("aire_acondicionado")),
        },
    }


# ---------------------------------------------------------------------------
# Demo / smoke test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    sample = """
    ALQUILER DEPARTAMENTO MIRAFLORES — AV. LARCO
    Hermoso departamento de 85 m2, 2 dormitorios, 2 baños completos.
    Ubicado en el piso 7 con vista al parque. Edificio moderno con ascensor,
    cochera incluida, gym y piscina. Amoblado completo, cocina equipada.
    Seguridad 24h. Precio: USD 1,200 al mes. Antigüedad 5 años.
    """

    print("Enviando a Claude API...")
    result = parse_listing_text(sample)
    if result:
        print("\n✅ Resultado:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print("\n→ Features para el modelo:")
        features = claude_to_model_features(result)
        print(json.dumps(features, indent=2, ensure_ascii=False))
    else:
        print("❌ Error al parsear")
        sys.exit(1)
