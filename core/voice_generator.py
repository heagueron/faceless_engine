import os
import json
from gtts import gTTS
from mutagen.mp3 import MP3

def generate_scene_audio(text: str, output_path: str, lang: str = "es") -> float:
    """
    Convierte un texto a voz MP3 usando gTTS y devuelve su duración en segundos.
    """
    tts = gTTS(text=text, lang=lang, slow=False)
    tts.save(output_path)
    
    # Obtener duración exacta del archivo generado
    audio = MP3(output_path)
    return round(audio.info.length, 2)


def generate_voice_over(project_dir: str = None):
    """
    Lee manifest.json desde la carpeta del proyecto, genera los audios de cada escena,
    guarda los .mp3 en <project_dir>/audio y actualiza manifest.json con las rutas y duraciones.
    """
    if not project_dir:
        # Fallback para pruebas independientes: buscar el proyecto más reciente en /projects
        projects_base = "projects"
        if os.path.exists(projects_base):
            subdirs = [os.path.join(projects_base, d) for d in os.listdir(projects_base) if os.path.isdir(os.path.join(projects_base, d))]
            if subdirs:
                project_dir = max(subdirs, key=os.path.getmtime)

    if not project_dir or not os.path.exists(project_dir):
        raise FileNotFoundError("No se encontró un directorio de proyecto válido en /projects. Ejecuta primero main.py o script_generator.py.")

    manifest_path = os.path.join(project_dir, "manifest.json")
    audio_dir = os.path.join(project_dir, "audio")

    if not os.path.exists(manifest_path):
        raise FileNotFoundError(f"No se encontró el archivo: {manifest_path}. Ejecuta primero la generación de guion.")

    os.makedirs(audio_dir, exist_ok=True)

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    print("=" * 80)
    print(" GENERANDO AUDIO PARA LAS ESCENAS (TTS)")
    print("=" * 80)

    total_duration = 0.0

    for scene in manifest.get("scenes", []):
        scene_num = scene["scene_number"]
        # Soporte para ambas llaves ('narration_text' o 'narration')
        text = scene.get("narration_text") or scene.get("narration", "")

        if not text:
            print(f" ⚠️ Escena {scene_num}: No tiene texto de locución, salteando...")
            continue

        audio_filename = f"scene_{scene_num}.mp3"
        audio_path = os.path.join(audio_dir, audio_filename)

        print(f"🎙 Generando voz para Escena {scene_num}...")
        print(f"   Texto: \"{text}\"")

        try:
            duration = generate_scene_audio(text, audio_path)
            
            # Enriquecer la escena con los metadatos de audio
            scene["audio_file"] = audio_path
            scene["audio_duration_seconds"] = duration
            total_duration += duration

            print(f"   ✔ Guardado: {audio_path} ({duration}s)\n")
        except Exception as e:
            print(f"   ❌ Error generando audio para Escena {scene_num}: {e}\n")
            scene["audio_file"] = None

    manifest["total_audio_duration_seconds"] = round(total_duration, 2)

    # Sobrescribir el manifiesto único dentro del proyecto
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print("=" * 80)
    print(" PROCESO DE AUDIO COMPLETADO")
    print(f" Duración total de voz: {round(total_duration, 2)} segundos")
    print(f" Manifiesto actualizado en: {manifest_path}")
    print("=" * 80)


# Alias para mantener compatibilidad con ambas llamadas
process_script_audio = generate_voice_over


if __name__ == "__main__":
    try:
        generate_voice_over()
    except Exception as e:
        print(f"\n❌ Error en la generación de audio: {e}")