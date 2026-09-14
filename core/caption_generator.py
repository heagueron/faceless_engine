import os
import json
import argparse
from datetime import timedelta
from typing import Dict, Any, Optional

def format_srt_timestamp(seconds: float) -> str:
    """Convierte un tiempo en segundos al formato estándar SRT (HH:MM:SS,mmm)."""
    td = timedelta(seconds=max(0.0, seconds))
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    millis = int(round((seconds - total_seconds) * 1000))

    if millis >= 1000:
        millis -= 1000
        secs += 1
        if secs >= 60:
            secs -= 60
            minutes += 1
            if minutes >= 60:
                minutes -= 60
                hours += 1

    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def generate_srt(manifest_data: Dict[str, Any], output_srt_path: str) -> str:
    """Genera un archivo .srt a partir de los datos del manifiesto."""
    current_time = 0.0

    os.makedirs(os.path.dirname(output_srt_path), exist_ok=True)

    with open(output_srt_path, "w", encoding="utf-8") as f:
        for idx, scene in enumerate(manifest_data.get("scenes", []), start=1):
            duration = scene.get("audio_duration_seconds") or 5.0
            start_time = current_time
            end_time = current_time + duration

            start_str = format_srt_timestamp(start_time)
            end_str = format_srt_timestamp(end_time)
            text = scene.get("narration_text", "").strip()

            f.write(f"{idx}\n{start_str} --> {end_str}\n{text}\n\n")
            current_time = end_time

    print(f"📝 Subtítulos SRT generados en: '{output_srt_path}'")
    return output_srt_path


def generate_srt_from_project(project_dir: str) -> Optional[str]:
    """Carga manifest.json de un proyecto y escribe el archivo subtitles.srt en su raíz."""
    manifest_path = os.path.join(project_dir, "manifest.json")
    if not os.path.exists(manifest_path):
        print(f"⚠️ Error: No se encontró '{manifest_path}' para generar subtítulos.")
        return None

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest_data = json.load(f)

        output_srt_path = os.path.join(project_dir, "subtitles.srt")
        return generate_srt(manifest_data, output_srt_path)
    except Exception as e:
        print(f"❌ Error al procesar el manifiesto para SRT: {e}")
        return None


# --- BLOQUE DE EJECUCIÓN DIRECTA DESDE CLI ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generador de subtítulos SRT para Faceless Engine")
    
    # Intentar leer el proyecto activo desde output/current_project.json
    default_dir = None
    current_proj_file = os.path.join("output", "current_project.json")
    if os.path.exists(current_proj_file):
        try:
            with open(current_proj_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                default_dir = data.get("project_dir")
        except Exception:
            pass

    parser.add_argument("--project_dir", type=str, default=default_dir, help="Ruta al directorio del proyecto")
    args = parser.parse_args()

    if args.project_dir:
        print(f"🎬 Procesando subtítulos para: {args.project_dir}")
        generate_srt_from_project(args.project_dir)
    else:
        print("⚠️ No se encontró 'output/current_project.json' ni se especificó --project_dir.")
        print("Uso: python core/caption_generator.py --project_dir projects/TU_CARPETA")