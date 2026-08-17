import os
import json
import time
import random
import requests
import urllib.parse


def fetch_image_for_prompt(prompt: str, output_path: str, seed: int) -> bool:
    """
    Descarga una imagen vertical (9:16) generada por IA según el prompt visual.
    Usa un seed dinámico único para evitar imágenes repetidas o en caché.
    """
    clean_prompt = prompt.replace("\n", " ").strip()
    full_prompt = f"{clean_prompt}, 8k resolution, cinematic lighting, photorealistic, 9:16 vertical format"
    encoded_prompt = urllib.parse.quote(full_prompt)
    
    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1080&height=1920&nologo=true&seed={seed}"

    try:
        response = requests.get(url, timeout=35)
        if response.status_code == 200 and len(response.content) > 2000:
            with open(output_path, "wb") as f:
                f.write(response.content)
            return True
        else:
            print(f"   ⚠️ Servidor respondió con status {response.status_code}")
    except Exception as e:
        print(f"   ⚠️ Error de red con Pollinations: {e}")

    # Fallback: Unsplash Source con palabras clave del prompt
    try:
        words = [w for w in clean_prompt.replace(",", " ").split() if len(w) > 3][:3]
        keywords = ",".join(words)
        fallback_url = f"https://source.unsplash.com/1080x1920/?{urllib.parse.quote(keywords)}"
        resp = requests.get(fallback_url, timeout=15)
        if resp.status_code == 200 and len(resp.content) > 2000:
            with open(output_path, "wb") as f:
                f.write(resp.content)
            return True
    except Exception as e:
        print(f"   ⚠️ Fallback Unsplash también falló: {e}")

    return False


def process_scene_media(project_dir: str):
    """
    Procesa cada escena del manifest.json, genera su imagen única en project_dir/images/
    y actualiza manifest.json con la ruta relativa y absoluta correcta.
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
        visual_prompt = scene.get("visual_prompt", "cartoon three little pigs and wolf")
        image_filename = f"scene_{idx}.jpg"
        image_path = os.path.join(images_dir, image_filename)

        # Semilla única combinando timestamp, índice y aleatoriedad
        unique_seed = timestamp_base + (idx * 333) + random.randint(100, 999)

        print(f"\n🖼 Procesando Escena {idx} de {len(scenes)}...")
        print(f"   Prompt: \"{visual_prompt[:75]}...\"")

        success = fetch_image_for_prompt(prompt=visual_prompt, output_path=image_path, seed=unique_seed)

        if success:
            print(f"   ✔ Imagen guardada en: {image_path}")
        else:
            print(f"   ❌ No se pudo descargar imagen para escena {idx}")

        # Guardar la ruta exacta en el diccionario de la escena
        scene["image_path"] = image_path

    # Guardar manifest actualizado
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 80)
    print(" ✔ Proceso visual completado y manifest.json actualizado.")
    print("=" * 80)