import os
import json
import argparse
from typing import Optional
import numpy as np
from PIL import Image

try:
    # MoviePy v2
    from moviepy import VideoClip, AudioFileClip, concatenate_videoclips  # type: ignore
except ImportError:
    # MoviePy v1 fallback
    from moviepy.editor import VideoClip, AudioFileClip, concatenate_videoclips  # type: ignore


def get_current_project_dir() -> str:
    """Carga automáticamente la ruta del proyecto activo desde output/current_project.json."""
    current_json_path = os.path.join("output", "current_project.json")
    if os.path.exists(current_json_path):
        try:
            with open(current_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                project_dir = data.get("project_dir")
                if project_dir and os.path.exists(project_dir):
                    print(f"📁 Proyecto activo cargado automáticamente: '{project_dir}'")
                    return project_dir
        except Exception as e:
            print(f"⚠️ Error al leer '{current_json_path}': {e}")

    # Fallback al directorio más reciente en /projects
    projects_base = "projects"
    if os.path.exists(projects_base):
        subdirs = [os.path.join(projects_base, d) for d in os.listdir(projects_base) if os.path.isdir(os.path.join(projects_base, d))]
        if subdirs:
            latest = max(subdirs, key=os.path.getmtime)
            print(f"📁 Proyecto más reciente seleccionado: '{latest}'")
            return latest

    raise FileNotFoundError(
        "No se especificó --project_dir y no se encontró un proyecto válido en 'output/current_project.json' ni en 'projects/'."
    )


def create_ken_burns_clip(image_path: str, duration: float, zoom_in: bool = True) -> VideoClip:
    """
    Crea un VideoClip con movimiento de cámara sutil (Ken Burns effect).
    - zoom_in=True:  Escala de 1.00x a 1.08x
    - zoom_in=False: Escala de 1.08x a 1.00x
    Manteniendo el encuadre centrado en 1080x1920 (Formato 9:16 para Shorts/Reels).
    """
    base_w, base_h = 1080, 1920

    # Cargar e inicializar la imagen base a 1080x1920 con PIL
    pil_img = Image.open(image_path).convert('RGB')
    pil_img = pil_img.resize((base_w, base_h), Image.Resampling.LANCZOS)

    def make_frame(t):
        # Progreso de 0.0 a 1.0
        progress = min(max(t / duration, 0.0), 1.0) if duration > 0 else 0.0

        # Calcular el factor de escala (zoom sutil del 8%)
        if zoom_in:
            scale = 1.0 + (0.08 * progress)
        else:
            scale = 1.08 - (0.08 * progress)

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


def assemble_final_video(project_dir: Optional[str] = None, fps: int = 24, preset: str = "ultrafast") -> str:
    """
    Une las imágenes con movimiento Ken Burns y los audios de cada escena
    definidos en manifest.json, y genera el video final final_short.mp4.
    """
    if not project_dir:
        project_dir = get_current_project_dir()

    manifest_path = os.path.join(project_dir, "manifest.json")
    if not os.path.exists(manifest_path):
        raise FileNotFoundError(f"No se encontró manifest.json en: {manifest_path}")

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    scenes = manifest.get("scenes", [])
    if not scenes:
        raise ValueError("El manifest.json no contiene escenas.")

    print("\n" + "=" * 80)
    print(" 🎬 ENSAMBLANDO VIDEO FINAL CON EFECTO KEN BURNS (9:16)")
    print(f" 📁 Proyecto: {project_dir}")
    print(f" 🎞️ Escenas a procesar: {len(scenes)}")
    print("=" * 80)

    clips = []

    for idx, scene in enumerate(scenes, 1):
        scene_num = scene.get("scene_number", idx)
        image_path = scene.get("image_path") or os.path.join(project_dir, "images", f"scene_{scene_num}.jpg")
        audio_path = scene.get("audio_file") or scene.get("audio_path") or os.path.join(project_dir, "audio", f"scene_{scene_num}.mp3")

        if not os.path.exists(image_path):
            print(f" ❌ Escena {scene_num}: Falta la imagen ('{image_path}'). Omite escena.")
            continue

        if not os.path.exists(audio_path):
            print(f" ❌ Escena {scene_num}: Falta el audio ('{audio_path}'). Omite escena.")
            continue

        # Cargar audio para obtener la duración
        audio_clip = AudioFileClip(audio_path)
        duration = audio_clip.duration

        # Alternar dirección del movimiento (Impar: Zoom-In / Par: Zoom-Out)
        is_zoom_in = (scene_num % 2 != 0)
        motion_type = "Zoom-In" if is_zoom_in else "Zoom-Out"

        print(f"\n🎥 Montando Escena #{scene_num} ({motion_type}):")
        print(f"   🖼️ Imagen: {image_path}")
        print(f"   🎙️ Audio:  {audio_path}")

        # Generar clip con efecto Ken Burns
        video_clip = create_ken_burns_clip(image_path, duration=duration, zoom_in=is_zoom_in)

        # Asignar audio al clip (Compatibilidad MoviePy v1 / v2)
        if hasattr(video_clip, 'with_audio'):
            clip_with_audio = video_clip.with_audio(audio_clip)
        else:
            clip_with_audio = video_clip.set_audio(audio_clip)

        clips.append(clip_with_audio)
        print(f"   ✔ Clip #{scene_num} animado listo ({duration:.2f}s)")

    if not clips:
        raise RuntimeError("No se pudieron generar los clips para el video final.")

    print("\n🎞️ Concatenando escenas animadas...")
    final_video = concatenate_videoclips(clips, method="compose")

    output_video_path = os.path.join(project_dir, "final_short.mp4")
    print(f"🚀 Exportando video animado a: {output_video_path}\n")

    final_video.write_videofile(
        output_video_path,
        fps=fps,
        codec="libx264",
        audio_codec="aac",
        preset=preset,
        threads=4
    )

    # Liberar memoria de los clips
    for c in clips:
        c.close()
    final_video.close()

    # Actualizar el manifiesto con la ruta del video resultante
    manifest["final_video_path"] = output_video_path
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 80)
    print(" 🎉 ¡VIDEO ANIMADO GENERADO EXITOSAMENTE!")
    print(f" 📄 Manifiesto actualizado con: final_video_path")
    print(f" 📹 Archivo: {output_video_path}")
    print("=" * 80)

    return output_video_path


# Alias de compatibilidad
build_video = assemble_final_video
process_video_assembly = assemble_final_video


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Módulo de Ensamblado de Video Animado (Ken Burns / MoviePy)")
    parser.add_argument("--project_dir", type=str, default=None, help="Directorio del proyecto")
    parser.add_argument("--fps", type=int, default=24, help="Frames por segundo (por defecto 24)")
    parser.add_argument("--preset", type=str, default="ultrafast", help="Preset de codificación FFmpeg (ej: ultrafast, medium)")

    args = parser.parse_args()

    try:
        assemble_final_video(
            project_dir=args.project_dir,
            fps=args.fps,
            preset=args.preset
        )
    except Exception as e:
        print(f"\n❌ Error durante el ensamblado del video: {e}")