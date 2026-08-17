import os
import re
import unicodedata
from datetime import datetime
from core.trend_analyzer import get_selected_topic
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
    """Crea un directorio único basado en timestamp y tema dentro de /projects."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = slugify(topic)
    project_dir = os.path.join("projects", f"{timestamp}_{slug}")
    os.makedirs(project_dir, exist_ok=True)
    return project_dir

def run_pipeline():
    """Ejecuta el flujo completo pidiendo primero el nicho a YouTube."""
    # 1. Investigar nicho y seleccionar tema interactivo desde YouTube
    topic = get_selected_topic()

    print("\n" + "=" * 80)
    print(f"🚀 INICIANDO PIPELINE DE VIDEO PARA: '{topic}'")
    print("=" * 80)

    # 2. Crear directorio de trabajo
    project_dir = create_project_dir(topic)
    print(f"📁 Directorio de trabajo: {project_dir}\n")

    # 3. Generar guion y manifiesto inicial
    print("Step 1/4: Generando guion con Gemini...")
    generate_script(topic=topic, project_dir=project_dir)

    # 4. Generar locuciones de audio
    print("\nStep 2/4: Generando audio TTS...")
    generate_voice_over(project_dir=project_dir)

    # 5. Descargar imágenes por escena
    print("\nStep 3/4: Buscando recursos visuales...")
    process_scene_media(project_dir=project_dir)

    # 6. Ensamblar video final
    print("\nStep 4/4: Renderizando video MP4...")
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