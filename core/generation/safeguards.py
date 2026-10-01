"""
Safeguards para los visual_prompts generados por el LLM.

Se encargan de:
- Garantizar el estilo del proyecto en cada prompt.
- Añadir la regla de split_right cuando corresponde.
- Añadir background_rules si faltan.
- Añadir reglas anti-texto y aspect ratio.
- Limpiar duplicaciones y residuos.
- Forzar el layout permitido si el manifest trae uno prohibido.
"""

import re
from typing import List, Dict, Any

from core.styles import (
    get_style_prompt,
    get_style_background_rules,
    get_style_key,
    STYLE_PROMPTS,
)


def apply_prompt_safeguards(
    scenes: List[Dict[str, Any]],
    thumbnail_prompt: str,
    aspect_ratio: str,
    style_key: str,
) -> tuple[List[Dict[str, Any]], str]:
    """Garantiza estilo, reglas de encuadre y aspect ratio sin duplicaciones."""
    style_prompt = get_style_prompt(style_key)
    bg_rules = get_style_background_rules(style_key)
    style_marker = style_prompt.split(",")[0].strip()[:40]

    style_meta = STYLE_PROMPTS[get_style_key(style_key)]
    allowed_layouts = style_meta.get("allowed_layouts", ["full_art", "split_right", "code_graphic"])
    default_layout = allowed_layouts[0]

    ratio_directive = "16:9" if aspect_ratio == "16:9" else "9:16"

    # ---- Helpers de detección robusta ----
    def _normalize(p: str) -> str:
        """Normaliza para comparaciones: lowercase, espacios colapsados, sin puntuación doble."""
        p = p.lower()
        p = re.sub(r"\s+", " ", p)
        p = re.sub(r"\.+", ".", p)
        return p.strip()

    def _has_any(p_norm: str, markers: List[str]) -> bool:
        return any(m in p_norm for m in markers)

    def _clean_prompt(p: str) -> str:
        """Limpia residuos obvios del prompt antes de las salvaguardas."""
        p = p.strip()
        p = re.sub(r"\s+", " ", p)
        p = re.sub(r"\.\.+", ".", p)
        p = re.sub(r"\s+\.", ".", p)
        p = re.sub(r"\.\s*,", ".", p)
        p = re.sub(r",\s*,", ",", p)
        return p.strip(" ,.")

    split_right_markers = [
        "left 70%", "70% of the image",
        "right 30%", "30% of the frame", "right third", "right side",
        "negative space on the right", "empty on the right",
        "empty space on the right", "empty right",
    ]

    no_text_markers = [
        "no text", "without any text", "clean without any text",
        "completely clean", "free of text", "no letters", "no words",
    ]

    bg_rules_markers = [
        m.strip().lower() for m in bg_rules.split(",") if m.strip()
    ] if bg_rules else []

    def _strip_embedded_style(p: str) -> str:
        """
        Si el prompt contiene el estilo embebido, cortar todo lo que viene después
        del inicio del estilo. Es defensa contra el LLM, que a veces incluye el
        estilo en el 'visual_prompt' aunque se le indique que no lo haga.
        """
        style_marker_lower = style_marker.lower()
        p_lower = p.lower()
        idx = p_lower.find(style_marker_lower)
        if idx > 20:
            return p[:idx].rstrip(" ,.")
        return p

    def _apply_to_prompt(prompt: str, layout: str) -> str:
        prompt = _clean_prompt(prompt or "")
        prompt = _strip_embedded_style(prompt)

        # 1. Estilo (prefijo)
        if style_marker.lower() not in _normalize(prompt):
            prompt = f"{prompt} {style_prompt} ".strip()

        # 2. Regla split_right
        p_norm = _normalize(prompt)
        if layout == "split_right" and not _has_any(p_norm, split_right_markers):
            prompt += (
                ". Subject and main action framed strictly on the left 70% of "
                "the image, the right 30% of the frame is clean empty negative "
                "space."
            )

        # 3. Background rules (por partes, no bloque completo)
        p_norm = _normalize(prompt)
        missing_bg = [m for m in bg_rules_markers if m not in p_norm]
        if missing_bg:
            prompt += f", {', '.join(missing_bg)}"

        # 4. No-text
        p_norm = _normalize(prompt)
        if not _has_any(p_norm, no_text_markers):
            prompt += ", no text"

        # 5. Aspect ratio
        p_norm = _normalize(prompt)
        if ratio_directive.lower() not in p_norm:
            prompt += f", {ratio_directive}"

        # Cierre final: punto único
        prompt = prompt.rstrip(" .,") + "."
        return prompt

    for scene in scenes:
        layout = scene.get("layout_type", "full_art")

        if layout not in allowed_layouts:
            print(
                f"   ⚠️ Escena {scene.get('scene_number')}: layout '{layout}' "
                f"no permitido por el estilo '{style_key}'. Forzando '{default_layout}'."
            )
            scene["layout_type"] = default_layout
            layout = default_layout
            if default_layout == "full_art":
                scene["overlay_content"] = None

        if layout == "code_graphic":
            scene["visual_prompt"] = None
            continue

        scene["visual_prompt"] = _apply_to_prompt(scene.get("visual_prompt", ""), layout)

    th_prompt = _apply_to_prompt(thumbnail_prompt, "full_art")
    return scenes, th_prompt