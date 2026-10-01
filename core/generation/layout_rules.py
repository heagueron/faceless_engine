"""
Helpers para construir las reglas de layout_type que se inyectan en el
batch_system_prompt del LLM.
"""

from core.styles import STYLE_PROMPTS, get_style_key


def _build_layout_rules(style_key: str) -> str:
    """
    Genera el bloque de reglas de layout_type para el batch_system_prompt,
    respetando los 'allowed_layouts' declarados por el estilo en styles.py.
    Si el estilo no declara el campo, se asumen los 3 layouts clásicos.
    """
    style = STYLE_PROMPTS[get_style_key(style_key)]
    allowed = style.get("allowed_layouts", ["full_art", "split_right", "code_graphic"])

    all_descriptions = {
        "full_art": (
            "layout_type = 'full_art' (DEFAULT): Para la mayoría de las escenas narrativas "
            "o conceptuales. Ocupa el 100% de la pantalla sin texto."
        ),
        "split_right": (
            "layout_type = 'split_right': Cuando se expliquen 2-3 puntos clave o cifras "
            "importantes que requieran apoyo visual escrito. La IA generará la imagen "
            "dejando el 30% derecho libre para una tarjeta de texto superpuesta por Python."
        ),
        "code_graphic": (
            "layout_type = 'code_graphic': ÚNICAMENTE para tablas comparativas complejas, "
            "gráficos de barras o cifras gigantes. La imagen NO se pide a la IA "
            "(visual_prompt = null), sino que se dibuja 100% por código en Python."
        ),
        "code_graphic_visual": (
            "layout_type = 'code_graphic_visual': Para reforzar visualmente un concepto "
            "con una pizarra blanca grande y un personaje explainer apuntando hacia ella. "
            "Se usa cuando los bullets son el foco de la escena y un explainer aporta "
            "claridad narrativa. La imagen NO se pide a la IA (visual_prompt = null)."
        ),
    }

    # Caso extremo: un solo layout permitido
    if len(allowed) == 1:
        only = allowed[0]
        desc = all_descriptions.get(only, "")
        return (
            f"REGLA CRÍTICA DE LAYOUT — ÚNICA OPCIÓN VÁLIDA:\n"
            f"Para este estilo SOLO se permite layout_type = '{only}'. "
            f"NINGUNA otra opción es válida. TODAS las escenas DEBEN usar '{only}'.\n"
            f"{desc}"
        )

    # Caso normal: varios layouts
    lines = ["REGLAS ESTRICTAS DE LAYOUT (layout_type):"]
    for i, layout in enumerate(allowed, 1):
        desc = all_descriptions.get(layout, "")
        if desc:
            lines.append(f"{i}. {desc}")
    return "\n".join(lines)


def _has_overlay_layouts(style_key: str) -> bool:
    """Indica si el estilo permite algún layout que use overlay_content."""
    style = STYLE_PROMPTS[get_style_key(style_key)]
    allowed = style.get("allowed_layouts", ["full_art", "split_right", "code_graphic"])
    return any(l in allowed for l in ("split_right", "code_graphic"))