import os
import time
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

# Cargar variables de entorno desde .env
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


# --- HELPER INTERACTIVO ---

def get_user_topic_selection(default_topics: list) -> str:
    """
    Permite al usuario elegir un número de la lista de tendencias 
    o escribir su propio tema/título personalizado.
    """
    print("\n" + "=" * 80)
    print(" SELECCIÓN DE TEMA / CONCEPTO PARA EL GUION")
    print("=" * 80)
    
    for idx, topic in enumerate(default_topics, start=1):
        print(f"  [{idx}] {topic}")
    
    print("-" * 80)
    user_input = input("👉 Ingresa el NÚMERO del tema o ESCRIBE tu propio concepto personalizado: ").strip()

    # Opción 1: Número de lista
    if user_input.isdigit():
        index = int(user_input) - 1
        if 0 <= index < len(default_topics):
            selected = default_topics[index]
            print(f"\n✔ Tema seleccionado de la lista: '{selected}'")
            return selected
        else:
            print("\n⚠️ Número fuera de rango. Usando la primera opción por defecto.")
            return default_topics[0]
    
    # Opción 2: Texto personalizado
    elif len(user_input) > 0:
        print(f"\n✔ Tema personalizado ingresado por el usuario: '{user_input}'")
        return user_input
    
    # Opción 3: Enter vacío
    else:
        print(f"\n✔ Usando opción por defecto: '{default_topics[0]}'")
        return default_topics[0]


# --- GENERADOR CON FALLBACK ---

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
    Tema / Concepto del video: "{topic}"
    """

    last_error = None

    for model_name in models_to_try:
        print(f"⏳ Generando guion con {model_name} ({target_duration}s)...")

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
            print(f"✔ Guion generado con éxito usando {model_name}\n")
            return manifest

        except Exception as e:
            last_error = e
            print(f"  ⚠️ Aviso: {model_name} no disponible ({e}). Probando alternativa...\n")
            time.sleep(1)

    raise RuntimeError(f"Todos los modelos de la lista fallaron. Último error: {last_error}")


# --- EJECUCIÓN PRINCIPAL ---

if __name__ == "__main__":
    # Simulación de tendencias extraídas previamente
    sample_trends = [
        "Cómo Romper los Hábitos que te Hacen Pobre y Construir Riqueza | Brian Tracy",
        "5 Reglas de Oro para Gestionar tu Dinero en 2026",
        "Por qué la Clase Media se Queda Atrapada en la Carrera de Ratas"
    ]

    # Entrada interactiva: Número o Texto libre
    niche_topic = get_user_topic_selection(sample_trends)

    try:
        script_manifest = generate_faceless_script(
            topic=niche_topic,
            target_duration=15,
            primary_model="models/gemini-3.7-flash"
        )

        output_dir = "output"
        os.makedirs(output_dir, exist_ok=True)
        file_path = os.path.join(output_dir, "script_manifest.json")

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(script_manifest.model_dump_json(indent=2))

        print("=" * 80)
        print(" GUION GENERADO EXITOSAMENTE")
        print("=" * 80)
        print(f" Título del Video: {script_manifest.title}")
        print(f" Duración estimada: {script_manifest.target_duration_seconds} segundos")
        print(f" Cantidad de escenas: {len(script_manifest.scenes)}")
        print("-" * 80)

        for scene in script_manifest.scenes:
            print(f" Escena {scene.scene_number}:")
            print(f"   Locución: \"{scene.narration_text}\"")
            print(f"   Prompt Visual: {scene.visual_prompt[:60]}...")

        print("=" * 80)
        print(f" Archivo guardado en: {file_path}")

    except Exception as e:
        print(f"\n❌ Error generando el guion: {e}")