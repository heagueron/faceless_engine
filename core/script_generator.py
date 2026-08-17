import os
import time
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

load_dotenv()


# --- ESQUEMAS DE DATOS (PYDANTIC) ---

class Scene(BaseModel):
    scene_number: int = Field(description="Número secuencial de la escena (1, 2, 3...)")
    narration_text: str = Field(description="Texto en español que dirá la voz en off para esta escena")
    visual_prompt: str = Field(description="Prompt visual ultradetallado en INGLÉS para la imagen o video de apoyo")


class ScriptManifest(BaseModel):
    title: str = Field(description="Título sugerido y atractivo para el video o Short")
    target_duration_seconds: int = Field(description="Duración estimada del video completo")
    scenes: list[Scene] = Field(description="Lista ordenada de las escenas que componen el guion")


# --- GENERADOR CON FALLBACK DE MODELOS ---

def generate_faceless_script(
    topic: str,
    target_duration: int = 15,
    primary_model: str = "models/gemini-3.6-flash"
) -> ScriptManifest:
    """
    Genera un guion ultracorto utilizando la API de Gemini con los modelos actuales.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Error: GEMINI_API_KEY no encontrada en las variables de entorno (.env).")

    client = genai.Client(api_key=api_key)

    models_to_try = list(dict.fromkeys([
        primary_model,
        "models/gemini-3.6-flash",
        "models/gemini-3.5-flash"
    ]))

    system_instruction = (
        "Eres un guionista experto en contenido viral ultracorto para YouTube Shorts, Reels y TikTok.\n"
        "Tu objetivo es crear un guion MUY CORTO Y DIRECTO (máximo 2 a 3 escenas).\n\n"
        "REGLAS OBLIGATORIAS:\n"
        "1. Narración (narration_text): En ESPAÑOL, directo al punto, sin introducciones largas.\n"
        "2. Prompts Visuales (visual_prompt): SIEMPRE en INGLÉS. Estilo cinematográfico, 8k, fotorrealista.\n"
        "3. Duración: Estricta alineación a los segundos solicitados."
    )

    prompt = f"""
    Crea un guion ULTRACORTO de aproximadamente {target_duration} segundos (máximo 2 o 3 escenas, corto e impactante).
    Tema / Concepto del video: "{topic}"
    """

    last_error = None

    for model_name in models_to_try:
        print(f"⏳ Generando guion con {model_name} ({target_duration}s)...")

        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                    response_schema=ScriptManifest,
                    temperature=0.7,
                )
            )

            manifest = ScriptManifest.model_validate_json(response.text)
            print(f"✔ Guion generado con éxito usando {model_name}\n")
            return manifest

        except Exception as e:
            last_error = e
            print(f"  ⚠️ Aviso: {model_name} no disponible ({e}). Probando alternativa...\n")
            time.sleep(1)

    raise RuntimeError(f"Todos los modelos de la lista fallaron. Último error: {last_error}")


# --- FUNCIÓN DE ENTRADA PARA MAIN.PY ---

def generate_script(topic: str, project_dir: str, target_duration: int = 15) -> dict:
    os.makedirs(project_dir, exist_ok=True)
    manifest_path = os.path.join(project_dir, "manifest.json")

    script_manifest = generate_faceless_script(
        topic=topic,
        target_duration=target_duration
    )

    manifest_data = script_manifest.model_dump()

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2, ensure_ascii=False)

    print(f"   ✔ Guion guardado en: {manifest_path}")
    return manifest_data