import os
import json
import asyncio
import argparse
from typing import Optional
import edge_tts
from mutagen.mp3 import MP3


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


async def _async_generate_audio(text: str, output_path: str, voice: str, rate: str = "+0%", pitch: str = "+0Hz"):
    """Función asíncrona que interactúa con el motor de Microsoft Edge TTS."""
    clean_voice = voice.strip()
    communicate = edge_tts.Communicate(text, clean_voice, rate=rate, pitch=pitch)
    await communicate.save(output_path)


def generate_scene_audio(
    text: str,
    output_path: str,
    voice: str = "es-VE-SebastianNeural",
    rate: str = "+0%",
    pitch: str = "+0Hz"
) -> float:
    """
    Convierte texto a voz MP3 usando edge-tts (Voz Neural de Microsoft)
    y devuelve su duración exacta en segundos.
    """
    asyncio.run(_async_generate_audio(text, output_path, voice, rate, pitch))
    audio = MP3(output_path)
    return round(audio.info.length, 2)


def generate_voice_over(
    project_dir: Optional[str] = None,
    target_scene: Optional[int] = None,
    voice: str = "es-VE-SebastianNeural",
    rate: str = "+0%"
):
    """
    Genera el audio TTS para las escenas del manifest.json usando edge-tts.
    Soporta procesamiento individual si se pasa target_scene.
    """
    if not project_dir:
        project_dir = get_current_project_dir()

    manifest_path = os.path.join(project_dir, "manifest.json")
    audio_dir = os.path.join(project_dir, "audio")

    if not os.path.exists(manifest_path):
        raise FileNotFoundError(f"No se encontró manifest.json en: {manifest_path}")

    os.makedirs(audio_dir, exist_ok=True)

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    all_scenes = manifest.get("scenes", [])
    if not all_scenes:
        print("⚠️ No hay escenas en manifest.json")
        return

    if target_scene is not None:
        scenes_to_process = [s for s in all_scenes if s.get("scene_number") == target_scene]
        if not scenes_to_process:
            print(f"❌ La escena número {target_scene} no existe en el manifest.")
            return
    else:
        scenes_to_process = all_scenes

    print("\n" + "=" * 80)
    print(" 🎙️ GENERANDO AUDIO NEURONAL (edge-tts)")
    print(f" 🗣️ Voz: {voice.strip()} | Velocidad: {rate}")
    if target_scene:
        print(f" 🎯 MODO ESCENA ÚNICA: Procesando la Escena #{target_scene}")
    print("=" * 80)

    for scene in scenes_to_process:
        scene_num = scene["scene_number"]
        text = scene.get("narration_text") or scene.get("narration", "")

        if not text:
            print(f" ⚠️ Escena {scene_num}: Sin texto de locución, salteando...")
            continue

        audio_filename = f"scene_{scene_num}.mp3"
        audio_path = os.path.join(audio_dir, audio_filename)

        print(f"\n🎙️ Generando voz para Escena {scene_num}...")
        print(f"   Texto: \"{text}\"")

        try:
            duration = generate_scene_audio(text, audio_path, voice=voice.strip(), rate=rate)
            scene["audio_file"] = audio_path
            scene["audio_duration_seconds"] = duration
            print(f"   ✔ Guardado: {audio_path} ({duration}s)")
        except Exception as e:
            print(f"   ❌ Error en Escena {scene_num}: {e}")
            scene["audio_file"] = None
            scene["audio_duration_seconds"] = None

    # Recalcular duración total acumulada
    total_duration = sum(s.get("audio_duration_seconds", 0.0) or 0.0 for s in all_scenes)
    manifest["total_audio_duration_seconds"] = round(total_duration, 2)

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 80)
    print(" ✔ Proceso de audio completado con edge-tts.")
    print(f" ⏱️ Duración total acumulada: {manifest['total_audio_duration_seconds']}s")
    print(f" 📄 Manifiesto actualizado: {manifest_path}")
    print("=" * 80)


# Alias de compatibilidad
process_script_audio = generate_voice_over


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Módulo de Locución Neural (edge-tts)")
    parser.add_argument("--project_dir", type=str, default=None, help="Directorio del proyecto")
    parser.add_argument("--scene", type=int, default=None, help="Número de escena específica a regenerar")
    parser.add_argument("--voice", type=str, default="es-VE-SebastianNeural", help="Voz neural")
    parser.add_argument("--rate", type=str, default="+0%", help="Ajuste de velocidad")

    args = parser.parse_args()

    try:
        generate_voice_over(
            project_dir=args.project_dir,
            target_scene=args.scene,
            voice=args.voice,
            rate=args.rate
        )
    except Exception as e:
        print(f"\n❌ Error en la generación de audio: {e}")