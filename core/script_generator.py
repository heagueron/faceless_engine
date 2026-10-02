"""
Fachada pública del generador de guiones.

Toda la lógica vive en el paquete `core.generation`. Este módulo solo
reexporta los símbolos públicos para mantener compatibilidad con los
imports existentes:

    from core.script_generator import generate_script
    from core.script_generator import Scene, ScriptManifest, OverlayContent

El CLI sigue funcionando igual:

    python -m core.script_generator --duration 60 --type short --ratio 16:9 --style cartoon_2d_cellshaded
"""

import argparse

from core.config import TARGET_LANGUAGE
from core.styles import list_available_styles

# --- Reexportaciones de schemas ---
from core.generation.schemas import Scene, ScriptManifest, OverlayContent

# --- Reexportaciones de utilidades públicas ---
from core.generation.project_io import (
    slugify,
    create_project_structure,
    load_selected_idea,
    load_reverse_analysis,
)
from core.generation.api_client import call_openrouter_api, _parse_json_safely
from core.generation.layout_rules import _build_layout_rules, _has_overlay_layouts
from core.generation.safeguards import apply_prompt_safeguards
from core.generation.proportions import _enforce_layout_proportions
from core.generation.review import display_and_review_script, _prompt_style_interactive

# --- Función principal (orquestador) ---
from core.generation.orchestrator import (
    generate_script,
    generate_script_from_openrouter,
)


__all__ = [
    # Schemas
    "Scene",
    "ScriptManifest",
    "OverlayContent",
    # I/O de proyectos
    "slugify",
    "create_project_structure",
    "load_selected_idea",
    "load_reverse_analysis",
    # API
    "call_openrouter_api",
    "_parse_json_safely",
    # Layout y safeguards
    "_build_layout_rules",
    "_has_overlay_layouts",
    "apply_prompt_safeguards",
    "_enforce_layout_proportions",
    # Review
    "display_and_review_script",
    "_prompt_style_interactive",
    # Orquestador
    "generate_script",
    "generate_script_from_openrouter",
]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generador de Guiones Faceless Engine")
    parser.add_argument("--duration", type=int, default=600, help="Duración objetivo en segundos")
    parser.add_argument("--type", type=str, default="long", choices=["short", "long"], help="Tipo de video")
    parser.add_argument("--ratio", type=str, default="16:9", choices=["9:16", "16:9"], help="Aspect Ratio")
    parser.add_argument("--model", type=str, default="google/gemini-3.7-flash", help="Modelo de OpenRouter")
    parser.add_argument("--lang", type=str, default=TARGET_LANGUAGE, help="Idioma objetivo del video (es, en, pt)")
    parser.add_argument(
        "--style",
        type=str,
        default=None,
        help=f"Clave del estilo visual. Disponibles: {', '.join(list_available_styles().keys())}"
    )
    parser.add_argument(
        "--channel",
        type=str,
        default=None,
        help="Identificador del canal (carpeta en assets/channels/). Si se omite, se pregunta interactivamente."
    )

    args = parser.parse_args()
    generate_script(
        target_duration=args.duration,
        video_type=args.type,
        aspect_ratio=args.ratio,
        model=args.model,
        language=args.lang,
        style=args.style,
        channel=args.channel,           # ← NUEVO
    )