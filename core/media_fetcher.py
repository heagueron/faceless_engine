import os
import re
import json
import time
import base64
import argparse
import requests
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from PIL import Image, ImageDraw

load_dotenv()

try:
    import fal_client
except ImportError:
    fal_client = None


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

    raise FileNotFoundError(
        "No se especificó --project_dir y no se encontró un proyecto válido en 'output/current_project.json'."
    )


def create_fallback_image(output_path: str, scene_num: int, text: str, aspect_ratio: str = "16:9"):
    """Crea una imagen local usando Pillow como respaldo infalible respetando la relación de aspecto."""
    if aspect_ratio == "9:16":
        width, height = 1080, 1920
    else:
        width, height = 1920, 1080

    img = Image.new('RGB', (width, height), color=(18, 22, 30))
    draw = ImageDraw.Draw(img)
    
    # Borde decorativo
    draw.rectangle([40, 40, width - 40, height - 40], outline=(60, 80, 110), width=6)
    
    # Texto de la escena
    draw.text((width // 4, height // 2 - 50), f"ESCENA {scene_num}", fill=(255, 200, 80))
    
    fmt = "PNG" if output_path.lower().endswith(".png") else "JPEG"
    img.save(output_path, fmt, quality=90)


def generate_image_via_fal(
    prompt: str,
    output_path: str,
    model: str = "fal-ai/flux/schnell",
    aspect_ratio: str = "16:9",
    max_retries: int = 3,
    retry_delay: float = 3.0
) -> bool:
    """
    Solicita la generación de imagen a fal.ai usando Flux Schnell.
    Maneja reintentos con backoff exponencial.
    """
    fal_key = os.getenv("FAL_KEY") or os.getenv("FAL_API_KEY")
    if not fal_key:
        print("   ❌ Error: FAL_KEY o FAL_API_KEY no encontrada en .env")
        return False

    os.environ["FAL_KEY"] = fal_key

    # Directiva obligatoria para forzar español en cualquier texto renderizado dentro de la imagen
    spanish_directive = " CRITICAL INSTRUCTION: All text, labels, signs, callouts, or annotations rendered inside the image MUST be written strictly in SPANISH language."
    if "SPANISH language" not in prompt:
        prompt = f"{prompt.rstrip('.')}.{spanish_directive}"

    # Mapeo de aspecto según lo soportado por Flux en fal.ai
    image_size = "portrait_16_9" if aspect_ratio == "9:16" else "landscape_16_9"
    current_delay = retry_delay

    for attempt in range(1, max_retries + 1):
        try:
            if fal_client is not None:
                # Opción 1: Cliente oficial SDK fal_client
                result = fal_client.subscribe(
                    model,
                    arguments={
                        "prompt": prompt,
                        "image_size": image_size,
                        "num_inference_steps": 4 if "schnell" in model else 28,
                        "enable_safety_checker": False
                    }
                )
                images = result.get("images", [])
                if images and "url" in images[0]:
                    img_url = images[0]["url"]
                    res = requests.get(img_url, timeout=30)
                    if res.status_code == 200 and len(res.content) > 1000:
                        with open(output_path, "wb") as f:
                            f.write(res.content)
                        return True
            else:
                # Opción 2: Reserva mediante REST API directa
                url = f"https://fal.run/{model}"
                headers = {
                    "Authorization": f"Key {fal_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "prompt": prompt,
                    "image_size": image_size,
                    "num_inference_steps": 4 if "schnell" in model else 28,
                    "enable_safety_checker": False
                }
                res = requests.post(url, headers=headers, json=payload, timeout=60)
                if res.status_code == 200:
                    data = res.json()
                    images = data.get("images", [])
                    if images and "url" in images[0]:
                        img_url = images[0]["url"]
                        img_res = requests.get(img_url, timeout=30)
                        if img_res.status_code == 200 and len(img_res.content) > 1000:
                            with open(output_path, "wb") as f:
                                f.write(img_res.content)
                            return True
                elif res.status_code == 429:
                    print(f"   ⏳ Tasa de peticiones superada (429 Rate Limit). Reintentando en {current_delay:.1f}s (Intento {attempt}/{max_retries})...")
                    time.sleep(current_delay)
                    current_delay *= 1.5
                    continue
                else:
                    print(f"   ⚠️ fal.ai respondió con status {res.status_code}: {res.text[:200]}")

        except Exception as e:
            print(f"   ⚠️ Fallo en llamada API (Intento {attempt}/{max_retries}): {e}")

        if attempt < max_retries:
            time.sleep(current_delay)
            current_delay *= 1.5

    return False


def is_valid_image_file(path: str) -> bool:
    """Verifica si un archivo existe y es una imagen válida de tamaño > 100 bytes."""
    if not os.path.exists(path):
        return False
    if os.path.getsize(path) < 100:
        return False
    try:
        with Image.open(path) as img:
            img.verify()
        return True
    except Exception:
        return False


def process_scene_media(
    project_dir: str,
    model: str = "fal-ai/flux/schnell",
    max_retries: int = 3,
    target_scene: Optional[int] = None,
    force: bool = False,
    rate_limit_delay: float = 1.0
):
    """
    Procesa escenas del manifest.json implementando Mecanismo de Checkpoint y Manejo de Rate Limits.
    """
    manifest_path = os.path.join(project_dir, "manifest.json")
    if not os.path.exists(manifest_path):
        raise FileNotFoundError(f"No se encontró manifest.json en: {project_dir}")

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    images_dir = os.path.join(project_dir, "images")
    os.makedirs(images_dir, exist_ok=True)

    aspect_ratio = manifest.get("aspect_ratio", "16:9")
    all_scenes = manifest.get("scenes", [])
    if not all_scenes:
        print("⚠️ No hay escenas en manifest.json")
        return

    if target_scene is not None:
        scenes_to_process = [s for s in all_scenes if s.get("scene_number") == target_scene]
        if not scenes_to_process:
            print(f"❌ La escena número {target_scene} no existe en el manifest. (Total escenas: {len(all_scenes)})")
            return
    else:
        scenes_to_process = all_scenes

    print("\n" + "=" * 80)
    print(f" 🖼️ GENERANDO IMÁGENES MEDIANTE FAL.AI ({model})")
    print(f" 📐 Aspect Ratio: {aspect_ratio}")
    if target_scene:
        print(f" 🎯 MODO ESCENA ÚNICA: Procesando únicamente la Escena #{target_scene}")
    else:
        print(f" ⚙️ Procesando {len(scenes_to_process)} escenas | Retries: {max_retries} | Delay: {rate_limit_delay}s")
    if force:
        print(" 🔄 Modo FORCED activado: Re-generando todas las imágenes seleccionadas.")
    print("=" * 80)

    processed_count = 0
    skipped_count = 0

    for scene in scenes_to_process:
        idx = scene.get("scene_number", 1)
        visual_prompt = scene.get("visual_prompt", "minimalist 2D vector stick figure cartoon")
        narration = scene.get("narration_text", "")
        image_filename = f"scene_{idx}.jpg"
        image_path = os.path.join(images_dir, image_filename)

        if not force and is_valid_image_file(image_path):
            print(f"\n⏭️ Escena {idx}: Imagen ya existe y es válida ('{image_filename}'). Omitiendo por Checkpoint.")
            scene["image_path"] = image_path
            skipped_count += 1
            continue

        print(f"\n🖼️ Procesando Escena {idx}...")
        print(f"   Prompt: \"{visual_prompt[:90]}...\"")

        success = generate_image_via_fal(
            prompt=visual_prompt,
            output_path=image_path,
            model=model,
            aspect_ratio=aspect_ratio,
            max_retries=max_retries
        )

        if success:
            print(f"   ✔ Imagen generada con éxito: {image_path}")
            processed_count += 1
        else:
            print("   ⚠️ Falló la generación en línea tras reintentos. Generando respaldo local (Pillow)...")
            create_fallback_image(image_path, idx, narration, aspect_ratio=aspect_ratio)
            print(f"   ✔ Respaldo guardado en: {image_path}")
            processed_count += 1

        scene["image_path"] = image_path

        if rate_limit_delay > 0 and (processed_count < len(scenes_to_process)):
            time.sleep(rate_limit_delay)

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 80)
    print(f" ✔ Proceso completado. Imágenes procesadas: {processed_count} | Omitidas (Checkpoint): {skipped_count}")
    print(" ✔ Manifest.json actualizado con éxito.")
    print("=" * 80)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Módulo Visual para Faceless Engine mediante fal.ai")
    parser.add_argument("--project_dir", type=str, default=None, help="Directorio del proyecto")
    parser.add_argument("--model", type=str, default="fal-ai/flux/schnell", help="Modelo de fal.ai")
    parser.add_argument("--retries", type=int, default=3, help="Reintentos por escena")
    parser.add_argument("--scene", type=int, default=None, help="Número específico de escena a regenerar")
    parser.add_argument("--force", action="store_true", help="Ignora el checkpoint y fuerza la regeneración")
    parser.add_argument("--delay", type=float, default=1.0, help="Pausa en segundos entre peticiones API")

    args = parser.parse_args()
    target_project_dir = args.project_dir or get_current_project_dir()

    process_scene_media(
        project_dir=target_project_dir,
        model=args.model,
        max_retries=args.retries,
        target_scene=args.scene,
        force=args.force,
        rate_limit_delay=args.delay
    )