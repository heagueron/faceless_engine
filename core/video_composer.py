import os
import json
import numpy as np
from PIL import Image

try:
    # MoviePy v2
    from moviepy import VideoClip, AudioFileClip, concatenate_videoclips # type: ignore
except ImportError:
    # MoviePy v1 fallback
    from moviepy.editor import VideoClip, AudioFileClip, concatenate_videoclips # type: ignore


def create_ken_burns_clip(image_path: str, duration: float, zoom_in: bool = True):
    """
    Crea un VideoClip con movimiento de cámara sutil (Ken Burns effect).
    - zoom_in=True: Escala de 1.0x a 1.08x
    - zoom_in=False: Escala de 1.08x a 1.0x
    Manteniendo el encuadre centrado en 1080x1920.
    """
    base_w, base_h = 1080, 1920
    
    # Cargar e inicializar la imagen base a 1080x1920 con PIL
    pil_img = Image.open(image_path).convert('RGB')
    pil_img = pil_img.resize((base_w, base_h), Image.Resampling.LANCZOS)

    def make_frame(t):
        # Progreso de 0.0 a 1.0
        progress = min(max(t / duration, 0.0), 1.0) if duration > 0 else 0.0
        
        # Calcular el factor de escala (zoom sutil del 10%)
        if zoom_in:
            scale = 1.0 + (0.1 * progress)
        else:
            scale = 1.08 - (0.1 * progress)

        new_w = int(base_w * scale)
        new_h = int(base_h * scale)

        # Redimensionar la imagen temporalmente según la escala del cuadro actual
        scaled_img = pil_img.resize((new_w, new_h), Image.Resampling.BILINEAR)

        # Recortar desde el centro para mantener exactamente 1080x1920
        left = (new_w - base_w) // 2
        top = (new_h - base_h) // 2
        cropped_img = scaled_img.crop((left, top, left + base_w, top + base_h))

        return np.array(cropped_img)

    return VideoClip(make_frame, duration=duration)


def assemble_final_video(project_dir: str):
    """
    Une las imágenes con movimiento Ken Burns y audios de cada escena leídos desde manifest.json.
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
    print(" 🎬 ENSAMBLANDO VIDEO FINAL CON EFECTO KEN BURNS (9:16)")
    print("=" * 80)

    clips = []

    for idx, scene in enumerate(scenes, 1):
        image_path = scene.get("image_path", os.path.join(project_dir, "images", f"scene_{idx}.jpg"))
        audio_path = scene.get("audio_path", os.path.join(project_dir, "audio", f"scene_{idx}.mp3"))

        if not os.path.exists(image_path):
            print(f"❌ Error: La imagen para la Escena {idx} no existe en {image_path}")
            continue

        if not os.path.exists(audio_path):
            print(f"❌ Error: El audio para la Escena {idx} no existe en {audio_path}")
            continue

        # Cargar audio para obtener la duración
        audio_clip = AudioFileClip(audio_path)
        duration = audio_clip.duration

        # Alternar dirección del movimiento (Impar: Zoom-In / Par: Zoom-Out)
        is_zoom_in = (idx % 2 != 0)
        motion_type = "Zoom-In" if is_zoom_in else "Zoom-Out"

        print(f"\n🎬 Montando Escena {idx} ({motion_type}):")
        print(f"   🖼 Imagen: {image_path}")
        print(f"   🎙 Audio:  {audio_path}")

        # Generar clip con efecto Ken Burns
        video_clip = create_ken_burns_clip(image_path, duration=duration, zoom_in=is_zoom_in)

        # Asignar audio al clip
        if hasattr(video_clip, 'with_audio'):
            clip_with_audio = video_clip.with_audio(audio_clip)
        else:
            clip_with_audio = video_clip.set_audio(audio_clip)

        clips.append(clip_with_audio)
        print(f"   ✔ Clip {idx} creado con animación ({duration:.2f}s)")

    if not clips:
        raise RuntimeError("No se pudieron generar los clips para el video final.")

    print("\n🎞 Concatenando escenas animadas...")
    final_video = concatenate_videoclips(clips, method="compose")

    output_video_path = os.path.join(project_dir, "final_short.mp4")
    print(f"🚀 Exportando video animado a: {output_video_path}\n")

    final_video.write_videofile(
        output_video_path,
        fps=24,
        codec="libx264",
        audio_codec="aac",
        preset="ultrafast",
        threads=4
    )

    # Liberar memoria
    for c in clips:
        c.close()
    final_video.close()

    print("\n" + "=" * 80)
    print(" 🎉 ¡VIDEO CON MOVIMIENTO GENERADO EXITOSAMENTE!")
    print(f" 📂 Archivo: {output_video_path}")
    print("=" * 80)

    return output_video_path