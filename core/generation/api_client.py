"""
Cliente de OpenRouter para el pipeline de generación de guiones.

Contiene la llamada base a la API y un parser JSON tolerante que
maneja errores comunes del LLM.
"""

import os
import re
import json
from typing import Optional, Dict, Any

from dotenv import load_dotenv
import requests

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

load_dotenv()


def call_openrouter_api(
    system_instruction: str,
    user_prompt: str,
    model: str,
    max_tokens: int = 8192,
) -> str:
    """Envía la solicitud a OpenRouter asegurando respuesta en formato JSON."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY no encontrada en .env")

    clean_json_str = ""
    if OpenAI is not None:
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
            extra_body={"reasoning": {"effort": "low"}},
        )
        clean_json_str = response.choices[0].message.content
    else:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/faceless-engine",
            "X-Title": "Faceless Engine",
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
            "reasoning": {"effort": "low"},
        }
        res = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=90,
        )
        res.raise_for_status()
        res_data = res.json()
        clean_json_str = res_data["choices"][0]["message"]["content"]

    clean_json_str = clean_json_str.strip()
    if clean_json_str.startswith("```"):
        clean_json_str = re.sub(r"^```[a-zA-Z]*\n?", "", clean_json_str)
        clean_json_str = re.sub(r"\n?```$", "", clean_json_str).strip()

    return clean_json_str


def _parse_json_safely(
    raw_json_str: str,
    context: str = "",
) -> Optional[Dict[str, Any]]:
    """
    Parsea JSON del LLM tolerando errores comunes.

    Intenta:
      1. json.loads() directo
      2. json_repair.loads() como fallback

    Retorna None si todo falla.
    """
    if not raw_json_str:
        return None

    # Intento 1: parseo estricto
    try:
        return json.loads(raw_json_str)
    except json.JSONDecodeError:
        pass

    # Intento 2: reparación con json_repair
    try:
        from json_repair import repair_json
        repaired = repair_json(raw_json_str, return_objects=True)
        if isinstance(repaired, dict):
            print(f"   🔧 JSON reparado automáticamente ({context}).")
            return repaired
    except ImportError:
        print("   ⚠️ json_repair no está instalado. Instala con: pip install json-repair")
    except Exception as e:
        print(f"   ⚠️ Fallo al reparar JSON ({context}): {e}")

    return None