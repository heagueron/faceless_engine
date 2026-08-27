import os
import re
import json
import time
import base64
import argparse
import requests
from typing import Optional
from dotenv import load_dotenv
from PIL import Image, ImageDraw

load_dotenv()


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


def create_fallback_image(output_path: str, scene_num: int, text: str):
    """Crea una imagen vertical 1080x1920 local usando Pillow como respaldo infalible."""
    img = Image.new('RGB', (1080, 1920), color=(18, 22, 30))
    draw = ImageDraw.Draw(img)
    draw.rectangle([40, 40, 1040, 1880], outline=(60, 80, 110), width=6)
    draw.text((100, 900), f"ESCENA {scene_num}", fill=(255, 200, 80))
    img.save(output_path, "JPEG", quality=90)


def _save_image_from_content(content: str, output_path: str) -> bool:
    """Decodifica y guarda la imagen si la respuesta es Base64, Data URL o una URL HTTP(S)."""
    try:
        # 1. Data URL con Base64
        base64_match = re.search(r'data:image/[^;]+;base64,([A-Za-z0-9+/=]+)', content)
        if base64_match:
            img_data = base64.b64decode(base64_match.group(1))
            with open(output_path, "wb") as f:
                f.write(img_data)
            return True

        # 2. Cadena Base64 pura
        if len(content) > 1000 and not content.startswith("http") and not content.startswith("{"):
            try:
                img_data = base64.b64decode(content.strip())
                with open(output_path, "wb") as f:
                    f.write(img_data)
                return True
            except Exception:
                pass

        # 3. URL de imagen HTTP(S) o markdown ![img](https://...)
        url_match = re.search(r'https?://[^\s\)\"\']+', content)
        if url_match:
            img_url = url_match.group(0)
            res = requests.get(img_url, timeout=30)
            if res.status_code == 200 and len(res.content) > 1000:
                with open(output_path, "wb") as f:
                    f.write(res.content)
                return True

    except Exception as e:
        print(f"   ⚠️ Error al procesar contenido de la imagen: {e}")

    return False


def generate_image_via_openrouter(
    prompt: str,
    output_path: str,
    model: str = "google/gemini-3.1-flash-image",
    max_retries: int = 1
) -> bool:
    """Solicita la generación de imagen a OpenRouter."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("   ❌ Error: OPENROUTER_API_KEY no encontrada en .env")
        return False

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/faceless-engine",
        "X-Title": "Faceless Engine"
    }

    payload = {
        "model": model,
        "modalities": ["image", "text"],
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ]
    }

    for attempt in range(1, max_retries + 1):
        try:
            res = requests.post(url, headers=headers, json=payload, timeout=60)
            
            if res.status_code == 200:
                data = res.json()
                
                os.makedirs("output", exist_ok=True)
                with open("output/debug_openrouter_response.json", "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)

                choice = data.get("choices", [{}])[0]
                message = choice.get("message", {})
                
                # Inspección 1: message.content
                content = message.get("content", "")
                if content and _save_image_from_content(str(content), output_path):
                    return True

                # Inspección 2: message.images
                images = message.get("images", [])
                if isinstance(images, list) and len(images) > 0:
                    first_img = images[0]
                    img_src = first_img.get("url") or first_img.get("b64_json") or first_img.get("image_url", {})
                    if isinstance(img_src, dict):
                        img_src = img_src.get("url", "")
                    if img_src and _save_image_from_content(str(img_src), output_path):
                        return True

                # Inspección 3: choice.image_url
                if "image_url" in choice and _save_image_from_content(str(choice["image_url"]), output_path):
                    return True

                print("\n   ⚠️ No se pudo extraer la imagen del JSON recibido.")
            else:
                print(f"   ⚠️ OpenRouter respondió con status {res.status_code}: {res.text[:200]}")

        except Exception as e:
            print(f"   ⚠️ Fallo en llamada API: {e}")

    return False


def process_scene_media(
    project_dir: str,
    model: str = "google/gemini-3.1-flash-image",
    max_retries: int = 1,
    target_scene: Optional[int] = None
):
    """
    Procesa escenas del manifest.json. 
    Si target_scene está definido (ej: 25), procesa ÚNICAMENTE esa escena.
    """
    manifest_path = os.path.join(project_dir, "manifest.json")
    if not os.path.exists(manifest_path):
        raise FileNotFoundError(f"No se encontró manifest.json en: {project_dir}")

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    images_dir = os.path.join(project_dir, "images")
    os.makedirs(images_dir, exist_ok=True)

    all_scenes = manifest.get("scenes", [])
    if not all_scenes:
        print("⚠️ No hay escenas en manifest.json")
        return

    # Filtrar si se solicitó una escena en específico
    if target_scene is not None:
        scenes_to_process = [s for s in all_scenes if s.get("scene_number") == target_scene]
        if not scenes_to_process:
            print(f"❌ La escena número {target_scene} no existe en el manifest. (Total escenas: {len(all_scenes)})")
            return
    else:
        scenes_to_process = all_scenes

    print("\n" + "=" * 80)
    print(f" 🖼️ GENERANDO IMÁGENES MEDIANTE OPENROUTER ({model})")
    if target_scene:
        print(f" 🎯 MODO ESCENA ÚNICA: Procesando únicamente la Escena #{target_scene}")
    else:
        print(f" ⚙️ Procesando todas las escenas ({len(scenes_to_process)}) | Retries: {max_retries}")
    print("=" * 80)

    for scene in scenes_to_process:
        idx = scene.get("scene_number", 1)
        visual_prompt = scene.get("visual_prompt", "minimalist 2D vector stick figure cartoon")
        narration = scene.get("narration_text", "")
        image_filename = f"scene_{idx}.jpg"
        image_path = os.path.join(images_dir, image_filename)

        print(f"\n🖼️ Procesando Escena {idx}...")
        print(f"   Prompt: \"{visual_prompt[:90]}...\"")

        success = generate_image_via_openrouter(
            prompt=visual_prompt,
            output_path=image_path,
            model=model,
            max_retries=max_retries
        )

        if success:
            print(f"   ✔ Imagen generada y actualizada en: {image_path}")
        else:
            print("   ⚠️ Falló la generación en línea. Generando respaldo local (Pillow)...")
            create_fallback_image(image_path, idx, narration)
            print(f"   ✔ Respaldo guardado en: {image_path}")

        scene["image_path"] = image_path

    # Guardar manifest.json actualizado preservando el resto de las escenas intactas
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 80)
    print(" ✔ Proceso completado y manifest.json actualizado.")
    print("=" * 80)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Módulo Visual para Faceless Engine")
    parser.add_argument("--project_dir", type=str, default=None, help="Directorio del proyecto")
    parser.add_argument("--model", type=str, default="google/gemini-3.1-flash-image", help="Modelo de OpenRouter")
    parser.add_argument("--retries", type=int, default=1, help="Reintentos por escena")
    parser.add_argument("--scene", type=int, default=None, help="Número específico de escena a regenerar (ej: --scene 25)")

    args = parser.parse_args()
    target_project_dir = args.project_dir or get_current_project_dir()

    process_scene_media(
        project_dir=target_project_dir,
        model=args.model,
        max_retries=args.retries,
        target_scene=args.scene
    )