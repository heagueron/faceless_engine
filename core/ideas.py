import os
import re
import json
import argparse
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv
import requests

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from pydantic import BaseModel, Field

load_dotenv()


class IdeaItem(BaseModel):
    id: int
    titulo: str = Field(description="Título corto y atractivo para la idea.")
    gancho_inicial: str = Field(description="Gancho de 0-3s para detener el scroll.")
    resumen_premisa: str = Field(description="Resumen corto de la historia o concepto (2 a 3 oraciones).")
    remate_o_giro: str = Field(description="Cierre, conclusión o giro de la historia.")


class IdeasResponse(BaseModel):
    ideas: List[IdeaItem]


def load_reverse_analysis() -> Optional[Dict[str, Any]]:
    """Carga el análisis de ingeniería inversa previo si existe en la carpeta output."""
    analysis_path = os.path.join("output", "reverse_prompting_analysis.json")
    if os.path.exists(analysis_path):
        try:
            with open(analysis_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                print(f"💡 Referencia cargada: '{data.get('title', 'Video previo')}'")
                return data.get("analysis")
        except Exception as e:
            print(f"⚠️ No se pudo leer el análisis previo: {e}")
    return None


def generate_ideas(
    topic: str,
    reverse_analysis: Optional[Dict[str, Any]] = None,
    model: str = "google/gemini-3.7-flash"
) -> List[Dict[str, Any]]:
    """
    Envía el tema y la estructura de referencia a Gemini vía OpenRouter para generar 5 ideas.
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("❌ Error: OPENROUTER_API_KEY no encontrada en .env")
        return []

    print(f"\n🧠 Generando 5 ideas conceptuales para: '{topic}' usando {model}...")

    context_str = ""
    if reverse_analysis:
        context_str = (
            f"- Usar patrón de gancho similar a: {reverse_analysis.get('gancho_inicial', '')}\n"
            f"- Estructura narrativa sugerida: {reverse_analysis.get('estructura_narrativa', '')}\n"
            f"- Recurso de retención a aplicar: {reverse_analysis.get('patron_retencion', '')}\n"
        )

    system_instruction = (
        "Eres un creador senior de contenido viral para YouTube Shorts (9:16).\n"
        "Tu objetivo es proponer EXACTAMENTE 5 ideas únicas, creativas y atrapantes basadas en el tema ingresado.\n\n"
        "REGLAS ESTRUCTURALES:\n"
        "1. Responde ÚNICAMENTE con un JSON válido que contenga una lista 'ideas' de 5 elementos.\n"
        "2. Cada idea debe tener: id (1 al 5), titulo, gancho_inicial, resumen_premisa, remate_o_giro.\n"
        "3. El resumen_premisa debe ser conciso (máximo 25 palabras).\n"
        "4. NO utilices saltos de línea dentro de los valores de texto del JSON.\n\n"
        "Esquema JSON requerido:\n"
        "{\n"
        '  "ideas": [\n'
        '    {\n'
        '      "id": 1,\n'
        '      "titulo": "Título de la idea",\n'
        '      "gancho_inicial": "Frase impactante (0-3s)",\n'
        '      "resumen_premisa": "Resumen corto en 2 oraciones.",\n'
        '      "remate_o_giro": "Cierre imprevisto o conclusión."\n'
        '    }\n'
        '  ]\n'
        "}"
    )

    user_prompt = f"Tema deseado: '{topic}'\n"
    if context_str:
        user_prompt += f"\nPautas de éxito (ingeniería inversa previa):\n{context_str}"

    raw_content = ""
    try:
        if OpenAI is not None:
            client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=api_key,
            )
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=2500,  # 👈 Aumentado para tolerar razonamiento + JSON completo
                response_format={"type": "json_object"},
                extra_body={
                    "reasoning": {"effort": "low"}  # 👈 Minimiza gasto excesivo de tokens en 'thinking'
                }
            )
            raw_content = response.choices[0].message.content
        else:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/faceless-engine",
                "X-Title": "Faceless Engine"
            }
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 2500,  # 👈 Aumentado
                "response_format": {"type": "json_object"},
                "reasoning": {"effort": "low"}  # 👈 Reducción de razonamiento
            }
            res = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=30)
            res.raise_for_status()
            res_data = res.json()
            raw_content = res_data["choices"][0]["message"]["content"]

        clean_json_str = raw_content.strip()
        if clean_json_str.startswith("```"):
            clean_json_str = re.sub(r"^```[a-zA-Z]*\n?", "", clean_json_str)
            clean_json_str = re.sub(r"\n?```$", "", clean_json_str).strip()

        ideas_dict = json.loads(clean_json_str)
        validated = IdeasResponse.model_validate(ideas_dict)
        return [idea.model_dump() for idea in validated.ideas]

    except Exception as e:
        print(f"❌ Error al generar ideas vía OpenRouter: {e}")
        if raw_content:
            print(f"📄 Respuesta cruda (truncada):\n{raw_content}")
        return []


def display_ideas(ideas: List[Dict[str, Any]]):
    """Muestra las 5 ideas formateadas en consola."""
    print("\n" + "=" * 85)
    print(" 💡 5 IDEAS GENERADAS PARA TU VIDEO")
    print("=" * 85)
    for idea in ideas:
        print(f"[{idea['id']}] 📌 {idea['titulo']}")
        print(f"    🎣 Gancho (0-3s): {idea['gancho_inicial']}")
        print(f"    📖 Premisa:     {idea['resumen_premisa']}")
        print(f"    🏁 Remate:      {idea['remate_o_giro']}\n")
    print("=" * 85)


def select_or_custom_idea(topic: str, ideas: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Permite al usuario elegir una de las 5 ideas o redactar/ajustar una propia."""
    if ideas:
        display_ideas(ideas)
        print("\n🛑 INTERVENCIÓN HUMANA:")
        print("👉 Selecciona el número [1-5] de la idea preferida.")
        print("👉 O escribe una idea/mejora personalizada directamente.")
    else:
        print("\n⚠️ No se pudieron generar las ideas automáticas.")
        print("🛑 INTERVENCIÓN HUMANA:")
        print("👉 Escribe directamente la idea o premisa que deseas usar para el video:")

    choice = input("\nSu elección: ").strip()

    selected_data = {}

    if ideas and choice.isdigit() and 1 <= int(choice) <= len(ideas):
        idx = int(choice) - 1
        selected_data = ideas[idx]
        print(f"\n✔ Idea seleccionada: [{selected_data['id']}] {selected_data['titulo']}")
    elif len(choice) > 0:
        print(f"\n✔ Idea personalizada ingresada: '{choice}'")
        selected_data = {
            "id": 0,
            "titulo": f"Idea: {topic}",
            "gancho_inicial": "Definido para el script",
            "resumen_premisa": choice,
            "remate_o_giro": "Definido para el script"
        }
    else:
        fallback_idea = ideas[0] if ideas else {
            "id": 0,
            "titulo": topic,
            "gancho_inicial": f"¿Sabías esto sobre {topic}?",
            "resumen_premisa": f"Un recorrido narrativo por {topic}.",
            "remate_o_giro": "Un dato impactante al final."
        }
        selected_data = fallback_idea
        print(f"\n✔ Opción seleccionada por defecto: {selected_data['titulo']}")

    os.makedirs("output", exist_ok=True)
    output_path = os.path.join("output", "selected_idea.json")
    
    final_payload = {
        "topic": topic,
        "selected_idea": selected_data
    }
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(final_payload, f, ensure_ascii=False, indent=2)

    print(f"📁 Idea guardada con éxito en: '{output_path}'\n")
    return final_payload

def run_ideas_workflow(custom_topic: Optional[str] = None) -> Dict[str, Any]:
    """Workflow interactivo principal para ideas.py."""
    print("\n" + "=" * 85)
    print(" 🎯 GENERADOR DE IDEAS NARRATIVAS PARA SHORTS")
    print("=" * 85)

    topic = custom_topic
    if not topic:
        topic = input("👉 Ingrese el TEMA para las 5 ideas (ej. 'Cultura griega antigua'): ").strip()
    
    if not topic:
        topic = "Aventuras en la montaña"

    reverse_analysis = load_reverse_analysis()
    ideas = generate_ideas(topic=topic, reverse_analysis=reverse_analysis)
    
    return select_or_custom_idea(topic=topic, ideas=ideas)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generador de Ideas de Video para Faceless Engine")
    parser.add_argument("--topic", type=str, help="Tema para generar las 5 ideas")
    parser.add_argument("--model", type=str, default="google/gemini-3.7-flash", help="Modelo de OpenRouter")

    args = parser.parse_args()
    run_ideas_workflow(custom_topic=args.topic)