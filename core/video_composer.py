import os
import json

try:
    # MoviePy v2
    from moviepy import ImageClip, AudioFileClip, concatenate_videoclips
except ImportError:
    # MoviePy v1 fallback
    from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips


def assemble_final_video(project_dir: str):
    """
    Une las imágenes y audios de cada escena leídos directamente del manifest.json del proyecto.
    """
    manifest_path = os.path.join(project_dir, "manifest.json")
    if not os.path.exists(manifest_path):
        raise FileNotFoundError(f"No se encontró manifest.json en: {project_dir}")

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    scenes = manifest.get("scenes", [])
    if not scenes:
        raise ValueError("El manifest.json no contiene escenas.")

    print("\n" + "=" * 80)
    print(" 🎬 ENSAMBLANDO VIDEO FINAL (MOVIEPY 9:16)")
    print("=" * 80)

    clips = []

    for idx, scene in enumerate(scenes, 1):
        # Tomar la ruta guardada por media_fetcher o construir la correspondiente al proyecto
        image_path = scene.get("image_path", os.path.join(project_dir, "images", f"scene_{idx}.jpg"))
        audio_path = scene.get("audio_path", os.path.join(project_dir, "audio", f"scene_{idx}.mp3"))

        if not os.path.exists(image_path):
            print(f"❌ Error: La imagen para la Escena {idx} no existe en {image_path}")
            continue

        if not os.path.exists(audio_path):
            print(f"❌ Error: El audio para la Escena {idx} no existe en {audio_path}")
            continue

        print(f"\n🎬 Montando Escena {idx}:")
        print(f"   🖼 Imagen: {image_path}")
        print(f"   🎙 Audio:  {audio_path}")

        # Cargar audio para saber la duración real
        audio_clip = AudioFileClip(audio_path)
        duration = audio_clip.duration

        # Cargar imagen y ajustar duración
        img_clip = ImageClip(image_path)
        if hasattr(img_clip, 'with_duration'):
            img_clip = img_clip.with_duration(duration)
        else:
            img_clip = img_clip.set_duration(duration)

        # Redimensionar a 1080x1920 (Shorts/Reels 9:16)
        if hasattr(img_clip, 'resized'):
            img_clip = img_clip.resized(new_size=(1080, 1920))
        elif hasattr(img_clip, 'resize'):
            img_clip = img_clip.resize(newsize=(1080, 1920))

        # Asignar audio al clip de video
        if hasattr(img_clip, 'with_audio'):
            clip_with_audio = img_clip.with_audio(audio_clip)
        else:
            clip_with_audio = img_clip.set_audio(audio_clip)

        clips.append(clip_with_audio)
        print(f"   ✔ Clip {idx} creado ({duration:.2f}s)")

    if not clips:
        raise RuntimeError("No se pudieron generar los clips para el video final.")

    print("\n🎞 Concatenando escenas...")
    final_video = concatenate_videoclips(clips, method="compose")

    output_video_path = os.path.join(project_dir, "final_short.mp4")
    print(f"🚀 Exportando video a: {output_video_path}\n")

    final_video.write_videofile(
        output_video_path,
        fps=24,
        codec="libx264",
        audio_codec="aac",
        preset="ultrafast",
        threads=4
    )

    # Liberar memoria de los clips
    for c in clips:
        c.close()
    final_video.close()

    print("\n" + "=" * 80)
    print(" 🎉 ¡VIDEO GENERADO EXITOSAMENTE!")
    print(f" 📂 Archivo: {output_video_path}")
    print("=" * 80)

    return output_video_path