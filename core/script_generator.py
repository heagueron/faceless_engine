import os
import re
import json
import argparse
from datetime import datetime
from typing import List, Optional, Dict, Any, Literal
from dotenv import load_dotenv
import requests

from core.config import TARGET_LANGUAGE, LAYOUT_PROPORTION_GUIDE, MIN_FULL_ART_RATIO

from core.styles import (
    get_style_prompt,
    get_style_key,
    get_style_background_rules,
    get_style_description,      
    get_style_fonts,            # ← NUEVO
    build_style_directive,
    list_available_styles,      
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
    layout_type: Literal["full_art", "split_right", "code_graphic", "code_graphic_visual"] = Field(
        default="full_art",
        description=(
            "full_art: Imagen completa 100% IA sin texto.\n"
            "split_right: Imagen IA encuadrada a la izquierda con 30% espacio negativo a la derecha para tarjeta de texto superpuesta por Python.\n"
            "code_graphic: Sin imagen de IA. Gráfico o tabla de datos generado 100% por Python.\n"
            "code_graphic_visual: Sin imagen de IA. Pizarra blanca con bullets grandes y figura explainer a un lado apuntando hacia ella."
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

    visual_style_fonts: Dict[str, str] = Field(
        default_factory=dict,
        description="Fuentes del estilo en el momento de generación (snapshot inmutable)."
    )

    visual_style_prompt: str = Field(
        default="",
        description="Fragmento de prompt en INGLÉS del estilo (snapshot para inmutabilidad del proyecto)"
    )

    allowed_layouts: List[str] = Field(
        default_factory=lambda: ["full_art", "split_right", "code_graphic", "code_graphic_visual"],
        description="Layouts permitidos por el estilo en el momento de generación (snapshot)."
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

def apply_prompt_safeguards(
    scenes: List[Dict[str, Any]],
    thumbnail_prompt: str,
    aspect_ratio: str,
    style_key: str
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
        # Detectar la firma del estilo (primeras palabras clave)
        style_marker_lower = style_marker.lower()
        p_lower = p.lower()
        idx = p_lower.find(style_marker_lower)
        if idx > 20:  # >20 para no cortar si el estilo empieza al principio (raro)
            # Cortar antes del estilo
            return p[:idx].rstrip(" ,.")
        return p

    def _apply_to_prompt(prompt: str, layout: str) -> str:
        prompt = _clean_prompt(prompt or "")
        prompt = _strip_embedded_style(prompt)  # ← NUEVO

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

def _parse_json_safely(raw_json_str: str, context: str = "") -> Optional[Dict[str, Any]]:
    """
    Parsea JSON del LLM tolerando errores comunes.
    Intenta:
      1. json.loads() directo
      2. json_repair.loads() como fallback
    Retorna None si todo falla.
    """
    if not raw_json_str:
        return None

    # Intento 1: parseo estricto
    try:
        return json.loads(raw_json_str)
    except json.JSONDecodeError:
        pass

    # Intento 2: reparación con json_repair
    try:
        from json_repair import repair_json
        repaired = repair_json(raw_json_str, return_objects=True)
        if isinstance(repaired, dict):
            print(f"   🔧 JSON reparado automáticamente ({context}).")
            return repaired
    except ImportError:
        print(f"   ⚠️ json_repair no está instalado. Instala con: pip install json-repair")
    except Exception as e:
        print(f"   ⚠️ Fallo al reparar JSON ({context}): {e}")

    return None

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
    # Solo se aplica al estilo stick_classic_klein, que requiere prompts muy cortos
    # para que Schnell/Klein respeten la escena. Otros estilos usan prompts más largos.
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

        # Bloque de decisión entre code_graphic y code_graphic_visual (solo si el estilo permite ambos)
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
            "por video. Si dudas, usa 'code_graphic'.\n"
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
        style_key,          # ← FALTABA
    )

    # Aplicar regla de proporción de layouts
    allowed_layouts = STYLE_PROMPTS[style_key].get(
        "allowed_layouts", ["full_art", "split_right", "code_graphic", "code_graphic_visual"]
    )
    scenes = _enforce_layout_proportions(scenes, allowed_layouts, MIN_FULL_ART_RATIO,)

    manifest_dict = {
        "language": language,
        "visual_style": style_key,                         
        "visual_style_prompt": get_style_prompt(style_key), 
        "visual_style_fonts": get_style_fonts(style_key),    # ← NUEVO
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
    import sys
    if not sys.stdin.isatty():
        return None

    styles = list_available_styles()
    print("\n" + "=" * 70)
    print(" 🎨 SELECCIÓN DE ESTILO VISUAL")
    print("=" * 70)
    for i, (key, desc) in enumerate(styles.items(), 1):
        default_marker = " [DEFAULT]" if key == DEFAULT_STYLE_KEY else ""
        print(f"  [{i}] {key}{default_marker}")
        print(f"      {desc}")
    print("=" * 70)

    choice = input(
        f"\n👉 Elige estilo por número o clave "
        f"[ENTER = default '{DEFAULT_STYLE_KEY}']: "
    ).strip()

    if not choice:
        return DEFAULT_STYLE_KEY   # ← explícito, no None

    if choice.isdigit():
        keys = list(styles.keys())
        idx = int(choice) - 1
        if 0 <= idx < len(keys):
            return keys[idx]
        print(f"⚠️ Número fuera de rango. Usando default.")
        return DEFAULT_STYLE_KEY

    if choice in styles:
        return choice

    print(f"⚠️ Estilo '{choice}' no reconocido. Usando default.")
    return DEFAULT_STYLE_KEY

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

def _enforce_layout_proportions(
    scenes: List[Dict[str, Any]],
    allowed_layouts: List[str],
    min_full_art_ratio: float = MIN_FULL_ART_RATIO
) -> List[Dict[str, Any]]:
    """
    Audita la proporción de layouts. Si 'full_art' está por debajo del
    mínimo, convierte los layouts sobrantes a 'full_art'.

    Prioridad de conversión (primero los que menos peso narrativo tienen):
      1. code_graphic_visual (nunca debería estar en exceso)
      2. code_graphic
      3. split_right
    """
    if "full_art" not in allowed_layouts:
        return scenes

    total = len(scenes)
    if total == 0:
        return scenes

    min_full_art_count = int(total * min_full_art_ratio)
    current_full_art = sum(1 for s in scenes if s.get("layout_type") == "full_art")

    if current_full_art >= min_full_art_count:
        return scenes

    deficit = min_full_art_count - current_full_art
    print(f"   🔧 Proporción de layouts: {current_full_art}/{total} full_art. "
          f"Faltan {deficit} para alcanzar el mínimo de {min_full_art_count}.")

    # Prioridad de conversión
    conversion_priority = ["code_graphic_visual", "code_graphic", "split_right"]

    for target_layout in conversion_priority:
        if deficit <= 0:
            break
        for scene in scenes:
            if deficit <= 0:
                break
            if scene.get("layout_type") == target_layout:
                # No convertir la primera ni la última escena si son code_graphic
                # (aunque en la práctica no deberían serlo)
                idx = scene.get("scene_number", 0)
                if idx == 1 or idx == total:
                    continue

                print(f"   🔧 Escena {idx}: '{target_layout}' → 'full_art' "
                      f"(por proporción).")
                scene["layout_type"] = "full_art"
                # Limpiar overlay_content si pasa a full_art
                scene["overlay_content"] = None
                # Mantener el visual_prompt original si existe; si no, un default
                if not scene.get("visual_prompt"):
                    scene["visual_prompt"] = (
                        "Simple abstract conceptual illustration representing "
                        "the narration"
                    )
                deficit -= 1

    return scenes

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

    args = parser.parse_args()
    generate_script(
        target_duration=args.duration,
        video_type=args.type,
        aspect_ratio=args.ratio,
        model=args.model,
        language=args.lang,
        style=args.style,
    )

    