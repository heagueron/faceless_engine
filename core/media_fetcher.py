import os
import json
import time
import random
import requests
import urllib.parse
from PIL import Image, ImageDraw


def create_fallback_image(output_path: str, scene_num: int, text: str):
    """
    Crea una imagen vertical 1080x1920 local usando Pillow como respaldo infalible
    para garantizar que ninguna escena quede huérfana de imagen.
    """
    img = Image.new('RGB', (1080, 1920), color=(18, 22, 30))
    draw = ImageDraw.Draw(img)
    
    # Marco estético
    draw.rectangle([40, 40, 1040, 1880], outline=(60, 80, 110), width=6)
    
    # Texto de la escena
    draw.text((100, 900), f"ESCENA {scene_num}", fill=(255, 200, 80))
    
    img.save(output_path, "JPEG", quality=90)


def fetch_image_for_prompt(prompt: str, output_path: str, seed: int, max_retries: int = 3) -> bool:
    """
    Descarga la imagen con reintentos automáticos y retardo progresivo
    para evitar bloquear por rate limits (429) o timeouts.
    """
    clean_prompt = prompt.replace("\n", " ").strip()
    full_prompt = f"{clean_prompt}, 8k resolution, cinematic lighting, photorealistic, 9:16 vertical format"
    encoded_prompt = urllib.parse.quote(full_prompt)
    
    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1080&height=1920&nologo=true&seed={seed}"

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200 and len(response.content) > 2000:
                with open(output_path, "wb") as f:
                    f.write(response.content)
                return True
            elif response.status_code == 429:
                wait_time = attempt * 4
                print(f"   ⚠️ Rate Limit (429). Esperando {wait_time}s para reintentar ({attempt}/{max_retries})...")
                time.sleep(wait_time)
            else:
                print(f"   ⚠️ Servidor respondió status {response.status_code}. Reintentando...")
                time.sleep(2)
        except Exception as e:
            print(f"   ⚠️ Intento {attempt} falló ({e}). Reintentando...")
            time.sleep(2)

    return False


def process_scene_media(project_dir: str):
    """
    Procesa cada escena del manifest.json, genera su imagen en project_dir/images/
    y garantiza que TODAS las escenas tengan un archivo asignado.
    """
    manifest_path = os.path.join(project_dir, "manifest.json")
    if not os.path.exists(manifest_path):
        raise FileNotFoundError(f"No se encontró manifest.json en: {project_dir}")

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    images_dir = os.path.join(project_dir, "images")
    os.makedirs(images_dir, exist_ok=True)

    print("\n" + "=" * 80)
    print(" 🖼 GENERANDO Y DESCARGANDO IMÁGENES ÚNICAS POR ESCENA")
    print("=" * 80)

    scenes = manifest.get("scenes", [])
    timestamp_base = int(time.time())

    for idx, scene in enumerate(scenes, 1):
        visual_prompt = scene.get("visual_prompt", "cinematic background shot")
        narration = scene.get("narration_text", "")
        image_filename = f"scene_{idx}.jpg"
        image_path = os.path.join(images_dir, image_filename)

        unique_seed = timestamp_base + (idx * 333) + random.randint(100, 999)

        print(f"\n🖼 Procesando Escena {idx} de {len(scenes)}...")
        print(f"   Prompt: \"{visual_prompt[:75]}...\"")

        success = fetch_image_for_prompt(prompt=visual_prompt, output_path=image_path, seed=unique_seed)

        if success:
            print(f"   ✔ Imagen IA guardada en: {image_path}")
        else:
            print(f"   ⚠️ No se pudo descargar imagen en línea. Generando imagen de respaldo local...")
            create_fallback_image(image_path, idx, narration)
            print(f"   ✔ Respaldo guardado en: {image_path}")

        scene["image_path"] = image_path

        # Pausa preventiva entre escenas para no saturar la API
        time.sleep(2.5)

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 80)
    print(" ✔ Proceso visual completado y manifest.json actualizado.")
    print("=" * 80)