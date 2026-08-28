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


# --- ESQUEMAS DE DATOS (PYDANTIC) ---

class VideoIdea(BaseModel):
    id: int = Field(description="Número de la opción (1, 2, 3...)")
    titulo: str = Field(description="Título sugerido, atractivo y corto para el Short")
    gancho_inicial: str = Field(description="Gancho de los primeros 0-3 segundos para capturar la atención")
    resumen_premisa: str = Field(description="Desarrollo o historia principal sintetizada en 2 oraciones")
    remate_o_giro: str = Field(description="Conclusión impactante, llamada a la acción o giro final")


class IdeasResponse(BaseModel):
    topic: str = Field(description="Tema general de la consulta")
    ideas: List[VideoIdea] = Field(description="Lista de 3 propuestas de ángulos virales")


# --- CARGA DE ANALISIS PREVIO ---

def load_reverse_analysis() -> Optional[Dict[str, Any]]:
    """Carga el análisis de ingeniería inversa si existe en output/."""
    analysis_path = os.path.join("output", "reverse_prompting_analysis.json")
    if os.path.exists(analysis_path):
        try:
            with open(analysis_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("analysis")
        except Exception as e:
            print(f"⚠️ No se pudo leer el análisis de ingeniería inversa: {e}")
    return None


# --- GENERADOR DE IDEAS VIA OPENROUTER ---

def generate_ideas_from_openrouter(
    topic: str,
    reverse_analysis: Optional[Dict[str, Any]] = None,
    model: str = "google/gemini-3.7-flash"
) -> Optional[IdeasResponse]:
    """Genera 3 propuestas de ángulos de video mediante OpenRouter."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("❌ Error: OPENROUTER_API_KEY no encontrada en .env")
        return None

    print(f"\n🧠 Ideando ángulos virales para '{topic}' usando {model}...")

    style_guidelines = ""
    if reverse_analysis:
        style_guidelines = (
            f"- Estilo detectado: {reverse_analysis.get('estilo_visual_narrativo', 'Educativo dinámico')}\n"
            f"- Retención basada en: {reverse_analysis.get('patron_retencion', 'Ganchos fuertes y alto ritmo')}\n"
        )

    system_instruction = (
        "Eres un estratega de contenido experto en YouTube Shorts, Reels y TikTok.\n"
        "Tu objetivo es proponer 3 ángulos virales distintos y altamente atractivos basados en el tema proporcionado.\n"
        "Cada opción debe incluir un gancho inicial irresistible (primeros 3 segundos), un resumen rápido de la premisa y un remate final memorable.\n\n"
        "Responde EXCLUSIVAMENTE en JSON que cumpla el esquema requerido:\n"
        "{\n"
        '  "topic": "Tema general",\n'
        '  "ideas": [\n'
        '    {\n'
        '      "id": 1,\n'
        '      "titulo": "Título corto y magnético",\n'
        '      "gancho_inicial": "Pregunta o afirmación chocante para los primeros 3 segundos",\n'
        '      "resumen_premisa": "Desarrollo rápido del tema en 2 frases",\n'
        '      "remate_o_giro": "Conclusión impactante o reflexión final"\n'
        '    }\n'
        '  ]\n'
        "}"
    )

    user_prompt = f"""
Tema principal: {topic}
{style_guidelines}

Genera 3 propuestas de ideas con enfoques dramáticos, educativos o curiosos para capturar el máximo de retención.
"""

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
                temperature=0.8,
                max_tokens=2000,
                response_format={"type": "json_object"}
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
                "temperature": 0.8,
                "max_tokens": 2000,
                "response_format": {"type": "json_object"}
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
        return IdeasResponse.model_validate(ideas_dict)

    except Exception as e:
        print(f"❌ Error al generar ideas vía OpenRouter: {e}")
        if raw_content:
            print(f"📄 Respuesta cruda:\n{raw_content}")
        return None


# --- SELECCIÓN INTERACTIVA ---

def select_idea_interactive(ideas_res: IdeasResponse) -> VideoIdea:
    """Muestra las opciones en consola y permite al usuario seleccionar una."""
    ideas = ideas_res.ideas

    print("\n" + "=" * 85)
    print(f"💡 PROPUESTAS DE ÁNGULOS VIRALES PARA: '{ideas_res.topic}'")
    print("=" * 85)

    for idx, idea in enumerate(ideas, 1):
        print(f"\n📌 Opción #{idx}: {idea.titulo}")
        print(f"   🎣 Gancho (0-3s): {idea.gancho_inicial}")
        print(f"   📖 Premisa:     {idea.resumen_premisa}")
        print(f"   💥 Remate:      {idea.remate_o_giro}")

    print("\n" + "=" * 85)
    
    while True:
        choice = input(f"👉 Selecciona una opción [1-{len(ideas)}] (ENTER para opción 1): ").strip()
        if choice == "":
            selected = ideas[0]
            break
        elif choice.isdigit():
            val = int(choice)
            if 1 <= val <= len(ideas):
                selected = ideas[val - 1]
                break
        print("⚠️ Selección inválida. Intenta de nuevo.")

    print(f"\n✔ Ángulo seleccionado: '{selected.titulo}'")
    return selected


# --- FUNCIÓN PRINCIPAL DE INTEGRACIÓN ---

def generate_ideas(
    topic: Optional[str] = None,
    project_dir: Optional[str] = None,
    model: str = "google/gemini-3.7-flash"
) -> Dict[str, Any]:
    """Genera ideas, solicita la elección del usuario y guarda la selección."""
    if not topic:
        # Intentar leer el tema desde current_project.json si existe
        current_path = os.path.join("output", "current_project.json")
        if os.path.exists(current_path):
            try:
                with open(current_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    topic = data.get("topic")
            except Exception:
                pass

    if not topic:
        topic = input("👉 Ingrese el tema para el video: ").strip() or "Tema General"

    reverse_analysis = load_reverse_analysis()

    ideas_res = generate_ideas_from_openrouter(
        topic=topic,
        reverse_analysis=reverse_analysis,
        model=model
    )

    if not ideas_res or not ideas_res.ideas:
        print("⚠️ No se pudieron generar opciones con la IA. Creando idea por defecto.")
        selected_idea = VideoIdea(
            id=1,
            titulo=topic,
            gancho_inicial=f"¿Conocías esto sobre {topic}?",
            resumen_premisa=f"Una mirada rápida al tema de {topic}.",
            remate_o_giro="Sorprendente pero cierto."
        )
    else:
        selected_idea = select_idea_interactive(ideas_res)

    output_payload = {
        "topic": topic,
        "selected_idea": selected_idea.model_dump()
    }

    # Guardar en output/selected_idea.json
    os.makedirs("output", exist_ok=True)
    selected_path = os.path.join("output", "selected_idea.json")
    with open(selected_path, "w", encoding="utf-8") as f:
        json.dump(output_payload, f, indent=2, ensure_ascii=False)

    # Si se pasó un directorio de proyecto, guardar también una copia allí
    if project_dir and os.path.exists(project_dir):
        project_idea_path = os.path.join(project_dir, "selected_idea.json")
        with open(project_idea_path, "w", encoding="utf-8") as f:
            json.dump(output_payload, f, indent=2, ensure_ascii=False)

    print(f"📄 Idea guardada en: '{selected_path}'\n")
    return output_payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generador de Ideas y Ángulos Virales")
    parser.add_argument("--topic", type=str, default=None, help="Tema del video")
    parser.add_argument("--model", type=str, default="google/gemini-3.7-flash", help="Modelo de OpenRouter")

    args = parser.parse_args()
    generate_ideas(topic=args.topic, model=args.model)