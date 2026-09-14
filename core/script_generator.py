import os
import re
import json
import argparse
from datetime import datetime
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv
import requests

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from pydantic import BaseModel, Field

load_dotenv()


# --- ESQUEMAS DE DATOS (PYDANTIC) ---

class Scene(BaseModel):
    scene_number: int = Field(description="Número secuencial de la escena (1, 2, 3...)")
    narration_text: str = Field(description="Texto en español que dirá la voz en off para esta escena")
    visual_prompt: str = Field(description="Prompt visual ultradetallado en INGLÉS listo para generador de imágenes 2D")
    audio_file: Optional[str] = Field(default=None, description="Ruta al archivo MP3 de la escena")
    audio_duration_seconds: Optional[float] = Field(default=None, description="Duración exacta en segundos del audio")
    image_path: Optional[str] = Field(default=None, description="Ruta a la imagen o video generado para la escena")


class ScriptManifest(BaseModel):
    title: str = Field(description="Título sugerido y atractivo para el video")
    video_type: str = Field(default="short", description="Tipo de video: 'short' o 'long'")
    aspect_ratio: str = Field(default="9:16", description="Relación de aspecto: '9:16' o '16:9'")
    target_duration_seconds: int = Field(description="Duración estimada del video completo en segundos")
    scenes: List[Scene] = Field(description="Lista ordenada de las escenas que componen el guion")
    total_audio_duration_seconds: Optional[float] = Field(default=None, description="Duración acumulada de los audios")


# --- MANEJO DE ESTRUCTURA DE PROYECTOS ---

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

    # Registrar el proyecto activo en output/current_project.json
    os.makedirs("output", exist_ok=True)
    current_proj_path = os.path.join("output", "current_project.json")
    with open(current_proj_path, "w", encoding="utf-8") as f:
        json.dump({"project_dir": project_dir, "title": title}, f, indent=2, ensure_ascii=False)

    return project_dir


# --- CARGA DE INPUTS PREVIOS ---

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


# --- GENERADOR VIA OPENROUTER ---

def generate_script_from_openrouter(
    idea_data: Dict[str, Any],
    reverse_analysis: Optional[Dict[str, Any]] = None,
    target_duration: int = 60,
    video_type: str = "long",
    aspect_ratio: str = "16:9",
    model: str = "google/gemini-3.7-flash"
) -> Optional[ScriptManifest]:
    """Genera el guion enviando la idea seleccionada a OpenRouter calculando dinámicamente el número de escenas."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("❌ Error: OPENROUTER_API_KEY no encontrada en .env")
        return None

    topic = idea_data.get("topic", "")
    idea = idea_data.get("selected_idea", {})

    # Cálculo dinámico de cantidad de escenas (promedio ~7s por escena)
    target_scenes = max(3, round(target_duration / 7.0))

    print(f"\n🧠 Generando guion de {target_duration}s ({target_scenes} escenas estimadas, formato {aspect_ratio}) usando {model}...")

    # Selección de Style Anchor según el aspect ratio
    if aspect_ratio == "16:9":
        style_anchor = (
            "Minimalist 2D vector stick-figure illustration in Deep Epoch educational style, "
            "Characters: Round white head with black outline, thin black stick limbs, simple flat colors, "
            "FACIAL FEATURES (MANDATORY): Every stick figure MUST have simple black dot eyes and a clear simple mouth line (smile, neutral line, or open mouth depending on the emotion), "
            "NEVER generate blank, featureless, or empty white circle heads, "
            "no 3D rendering, no gradients, no shading, high contrast, 16:9 horizontal widescreen ratio, "
            "panoramic composition, flat ground line extending horizontally."
        )
    else:
        style_anchor = (
            "Minimalist 2D vector stick-figure illustration in Deep Epoch educational style, "
            "round white head with black outline, thin black stick limbs, simple flat colors, "
            "no 3D rendering, no gradients, no shading, high contrast, 9:16 vertical ratio."
        )

    narrative_structure_instructions = ""
    if video_type == "long":
        narrative_structure_instructions = (
            f"ESTRUCURA NARRATIVA PARA FORMATO LARGO ({target_scenes} escenas exactas):\n"
            "- Escena 1: Gancho inicial directo e impactante.\n"
            "- Escena 2: Introducción al problema o tema central.\n"
            f"- Escenas 3 a {target_scenes - 1}: Desarrollo pedagógico paso a paso, dividido en conceptos clave o ejemplos visuales.\n"
            f"- Escena {target_scenes}: Conclusión, reflexión final o remate definitivo.\n\n"
        )

    style_guidelines = ""
    if reverse_analysis:
        style_guidelines = (
            f"- Estilo narrativo: {reverse_analysis.get('estilo_visual_narrativo', 'Educativo y directo')}\n"
            f"- Recurso de retención: {reverse_analysis.get('patron_retencion', 'Cambios visuales constantes y elementos icónicos')}\n"
        )

    system_instruction = (
        f"Eres un director de arte y guionista experto en videos educativos virales en formato monigotes 2D ('Deep Epoch style').\n"
        f"Tu tarea es transformar la idea recibida en un guion estructurado de EXACTAMENTE {target_scenes} escenas.\n\n"
        f"{narrative_structure_instructions}"
        "REGLAS ESTRICTAS DE ESTILO VISUAL (STICK FIGURE 2D):\n"
        "1. Narración (narration_text): En ESPAÑOL, directo al punto, dinámico, sin muletillas.\n"
        "2. Prompts Visuales (visual_prompt): Se escriben en INGLÉS para la API de imagen.\n"
        "3. IDIOMA DEL TEXTO DENTRO DE LA IMAGEN: Si el visual_prompt requiere texto impreso, diagramas, flechas con etiquetas, carteles o letreros en la imagen, ESE TEXTO ESPECÍFICO DEBE ESTAR EN ESPAÑOL (ej. text label in Spanish saying 'Nieve 130 km/h').\n"
        "4. Estilo Visual Obligatorio en CADA visual_prompt:\n"
        f"   - DEBES comenzar la descripción visual con este Style Anchor EXACTO:\n"
        f"     '{style_anchor}'\n"
        "   - Luego describe los personajes de palitos, sus expresiones, acciones simples, fondo plano y elementos icónicos.\n"
        "5. Evita términos como 'photorealistic', '3D render', 'cinematic lighting', 'shading'.\n\n"
        "Esquema JSON requerido:\n"
        "{\n"
        '  "title": "Título del video",\n'
        f'  "video_type": "{video_type}",\n'
        f'  "aspect_ratio": "{aspect_ratio}",\n'
        f'  "target_duration_seconds": {target_duration},\n'
        '  "scenes": [\n'
        '    {\n'
        '      "scene_number": 1,\n'
        '      "narration_text": "Texto exacto de locución en español",\n'
        f'      "visual_prompt": "{style_anchor} Two stick figure cavemen examining a puddle of dirty water, text label in Spanish reading \'Agua Contaminada\'."\n'
        '    }\n'
        '  ]\n'
        "}"
    )

    user_prompt = f"""
Tema general: {topic}
Título/Idea: {idea.get('titulo', topic)}
Gancho Obligatorio (0-3s): {idea.get('gancho_inicial', '')}
Premisa/Desarrollo: {idea.get('resumen_premisa', '')}
Remate/Giro Final: {idea.get('remate_o_giro', '')}

{style_guidelines}
Duración objetivo: {target_duration} segundos.
Cantidad obligatoria de escenas: {target_scenes} escenas.
Asegúrate de estructurar cada visual_prompt aplicando el Style Anchor especificado.
"""

    raw_content = ""
    try:
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
                temperature=0.7,
                max_tokens=3500,
                response_format={"type": "json_object"},
                extra_body={"reasoning": {"effort": "low"}}
            )
            raw_content = response.choices[0].message.content
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
                "temperature": 0.7,
                "max_tokens": 3500,
                "response_format": {"type": "json_object"},
                "reasoning": {"effort": "low"}
            }
            res = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=45)
            res.raise_for_status()
            res_data = res.json()
            raw_content = res_data["choices"][0]["message"]["content"]

        clean_json_str = raw_content.strip()
        if clean_json_str.startswith("```"):
            clean_json_str = re.sub(r"^```[a-zA-Z]*\n?", "", clean_json_str)
            clean_json_str = re.sub(r"\n?```$", "", clean_json_str).strip()

        manifest_dict = json.loads(clean_json_str)
        
        # Garantizar que los metadatos de formato estén explícitos
        manifest_dict["video_type"] = video_type
        manifest_dict["aspect_ratio"] = aspect_ratio
        manifest_dict["target_duration_seconds"] = target_duration

        return ScriptManifest.model_validate(manifest_dict)

    except Exception as e:
        print(f"❌ Error al generar el guion vía OpenRouter: {e}")
        if raw_content:
            print(f"📄 Respuesta cruda:\n{raw_content}")
        return None


# --- REVISIÓN Y EDICIÓN INTERACTIVA ---

def display_and_review_script(manifest: ScriptManifest) -> ScriptManifest:
    """Muestra el guion en consola y permite ajustes manuales directos."""
    data = manifest.model_dump()

    while True:
        print("\n" + "=" * 85)
        print(f" 📜 GUION GENERADO: '{data['title']}' ({data['target_duration_seconds']}s | {data['video_type'].upper()} {data['aspect_ratio']})")
        print(f" 🎬 Total Escenas: {len(data['scenes'])}")
        print("=" * 85)

        for sc in data["scenes"]:
            print(f"\n🎬 ESCENA {sc['scene_number']}:")
            print(f"   🗣️  Locución (ES): \"{sc['narration_text']}\"")
            print(f"   🖼️  Visual Prompt (EN): {sc['visual_prompt']}")

        print("\n" + "=" * 85)
        print("🛑 REVISIÓN E INTERVENCIÓN HUMANA:")
        print("👉 Presiona [ENTER] o '1' para APROBAR el guion.")
        print("👉 Escribe '2' para editar una escena específica.")
        print("👉 Escribe '3' para cambiar el título del video.")

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

    return ScriptManifest.model_validate(data)


# --- FUNCIÓN PRINCIPAL INTEGRADA ---

def generate_script(
    topic: Optional[str] = None,
    video_url: Optional[str] = None,
    target_duration: int = 60,
    video_type: str = "long",
    aspect_ratio: str = "16:9",
    model: str = "google/gemini-3.7-flash",
    project_dir: Optional[str] = None
) -> Dict[str, Any]:
    """Flujo completo de generación, aprobación y almacenamiento del guion."""
    print("\n" + "=" * 85)
    print(" 🎬 GENERADOR DE GUIONES PARA FACELESS ENGINE")
    print("=" * 85)

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
        model=model
    )

    if not manifest:
        raise RuntimeError("No se pudo generar el guion con OpenRouter.")

    # Intervención humana
    final_manifest = display_and_review_script(manifest)
    manifest_data = final_manifest.model_dump()

    # Determinar el directorio de destino del proyecto
    if not project_dir:
        project_dir = create_project_structure(manifest_data["title"])
    else:
        os.makedirs(os.path.join(project_dir, "audio"), exist_ok=True)
        os.makedirs(os.path.join(project_dir, "images"), exist_ok=True)

    manifest_path = os.path.join(project_dir, "manifest.json")

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2, ensure_ascii=False)

    # Actualizar estado global del proyecto activo
    os.makedirs("output", exist_ok=True)
    current_proj_path = os.path.join("output", "current_project.json")
    with open(current_proj_path, "w", encoding="utf-8") as f:
        json.dump({"project_dir": project_dir, "title": manifest_data["title"]}, f, indent=2, ensure_ascii=False)

    print(f"\n📁 Proyecto actualizado en: '{project_dir}'")
    print(f"📄 Guion y manifiesto guardados en: '{manifest_path}'\n")

    return manifest_data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generador de Guiones Faceless Engine")
    parser.add_argument("--duration", type=int, default=60, help="Duración objetivo en segundos")
    parser.add_argument("--type", type=str, default="long", choices=["short", "long"], help="Tipo de video")
    parser.add_argument("--ratio", type=str, default="16:9", choices=["9:16", "16:9"], help="Aspect Ratio")
    parser.add_argument("--model", type=str, default="google/gemini-3.7-flash", help="Modelo de OpenRouter")

    args = parser.parse_args()
    generate_script(
        target_duration=args.duration,
        video_type=args.type,
        aspect_ratio=args.ratio,
        model=args.model
    )