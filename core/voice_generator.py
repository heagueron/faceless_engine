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


def process_script_audio():
    """
    Lee output/script_manifest.json, genera el audio de cada escena
    y guarda el resultado enriquecido con rutas de audio y duraciones.
    """
    input_file = os.path.join("output", "script_manifest.json")
    audio_dir = os.path.join("output", "audio")
    output_file = os.path.join("output", "script_manifest_with_audio.json")

    if not os.path.exists(input_file):
        raise FileNotFoundError(f"No se encontró el archivo: {input_file}. Ejecuta primero script_generator.py.")

    os.makedirs(audio_dir, exist_ok=True)

    with open(input_file, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    print("=" * 80)
    print(" GENERANDO AUDIO PARA LAS ESCENAS (TTS)")
    print("=" * 80)

    total_duration = 0.0

    for scene in manifest.get("scenes", []):
        scene_num = scene["scene_number"]
        text = scene["narration_text"]
        audio_filename = f"scene_{scene_num}.mp3"
        audio_path = os.path.join(audio_dir, audio_filename)

        print(f"🎙 Generando voz para Escena {scene_num}...")
        print(f"   Texto: \"{text}\"")

        duration = generate_scene_audio(text, audio_path)
        
        # Enriquecer la escena con los metadatos de audio
        scene["audio_file"] = audio_path
        scene["audio_duration_seconds"] = duration
        total_duration += duration

        print(f"   ✔ Guardado: {audio_path} ({duration}s)\n")

    manifest["total_audio_duration_seconds"] = round(total_duration, 2)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print("=" * 80)
    print(" PROCESO DE AUDIO COMPLETADO")
    print(f" Duración total de voz: {round(total_duration, 2)} segundos")
    print(f" Manifiesto actualizado en: {output_file}")
    print("=" * 80)


if __name__ == "__main__":
    try:
        process_script_audio()
    except Exception as e:
        print(f"❌ Error en la generación de audio: {e}")