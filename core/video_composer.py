import os
import json
from moviepy import ImageClip, AudioFileClip, concatenate_videoclips

def create_scene_clip(image_path: str, audio_path: str, target_size=(1080, 1920)):
    """
    Combina una imagen y un archivo de audio en un clip de video vertical.
    Compatible con MoviePy v2.x.
    """
    audio_clip = AudioFileClip(audio_path)
    duration = audio_clip.duration

    # En MoviePy v2.x, resized se aplica con .resized()
    image_clip = (
        ImageClip(image_path)
        .with_duration(duration)
        .resized(target_size)
    )

    # Vincular el audio al clip de video
    video_clip = image_clip.with_audio(audio_clip)
    return video_clip


def assemble_final_video(project_dir: str = None):
    """
    Lee manifest.json desde la carpeta del proyecto, une los clips de cada escena
    y exporta el video final MP4 dentro de la subcarpeta del proyecto.
    """
    if not project_dir:
        # Fallback para pruebas independientes: buscar el proyecto más reciente en /projects
        projects_base = "projects"
        if os.path.exists(projects_base):
            subdirs = [os.path.join(projects_base, d) for d in os.listdir(projects_base) if os.path.isdir(os.path.join(projects_base, d))]
            if subdirs:
                project_dir = max(subdirs, key=os.path.getmtime)

    if not project_dir or not os.path.exists(project_dir):
        raise FileNotFoundError("No se encontró un directorio de proyecto válido en /projects. Ejecuta primero main.py.")

    manifest_path = os.path.join(project_dir, "manifest.json")
    output_video_path = os.path.join(project_dir, "final_short.mp4")

    if not os.path.exists(manifest_path):
        raise FileNotFoundError(f"No se encontró el archivo: {manifest_path}")

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    print("=" * 80)
    print(" ENSAMBLANDO VIDEO FINAL (MP4 9:16) - MOVIEPY V2")
    print("=" * 80)

    scene_clips = []
    scenes = manifest.get("scenes", [])

    for scene in scenes:
        scene_num = scene["scene_number"]
        image_path = scene.get("image_file")
        audio_path = scene.get("audio_file")

        if not image_path or not os.path.exists(image_path):
            print(f" ⚠️ Salteando Escena {scene_num}: Imagen no encontrada ({image_path})")
            continue

        if not audio_path or not os.path.exists(audio_path):
            print(f" ⚠️ Salteando Escena {scene_num}: Audio no encontrado ({audio_path})")
            continue

        print(f"🎬 Procesando Escena {scene_num}...")
        clip = create_scene_clip(image_path, audio_path)
        scene_clips.append(clip)
        print(f"   ✔ Clip creado ({clip.duration:.2f}s)")

    if not scene_clips:
        raise RuntimeError("No se pudieron generar clips para ensamblar.")

    print("\n🎞 Concatenando escenas...")
    final_video = concatenate_videoclips(scene_clips, method="compose")

    print(f"🚀 Exportando video a: {output_video_path}")
    print("   (Esto puede tomar unos segundos)...")

    final_video.write_videofile(
        output_video_path,
        fps=30,
        codec="libx264",
        audio_codec="aac",
        threads=4,
        logger=None
    )

    # Liberar memoria
    for clip in scene_clips:
        clip.close()
    final_video.close()

    print("\n" + "=" * 80)
    print(" ¡VIDEO GENERADO EXITOSAMENTE!")
    print("=" * 80)
    print(f" Archivo listo en: {output_video_path}")
    print("=" * 80)


if __name__ == "__main__":
    try:
        assemble_final_video()
    except Exception as e:
        print(f"\n❌ Error en el ensamblado de video: {e}")