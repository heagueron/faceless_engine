"""
Proveedor de generación de imágenes vía NVIDIA Build (NIM).

Usa el endpoint ai.api.nvidia.com/v1/genai que tiene formato NIM nativo
(distinto del OpenAI-compatible). Doc: build.nvidia.com

Rate limit: 40 requests por minuto (según documentación de NVIDIA Build).
El proveedor implementa un throttle interno entre llamadas para no excederlo.
"""

import os
import time
import base64
import requests
from typing import Optional
from dotenv import load_dotenv

from core.config import get_language_directive

load_dotenv()

# --- Endpoint NIM de imágenes ---
NVIDIA_NIM_BASE = "https://ai.api.nvidia.com/v1/genai"

# --- Rate limiting ---
# 40 requests/minuto según docs. Dejamos margen de seguridad: 36 rpm efectivos.
MAX_REQUESTS_PER_MINUTE = 36
_MIN_INTERVAL_BETWEEN_CALLS = 60.0 / MAX_REQUESTS_PER_MINUTE  # ~1.67s

# Timestamp de la última llamada realizada (a nivel de módulo, para throttling global)
_last_call_ts: float = 0.0


def _throttle() -> None:
    """Espera si es necesario para respetar el rate limit global."""
    global _last_call_ts
    now = time.time()
    elapsed = now - _last_call_ts
    if elapsed < _MIN_INTERVAL_BETWEEN_CALLS:
        wait = _MIN_INTERVAL_BETWEEN_CALLS - elapsed
        time.sleep(wait)
    _last_call_ts = time.time()


def _extract_image_bytes(data: dict) -> Optional[bytes]:
    """
    Extrae los bytes de la imagen desde la respuesta NIM.
    Formato NIM: {"artifacts": [{"base64": "..."}]}
    Fallback: formato OpenAI-compatible {"data": [{"b64_json": "..."}]}
    """
    artifacts = data.get("artifacts", [])
    if artifacts and "base64" in artifacts[0]:
        return base64.b64decode(artifacts[0]["base64"])

    items = data.get("data", [])
    if items and "b64_json" in items[0]:
        return base64.b64decode(items[0]["b64_json"])

    return None

def _compress_prompt_for_nvidia(prompt: str, max_chars: int = 800) -> str:
    """
    Comprime el prompt para cumplir con el límite de 800 caracteres de NVIDIA NIM.

    Estrategias en orden:
      1. Normalizar espacios y eliminar duplicados por frases repetidas.
      2. Acortar reglas de aspect ratio (largas → cortas).
      3. Eliminar reglas anti-texto redundantes (se conserva una sola).
      4. Truncado por frases completas (no cortar a mitad de palabra).
    """
    if len(prompt) <= max_chars:
        return prompt

    # 1. Normalizar espacios
    import re
    p = re.sub(r"\s+", " ", prompt).strip()

    # 2. Acortar aspect ratio
    p = p.replace("16:9 horizontal widescreen ratio", "16:9")
    p = p.replace("9:16 vertical ratio", "9:16")
    p = p.replace("16:9 widescreen ratio", "16:9")

    # 3. Reducir reglas anti-texto redundantes
    # (busca la primera ocurrencia y elimina repeticiones)
    anti_text_patterns = [
        "completely clean without any text, letters, or words",
        "completely clean without any text",
        "no text, no letters, no words",
        "no text",
    ]
    first_found = None
    for pattern in anti_text_patterns:
        idx = p.lower().find(pattern.lower())
        if idx != -1:
            if first_found is None:
                first_found = pattern
            else:
                # eliminar repeticiones
                p = p[:idx] + p[idx + len(pattern):]
                p = re.sub(r"\s+", " ", p)
                p = p.replace(", ,", ",").replace(",.", ".").replace(",. ", ". ")
                break

    # 4. Normalizar comas dobles y espacios raros
    p = re.sub(r"\s*,\s*", ", ", p)
    p = re.sub(r"\s*\.\s*", ". ", p).strip()

    if len(p) <= max_chars:
        return p

    # 5. Truncado por frases completas (buscar el último punto antes del límite)
    print(f"   ⚠️ Prompt aún tiene {len(p)} chars (> {max_chars}). Truncando por frases.")
    truncated = p[:max_chars]
    last_period = truncated.rfind(".")
    last_comma = truncated.rfind(",")
    cut_at = max(last_period, last_comma)
    if cut_at > max_chars * 0.7:  # al menos conservar 70%
        truncated = truncated[:cut_at + 1]
    else:
        truncated = truncated.rsplit(" ", 1)[0] + "."

    return truncated.strip()

def generate_image_via_nvidia(
    prompt: str,
    output_path: str,
    model: str = "black-forest-labs/flux.2-klein-4b",
    aspect_ratio: str = "16:9",
    seed: int = 100,
    width: int = 1024,
    height: int = 1024,
    steps: int = 4,
    cfg_scale: float = 1.0,
    max_retries: int = 3,
    retry_delay: float = 3.0,
) -> bool:
    """Genera una imagen vía NVIDIA Build NIM."""
    api_key = os.getenv("NVIDIA_API_KEY")
    if not api_key:
        print("   ❌ Error: NVIDIA_API_KEY no encontrada en .env")
        return False

    # Ajustar imagen según aspect ratio
    if aspect_ratio == "16:9":
        width, height = 1344, 768
    elif aspect_ratio == "9:16":
        width, height = 768, 1344

    # Modelos few-step como Klein requieren steps bajos y cfg bajo
    if "klein" in model.lower():
        steps = 4
        cfg_scale = 1.0
    elif "schnell" in model.lower():
        steps = 4
        cfg_scale = 0.0

    # Añadir directiva de idioma
    lang_directive = get_language_directive()
    if "CRITICAL INSTRUCTION" not in prompt:
        prompt = f"{prompt.rstrip('.')}. {lang_directive}"

    url = f"{NVIDIA_NIM_BASE}/{model}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    # Comprimir prompt para respetar el límite de 800 chars de NVIDIA
    original_len = len(prompt)
    prompt = _compress_prompt_for_nvidia(prompt, max_chars=800)
    if len(prompt) < original_len:
        print(f"   ✂️ Prompt comprimido: {original_len} → {len(prompt)} chars")

    payload = {
        "prompt": prompt,
        "width": width,
        "height": height,
        "steps": steps,
        "cfg_scale": cfg_scale,
        "seed": seed,
    }

    current_delay = retry_delay

    for attempt in range(1, max_retries + 1):
        _throttle()  # respeta el rate limit antes de cada llamada

        try:
            res = requests.post(url, headers=headers, json=payload, timeout=120)

            if res.status_code == 200:
                data = res.json()
                img_bytes = _extract_image_bytes(data)
                if img_bytes and len(img_bytes) > 1000:
                    with open(output_path, "wb") as f:
                        f.write(img_bytes)
                    return True
                else:
                    print(f"   ⚠️ Respuesta sin imagen válida. Keys: {list(data.keys())}")

            elif res.status_code == 429:
                print(f"   ⏳ Rate Limit (429) en NVIDIA. Reintentando en {current_delay:.1f}s (Intento {attempt}/{max_retries})...")
                time.sleep(current_delay)
                current_delay *= 2.0
                continue

            elif res.status_code == 422:
                print(f"   ⚠️ Parámetros inválidos (422): {res.text[:200]}")
                return False

            else:
                print(f"   ⚠️ HTTP {res.status_code}: {res.text[:200]}")

        except requests.exceptions.Timeout:
            print(f"   ⏳ Timeout en NVIDIA (Intento {attempt}/{max_retries})...")
        except Exception as e:
            print(f"   ⚠️ Fallo en llamada NVIDIA (Intento {attempt}/{max_retries}): {e}")

        if attempt < max_retries:
            time.sleep(current_delay)
            current_delay *= 1.5

    return False