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
from core.caption_generator import generate_srt_from_project
from core.description_generator import generate_description


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


def select_video_format_and_duration():
    """Solicita al usuario las preferencias de formato y duración del video."""
    print("\n" + "=" * 80)
    print(" 📐 CONFIGURACIÓN DE FORMATO Y DURACIÓN DEL VIDEO")
    print("=" * 80)
    print("1. Short / Reel (9:16 Vertical)")
    print("2. Video Horizontal (16:9 Widescreen) [Defecto]")

    fmt_choice = input("\nSeleccione formato (1 o 2) [Defecto: 2]: ").strip()

    if fmt_choice == "1":
        video_type = "short"
        aspect_ratio = "9:16"
        default_duration = 15
    else:
        video_type = "long"
        aspect_ratio = "16:9"
        default_duration = 60

    dur_input = input(f"Duración estimada en segundos [Defecto: {default_duration}s]: ").strip()
    
    if dur_input.isdigit() and int(dur_input) > 0:
        target_duration = int(dur_input)
    else:
        target_duration = default_duration

    print(f"\n✔ Configuración seleccionada: Formato {video_type.upper()} ({aspect_ratio}), Duración: {target_duration}s")
    return video_type, aspect_ratio, target_duration


def run_pipeline():
    """Ejecuta el flujo completo de producción de video en Faceless Engine."""
    # 1. Investigar nicho, seleccionar tema e ingeniería inversa desde YouTube
    topic, video_url = get_selected_topic()

    print("\n" + "=" * 80)
    print(f"🚀 INICIANDO PIPELINE DE VIDEO PARA: '{topic}'")
    if video_url:
        print(f"🔗 Video de referencia: {video_url}")
    print("=" * 80)

    # 2. Configurar formato (Short vs Horizontal) y duración estimada
    video_type, aspect_ratio, target_duration = select_video_format_and_duration()

    # 3. Crear directorio de trabajo e inicializar estado
    project_dir = create_project_dir(topic)
    print(f"\n📁 Directorio de trabajo: {project_dir}\n")

    # 4. Generar y elegir ángulos/ideas virales
    print("Step 1/6: Desarrollando ángulos virales con core/ideas.py...")
    generate_ideas(topic=topic, project_dir=project_dir)

    # 5. Generar guion estructurado en 2D monigotes y manifest.json
    print("\nStep 2/6: Generando guion con Gemini...")
    generate_script(
        topic=topic,
        video_url=video_url,
        target_duration=target_duration,
        video_type=video_type,
        aspect_ratio=aspect_ratio,
        project_dir=project_dir
    )

    # 6. Generar locuciones de audio por escena
    print("\nStep 3/6: Generando audio TTS (edge-tts)...")
    generate_voice_over(project_dir=project_dir)

    # Punto de revisión previo a la generación visual
    print("\n" + "=" * 80)
    print(" ⏸️ PUNTO DE REVISIÓN: GUION Y AUDIOS GENERADOS")
    print("=" * 80)
    user_confirm = input("¿Desea continuar con la generación de las imágenes? (S/n) [Defecto: S]: ").strip().lower()

    if user_confirm in ["n", "no"]:
        print(f"\n⏸️ Generación de imágenes pausada.")
        print(f"📁 Guion y audios guardados en: {project_dir}")
        print("Puedes revisar/editar 'manifest.json' y reanudar ejecutando: python core/media_fetcher.py")
        return

    # 7. Generar imágenes
    print("\nStep 4/6: Generando recursos visuales...")
    process_scene_media(project_dir=project_dir)

    # 8. Ensamblar video final con movimiento Ken Burns y audio
    print("\nStep 5/6: Renderizando video MP4...")
    assemble_final_video(project_dir=project_dir)

    # 9. Generación de recursos finales para publicación (SRT + Descripción + Comentario Fijado + Metadatos)
    print("\nStep 6/6: Generando metadatos y recursos de publicación (SRT, Descripción, SEO)...")
    if project_dir:
        generate_srt_from_project(project_dir)
        generate_description(project_dir=project_dir)

    print("\n" + "=" * 80)
    print("🎉 PIPELINE COMPLETADO CON ÉXITO")
    print(f"📁 Proyecto generado en: {project_dir}")
    print("  ├─ 🎥 Video MP4 renderizado")
    print("  ├─ 📜 Subtítulos SRT")
    print("  ├─ 📝 Descripción optimizada (description.txt)")
    print("  ├─ 💬 Comentario fijado (pinned_comment.txt)")
    print("  └─ ⚙️ Metadatos YouTube (metadata.json)")
    print("=" * 80)


if __name__ == "__main__":
    try:
        run_pipeline()
    except Exception as e:
        print(f"\n❌ Falla durante la ejecución: {e}")