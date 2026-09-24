# core/styles.py
import os
from typing import Dict, Any, Optional

# --- CONFIGURACIÓN DE FUENTES ---
# Nombres de archivo (relativos a assets/fonts/).
# El fallback global se usa cuando un estilo no declara fuente propia.
HAND_DRAWN_FONT = "PatrickHand-Regular.ttf"
GLOBAL_FALLBACK_FONT = "DejaVuSans.ttf"

# ==============================================================================
# CATÁLOGO DE ESTILOS VISUALES
# ==============================================================================
# Cada estilo declara:
#   - description: texto humano para el menú CLI
#   - prompt: fragmento en INGLÉS que se inyecta en los visual_prompts
#   - background_rules: reglas de fondo que reforzarán las salvaguardas
#   - text_safe: True si la regla anti-texto NO se necesita (el estilo
#     tiende a no generar texto espontáneo)
#   - fonts: dict {'title', 'body'} con nombres de archivo en assets/fonts/.
#     Opcional. Si falta, se usa el fallback global (DejaVu).
#   - allowed_layouts: lista de layouts permitidos ('full_art', 'split_right',
#     'code_graphic'). Si falta, se asumen los tres.
#
# Convención: los estilos cartoon/doodle/editorial suelen usar Patrick Hand
# (HAND_DRAWN_FONT). Los estilos realistas/corporativos omiten 'fonts' y
# heredan el fallback global.
# ==============================================================================

STYLE_PROMPTS: Dict[str, Dict[str, Any]] = {
    "stick_figure_minimalist": {
        "description": "Stick figures minimalistas en blanco y negro, alto contraste, humor limpio.",
        "prompt": (
            "minimalist black and white stick figure illustration, simple clean line art, "
            "pure white background, humorous expressive poses, vector style, high clarity"
        ),
        "background_rules": "pure solid white background, no gradients, no texture",
        "text_safe": True,
        "fonts": {
            "title": HAND_DRAWN_FONT,
            "body": HAND_DRAWN_FONT,
        },
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
        "fonts": {
            "title": HAND_DRAWN_FONT,
            "body": HAND_DRAWN_FONT,
        },
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
        "fonts": {
            "title": HAND_DRAWN_FONT,
            "body": HAND_DRAWN_FONT,
        },
        "allowed_layouts": ["full_art", "split_right", "code_graphic"],
    },
    "doodle_cartoon_lite": {
        "description": (
            "Monigote cartoon expresivo con cabeza grande sobre fondo de paisaje "
            "semi-pintado estilo gouache digital, iluminación cálida cinematográfica."
        ),
        "prompt": (
            "cartoon doodle, "
            "characters: expressive 2D cartoon doodle with classic hairstyle, "
 
        ),
        "background_rules": (
            "semi-painted landscape with visible brush textures and warm atmospheric lighting, "
        ),
        "text_safe": False,
        "fonts": {
            "title": HAND_DRAWN_FONT,
            "body": HAND_DRAWN_FONT,
        },
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
    "flat_editorial_2d_lite": {
        "description": (
            "Ilustración editorial 2D plana con personajes de cabeza circular blanca, "
            "contorno negro fino y fondos de color plano. Variante optimizada para FLUX."
    ),
        "prompt": (
            "Flat 2D editorial cartoon, simple humanoid figures with round white "
            "heads, thin black outlines, dotted eyes, two curved eyebrows"
            "and a small mouth, flat solid colored clothing, "
            "flat solid color background shapes with subtle tonal variation "
            "for depth, no outlines on the background, "
            "clean hand-drawn editorial look."
        ),
        "background_rules": (
            "flat solid color shapes, subtle tonal variation for depth, "
            "thin black outlines on characters only, clean hand-drawn editorial style"
        ),
        "text_safe": False,
        "fonts": {
            "title": HAND_DRAWN_FONT,
            "body": HAND_DRAWN_FONT,
        },
        "allowed_layouts": ["full_art", "split_right", "code_graphic"],
    },
    "documentary_stickman_flow": {
        "description": (
            "Personaje stickman cartoon plano sobre fondo de pintura digital "
            "semi-realista con niebla atmosférica, paleta fría documental. "
            "Estilo híbrido tipo video educativo documental."
        ),
        "prompt": (
            "Hybrid illustration style combining a flat 2D cartoon character "
            "with a semi-realistic painted background. "
            "Character: simple stickman figure with a perfectly round bone-white "
            "head, thin black outline, minimal facial features with small oval "
            "eyes, thin curved eyebrows, a small curved mouth, and a subtle short "
            "vertical nose line, visible thin neck, torso with slight shoulder "
            "volume and defined waist rendered as a closed flat-colored shape, "
            "arms and legs drawn as thick black lines with rounded ends, "
            "bone-white circular cartoon hands and feet, "
            "simple flat-colored clothing like irregular animal-skin garments "
            "with jagged edges, bold black outline around the character, "
            "flat solid colors with no shading. "
            "Background: semi-realistic digital painting with atmospheric fog, "
            "soft color gradients, muted desaturated cold palette of greyish "
            "greens, pale blues and dull browns, soft brush textures, "
            "layered landscape silhouettes receding into mist, "
            "cinematic composition with low horizon and wide sky, "
            "no outlines on background elements, painterly soft edges. "
            "Clean visual separation between the outlined cartoon character "
            "and the atmospheric painted background."
    ),
        "background_rules": (
            "semi-realistic digital painting with atmospheric fog and soft "
            "gradients, muted desaturated cold palette, layered misty landscape, "
            "no outlines on background, painterly soft edges, "
            "character rendered flat with bold black outline on top of the painted scene"
    ),
        "text_safe": True,
        "fonts": {
            "title": HAND_DRAWN_FONT,
            "body": HAND_DRAWN_FONT,
        },
        "allowed_layouts": ["full_art"],
    },
    
}

DEFAULT_STYLE_KEY = "cartoon_2d_cellshaded"

def _default_fonts() -> Dict[str, str]:
    """Fuentes por defecto cuando un estilo no declara las suyas."""
    return {
        "title": GLOBAL_FALLBACK_FONT,
        "body": GLOBAL_FALLBACK_FONT,
    }


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

def get_style_fonts(style_key: Optional[str] = None) -> Dict[str, str]:
    """
    Devuelve el dict de fuentes del estilo: {'title': ..., 'body': ...}.
    Si el estilo no declara fuentes, devuelve el fallback global.
    """
    style = STYLE_PROMPTS[get_style_key(style_key)]
    fonts = style.get("fonts")
    if isinstance(fonts, dict) and "title" in fonts and "body" in fonts:
        return dict(fonts)
    return _default_fonts()

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