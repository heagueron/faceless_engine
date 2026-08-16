import os
import json
import time
import sys
import threading
from typing import List, Optional
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

load_dotenv()


# ============================================================================
# 1. ESQUEMA DE DATOS CON PYDANTIC
# ============================================================================

class ScriptScene(BaseModel):
    scene_number: int = Field(description="Número secuencial de la escena (1, 2, 3...)")
    narration_text: str = Field(description="Texto exacto que leerá la voz en off AI en español.")
    visual_prompt: str = Field(
        description="Prompt detallado en INGLÉS para la generación de imagen (fotorrealista, 8k)."
    )
    camera_movement: str = Field(
        description="Efecto visual o movimiento de cámara (ej: zoom-in, pan-left, static)."
    )


class ScriptManifest(BaseModel):
    video_title: str = Field(description="Título llamativo y optimizado para el video.")
    target_niche: str = Field(description="Nicho o tema analizado.")
    estimated_duration_seconds: int = Field(description="Duración aproximada total en segundos.")
    scenes: List[ScriptScene] = Field(description="Lista ordenada de las escenas del guion.")


# ============================================================================
# 2. INDICADOR DE PROGRESO (SPINNER EN CONSOLA)
# ============================================================================

class ConsoleSpinner:
    def __init__(self, message: str = "Procesando"):
        self.message = message
        self.running = False
        self.thread = None

    def _spin(self):
        chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        idx = 0
        while self.running:
            sys.stdout.write(f"\r  {chars[idx % len(chars)]} {self.message}...")
            sys.stdout.flush()
            idx += 1
            time.sleep(0.1)
        # Limpiar la línea al terminar
        sys.stdout.write("\r" + " " * (len(self.message) + 10) + "\r")
        sys.stdout.flush()

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._spin)
        self.thread.daemon = True
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()


# ============================================================================
# 3. LÓGICA DE GENERACIÓN CON GEMINI
# ============================================================================

def generate_faceless_script(
    topic: str,
    target_duration: int = 15,
    primary_model: str = "models/gemini-3.7-flash"
) -> ScriptManifest:
    """
    Genera un guion ultracorto utilizando Gemini API con fallback automático
    entre modelos activos para evitar errores 503 por alta demanda.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Error: GEMINI_API_KEY no encontrada en las variables de entorno (.env).")

    client = genai.Client(api_key=api_key)

    # Lista ordenada de fallback en caso de 503 o alta demanda
    models_to_try = [
        primary_model,
        "models/gemini-3.6-flash",
        "models/gemini-3.5-flash"
    ]

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
    Tema / Video de referencia: "{topic}"
    """

    last_error = None

    for model_name in models_to_try:
        spinner = ConsoleSpinner(f"Intentando con {model_name} ({target_duration}s)")
        spinner.start()

        try:
            chat = client.chats.create(
                model=model_name,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                    response_schema=ScriptManifest,
                    temperature=0.7,
                )
            )

            response = chat.send_message(prompt)
            manifest = ScriptManifest.model_validate_json(response.text)
            spinner.stop()
            print(f"✔ Guion generado con éxito usando {model_name}\n")
            return manifest

        except Exception as e:
            spinner.stop()
            last_error = e
            # Si es error de demanda/503 o 404, prueba el siguiente modelo
            print(f"  Aviso: {model_name} no disponible ({e}). Probando alternativa...")
            time.sleep(1)

    raise RuntimeError(f"Todos los modelos de la lista fallaron. Último error: {last_error}")


# ============================================================================
# 4. EJECUCIÓN PRINCIPAL
# ============================================================================

if __name__ == "__main__":
    trend_file = os.path.join("output", "selected_trend.json")
    niche_topic = "Hábitos financieros para construir riqueza"

    if os.path.exists(trend_file):
        try:
            with open(trend_file, "r", encoding="utf-8") as f:
                trend_data = json.load(f)
                niche_topic = trend_data.get("title", niche_topic)
                print(f" Carga exitosa: Usando tema seleccionado de YouTube:\n 👉 '{niche_topic}'\n")
        except Exception as e:
            print(f" Advertencia: No se pudo leer {trend_file}, usando tema por defecto. Error: {e}")
    else:
        print(f" No se encontró '{trend_file}'. Usando tema por defecto: '{niche_topic}'\n")

    try:
        #  Configurado a 15 segundos para acelerar la prueba local
        script_manifest = generate_faceless_script(
            topic=niche_topic,
            target_duration=15,
            primary_model="models/gemini-3.7-flash"
        )

        output_path = os.path.join("output", "script_manifest.json")
        os.makedirs("output", exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(script_manifest.model_dump_json(indent=2))

        print("✔ Guion recibido correctamente de Gemini.\n")
        print("=" * 80)
        print(" GUION GENERADO EXITOSAMENTE (MODO PRUEBA RÁPIDA)")
        print("=" * 80)
        print(f" Título del Video: {script_manifest.video_title}")
        print(f" Duración estimada: {script_manifest.estimated_duration_seconds} segundos")
        print(f" Cantidad de escenas: {len(script_manifest.scenes)}")
        print("-" * 80)
        for scene in script_manifest.scenes:
            print(f" Escena {scene.scene_number}:")
            print(f"   Locución: \"{scene.narration_text}\"")
            print(f"   Prompt Visual: {scene.visual_prompt[:60]}...")
        print("=" * 80)
        print(f" Archivo guardado en: {output_path}")

    except Exception as e:
        print(f" Error generando el guion: {e}")