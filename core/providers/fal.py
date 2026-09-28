"""
Proveedor de generación de imágenes vía fal.ai.
"""

import os
import time
import requests
from dotenv import load_dotenv

from core.config import get_language_directive

load_dotenv()

try:
    import fal_client
except ImportError:
    fal_client = None


def generate_image_via_fal(
    prompt: str,
    output_path: str,
    model: str = "fal-ai/flux-1/schnell",
    aspect_ratio: str = "16:9",
    max_retries: int = 3,
    retry_delay: float = 3.0
) -> bool:
    """Solicita la generación de imagen a fal.ai."""
    fal_key = os.getenv("FAL_KEY") or os.getenv("FAL_API_KEY")
    if not fal_key:
        print("   ❌ Error: FAL_KEY o FAL_API_KEY no encontrada en .env")
        return False

    os.environ["FAL_KEY"] = fal_key

    lang_directive = get_language_directive()
    if "CRITICAL INSTRUCTION" not in prompt:
        prompt = f"{prompt.rstrip('.')}. {lang_directive}"

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

        except Exception as e:
            print(f"   ⚠️ Fallo en llamada API (Intento {attempt}/{max_retries}): {e}")

        if attempt < max_retries:
            time.sleep(current_delay)
            current_delay *= 1.5

    return False