import os
import json
import argparse
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
import requests

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

load_dotenv()


# --- UTILIDADES DE TIEMPO ---

def format_timestamp(seconds: float) -> str:
    """Convierte segundos a formato MM:SS o HH:MM:SS para los capítulos de YouTube."""
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def prepare_scenes_with_timestamps(scenes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Calcula la marca de tiempo exacta de inicio de cada escena."""
    current_time = 0.0
    prepared_scenes = []

    for idx, sc in enumerate(scenes):
        duration = sc.get("audio_duration_seconds") or 6.0
        prepared_scenes.append({
            "scene_number": sc.get("scene_number", idx + 1),
            "start_seconds": current_time,
            "timestamp": format_timestamp(current_time),
            "narration_text": sc.get("narration_text", ""),
            "is_interactive_cta": sc.get("is_interactive_cta", False)
        })
        current_time += duration

    return prepared_scenes


# --- GENERACIÓN DE RESUMEN SEO Y CAPÍTULOS VÍA OPENROUTER ---

def generate_seo_metadata_and_chapters(
    title: str,
    scenes_with_time: List[Dict[str, Any]],
    target_duration: int = 60,
    model: str = "google/gemini-3.7-flash"
) -> Dict[str, Any]:
    """Sintetiza un resumen SEO, etiquetas y marca capítulos temáticos agrupados por significado."""
    api_key = os.getenv("OPENROUTER_API_KEY")

    # Formatear el timeline para que el LLM lo entienda
    timeline_str = "\n".join([
        f"[{sc['timestamp']}] Escena {sc['scene_number']}: {sc['narration_text']}"
        for sc in scenes_with_time
    ])

    cta_scene = next((sc for sc in scenes_with_time if sc.get("is_interactive_cta")), None)
    cta_question = cta_scene["narration_text"] if cta_scene else None

    system_prompt = (
        "Eres un experto en optimización SEO y retención para YouTube en el nicho de economía y finanzas.\n"
        "Tu tarea es analizar el guion de un video con sus marcas de tiempo y generar los metadatos de publicación.\n\n"
        "REGLAS ESTRICTAS PARA LOS CAPÍTULOS DE YOUTUBE (TIMELINE):\n"
        "1. NO crees un capítulo por cada escena. Agrupa las escenas en bloques temáticos principales.\n"
        "2. El primer capítulo DEBE ser obligatoriamente a los '00:00'.\n"
        "3. Duración total del video ~ " + str(target_duration) + " segundos:\n"
        "   - Si el video dura ~1 minuto (Short/Reel/Largo corto): Genera entre 3 y 4 capítulos clave como máximo (espaciados al menos 15-20s).\n"
        "   - Si el video dura más de 5 minutos: Genera entre 5 y 8 capítulos temáticos (espaciados al menos 45-60s).\n"
        "4. Asigna a cada capítulo un título llamativo, breve (3-6 palabras) y descriptivo derivado del contenido de esas escenas (ej: '00:21 - La estrategia de liquidez', NUNCA use 'Parte 1', 'Parte 2').\n"
        "5. Si hay una escena interactiva final (CTA), haz que sea el último capítulo (ej. '¿Tú qué opinas?').\n\n"
        "Responde EXCLUSIVAMENTE con un JSON con esta estructura:\n"
        "{\n"
        '  "seo_summary": "Resumen persuasivo de 2-3 oraciones optimizado para SEO.",\n'
        '  "hashtags": ["#Hashtag1", "#Hashtag2", "#Hashtag3"],\n'
        '  "tags": ["etiqueta 1", "etiqueta 2", "palabra clave 3"],\n'
        '  "chapters": [\n'
        '    {"timestamp": "00:00", "title": "Introducción / El aviso de Buffett"},\n'
        '    {"timestamp": "00:21", "title": "Acumulación masiva de liquidez"},\n'
        '    {"timestamp": "00:53", "title": "¿Tú qué opinas?"}\n'
        '  ]\n'
        "}"
    )

    user_prompt = f"Título del video: {title}\n\nEstructura temporal del video:\n{timeline_str}"

    try:
        if OpenAI is not None and api_key:
            client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.5,
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        elif api_key:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.5,
                "response_format": {"type": "json_object"}
            }
            res = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=35)
            res.raise_for_status()
            return json.loads(res.json()["choices"][0]["message"]["content"])
    except Exception as e:
        print(f"⚠️ No se pudo generar SEO y capítulos vía LLM ({e}). Se usará fallback heurístico.")

    # Fallback heurístico en caso de fallo de API
    fallback_chapters = [
        {"timestamp": "00:00", "title": "Introducción"},
        {"timestamp": scenes_with_time[len(scenes_with_time)//2]["timestamp"], "title": "Análisis principal"}
    ]
    if cta_scene:
        fallback_chapters.append({"timestamp": cta_scene["timestamp"], "title": "¿Tú qué opinas?"})

    return {
        "seo_summary": f"Análisis sobre {title}. Descubre los detalles clave en este video.",
        "hashtags": ["#Economia", "#Finanzas", "#Educacion"],
        "tags": [title.lower(), "economia", "finanzas"],
        "chapters": fallback_chapters
    }


# --- GENERADOR PRINCIPAL DE ARCHIVOS ---

def generate_description(
    project_dir: Optional[str] = None,
    model: str = "google/gemini-3.7-flash"
) -> Dict[str, str]:
    """Genera description.txt, pinned_comment.txt y metadata.json en la carpeta del proyecto."""
    print("\n" + "=" * 85)
    print(" 📝 GENERADOR DE DESCRIPCIÓN Y METADATOS PARA YOUTUBE")
    print("=" * 85)

    # 1. Determinar directorio del proyecto
    if not project_dir:
        current_proj_path = os.path.join("output", "current_project.json")
        if os.path.exists(current_proj_path):
            with open(current_proj_path, "r", encoding="utf-8") as f:
                project_dir = json.load(f).get("project_dir")

    if not project_dir or not os.path.exists(project_dir):
        raise FileNotFoundError("❌ No se especificó ni encontró un directorio de proyecto activo válido.")

    manifest_path = os.path.join(project_dir, "manifest.json")
    if not os.path.exists(manifest_path):
        raise FileNotFoundError(f"❌ No se encontró 'manifest.json' en '{project_dir}'.")

    # 2. Cargar manifiesto
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    title = manifest.get("title", "Video Sin Título")
    scenes = manifest.get("scenes", [])
    target_duration = manifest.get("target_duration_seconds", 60)

    # Preparar escenas con tiempos absolutos
    scenes_with_time = prepare_scenes_with_timestamps(scenes)

    cta_question = None
    for sc in scenes:
        if sc.get("is_interactive_cta"):
            cta_question = sc.get("narration_text")
            break

    # 3. Generar capítulos inteligentes y metadatos SEO
    seo_data = generate_seo_metadata_and_chapters(
        title=title,
        scenes_with_time=scenes_with_time,
        target_duration=target_duration,
        model=model
    )

    # Formatear lista de capítulos
    formatted_chapters = "\n".join([
        f"{ch['timestamp']} - {ch['title']}"
        for ch in seo_data.get("chapters", [])
    ])

    # 4. Construir contenido de description.txt
    desc_lines = [
        seo_data["seo_summary"],
        "",
        "📌 CAPÍTULOS DEL VIDEO:",
        formatted_chapters,
        ""
    ]

    if cta_question:
        desc_lines.extend([
            "💬 PREGUNTA DEL DÍA:",
            f"{cta_question} ¡Déjanos tu opinión en los comentarios! 👇",
            ""
        ])

    desc_lines.extend([
        "--------------------------------------------------",
        "⚠️ DESCARGO DE RESPONSABILIDAD:",
        "El contenido de este video es puramente educativo e informativo. No constituye asesoramiento financiero, legal o de inversión.",
        "",
        " ".join(seo_data["hashtags"])
    ])

    final_description = "\n".join(desc_lines)

    # 5. Construir comentario fijado
    pinned_comment = cta_question if cta_question else f"¿Qué opinas sobre {title}? ¡Déjanos tu comentario abajo! 👇"

    # 6. Escribir archivos en la carpeta del proyecto
    desc_path = os.path.join(project_dir, "description.txt")
    comment_path = os.path.join(project_dir, "pinned_comment.txt")
    metadata_path = os.path.join(project_dir, "metadata.json")

    with open(desc_path, "w", encoding="utf-8") as f:
        f.write(final_description)

    with open(comment_path, "w", encoding="utf-8") as f:
        f.write(pinned_comment)

    metadata_payload = {
        "title": title,
        "category_id": "27",  # Educación en YouTube
        "language": "es",
        "privacy_status": "private",
        "tags": seo_data["tags"],
        "hashtags": seo_data["hashtags"],
        "chapters": seo_data.get("chapters", []),
        "interactive_question": cta_question
    }

    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata_payload, f, indent=2, ensure_ascii=False)

    print(f"✔ Descripción guardada en: '{desc_path}'")
    print(f"✔ Comentario fijado guardado en: '{comment_path}'")
    print(f"✔ Metadatos JSON guardados en: '{metadata_path}'\n")

    return {
        "description": final_description,
        "pinned_comment": pinned_comment,
        "metadata_path": metadata_path
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generador de Descripciones para YouTube")
    parser.add_argument("--project_dir", type=str, default=None, help="Ruta al directorio del proyecto")
    parser.add_argument("--model", type=str, default="google/gemini-3.7-flash", help="Modelo de OpenRouter")

    args = parser.parse_args()
    generate_description(project_dir=args.project_dir, model=args.model)