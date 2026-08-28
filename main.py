import os
import re
import json
import unicodedata
from datetime import datetime

from core.trend_analyzer import get_selected_topic
from core.ideas import generate_ideas
from core.script_generator import generate_script
from core.voice_generator import generate_voice_over
from core.media_fetcher import process_scene_media
from core.video_composer import assemble_final_video


def slugify(text: str) -> str:
    """Convierte cualquier texto en un slug ASCII puro (sin acentos) para compatibilidad con el sistema de archivos."""
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8')
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    return re.sub(r'[-\s]+', '_', text)[:30].strip('_')


def create_project_dir(topic: str) -> str:
    """Crea un directorio único basado en timestamp y tema dentro de /projects y actualiza output/current_project.json."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = slugify(topic)
    project_dir = os.path.join("projects", f"{timestamp}_{slug}")
    os.makedirs(project_dir, exist_ok=True)

    # Registrar el proyecto activo en output/current_project.json para sincronización global
    os.makedirs("output", exist_ok=True)
    current_json_path = os.path.join("output", "current_project.json")
    with open(current_json_path, "w", encoding="utf-8") as f:
        json.dump({"project_dir": project_dir, "topic": topic}, f, indent=2, ensure_ascii=False)

    return project_dir


def run_pipeline():
    """Ejecuta el flujo completo de producción de video en Faceless Engine."""
    # 1. Investigar nicho, seleccionar tema e ingeniería inversa desde YouTube
    topic, video_url = get_selected_topic()

    print("\n" + "=" * 80)
    print(f"🚀 INICIANDO PIPELINE DE VIDEO PARA: '{topic}'")
    if video_url:
        print(f"🔗 Video de referencia: {video_url}")
    print("=" * 80)

    # 2. Crear directorio de trabajo e inicializar estado
    project_dir = create_project_dir(topic)
    print(f"📁 Directorio de trabajo: {project_dir}\n")

    # 3. Generar y elegir ángulos/ideas virales
    print("Step 1/5: Desarrollando ángulos virales con core/ideas.py...")
    generate_ideas(topic=topic, project_dir=project_dir)

    # 4. Generar guion estructurado en 2D monigotes y manifest.json
    print("\nStep 2/5: Generando guion con Gemini...")
    generate_script(topic=topic, video_url=video_url, project_dir=project_dir)

    # 5. Generar locuciones de audio por escena
    print("\nStep 3/5: Generando audio TTS (edge-tts)...")
    generate_voice_over(project_dir=project_dir)

    # 6. Generar imágenes en 2D vector vía OpenRouter
    print("\nStep 4/5: Generando recursos visuales...")
    process_scene_media(project_dir=project_dir)

    # 7. Ensamblar video final con movimiento Ken Burns y audio
    print("\nStep 5/5: Renderizando video MP4...")
    assemble_final_video(project_dir=project_dir)

    print("\n" + "=" * 80)
    print("🎉 PIPELINE COMPLETADO CON ÉXITO")
    print(f"📂 Proyecto generado en: {project_dir}")
    print("=" * 80)


if __name__ == "__main__":
    try:
        run_pipeline()
    except Exception as e:
        print(f"\n❌ Falla durante la ejecución: {e}")