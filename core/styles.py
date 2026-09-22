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
        "allowed_layouts": ["full_art", "split_right", "code_graphic"],
    },
    "flat_vector": {
        "description": "Ilustración vectorial plana moderna, colores vibrantes, estilo corporativo.",
        "prompt": (
            "modern flat vector illustration, clean geometric shapes, vibrant saturated colors, "
            "minimal corporate design, subtle shadows, solid color background"
        ),
        "background_rules": "solid flat color background, no gradients, uncluttered",
        "text_safe": True,
        "allowed_layouts": ["full_art", "split_right", "code_graphic"],
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
        "allowed_layouts": ["full_art", "split_right", "code_graphic"],
    },
    "cyberpunk": {
        "description": "Estética cyberpunk con neones azul/magenta y fondos oscuros.",
        "prompt": (
            "neon cyberpunk aesthetic, dark atmospheric background, glowing blue and magenta lights, "
            "detailed digital art, futuristic urban environment"
        ),
        "background_rules": "dark moody background with neon accents, no daylight",
        "text_safe": True,
        "allowed_layouts": ["full_art", "split_right", "code_graphic"],
    },
    "photorealistic": {
        "description": "Fotorrealismo cinematográfico, iluminación natural, alta nitidez.",
        "prompt": (
            "photorealistic cinematic photography, natural lighting, shallow depth of field, "
            "high detail, 8k, professional color grading"
        ),
        "background_rules": "clean background, natural environment, no artificial elements",
        "text_safe": True,
        "allowed_layouts": ["full_art", "split_right", "code_graphic"],
    },
    "watercolor": {
        "description": "Acuarela artística con texturas suaves y colores pastel.",
        "prompt": (
            "soft watercolor painting, artistic brush strokes, pastel color palette, "
            "paper texture, gentle gradients, hand-painted feel"
        ),
        "background_rules": "textured watercolor paper background, soft edges",
        "text_safe": False,
        "allowed_layouts": ["full_art", "split_right", "code_graphic"],
    },
    "doodle_cartoon_landscape": {
        "description": (
            "Monigote cartoon expresivo con cabeza grande sobre fondo de paisaje "
            "semi-pintado estilo gouache digital, iluminación cálida cinematográfica."
        ),
        "prompt": (
            "Expressive cartoon doodle character with oversized round head, "
            "minimal facial features (two black dot eyes, thin curved eyebrows, "
            "simple curved smile line, no defined nose), classic hairstyle, "
            "thin stick-like arms and legs drawn as "
            "bold black outlines, simple flat-colored solid clothe, rounded mitten "
            "hands. Bold clean black outline around the entire character, no internal "
            "shading, flat solid colors. "
            "Background: warm cinematic atmospheric lighting "
        
        ),
        "background_rules": (
            "semi-painted landscape with visible brush textures and warm atmospheric lighting, "
            "character drawn with bold black outlines and flat solid colors, "
            "clear visual hierarchy between character (outlined) and background (painterly)"
        ),
        "text_safe": True,
        "allowed_layouts": ["full_art", "split_right", "code_graphic"],
    },

    "doodle_cartoon_lite": {
        "description": (
            "Monigote cartoon expresivo con cabeza grande sobre fondo de paisaje "
            "semi-pintado estilo gouache digital, iluminación cálida cinematográfica."
        ),
        "prompt": (
            "cartoon doodle classic hairstyle, "
 
        ),
        "background_rules": (
            "semi-painted landscape with visible brush textures and warm atmospheric lighting, "
        ),
        "text_safe": False,
        "allowed_layouts": ["full_art", "split_right", "code_graphic"],
    },

    "stickman_cinematic_2d": {
        "description": (
            "Personaje doodle de cabeza blanca y guantes estilo clásico con ropa detallada, integrado en fondos cinemáticos de animación 2D "
        ),
        "prompt": (
            "A frame from a high-end 2D animated feature film. "
            "The main character is a hybrid doodle stickman: a smooth white spherical head with simple expressive black dot eyes, thin eyebrows and mouth, "
            "classic white 4-finger cartoon gloves, white cartoon shoes, and thin black stick-figure legs. "
            "The character is wearing detailed, stylized 2D clothing fully appropriate for the context of the scene."
 
        ),
        "background_rules": (
            "The backdrop is a rich, hand-painted 2D animated film background with warm atmospheric lighting, "
            "volumetric light rays, detailed textures, and cinematic depth of field. "
            "Cohesive blending between the cartoon character features and the painterly background environment."
        ),
        "text_safe": True,
        "allowed_layouts": ["full_art"],
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