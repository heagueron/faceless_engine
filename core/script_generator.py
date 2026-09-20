import os
import re
import json
import argparse
from datetime import datetime
from typing import List, Optional, Dict, Any, Literal
from dotenv import load_dotenv
import requests

from core.config import TARGET_LANGUAGE

from core.styles import (
    get_style_prompt,
    get_style_key,
    get_style_background_rules,
    get_style_description,      # ← FALTABA
    build_style_directive,
    list_available_styles,      # ← FALTABA
    STYLE_PROMPTS,
    DEFAULT_STYLE_KEY
)

# Mapeo auxiliar para indicarle al LLM el nombre del idioma en inglés
LANGUAGE_NAMES = {
    "es": "SPANISH",
    "en": "ENGLISH",
    "pt": "PORTUGUESE"
}

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from pydantic import BaseModel, Field

load_dotenv()


PROMPT_SUFFIX = "16:9 horizontal widescreen ratio"


# --- ESQUEMAS DE DATOS (PYDANTIC) ---

class OverlayContent(BaseModel):
    title: Optional[str] = Field(
        default=None, 
        description="Título o cifra principal en MAYÚSCULAS para superponer mediante Python."
    )
    bullets: Optional[List[str]] = Field(
        default=None, 
        description="Lista de 1 a 3 puntos clave o datos breves a superponer."
    )


class Scene(BaseModel):
    scene_number: int = Field(description="Número secuencial de la escena (1, 2, 3...)")
    narration_text: str = Field(description="Texto en español que dirá la voz en off para esta escena")
    layout_type: Literal["full_art", "split_right", "code_graphic"] = Field(
        default="full_art",
        description=(
            "full_art: Imagen completa 100% IA sin texto.\n"
            "split_right: Imagen IA encuadrada a la izquierda con 30% espacio negativo a la derecha para tarjeta de texto superpuesta por Python.\n"
            "code_graphic: Sin imagen de IA. Gráfico o tabla de datos generado 100% por Python."
        )
    )
    visual_prompt: Optional[str] = Field(
        default=None,
        description="Prompt visual ultradetallado en INGLÉS listo para FLUX.1 (None si layout_type es 'code_graphic')"
    )
    overlay_content: Optional[OverlayContent] = Field(
        default=None,
        description="Contenido de texto o cifras a renderizar mediante Python si layout_type es 'split_right' o 'code_graphic'"
    )
    is_interactive_cta: bool = Field(
        default=False,
        description="True únicamente si esta escena es una pregunta final condicional para generar interacción en los comentarios."
    )
    audio_file: Optional[str] = Field(default=None, description="Ruta al archivo MP3 de la escena")
    audio_duration_seconds: Optional[float] = Field(default=None, description="Duración exacta en segundos del audio")
    image_path: Optional[str] = Field(default=None, description="Ruta a la imagen o video generado para la escena")


class ScriptManifest(BaseModel):
    language: str = Field(default="es", description="Código de idioma del proyecto ('es', 'en', 'pt', etc.)")
    
    visual_style: str = Field(
        default="cartoon_2d_cellshaded",
        description="Clave del estilo visual aplicado (debe existir en core/styles.py)"
    )
    visual_style_prompt: str = Field(
        default="",
        description="Fragmento de prompt en INGLÉS del estilo (snapshot para inmutabilidad del proyecto)"
    )

    title: str = Field(description="Título sugerido y atractivo para el video")
    video_type: str = Field(default="long", description="Tipo de video: 'short' o 'long'")
    aspect_ratio: str = Field(default="16:9", description="Relación de aspecto: '9:16' o '16:9'")
    target_duration_seconds: int = Field(description="Duración estimada del video completo en segundos")
    includes_interactive_cta: bool = Field(
        default=False,
        description="Indica si el guion incluye una escena final con pregunta de debate para los comentarios."
    )
    thumbnail_prompt: str = Field(
        description="Prompt visual ultradetallado en INGLÉS optimizado para la miniatura."
    )
    thumbnail_text: str = Field(
        description="Texto de gancho corto en MAYÚSCULAS en español para la miniatura (ej. '¡ERROR FATAL!', '¡NO HAGAS ESTO!')."
    )
    scenes: List[Scene] = Field(description="Lista ordenada de las escenas que componen el guion")
    total_audio_duration_seconds: Optional[float] = Field(default=None, description="Duración acumulada de los audios")


# --- MANEJO DE ESTRUCTURA DE PROYECTOS Y ARCHIVOS ---

def slugify(text: str, max_words: int = 4) -> str:
    """Convierte un título en un slug limpio usando las primeras N palabras."""
    clean_text = re.sub(r"[^\w\s]", "", text.lower(), flags=re.UNICODE)
    words = clean_text.split()[:max_words]
    return "_".join(words) if words else "proyecto_faceless"


def create_project_structure(title: str, base_projects_dir: str = "projects") -> str:
    """Crea la carpeta timestamped del proyecto e interactúa con audio/ e images/."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder_slug = slugify(title)
    project_dir = os.path.join(base_projects_dir, f"{timestamp}_{folder_slug}")

    os.makedirs(os.path.join(project_dir, "audio"), exist_ok=True)
    os.makedirs(os.path.join(project_dir, "images"), exist_ok=True)

    os.makedirs("output", exist_ok=True)
    current_proj_path = os.path.join("output", "current_project.json")
    with open(current_proj_path, "w", encoding="utf-8") as f:
        json.dump({"project_dir": project_dir, "title": title}, f, indent=2, ensure_ascii=False)

    return project_dir


def load_selected_idea() -> Optional[Dict[str, Any]]:
    """Carga la idea seleccionada desde output/selected_idea.json."""
    idea_path = os.path.join("output", "selected_idea.json")
    if os.path.exists(idea_path):
        try:
            with open(idea_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                print(f"💡 Idea cargada desde '{idea_path}': '{data.get('selected_idea', {}).get('titulo', 'Sin título')}'")
                return data
        except Exception as e:
            print(f"⚠️ No se pudo leer '{idea_path}': {e}")
    return None


def load_reverse_analysis() -> Optional[Dict[str, Any]]:
    """Carga el análisis de ingeniería inversa si existe en output/."""
    analysis_path = os.path.join("output", "reverse_prompting_analysis.json")
    if os.path.exists(analysis_path):
        try:
            with open(analysis_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("analysis")
        except Exception as e:
            print(f"⚠️ No se pudo leer el análisis de ingeniería inversa: {e}")
    return None


def apply_prompt_safeguards(
    scenes: List[Dict[str, Any]],
    thumbnail_prompt: str,
    aspect_ratio: str,
    style_key: str
) -> tuple[List[Dict[str, Any]], str]:
    """Garantiza estilo, reglas de encuadre y aspect ratio sin duplicaciones."""
    style_prompt = get_style_prompt(style_key)
    bg_rules = get_style_background_rules(style_key)
    # Detectar la "firma" del estilo (primeras palabras clave) para evitar duplicar
    style_marker = style_prompt.split(",")[0].strip()[:40]

    ratio_directive = (
        "16:9 horizontal widescreen ratio" if aspect_ratio == "16:9"
        else "9:16 vertical ratio"
    )

    def _apply_to_prompt(prompt: str, layout: str) -> str:
        prompt = (prompt or "").strip()

        if style_marker.lower() not in prompt.lower():
            prompt = f"{style_prompt} {prompt}"

        if layout == "split_right" and "left 70%" not in prompt.lower():
            prompt += (
                ". Subject and main action framed strictly on the left 70% of the image, "
                "the right 30% of the frame is an empty neutral wall or clean blurred "
                "background with empty negative space."
            )

        if bg_rules and bg_rules.lower() not in prompt.lower():
            prompt += f", {bg_rules}"

        if "completely clean" not in prompt.lower() and "no text" not in prompt.lower():
            prompt += ", completely clean without any text, letters, or words"

        if ratio_directive.lower() not in prompt.lower():
            prompt += f", {ratio_directive}."

        return prompt

    for scene in scenes:
        layout = scene.get("layout_type", "full_art")
        if layout == "code_graphic":
            scene["visual_prompt"] = None
            continue
        scene["visual_prompt"] = _apply_to_prompt(scene.get("visual_prompt", ""), layout)

    th_prompt = _apply_to_prompt(thumbnail_prompt, "full_art")
    return scenes, th_prompt

# --- LLAMADA BASE A OPENROUTER ---

def call_openrouter_api(system_instruction: str, user_prompt: str, model: str, max_tokens: int = 8192) -> str:
    """Envía la solicitud a OpenRouter asegurando respuesta en formato JSON."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY no encontrada en .env")

    clean_json_str = ""
    if OpenAI is not None:
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
            extra_body={"reasoning": {"effort": "low"}}
        )
        clean_json_str = response.choices[0].message.content
    else:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/faceless-engine",
            "X-Title": "Faceless Engine"
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.2,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
            "reasoning": {"effort": "low"}
        }
        res = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=90)
        res.raise_for_status()
        res_data = res.json()
        clean_json_str = res_data["choices"][0]["message"]["content"]

    clean_json_str = clean_json_str.strip()
    if clean_json_str.startswith("```"):
        clean_json_str = re.sub(r"^```[a-zA-Z]*\n?", "", clean_json_str)
        clean_json_str = re.sub(r"\n?```$", "", clean_json_str).strip()

    return clean_json_str


# --- GENERACIÓN POR LOTES (STATEFUL BATCHING) ---

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
        outline_data = json.loads(raw_outline_json)
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

    batch_system_prompt = f"""
Eres un director de arte y guionista experto en videos educativos de economía y finanzas en estilo animación 2D vectorial limpia (cell-shaded).
Generas un subconjunto de escenas específicas manteniendo absoluta continuidad narrativa con las escenas previas.

REGLAS STRICTAS DE IDIOMA:
1. 'narration_text' MUST be written strictly in {lang_name}.
2. 'overlay_content' ('title' and 'bullets') MUST be written strictly in {lang_name}.
3. 'visual_prompt' MUST ALWAYS be written strictly in ENGLISH (regardless of target language).

REGLAS ESTRICTAS DE LAYOUT (layout_type):
1. layout_type = 'full_art' (DEFAULT): Para la mayoría de las escenas narrativas o conceptuales. Ocupa el 100% de la pantalla sin texto.
2. layout_type = 'split_right': Cuando se expliquen 2-3 puntos clave o cifras importantes que requieran apoyo visual escrito. La IA generará la imagen dejando el 30% derecho libre para una tarjeta de texto superpuesta por Python.
3. layout_type = 'code_graphic': ÚNICAMENTE para tablas comparativas complejas, gráficos de barras o cifras gigantes. La imagen NO se pide a la IA (visual_prompt = null), sino que se dibuja 100% por código en Python.

REGLAS DE CONTENIDO SUPERPUESTO (overlay_content):
- Si layout_type es 'split_right' o 'code_graphic', DEBES completar 'overlay_content' con 'title' (MAYÚSCULAS) y/o 'bullets' (lista de 1 a 3 ítems breves).
- Si layout_type es 'full_art', 'overlay_content' debe ser null.

REGLAS DE PROMPT VISUAL ('visual_prompt'):
Si layout_type NO es 'code_graphic', 'visual_prompt' DEBE estar escrito en INGLÉS y seguir la siguiente plantilla base:

"{get_style_prompt(style_key)} [DESCRIPCIÓN DE LA ACCIÓN Y ENTORNO], {get_style_background_rules(style_key)}, completely clean without any text, letters, or words, 16:9 horizontal widescreen ratio."

Esquema JSON requerido para este lote:
{{
  "scenes": [
    {{
      "scene_number": 1,
      "narration_text": "Texto exacto de locución en {lang_name}...",
      "layout_type": "full_art",
      "visual_prompt": "{style_example}, ...descripción de la acción...",
      "overlay_content": null,
      "is_interactive_cta": false
    }},
    {{
      "scene_number": 2,
      "narration_text": "Texto explicativo en {lang_name}...",
      "layout_type": "split_right",
      "visual_prompt": "{style_example}, ...descripción de la acción...",
      "overlay_content": {{
        "title": "FACTORES CLAVE",
        "bullets": ["Tasa de interés", "Inflación anual"]
      }},
      "is_interactive_cta": false
    }}
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
            batch_data = json.loads(raw_batch_json)
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
        style_key,          # ← FALTABA
    )

    manifest_dict = {
        "language": language,
        "visual_style": style_key,                          # ← NUEVO
        "visual_style_prompt": get_style_prompt(style_key), # ← NUEVO (snapshot inmutable)
        "title": outline_data.get("title", idea.get("titulo", topic)),
        "video_type": video_type,
        "aspect_ratio": aspect_ratio,
        "target_duration_seconds": target_duration,
        "includes_interactive_cta": outline_data.get("includes_interactive_cta", True),
        "thumbnail_prompt": th_prompt,
        "thumbnail_text": outline_data.get("thumbnail_text", "¡ERROR FATAL!"),
        "scenes": scenes
    }

    try:
        return ScriptManifest.model_validate(manifest_dict)
    except Exception as e:
        print(f"❌ Error de validación en Pydantic al ensamblar el guion final: {e}")
        return None


# --- REVISIÓN Y EDICIÓN INTERACTIVA ---

def display_and_review_script(manifest: ScriptManifest) -> ScriptManifest:
    """Muestra el guion en consola y permite ajustes manuales directos."""
    data = manifest.model_dump()

    while True:
        cta_badge = " [💬 INCLUYE PREGUNTA Y GLOBO DE TEXTO]" if data.get("includes_interactive_cta") else ""
        print("\n" + "=" * 85)
        print(f" 📜 GUION GENERADO: '{data['title']}' ({data['target_duration_seconds']}s | {data['video_type'].upper()} {data['aspect_ratio']}){cta_badge}")
        print(f" 🎬 Total Escenas: {len(data['scenes'])}")
        print("=" * 85)

        print(f"\n 🖼️  METADATOS DE MINIATURA (THUMBNAIL):")
        print(f"    💬 Texto Gancho (ES): \"{data.get('thumbnail_text', '')}\"")
        print(f"    🎨 Visual Prompt (EN): {data.get('thumbnail_prompt', '')}")
        print("-" * 85)

        for sc in data["scenes"]:
            tag_cta = " 💬 [PREGUNTA INTERACTIVA CON GLOBO]" if sc.get("is_interactive_cta") else ""
            layout = sc.get("layout_type", "full_art").upper()
            print(f"\n🎬 ESCENA {sc['scene_number']} [{layout}]{tag_cta}:")
            print(f"   🗣️  Locución (ES): \"{sc['narration_text']}\"")

            if sc.get("layout_type") == "code_graphic":
                print("   🖼️  Visual Prompt: [GRÁFICO GENERADO 100% POR CÓDIGO PYTHON]")
            else:
                print(f"   🖼️  Visual Prompt (EN): {sc.get('visual_prompt', '')}")

            if sc.get("overlay_content"):
                ov = sc["overlay_content"]
                if ov.get("title"):
                    print(f"   📝 Texto Overlay Título: \"{ov['title']}\"")
                if ov.get("bullets"):
                    print(f"   📝 Texto Overlay Bullets: {ov['bullets']}")

        print("\n" + "=" * 85)
        print("🛑 REVISIÓN E INTERVENCIÓN HUMANA:")
        print("👉 Presiona [ENTER] o '1' para APROBAR el guion.")
        print("👉 Escribe '2' para editar una escena específica.")
        print("👉 Escribe '3' para cambiar el título del video.")
        print("👉 Escribe '4' para editar los metadatos de la miniatura (Texto / Prompt).")

        opt = input("\nSelección: ").strip()

        if opt in ["", "1"]:
            print("\n✔ Guion aprobado sin cambios.")
            break
        elif opt == "2":
            scene_num = input("Número de escena a editar (ej. 1): ").strip()
            if scene_num.isdigit():
                idx = int(scene_num) - 1
                if 0 <= idx < len(data["scenes"]):
                    target_sc = data["scenes"][idx]
                    print(f"\n--- Editando Escena {target_sc['scene_number']} ---")

                    new_narr = input("Nueva locución [ENTER para mantener]: ").strip()
                    if new_narr:
                        target_sc["narration_text"] = new_narr

                    if target_sc.get("layout_type") != "code_graphic":
                        new_vis = input("Nuevo prompt visual [ENTER para mantener]: ").strip()
                        if new_vis:
                            target_sc["visual_prompt"] = new_vis

                    print(f"✔ Escena {target_sc['scene_number']} actualizada.")
                else:
                    print("⚠️ Número de escena fuera de rango.")
            else:
                print("⚠️ Número inválido.")
        elif opt == "3":
            new_title = input("Nuevo título para el video: ").strip()
            if new_title:
                data["title"] = new_title
                print(f"✔ Título actualizado a: '{new_title}'")
        elif opt == "4":
            print("\n--- Editando Metadatos de la Miniatura ---")
            new_th_text = input(f"Nuevo texto de gancho ({data.get('thumbnail_text', '')}) [ENTER para mantener]: ").strip()
            if new_th_text:
                data["thumbnail_text"] = new_th_text.upper()

            new_th_prompt = input("Nuevo visual prompt para la miniatura [ENTER para mantener]: ").strip()
            if new_th_prompt:
                data["thumbnail_prompt"] = new_th_prompt

            print("✔ Metadatos de miniatura actualizados.")

    return ScriptManifest.model_validate(data)

def _prompt_style_interactive() -> Optional[str]:
    """
    Pregunta al usuario qué estilo visual usar cuando:
      - No se pasó --style por CLI, y
      - El script se ejecuta en una terminal interactiva (TTY).
    Retorna la clave del estilo, o None para que get_style_key() use el default.
    """
    import sys
    if not sys.stdin.isatty():
        return None

    styles = list_available_styles()
    print("\n" + "=" * 70)
    print(" 🎨 SELECCIÓN DE ESTILO VISUAL")
    print("=" * 70)
    for i, (key, desc) in enumerate(styles.items(), 1):
        default_marker = " [DEFAULT]" if key == {DEFAULT_STYLE_KEY} else ""
        print(f"  [{i}] {key}{default_marker}")
        print(f"      {desc}")
    print("=" * 70)

    choice = input(
        f"\n👉 Elige estilo por número o clave "
        f"[ENTER = default 'cartoon_2d_cellshaded']: "
    ).strip()

    if not choice:
        return None

    if choice.isdigit():
        keys = list(styles.keys())
        idx = int(choice) - 1
        if 0 <= idx < len(keys):
            return keys[idx]
        print(f"⚠️ Número fuera de rango. Usando default.")
        return None

    if choice in styles:
        return choice

    print(f"⚠️ Estilo '{choice}' no reconocido. Usando default.")
    return None

# --- FUNCIÓN PRINCIPAL INTEGRADA ---

def generate_script(
    topic: Optional[str] = None,
    video_url: Optional[str] = None,
    target_duration: int = 600,
    video_type: str = "long",
    aspect_ratio: str = "16:9",
    model: str = "google/gemini-3.7-flash",
    project_dir: Optional[str] = None,
    language: str = TARGET_LANGUAGE,
    style: Optional[str] = None,   # NUEVO
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

    def _prompt_style_interactive() -> Optional[str]:
        """Pregunta al usuario qué estilo usar si corre en TTY y no se pasó --style."""
        import sys
        if not sys.stdin.isatty():
            return None
        styles = list_available_styles()
        print("\n🎨 Estilos visuales disponibles:")
        for i, (k, desc) in enumerate(styles.items(), 1):
            print(f"  [{i}] {k}")
            print(f"      {desc}")
        choice = input(f"\nElige estilo por número o clave [ENTER = default]: ").strip()
        if not choice:
            return None
        if choice.isdigit():
            keys = list(styles.keys())
            idx = int(choice) - 1
        if 0 <= idx < len(keys):
            return keys[idx]
        if choice in styles:
            return choice
        print(f"⚠️ Estilo '{choice}' no reconocido. Usando default.")
        return None

    args = parser.parse_args()
    generate_script(
        target_duration=args.duration,
        video_type=args.type,
        aspect_ratio=args.ratio,
        model=args.model,
        language=args.lang,
        style=args.style,        # ← FALTABA
    )

    