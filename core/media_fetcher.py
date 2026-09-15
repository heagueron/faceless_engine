import os
import re
import json
import time
import base64
import argparse
import requests
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
from PIL import Image, ImageDraw

load_dotenv()

try:
    import fal_client
except ImportError:
    fal_client = None


# ==============================================================================
# CONFIGURACIÓN GENERAL Y PROVEEDOR POR DEFECTO
# ==============================================================================
DEFAULT_IMAGE_PROVIDER = "openrouter"

DEFAULT_MODELS = {
    "openrouter": "qwen/qwen-image-3",
    "fal": "fal-ai/qwen-image-2512"
}
# ==============================================================================


def parse_scene_input(scene_str: str) -> List[int]:
    """
    Soporta formatos:
    - Individual: '3' -> [3]
    - Rango: '1-10' -> [1, 2, ..., 10]
    - Lista: '1,3,5' -> [1, 3, 5]
    - Mixto: '1-3,5,8-10' -> [1, 2, 3, 5, 8, 9, 10]
    """
    scenes = set()
    for part in scene_str.split(','):
        part = part.strip()
        if not part:
            continue
        if '-' in part:
            try:
                start, end = part.split('-', 1)
                scenes.update(range(int(start), int(end) + 1))
            except ValueError:
                pass
        elif part.isdigit():
            scenes.add(int(part))
    return sorted(list(scenes))


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


def generate_image_via_openrouter(
    prompt: str,
    output_path: str,
    model: str = "qwen/qwen-image-3",
    aspect_ratio: str = "16:9",
    max_retries: int = 3,
    retry_delay: float = 3.0,
    request_timeout: int = 120
) -> bool:
    """
    Genera una imagen utilizando la API de OpenRouter aumentando el timeout a 120s
    para evitar cierres de conexión prematuros.
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("   ❌ Error: OPENROUTER_API_KEY no encontrada en .env")
        return False

    spanish_directive = " CRITICAL INSTRUCTION: All text, labels, signs, callouts, or annotations rendered inside the image MUST be written strictly in SPANISH language."
    if "SPANISH language" not in prompt:
        prompt = f"{prompt.rstrip('.')}.{spanish_directive}"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/faceless-engine",
        "X-Title": "Faceless Engine"
    }

    current_delay = retry_delay

    for attempt in range(1, max_retries + 1):
        try:
            # 1. Intentar endpoint /images/generations con timeout extendido
            url_img = "https://openrouter.ai/api/v1/images/generations"
            payload_img = {
                "model": model,
                "prompt": prompt,
                "aspect_ratio": aspect_ratio
            }
            
            res = requests.post(url_img, headers=headers, json=payload_img, timeout=request_timeout)

            if res.status_code == 200:
                data = res.json()
                items = data.get("data", [])
                if items:
                    first_item = items[0]
                    if "url" in first_item and first_item["url"]:
                        img_res = requests.get(first_item["url"], timeout=45)
                        if img_res.status_code == 200 and len(img_res.content) > 1000:
                            with open(output_path, "wb") as f:
                                f.write(img_res.content)
                            return True
                    elif "b64_json" in first_item:
                        b64_data = first_item["b64_json"]
                        with open(output_path, "wb") as f:
                            f.write(base64.b64decode(b64_data))
                        return True

            # 2. Fallback: Intentar /chat/completions si el primer endpoint devuelve error no fatal
            url_chat = "https://openrouter.ai/api/v1/chat/completions"
            payload_chat = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "modalities": ["image"]
            }
            res_chat = requests.post(url_chat, headers=headers, json=payload_chat, timeout=request_timeout)
            if res_chat.status_code == 200:
                chat_data = res_chat.json()
                choices = chat_data.get("choices", [])
                if choices:
                    msg = choices[0].get("message", {})
                    content = msg.get("content", "")
                    
                    urls = re.findall(r'https?://[^\s\)]+', content)
                    msg_images = msg.get("images", [])
                    if msg_images and isinstance(msg_images, list):
                        for img_obj in msg_images:
                            if isinstance(img_obj, dict) and "url" in img_obj:
                                urls.append(img_obj["url"])
                            elif isinstance(img_obj, str):
                                urls.append(img_obj)

                    for url_candidate in urls:
                        img_res = requests.get(url_candidate, timeout=45)
                        if img_res.status_code == 200 and len(img_res.content) > 1000:
                            with open(output_path, "wb") as f:
                                f.write(img_res.content)
                            return True

            if res.status_code == 429 or res_chat.status_code == 429:
                print(f"   ⏳ Rate Limit (429) en OpenRouter. Reintentando en {current_delay:.1f}s (Intento {attempt}/{max_retries})...")
            else:
                print(f"   ⚠️ OpenRouter status: {res.status_code} / chat status: {res_chat.status_code}")

        except requests.exceptions.Timeout:
            print(f"   ⏳ Timeout ({request_timeout}s alcanzado). El modelo tardó demasiado. Reintentando ({attempt}/{max_retries})...")
        except Exception as e:
            print(f"   ⚠️ Fallo en llamada OpenRouter (Intento {attempt}/{max_retries}): {e}")

        if attempt < max_retries:
            time.sleep(current_delay)
            current_delay *= 1.5

    return False


def generate_image_via_fal(
    prompt: str,
    output_path: str,
    model: str = "fal-ai/qwen-image-2512",
    aspect_ratio: str = "16:9",
    max_retries: int = 3,
    retry_delay: float = 3.0
) -> bool:
    """
    Solicita la generación de imagen a fal.ai.
    Maneja reintentos con backoff exponencial.
    """
    fal_key = os.getenv("FAL_KEY") or os.getenv("FAL_API_KEY")
    if not fal_key:
        print("   ❌ Error: FAL_KEY o FAL_API_KEY no encontrada en .env")
        return False

    os.environ["FAL_KEY"] = fal_key

    spanish_directive = " CRITICAL INSTRUCTION: All text, labels, signs, callouts, or annotations rendered inside the image MUST be written strictly in SPANISH language."
    if "SPANISH language" not in prompt:
        prompt = f"{prompt.rstrip('.')}.{spanish_directive}"

    image_size = "portrait_16_9" if aspect_ratio == "9:16" else "landscape_16_9"
    current_delay = retry_delay

    for attempt in range(1, max_retries + 1):
        try:
            if fal_client is not None:
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
                    print(f"   ⏳ Rate Limit (429) en fal.ai. Reintentando en {current_delay:.1f}s (Intento {attempt}/{max_retries})...")
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
    provider: str = DEFAULT_IMAGE_PROVIDER,
    model: Optional[str] = None,
    max_retries: int = 3,
    target_scenes: Optional[List[int]] = None,
    force: bool = False,
    rate_limit_delay: float = 1.0
):
    """
    Procesa escenas del manifest.json seleccionando el proveedor ('openrouter' o 'fal').
    Soporta lista o rango de escenas objetivo.
    """
    provider_key = provider.lower().strip()
    if provider_key not in ["openrouter", "fal"]:
        print(f"⚠️ Proveedor '{provider}' no válido. Usando '{DEFAULT_IMAGE_PROVIDER}'.")
        provider_key = DEFAULT_IMAGE_PROVIDER

    selected_model = model or DEFAULT_MODELS[provider_key]

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

    if target_scenes:
        scenes_to_process = [s for s in all_scenes if s.get("scene_number") in target_scenes]
        if not scenes_to_process:
            print(f"❌ Ninguna de las escenas solicitadas ({target_scenes}) existe en el manifest. (Total escenas: {len(all_scenes)})")
            return
    else:
        scenes_to_process = all_scenes

    print("\n" + "=" * 80)
    print(f" 🖼️ GENERANDO IMÁGENES MEDIANTE {provider_key.upper()} ({selected_model})")
    print(f" 📐 Aspect Ratio: {aspect_ratio}")
    if target_scenes:
        print(f" 🎯 MODO SELECCIÓN DE ESCENAS: Procesando {len(scenes_to_process)} escena(s): {target_scenes}")
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

        if provider_key == "openrouter":
            success = generate_image_via_openrouter(
                prompt=visual_prompt,
                output_path=image_path,
                model=selected_model,
                aspect_ratio=aspect_ratio,
                max_retries=max_retries
            )
        else:
            success = generate_image_via_fal(
                prompt=visual_prompt,
                output_path=image_path,
                model=selected_model,
                aspect_ratio=aspect_ratio,
                max_retries=max_retries
            )

        if success:
            print(f"   ✔ Imagen generada con éxito ({provider_key.upper()}): {image_path}")
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
    parser = argparse.ArgumentParser(description="Módulo Visual para Faceless Engine")
    parser.add_argument("--project_dir", type=str, default=None, help="Directorio del proyecto")
    parser.add_argument("--provider", type=str, default=DEFAULT_IMAGE_PROVIDER, choices=["openrouter", "fal"], help="Proveedor de imágenes")
    parser.add_argument("--model", type=str, default=None, help="Modelo específico (omita para usar el predeterminado del proveedor)")
    parser.add_argument("--retries", type=int, default=3, help="Reintentos por escena")
    parser.add_argument("--scene", type=str, default=None, help="Escena(s) a regenerar (ej: '3', '1-10', '1,3,5' o '1-3,5,8-10')")
    parser.add_argument("--force", action="store_true", help="Ignora el checkpoint y fuerza la regeneración")
    parser.add_argument("--delay", type=float, default=1.0, help="Pausa en segundos entre peticiones API")

    args = parser.parse_args()
    target_project_dir = args.project_dir or get_current_project_dir()
    target_scenes = parse_scene_input(args.scene) if args.scene else None

    process_scene_media(
        project_dir=target_project_dir,
        provider=args.provider,
        model=args.model,
        max_retries=args.retries,
        target_scenes=target_scenes,
        force=args.force,
        rate_limit_delay=args.delay
    )