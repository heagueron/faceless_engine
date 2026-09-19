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
from core.config import TARGET_LANGUAGE

load_dotenv()

# Mapeo de nombres de idioma para prompts de la IA
LANGUAGE_NAMES = {
    "es": "SPANISH",
    "en": "ENGLISH",
    "pt": "PORTUGUESE"
}


# --- ESQUEMAS DE DATOS (PYDANTIC) ---

class VideoIdea(BaseModel):
    id: int = Field(description="Número de la opción (1, 2, 3, 4, 5...)")
    titulo: str = Field(description="Título sugerido, atractivo y corto para el Short")
    gancho_inicial: str = Field(description="Gancho de los primeros 0-3 segundos para capturar la atención")
    resumen_premisa: str = Field(description="Desarrollo o historia principal sintetizada en 2 oraciones")
    remate_o_giro: str = Field(description="Conclusión impactante, llamada a la acción o giro final")


class IdeasResponse(BaseModel):
    topic: str = Field(description="Tema general de la consulta")
    ideas: List[VideoIdea] = Field(description="Lista de 5 propuestas de ángulos virales")


# --- CARGA DE ANÁLISIS PREVIO ---

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


# --- GENERADOR DE IDEAS VÍA OPENROUTER ---

def generate_ideas_from_openrouter(
    topic: str,
    reverse_analysis: Optional[Dict[str, Any]] = None,
    model: str = "google/gemini-3.7-flash",
    language: str = TARGET_LANGUAGE
) -> Optional[IdeasResponse]:
    """Genera 5 propuestas de ángulos de video mediante OpenRouter en el idioma objetivo."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("❌ Error: OPENROUTER_API_KEY no encontrada en .env")
        return None

    lang_name = LANGUAGE_NAMES.get(language.lower(), "SPANISH")
    print(f"\n🧠 Ideando ángulos virales para '{topic}' (idioma: {language.upper()}) usando {model}...")

    style_guidelines = ""
    if reverse_analysis:
        style_guidelines = (
            f"- Estilo detectado: {reverse_analysis.get('estilo_visual_narrativo', 'Educativo dinámico')}\n"
            f"- Retención basada en: {reverse_analysis.get('patron_retencion', 'Ganchos fuertes y alto ritmo')}\n"
        )

    system_instruction = f"""
Eres un estratega de contenido experto en YouTube Shorts, Reels y TikTok.
Tu objetivo es proponer 5 ángulos virales distintos y altamente atractivos basados en el tema proporcionado.
Cada opción debe incluir un gancho inicial irresistible (primeros 3 segundos), un resumen rápido de la premisa y un remate final memorable.

REGLA ESTRICTA DE IDIOMA:
Todas las propuestas (titulo, gancho_inicial, resumen_premisa, remate_o_giro) DEBEN estar escritas estrictamente en {lang_name}.

Responde EXCLUSIVAMENTE en JSON que cumpla el esquema requerido:
{{
  "topic": "Tema general",
  "ideas": [
    {{
      "id": 1,
      "titulo": "Título corto y magnético en {lang_name}",
      "gancho_inicial": "Pregunta o afirmación chocante en {lang_name}",
      "resumen_premisa": "Desarrollo rápido del tema en 2 frases en {lang_name}",
      "remate_o_giro": "Conclusión impactante o reflexión final en {lang_name}"
    }}
  ]
}}
"""

    user_prompt = f"""
Tema principal: {topic}
{style_guidelines}

Genera 5 propuestas de ideas con enfoques dramáticos, educativos, contraintuitivos o curiosos para capturar el máximo de retención.
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
                max_tokens=2500,
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
                "max_tokens": 2500,
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


# --- SELECCIÓN E INTERACCIÓN ---

def _prompt_custom_idea(default_topic: str) -> VideoIdea:
    """Permite crear o ingresar manualmente una idea personalizada."""
    print("\n✏️  MODO IDEA PERSONALIZADA")
    titulo = input(f"   • Título [{default_topic}]: ").strip() or default_topic
    gancho = input("   • Gancho inicial (0-3s): ").strip() or f"¿Conocías esto sobre {default_topic}?"
    premisa = input("   • Resumen de premisa: ").strip() or f"Desarrollo sobre {default_topic}."
    remate = input("   • Remate o giro final: ").strip() or "Un dato imperdible."

    return VideoIdea(
        id=0,
        titulo=titulo,
        gancho_inicial=gancho,
        resumen_premisa=premisa,
        remate_o_giro=remate
    )


def select_idea_interactive(ideas_res: IdeasResponse) -> VideoIdea:
    """Muestra las 5 opciones en consola y permite elegir una, combinar varias o crear una personalizada."""
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
    print("Opciones de selección:")
    print("  • Número único (ej. '1' o '5') -> Selecciona esa idea.")
    print("  • Combinación (ej. '1,3' o '1+4+5') -> Fusiona las ideas seleccionadas.")
    print("  • '0' o 'c' -> Ingresar o editar una idea personalizada.")
    print("=" * 85)

    while True:
        choice = input(f"👉 Selección [1-{len(ideas)}, combinación o 0] (ENTER para opción 1): ").strip().lower()

        if choice == "":
            selected = ideas[0]
            break

        if choice in ["0", "c", "custom"]:
            selected = _prompt_custom_idea(ideas_res.topic)
            break

        # Extraer índices de la entrada (soporta comas, signos más o espacios)
        indices = [int(n) for n in re.split(r'[,+\s]+', choice) if n.isdigit()]
        valid_indices = [idx for idx in indices if 1 <= idx <= len(ideas)]

        if not valid_indices:
            print("⚠️ Selección inválida. Ingrese un número válido, combinación o '0'.")
            continue

        # Selección única
        if len(valid_indices) == 1:
            selected = ideas[valid_indices[0] - 1]
            break

        # Combinación de múltiples opciones
        selected_ideas = [ideas[i - 1] for i in valid_indices]
        print(f"\n🔀 Combinando opciones: {', '.join(f'#{i}' for i in valid_indices)}...")

        combined_titulo = " / ".join([i.titulo for i in selected_ideas])
        combined_gancho = " ".join([i.gancho_inicial for i in selected_ideas])
        combined_premisa = " ".join([i.resumen_premisa for i in selected_ideas])
        combined_remate = " ".join([i.remate_o_giro for i in selected_ideas])

        print("\n--- IDEA FUSIONADA DRAFT ---")
        print(f"📌 Título:  {combined_titulo}")
        print(f"🎣 Gancho:  {combined_gancho}")
        print(f"📖 Premisa: {combined_premisa}")
        print(f"💥 Remate:  {combined_remate}")
        print("---------------------------")

        confirm = input("¿Deseas usar esta combinación tal cual [S], editarla [E] o reintentar [N]? ").strip().lower()
        if confirm in ["s", "si", "yes", "y", ""]:
            selected = VideoIdea(
                id=99,
                titulo=combined_titulo,
                gancho_inicial=combined_gancho,
                resumen_premisa=combined_premisa,
                remate_o_giro=combined_remate
            )
            break
        elif confirm in ["e", "editar"]:
            print("\n✏️  Edición de la combinación:")
            edit_titulo = input(f"   • Título [{combined_titulo}]: ").strip() or combined_titulo
            edit_gancho = input(f"   • Gancho [{combined_gancho}]: ").strip() or combined_gancho
            edit_premisa = input(f"   • Premisa [{combined_premisa}]: ").strip() or combined_premisa
            edit_remate = input(f"   • Remate [{combined_remate}]: ").strip() or combined_remate

            selected = VideoIdea(
                id=99,
                titulo=edit_titulo,
                gancho_inicial=edit_gancho,
                resumen_premisa=edit_premisa,
                remate_o_giro=edit_remate
            )
            break

    print(f"\n✔ Ángulo seleccionado: '{selected.titulo}'")
    return selected


# --- FUNCIÓN PRINCIPAL DE INTEGRACIÓN ---

def generate_ideas(
    topic: Optional[str] = None,
    project_dir: Optional[str] = None,
    model: str = "google/gemini-3.7-flash",
    language: str = TARGET_LANGUAGE
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
        model=model,
        language=language
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
        "language": language,
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
    parser.add_argument("--lang", type=str, default=TARGET_LANGUAGE, help="Idioma objetivo (es, en, pt)")

    args = parser.parse_args()
    generate_ideas(topic=args.topic, model=args.model, language=args.lang)