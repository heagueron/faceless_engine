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

    # En MoviePy v2.x, resized se aplica con .resized() o manteniendo el tamaño original
    image_clip = (
        ImageClip(image_path)
        .with_duration(duration)
        .resized(target_size)
    )

    # Vincular el audio al clip de video
    video_clip = image_clip.with_audio(audio_clip)
    return video_clip


def assemble_final_video():
    """
    Lee script_manifest_complete.json, une los clips de cada escena
    y exporta el video final MP4.
    """
    input_file = os.path.join("output", "script_manifest_complete.json")
    output_dir = os.path.join("output", "renders")
    output_video_path = os.path.join(output_dir, "final_short.mp4")

    if not os.path.exists(input_file):
        raise FileNotFoundError(f"No se encontró el archivo: {input_file}")

    os.makedirs(output_dir, exist_ok=True)

    with open(input_file, "r", encoding="utf-8") as f:
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
        print(f"❌ Error en el ensamblado de video: {e}")