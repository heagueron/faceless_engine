"""
Orquestador principal del pipeline de generación de guiones.

Contiene la función que coordina las dos fases de generación (escaleta
maestra + batches de escenas) y la función pública `generate_script`
que ejecuta el flujo completo de generación, revisión y almacenamiento.
"""

import os
import re
import json
import argparse
from datetime import datetime
from typing import List, Optional, Dict, Any

from core.config import TARGET_LANGUAGE, LAYOUT_PROPORTION_GUIDE, MIN_FULL_ART_RATIO
from core.styles import (
    get_style_prompt,
    get_style_key,
    get_style_background_rules,
    get_style_description,
    get_style_fonts,
    build_style_directive,
    list_available_styles,
    STYLE_PROMPTS,
    DEFAULT_STYLE_KEY,
)

from core.generation.schemas import OverlayContent, Scene, ScriptManifest
from core.generation.project_io import (
    create_project_structure,
    load_selected_idea,
    load_reverse_analysis,
)
from core.generation.api_client import call_openrouter_api, _parse_json_safely
from core.generation.layout_rules import _build_layout_rules, _has_overlay_layouts
from core.generation.safeguards import apply_prompt_safeguards
from core.generation.proportions import _enforce_layout_proportions
from core.generation.review import display_and_review_script, _prompt_style_interactive


# Mapeo auxiliar para indicarle al LLM el nombre del idioma en inglés
LANGUAGE_NAMES = {
    "es": "SPANISH",
    "en": "ENGLISH",
    "pt": "PORTUGUESE",
}

def generate_script_from_openrouter(
    idea_data: Dict[str, Any],
    reverse_analysis: Optional[Dict[str, Any]] = None,
    target_duration: int = 600,
    video_type: str = "long",
    aspect_ratio: str = "16:9",
    model: str = "google/gemini-3.7-flash",
    batch_size: int = 15,
    language: str = TARGET_LANGUAGE,
    style_key: str = "cartoon_2d_cellshaded"
) -> Optional[ScriptManifest]:
    """Genera el guion dividiendo la tarea en Escaleta Global + Lotes para evitar desbordamiento de tokens."""
    topic = idea_data.get("topic", "")
    idea = idea_data.get("selected_idea", {})
    target_scenes = max(3, round(target_duration / 7.0))
    lang_name = LANGUAGE_NAMES.get(language.lower(), "SPANISH")
    style_directive = build_style_directive(style_key)

    print(f"\n🧠 Iniciando generación de guion: {target_duration}s (~{target_scenes} escenas, {aspect_ratio}, idioma: {language.upper()}) vía {model}...")

    # --------------------------------------------------------------------------
    # FASE 1: GENERACIÓN DE LA ESCALETA GLOBAL (MASTER OUTLINE)
    # --------------------------------------------------------------------------
    print("📋 [Paso 1/2] Generando la Escaleta Maestra del video...")

    outline_system_prompt = f"""
Eres un director de arte y guionista experto en videos educativos virales de economía y finanzas.
Tu tarea es definir la ESTRUCTURA GLOBAL y la MINIATURA de un video de {target_duration} segundos.
Debes proyectar exactamente {target_scenes} escenas continuas.

REGLAS DE IDIOMA:
1. All narration summaries, headlines, titles, and text overlays MUST be strictly in {lang_name}.
2. Visual prompts (thumbnail_prompt) MUST be strictly in ENGLISH.

REGLAS DE MINIATURA (THUMBNAIL):
1. STRICT NO-TEXT RULE IN RAW IMAGE: The thumbnail_prompt raw image MUST be 100% clean of typography.
2. {style_directive}
3. TIGHT COMPOSITION: Medium close-up shot, key characters fill 80% frame near center.
4. thumbnail_prompt: Prompt ultradetallado en INGLÉS.
5. thumbnail_text: Texto de gancho en MAYÚSCULAS en {lang_name} (2-3 palabras máximo) o "" si no aplica.

Esquema JSON requerido:
{{
  "title": "Título del video",
  "includes_interactive_cta": true,
  "thumbnail_prompt": "...",
  "thumbnail_text": "¡ERROR FATAL!",
  "master_outline": [
    {{"scene_number": 1, "narration_summary": "Resumen de lo que se hablará..."}},
    ...
    {{"scene_number": {target_scenes}, "narration_summary": "..."}}
  ]
}}
"""

    outline_user_prompt = f"""
Tema: {topic}
Título/Idea: {idea.get('titulo', topic)}
Gancho Inicial: {idea.get('gancho_inicial', '')}
Premisa: {idea.get('resumen_premisa', '')}
Giro Final: {idea.get('remate_o_giro', '')}
Cantidad total de escenas requeridas: {target_scenes} escenas.
"""

    try:
        raw_outline_json = call_openrouter_api(outline_system_prompt, outline_user_prompt, model, max_tokens=4096)
        outline_data = _parse_json_safely(raw_outline_json, "FASE 1 - escaleta")
        if outline_data is None:
            print(f"❌ Error al parsear la Escaleta Maestra. Respuesta cruda (primeros 500 chars):")
            print(raw_outline_json[:500])
            return None
    except Exception as e:
        print(f"❌ Error al generar la Escaleta Maestra: {e}")
        return None

    master_outline = outline_data.get("master_outline", [])
    if not master_outline:
        print("❌ Error: La escaleta maestra regresó vacía.")
        return None

    # --------------------------------------------------------------------------
    # FASE 2: GENERACIÓN DE ESCENAS DETALLADAS EN LOTES (BATCHES)
    # --------------------------------------------------------------------------
    all_scenes: List[Dict[str, Any]] = []

    style_example = get_style_prompt(style_key).split(",")[0].strip()

    layout_rules_block = _build_layout_rules(style_key)

    # --- Regla de longitud de prompt para estilos específicos (bajo coste) ---
    style_key_resolved = get_style_key(style_key)
    if style_key_resolved == "stick_classic_klein":
        prompt_length_block = (
            "REGLA CRÍTICA DE LONGITUD DE PROMPT:\n"
            "El campo 'visual_prompt' debe ser CORTO: máximo 150 caracteres en total. "
            "Describe la escena en UNA sola frase sencilla. "
            "Estructura: [SUJETO] [ACCIÓN] [CONTEXTO BREVE].\n"
            "Ejemplo genérico de estructura (NO copiar literalmente el sujeto):\n"
            "  '[personaje del estilo del proyecto] realizando [una sola acción] en [contexto breve]'.\n"
            "NO repitas el estilo en el 'visual_prompt'. NO incluyas reglas de fondo. "
            "NO describas múltiples acciones. UNA escena, UN sujeto principal, UNA acción."
        )
    else:
        prompt_length_block = ""

    subject_rules_block = (
        "REGLA DEL SUJETO DEL 'visual_prompt':\n"
        "Cuando el 'visual_prompt' describa un personaje, usa el término apropiado "
        "según el ESTILO VISUAL DEL PROYECTO (indicado arriba). Ejemplos:\n"
        "  - Estilo 'cartoon_2d_cellshaded' o 'doodle_cartoon_landscape': "
        "usa 'a cartoon man', 'a cartoon woman', 'a cartoon character'.\n"
        "  - Estilo 'stick_classic_klein': usa 'a stick figure'.\n"
        "  - Estilo 'flat_editorial_2d_lite': usa 'a simple humanoid figure'.\n"
        "  - Estilo 'documentary_stickman_flow': usa 'a stick figure'.\n"
        "PROHIBIDO usar 'stick figure' en estilos que NO son de stick figures. "
        "PROHIBIDO mezclar terminología de estilos distintos en la misma escena.\n"
        "El sujeto debe ser coherente con la descripción del estilo, no con un "
        "ejemplo genérico.\n"
        "\n"
        "REGLA ADICIONAL DE SUJETO:\n"
        "Si la escena NO menciona explícitamente figuras humanas, personajes o "
        "seres vivos, el 'visual_prompt' NO debe incluirlos. Describe solo los "
        "objetos, partículas, símbolos, entornos u otros elementos que la narración "
        "requiera. NO añadas personajes 'por defecto' solo porque el estilo visual "
        "los menciona."
    )

    # Bloque de proporción de layouts (construido dinámicamente desde config)
    allowed = STYLE_PROMPTS[style_key].get("allowed_layouts", [])
    if len(allowed) > 1:
        lines = ["REGLA CRÍTICA DE PROPORCIÓN DE LAYOUTS:"]
        lines.append(
            "La distribución de layouts en el video DEBE respetar aproximadamente "
            "estas proporciones:"
        )
        for layout_key in ["full_art", "split_right", "code_graphic", "code_graphic_visual"]:
            if layout_key not in allowed:
                continue
            if layout_key not in LAYOUT_PROPORTION_GUIDE:
                continue
            min_r, max_r = LAYOUT_PROPORTION_GUIDE[layout_key]
            min_pct = int(min_r * 100)
            max_pct = int(max_r * 100)
            dominant = " ES EL LAYOUT DOMINANTE." if layout_key == "full_art" else ""
            max_note = " (máximo 1 por video)" if layout_key == "code_graphic_visual" else ""
            lines.append(
                f"- '{layout_key}': {min_pct}-{max_pct}% de las escenas"
                f"{dominant}{max_note}."
            )
        lines.append("")
        lines.append(
            "Esto significa que en la mayoría de los videos, la mayor parte "
            "de las escenas deben ser 'full_art'. Cuando dudes entre 'full_art' "
            "y otro layout, USA 'full_art'."
        )
        lines.append("")
        lines.append(
            "Las escenas 'full_art' son las que sostienen la narrativa. Los otros "
            "layouts son ACENTOS, no la norma."
        )
        layout_proportion_block = "\n".join(lines)
    else:
        layout_proportion_block = ""

    # Bloque de decisión entre code_graphic y code_graphic_visual
    style_allowed = STYLE_PROMPTS[style_key].get("allowed_layouts", [])
    if "code_graphic" in style_allowed and "code_graphic_visual" in style_allowed:
        code_graphic_decision_block = (
            "REGLAS DE DECISIÓN: 'code_graphic' vs 'code_graphic_visual':\n"
            "Ambos layouts son válidos, pero se usan en contextos distintos:\n"
            "\n"
            "- Usa 'code_graphic' para la mayoría de las escenas con datos, listas "
            "o cifras. Es la opción por defecto cuando dudes.\n"
            "\n"
            "- Usa 'code_graphic_visual' SOLO cuando se cumplan las DOS condiciones:\n"
            "  1. Los bullets de la escena sean el FOCO de la narración (no un apoyo).\n"
            "  2. El concepto sea lo bastante importante como para merecer una pausa "
            "visual reforzada con un explainer.\n"
            "  Regla práctica: usa 'code_graphic_visual' un máximo de 1-2 veces "
            "por video. Si dudes, usa 'code_graphic'.\n"
            "\n"
            "- PROHIBIDO usar 'code_graphic_visual' en la primera escena del video "
            "(el hook va con 'full_art').\n"
            "- PROHIBIDO usar 'code_graphic_visual' en la escena final (el CTA va "
            "con 'full_art').\n"
        )
    else:
        code_graphic_decision_block = ""

    bullet_quality_block = (
        "REGLAS DE CALIDAD DE BULLETS:\n"
        "- Cada bullet debe ser un concepto autónomo y concreto, no una frase "
        "genérica.\n"
        "- Máximo 60 caracteres por bullet en 'code_graphic_visual'.\n"
        "- Evita bullets con subordinadas o comas múltiples.\n"
        "- Los bullets NO son oraciones completas; son etiquetas o frases nominales."
    )

    if _has_overlay_layouts(style_key):
        overlay_rules_block = (
            "REGLAS DE CONTENIDO SUPERPUESTO (overlay_content):\n"
            "- Si layout_type es 'split_right': completa 'overlay_content' con "
            "'title' (MAYÚSCULAS cortas, 2-4 palabras) y 'bullets' "
            "(lista de 1 a 3 ítems breves).\n"
            "- Si layout_type es 'code_graphic': completa 'overlay_content' con "
            "'title' (MAYÚSCULAS) y 'bullets' (lista de 1 a 3 ítems breves).\n"
            "- Si layout_type es 'code_graphic_visual': completa 'overlay_content' "
            "SOLO con 'bullets' (2 a 4 ítems). El campo 'title' debe ser null. "
            "Cada bullet debe ser corto y autónomo (máximo 60 caracteres).\n"
            "- Si layout_type es 'full_art': 'overlay_content' debe ser null."
        )
    else:
        overlay_rules_block = (
            "REGLAS DE CONTENIDO SUPERPUESTO (overlay_content):\n"
            "- Este estilo SOLO permite 'full_art', por lo que 'overlay_content' "
            "SIEMPRE debe ser null en TODAS las escenas."
        )

    if _has_overlay_layouts(style_key):
        example_scene_2 = f"""{{
            "scene_number": 2,
            "narration_text": "Texto explicativo en {lang_name}...",
            "layout_type": "split_right",
            "visual_prompt": "{style_example}, ...descripción de la acción...",
            "overlay_content": {{
                "title": "FACTORES CLAVE",
                "bullets": ["Tasa de interés", "Inflación anual"]
            }},
            "is_interactive_cta": false
        }}"""
    else:
        example_scene_2 = f"""{{
            "scene_number": 2,
            "narration_text": "Texto explicativo en {lang_name}...",
            "layout_type": "full_art",
            "visual_prompt": "{style_example}, ...descripción de la acción...",
            "overlay_content": null,
            "is_interactive_cta": false
        }}"""

    visual_prompt_rules_block = (
        "REGLAS DE PROMPT VISUAL ('visual_prompt') — CRÍTICAS:\n"
        "Si layout_type NO es 'code_graphic' ni 'code_graphic_visual', "
        "'visual_prompt' DEBE estar en INGLÉS.\n"
        "ESTRUCTURA OBLIGATORIA del 'visual_prompt': SOLO la descripción de la escena.\n"
        "NO incluyas NUNCA:\n"
        "  - El estilo visual del proyecto (ej. 'Clean 2D vector cartoon illustration', 'Classic stick figure').\n"
        "  - Reglas de fondo (ej. 'spacious uncluttered composition', 'pure white background').\n"
        "  - Reglas anti-texto (ej. 'no text', 'without any text').\n"
        "  - Directivas de aspect ratio (ej. '16:9', 'horizontal widescreen ratio').\n"
        "El pipeline añade TODOS esos elementos automáticamente después. Si los incluyes, "
        "se duplicarán y el prompt resultante quedará demasiado largo.\n"
        "\n"
        "Ejemplo INCORRECTO (NO hagas esto):\n"
        "  'A cartoon man standing in front of a graduation hall Clean 2D vector cartoon "
        "illustration, cell-shaded style. Characters: Expressive 2D cartoon human figures..., "
        "spacious uncluttered composition, soft depth of field, no text, 16:9.'\n"
        "\n"
        "Ejemplo CORRECTO:\n"
        "  'A cartoon man standing in front of a graduation hall, smiling brightly.'\n"
        "\n"
        "La diferencia: el INCORRECTO incluye estilo, fondo y ratio. El CORRECTO solo "
        "describe la escena.\n"
        "\n"
        "Longitud máxima del 'visual_prompt': 150 caracteres."
        "NOTA SOBRE EL ESTILO: El estilo visual del proyecto describe CÓMO se renderizan los elementos, "
        "no QUÉ elementos deben aparecer. Si la escena no menciona personas, "
        "NO las incluyas aunque el estilo mencione 'human figures'."
    )

    final_reminder = (
        "\nRECORDATORIO FINAL:\n"
        "El 'visual_prompt' NO incluye estilo, ni reglas de fondo, ni 'no text', "
        "ni ratio. El pipeline los añade automáticamente. Si los ves en tu respuesta, "
        "está MAL."
    )

    batch_system_prompt = f"""
Eres un director de arte y guionista experto en videos educativos de economía y finanzas en estilo animación 2D vectorial limpia (cell-shaded).
Generas un subconjunto de escenas específicas manteniendo absoluta continuidad narrativa con las escenas previas.

REGLAS STRICTAS DE IDIOMA:
1. 'narration_text' MUST be written strictly in {lang_name}.
2. 'overlay_content' ('title' and 'bullets') MUST be written strictly in {lang_name}.
3. 'visual_prompt' MUST ALWAYS be written strictly in ENGLISH (regardless of target language).

{visual_prompt_rules_block}

{subject_rules_block}

{layout_rules_block}

{layout_proportion_block}

{code_graphic_decision_block}

{overlay_rules_block}

{bullet_quality_block}

{prompt_length_block}

{final_reminder}


REGLAS CRÍTICAS DE COMPLEJIDAD VISUAL (OBLIGATORIAS):
1. UN SOLO FOCO POR ESCENA: Cada 'visual_prompt' describe UNA sola escena concreta con MÁXIMO 2-3 elementos principales. NO combines múltiples metáforas en una misma imagen.
2. PROHIBIDO ENCADENAR ACCIONES: No uses construcciones tipo "X fluyendo hacia Y mientras Z observa" o "X alineando Y con Z". Elige UNA sola acción principal y descarta las demás.
3. PROHIBIDO METÁFORAS COMPUESTAS: No uses metáforas abstractas híbridas como "engranajes que son calendarios", "cerebros que contienen plantas", "tuberías que llevan dividendos". Elige UNA metáfora simple o usa una escena literal.
4. SIMPLIFICACIÓN NARRATIVA: Si la narración es compleja, elige el elemento MÁS representativo y descarta los demás. Es mejor una imagen simple y clara que una sobrecargada y confusa.
5. ACCIONES SIMPLES DE PERSONAJE: Los personajes deben tener UNA acción simple y clara. Bien: "señalando un calendario", "mirando una pantalla con sorpresa". Mal: "alineando discos con engranajes mientras guía un río".
6. EVITAR SUPERFICIES CON TEXTO POTENCIAL: No describas fachadas de tiendas, carteles, menús, periódicos, libros abiertos, pantallas con texto o etiquetas. Si la narración requiere esos elementos, descríbelos como "una forma geométrica abstracta" o "un rectángulo de color plano" en lugar de un objeto con texto legible.


Esquema JSON requerido para este lote:
{{
  "scenes": [
    {{
      "scene_number": 1,
      "narration_text": "Texto exacto de locución en {lang_name}...",
      "layout_type": "{STYLE_PROMPTS[style_key].get('allowed_layouts', ['full_art'])[0]}",
      "visual_prompt": "{style_example}, ...descripción de la acción...",
      "overlay_content": null,
      "is_interactive_cta": false
    }},
    {example_scene_2}
  ]
}}

"""

    for start_scene in range(1, target_scenes + 1, batch_size):
        end_scene = min(start_scene + batch_size - 1, target_scenes)
        print(f"🎬 [Paso 2/2] Generando lote de escenas {start_scene} a {end_scene} (de {target_scenes})...")

        previous_context = all_scenes[-2:] if all_scenes else []
        current_batch_outline = [s for s in master_outline if start_scene <= s.get("scene_number", 0) <= end_scene]

        batch_user_prompt = f"""
OBJETIVO: Generar el JSON detallado para las escenas de la {start_scene} a la {end_scene}.

ESCALETA MAESTRA PARA ESTE LOTE:
{json.dumps(current_batch_outline, ensure_ascii=False, indent=2)}

ÚLTIMAS ESCENAS GENERADAS PREVIAMENTE (Para continuidad):
{json.dumps(previous_context, ensure_ascii=False, indent=2)}

Instrucciones: Devuelve el objeto JSON 'scenes' correspondiente EXCLUSIVAMENTE a las escenas del rango [{start_scene} - {end_scene}].
"""

        try:
            raw_batch_json = call_openrouter_api(batch_system_prompt, batch_user_prompt, model, max_tokens=8192)
            batch_data = _parse_json_safely(raw_batch_json, f"FASE 2 - lote {start_scene}-{end_scene}")
            if batch_data is None:
                print(f"❌ Error al parsear el lote {start_scene}-{end_scene}. Respuesta cruda (primeros 500 chars):")
                print(raw_batch_json[:500])
                break
            batch_scenes = batch_data.get("scenes", [])
            all_scenes.extend(batch_scenes)
        except Exception as e:
            print(f"❌ Error al procesar el lote {start_scene}-{end_scene}: {e}")
            break

    if not all_scenes:
        print("❌ Error: No se pudo compilar ninguna escena.")
        return None

    # --------------------------------------------------------------------------
    # FASE 3: ENSAMBLAJE FINAL Y VERIFICACIÓN
    # --------------------------------------------------------------------------
    scenes, th_prompt = apply_prompt_safeguards(
        all_scenes,
        outline_data.get("thumbnail_prompt", ""),
        aspect_ratio,
        style_key,
    )

    allowed_layouts = STYLE_PROMPTS[style_key].get(
        "allowed_layouts", ["full_art", "split_right", "code_graphic", "code_graphic_visual"]
    )
    scenes = _enforce_layout_proportions(scenes, allowed_layouts, MIN_FULL_ART_RATIO)

    manifest_dict = {
        "language": language,
        "visual_style": style_key,
        "visual_style_prompt": get_style_prompt(style_key),
        "visual_style_fonts": get_style_fonts(style_key),
        "allowed_layouts": STYLE_PROMPTS[style_key].get(
            "allowed_layouts", ["full_art", "split_right", "code_graphic"]
        ),
        "title": outline_data.get("title", idea.get("titulo", topic)),
        "video_type": video_type,
        "aspect_ratio": aspect_ratio,
        "target_duration_seconds": target_duration,
        "includes_interactive_cta": outline_data.get("includes_interactive_cta", True),
        "thumbnail_prompt": th_prompt,
        "thumbnail_text": outline_data.get("thumbnail_text", "¡ERROR FATAL!"),
        "scenes": scenes,
    }

    try:
        return ScriptManifest.model_validate(manifest_dict)
    except Exception as e:
        print(f"❌ Error de validación en Pydantic al ensamblar el guion final: {e}")
        return None

def generate_script(
    topic: Optional[str] = None,
    video_url: Optional[str] = None,
    target_duration: int = 600,
    video_type: str = "long",
    aspect_ratio: str = "16:9",
    model: str = "google/gemini-3.7-flash",
    project_dir: Optional[str] = None,
    language: str = TARGET_LANGUAGE,
    style: Optional[str] = None,
) -> Dict[str, Any]:
    """Flujo completo de generación, aprobación y almacenamiento del guion."""
    print("\n" + "=" * 85)
    print(" 🎬 GENERADOR DE GUIONES PARA FACELESS ENGINE")
    print("=" * 85)

    style_key = get_style_key(style or _prompt_style_interactive())

    print(f"🎨 Estilo visual seleccionado: '{style_key}' — {get_style_description(style_key)}")

    idea_data = load_selected_idea()

    if not idea_data:
        print("⚠️ No se encontró 'output/selected_idea.json'. Generando a partir del tema directo.")
        user_topic = topic or input("👉 Ingrese el tema del video: ").strip() or "Tema General"
        idea_data = {
            "topic": user_topic,
            "selected_idea": {
                "titulo": user_topic,
                "gancho_inicial": f"¿Sabías esto sobre {user_topic}?",
                "resumen_premisa": f"Un recorrido por {user_topic}.",
                "remate_o_giro": "Increíble pero cierto."
            }
        }

    reverse_analysis = load_reverse_analysis()

    manifest = generate_script_from_openrouter(
        idea_data=idea_data,
        reverse_analysis=reverse_analysis,
        target_duration=target_duration,
        video_type=video_type,
        aspect_ratio=aspect_ratio,
        model=model,
        language=language,
        style_key=style_key,
    )

    if not manifest:
        raise RuntimeError("No se pudo generar el guion con OpenRouter.")

    final_manifest = display_and_review_script(manifest)
    manifest_data = final_manifest.model_dump()

    if not project_dir:
        project_dir = create_project_structure(manifest_data["title"])
    else:
        os.makedirs(os.path.join(project_dir, "audio"), exist_ok=True)
        os.makedirs(os.path.join(project_dir, "images"), exist_ok=True)

    manifest_path = os.path.join(project_dir, "manifest.json")

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2, ensure_ascii=False)

    os.makedirs("output", exist_ok=True)
    current_proj_path = os.path.join("output", "current_project.json")
    with open(current_proj_path, "w", encoding="utf-8") as f:
        json.dump({"project_dir": project_dir, "title": manifest_data["title"]}, f, indent=2, ensure_ascii=False)

    print(f"\n📁 Proyecto actualizado en: '{project_dir}'")
    print(f"📄 Guion y manifiesto guardados en: '{manifest_path}'\n")

    return manifest_data