"""
Proveedor de generación de imágenes vía OpenRouter.
"""

import os
import re
import base64
import time
import requests
from dotenv import load_dotenv

from core.config import get_language_directive

load_dotenv()


def generate_image_via_openrouter(
    prompt: str,
    output_path: str,
    model: str = "qwen/qwen-image-3",
    aspect_ratio: str = "16:9",
    max_retries: int = 3,
    retry_delay: float = 3.0,
    request_timeout: int = 120
) -> bool:
    """Genera una imagen utilizando la API de OpenRouter."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("   ❌ Error: OPENROUTER_API_KEY no encontrada en .env")
        return False

    lang_directive = get_language_directive()
    if "CRITICAL INSTRUCTION" not in prompt:
        prompt = f"{prompt.rstrip('.')}. {lang_directive}"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/faceless-engine",
        "X-Title": "Faceless Engine"
    }

    current_delay = retry_delay

    for attempt in range(1, max_retries + 1):
        try:
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
            print(f"   ⏳ Timeout ({request_timeout}s alcanzado). Reintentando ({attempt}/{max_retries})...")
        except Exception as e:
            print(f"   ⚠️ Fallo en llamada OpenRouter (Intento {attempt}/{max_retries}): {e}")

        if attempt < max_retries:
            time.sleep(current_delay)
            current_delay *= 1.5

    return False