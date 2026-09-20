# core/styles.py
import os
from typing import Dict, Any, Optional

STYLE_PROMPTS: Dict[str, Dict[str, Any]] = {
    "stick_figure_minimalist": {
        "description": "Stick figures minimalistas en blanco y negro, alto contraste, humor limpio.",
        "prompt": (
            "minimalist black and white stick figure illustration, simple clean line art, "
            "pure white background, humorous expressive poses, vector style, high clarity"
        ),
        "background_rules": "pure solid white background, no gradients, no texture",
        "text_safe": True,
    },
    "flat_vector": {
        "description": "Ilustración vectorial plana moderna, colores vibrantes, estilo corporativo.",
        "prompt": (
            "modern flat vector illustration, clean geometric shapes, vibrant saturated colors, "
            "minimal corporate design, subtle shadows, solid color background"
        ),
        "background_rules": "solid flat color background, no gradients, uncluttered",
        "text_safe": True,
    },
    "cartoon_2d_cellshaded": {
        "description": "Cartoon 2D con cell-shading (estilo actual del proyecto).",
        "prompt": (
            "Clean 2D vector cartoon illustration, cell-shaded style. "
            "Characters: Expressive 2D cartoon human figures with natural skin tones, "
            "clear facial features, classic hairstyles, and simple textured clothing."
        ),
        "background_rules": "spacious uncluttered composition, soft depth of field",
        "text_safe": False,
    },
    "cyberpunk": {
        "description": "Estética cyberpunk con neones azul/magenta y fondos oscuros.",
        "prompt": (
            "neon cyberpunk aesthetic, dark atmospheric background, glowing blue and magenta lights, "
            "detailed digital art, futuristic urban environment"
        ),
        "background_rules": "dark moody background with neon accents, no daylight",
        "text_safe": True,
    },
    "photorealistic": {
        "description": "Fotorrealismo cinematográfico, iluminación natural, alta nitidez.",
        "prompt": (
            "photorealistic cinematic photography, natural lighting, shallow depth of field, "
            "high detail, 8k, professional color grading"
        ),
        "background_rules": "clean background, natural environment, no artificial elements",
        "text_safe": True,
    },
    "watercolor": {
        "description": "Acuarela artística con texturas suaves y colores pastel.",
        "prompt": (
            "soft watercolor painting, artistic brush strokes, pastel color palette, "
            "paper texture, gentle gradients, hand-painted feel"
        ),
        "background_rules": "textured watercolor paper background, soft edges",
        "text_safe": False,
    },
}

DEFAULT_STYLE_KEY = "cartoon_2d_cellshaded"


def get_style_key(style_key: Optional[str] = None) -> str:
    """Resuelve el estilo efectivo: argumento > variable de entorno > default."""
    key = style_key or os.getenv("DEFAULT_VISUAL_STYLE", DEFAULT_STYLE_KEY)
    if key not in STYLE_PROMPTS:
        print(f"⚠️ Estilo '{key}' no reconocido. Usando '{DEFAULT_STYLE_KEY}'.")
        return DEFAULT_STYLE_KEY
    return key


def get_style_prompt(style_key: Optional[str] = None) -> str:
    """Devuelve el fragmento de prompt del estilo (compatibilidad con código existente)."""
    return STYLE_PROMPTS[get_style_key(style_key)]["prompt"]


def get_style_background_rules(style_key: Optional[str] = None) -> str:
    return STYLE_PROMPTS[get_style_key(style_key)].get("background_rules", "")


def get_style_description(style_key: Optional[str] = None) -> str:
    return STYLE_PROMPTS[get_style_key(style_key)]["description"]


def list_available_styles() -> Dict[str, str]:
    """Retorna {clave: descripción} para el CLI."""
    return {k: v["description"] for k, v in STYLE_PROMPTS.items()}


def build_style_directive(style_key: Optional[str] = None) -> str:
    """
    Construye el bloque de instrucción de estilo listo para inyectar
    en prompts de sistema del LLM. Todo en INGLÉS.
    """
    key = get_style_key(style_key)
    style = STYLE_PROMPTS[key]
    directive = (
        f"MANDATORY VISUAL STYLE — '{key}':\n"
        f"Every 'visual_prompt' MUST start with this exact style primer:\n"
        f"\"{style['prompt']}\"\n"
    )
    if style.get("background_rules"):
        directive += f"Background rules: {style['background_rules']}.\n"
    if not style.get("text_safe", False):
        directive += (
            "STRICT NO-TEXT RULE: the raw image MUST be 100% clean of any typography, "
            "letters, numbers, labels, captions, logos, or watermarks.\n"
        )
    return directive