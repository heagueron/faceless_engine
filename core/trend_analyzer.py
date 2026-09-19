import os
import re
import json
import argparse
from datetime import datetime, timedelta
from typing import List, Optional, Tuple, Dict, Any
from dotenv import load_dotenv
import requests

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from googleapiclient.discovery import build
from pydantic import BaseModel, Field
from core.config import TARGET_LANGUAGE

load_dotenv()

LANGUAGE_NAMES = {
    "es": "SPANISH",
    "en": "ENGLISH",
    "pt": "PORTUGUESE"
}


class TrendVideo(BaseModel):
    video_id: str
    title: str
    channel_title: str
    published_at: str
    view_count: int
    daily_views_estimate: float = Field(description="Promedio de vistas diarias")
    video_url: str


class ReversePromptingAnalysis(BaseModel):
    gancho_inicial: str = Field(description="Análisis del gancho (0-3s).")
    estructura_narrativa: str = Field(description="Desglose del conflicto, desarrollo y remate.")
    estilo_visual_narrativo: str = Field(description="Ritmo de locución, tipo de gráficos, tono.")
    patron_retencion: str = Field(description="Recurso usado para mantener el interés.")
    areas_mejora: List[str] = Field(description="Oportunidades breves para superarlo.")


def extract_video_id(url_or_id: str) -> Optional[str]:
    """Extrae el ID de video de YouTube desde diversas estructuras de URL o texto plano."""
    patterns = [
        r'(?:v=|\/embed\/|\/v\/|youtu\.be\/|\/shorts\/)([0-9A-Za-z_-]{11})',
        r'([0-9A-Za-z_-]{11})'
    ]
    for pattern in patterns:
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)
    return None


def get_video_details(video_id: str) -> Optional[Dict[str, Any]]:
    """Consulta la API de YouTube para obtener metadatos detallados de un video específico."""
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        return None
    try:
        youtube = build("youtube", "v3", developerKey=api_key)
        response = youtube.videos().list(
            part="snippet,statistics",
            id=video_id
        ).execute()
        items = response.get("items", [])
        if items:
            snippet = items[0]["snippet"]
            stats = items[0].get("statistics", {})
            return {
                "video_id": video_id,
                "title": snippet.get("title", ""),
                "description": snippet.get("description", ""),
                "channel_title": snippet.get("channelTitle", ""),
                "tags": snippet.get("tags", []),
                "published_at": snippet.get("publishedAt", ""),
                "view_count": int(stats.get("viewCount", 0)),
                "like_count": int(stats.get("likeCount", 0)),
                "video_url": f"https://www.youtube.com/watch?v={video_id}"
            }
    except Exception as e:
        print(f"⚠️ No se pudieron obtener detalles completos desde YouTube API: {e}")
    return None


def analyze_video_reverse_prompting(
    video_url: str,
    title: Optional[str] = None,
    model: str = "google/gemini-3.7-flash",
    language: str = TARGET_LANGUAGE
) -> Optional[Dict[str, Any]]:
    """
    Realiza Ingeniería Inversa (Reverse Prompting) sobre un video de YouTube
    usando la API de Gemini vía OpenRouter con margen seguro de tokens y en el idioma objetivo.
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("⚠️ Advertencia: OPENROUTER_API_KEY no encontrada en las variables de entorno (.env).")
        return None

    video_id = extract_video_id(video_url)
    details = get_video_details(video_id) if video_id else None

    video_title = (details.get("title") if details else None) or title or "Video de referencia"
    channel_name = details.get("channel_title", "Desconocido") if details else "Desconocido"
    description = details.get("description", "")[:500] if details else ""
    tags = ", ".join(details.get("tags", []))[:200] if details else ""

    lang_name = LANGUAGE_NAMES.get(language.lower(), "SPANISH")
    print(f"\n🧠 Iniciando Ingeniería Inversa con {model} (Idioma: {language.upper()})...")
    print(f"   Video: '{video_title}' ({video_url})")

    system_instruction = (
        "Eres un analista experto de viralidad para YouTube Shorts.\n"
        f"REGLA ESTRICTA DE IDIOMA: Responde absolutamente todo el análisis en {lang_name}.\n"
        "REGLAS OBLIGATORIAS:\n"
        "1. Responde ÚNICAMENTE con un objeto JSON válido.\n"
        "2. NO incluyas saltos de línea ni comillas dobles dentro de los textos de cada campo.\n"
        "3. Sé conciso: máximo 20 palabras por campo.\n\n"
        "Esquema JSON requerido:\n"
        "{\n"
        f'  "gancho_inicial": "Frase/elemento para frenar el scroll (en {lang_name})",\n'
        f'  "estructura_narrativa": "Conflicto, desarrollo y remate (en {lang_name})",\n'
        f'  "estilo_visual_narrativo": "Ritmo, gráficos, tono (en {lang_name})",\n'
        f'  "patron_retencion": "Recurso clave de retención (en {lang_name})",\n'
        f'  "areas_mejora": ["Mejora 1", "Mejora 2"]\n'
        "}"
    )

    prompt = f"""
Ingeniería inversa para este video:
- Título: {video_title}
- Canal: {channel_name}
- Descripción: {description}
- Tags: {tags}
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
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=800,
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
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.2,
                "max_tokens": 800,
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

        analysis_dict = json.loads(clean_json_str)
        validated_analysis = ReversePromptingAnalysis.model_validate(analysis_dict)
        final_result = validated_analysis.model_dump()

        os.makedirs("output", exist_ok=True)
        analysis_path = os.path.join("output", "reverse_prompting_analysis.json")
        with open(analysis_path, "w", encoding="utf-8") as f:
            json.dump({
                "video_url": video_url,
                "title": video_title,
                "language": language,
                "analysis": final_result
            }, f, ensure_ascii=False, indent=2)

        display_reverse_prompting_summary(video_title, final_result)
        return final_result

    except json.JSONDecodeError as jde:
        print(f"❌ Error al parsear JSON devuelto por el modelo: {jde}")
        print(f"📄 Respuesta cruda recibida:\n{raw_content}")
        return None
    except Exception as e:
        print(f"❌ Error al realizar Ingeniería Inversa vía OpenRouter: {e}")
        return None


def display_reverse_prompting_summary(title: str, analysis: Dict[str, Any]):
    """Muestra en consola el resumen formateado de la ingeniería inversa."""
    print("\n" + "=" * 85)
    print(f" 🔬 RESULTADO DE INGENIERÍA INVERSA: '{title}'")
    print("=" * 85)
    print(f"🎣 Gancho Inicial (0-3s):\n   {analysis.get('gancho_inicial')}\n")
    print(f"🧱 Estructura Narrativa:\n   {analysis.get('estructura_narrativa')}\n")
    print(f"🎨 Estilo Visual y Narrativo:\n   {analysis.get('estilo_visual_narrativo')}\n")
    print(f"🧲 Patrón de Retención:\n   {analysis.get('patron_retencion')}\n")
    print("💡 Áreas de Mejora para Superar el Video:")
    for i, mejora in enumerate(analysis.get("areas_mejora", []), 1):
        print(f"   {i}. {mejora}")
    print("=" * 85 + "\n")


def fetch_niche_trends(
    query: str,
    max_results: int = 10,
    days_back: int = 30,
    language: str = TARGET_LANGUAGE,
    region_code: Optional[str] = None
) -> List[TrendVideo]:
    """
    Busca videos relevantes en YouTube publicados recientemente, ordenados por reproducciones diarias estimadas.
    """
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        print("\n⚠️ Advertencia: YOUTUBE_API_KEY no encontrada en .env.")
        return []

    try:
        youtube = build("youtube", "v3", developerKey=api_key)
        published_after = (datetime.utcnow() - timedelta(days=days_back)).isoformat() + "Z"

        print(f"\n🔍 Buscando tendencias en YouTube para: '{query}'")
        print(f"   Idioma: {language.upper()} | Últimos {days_back} días | Máx. resultados: {max_results}...\n")

        search_kwargs = {
            "q": query,
            "part": "id,snippet",
            "maxResults": max_results,
            "type": "video",
            "order": "viewCount",
            "publishedAfter": published_after,
            "relevanceLanguage": language,
        }
        
        if region_code:
            search_kwargs["regionCode"] = region_code

        search_response = youtube.search().list(**search_kwargs).execute()
        video_ids = [item["id"]["videoId"] for item in search_response.get("items", []) if "videoId" in item["id"]]

        if not video_ids:
            print("⚠️ No se encontraron videos en YouTube con esos criterios.")
            return []

        stats_response = youtube.videos().list(
            part="snippet,statistics",
            id=",".join(video_ids)
        ).execute()

        trends: List[TrendVideo] = []
        now = datetime.utcnow()

        for item in stats_response.get("items", []):
            snippet = item["snippet"]
            stats = item["statistics"]
            
            pub_date = datetime.strptime(snippet["publishedAt"], "%Y-%m-%dT%H:%M:%SZ")
            days_old = max((now - pub_date).days, 1)
            
            view_count = int(stats.get("viewCount", 0))
            daily_views = round(view_count / days_old, 2)

            trend = TrendVideo(
                video_id=item["id"],
                title=snippet["title"],
                channel_title=snippet["channelTitle"],
                published_at=snippet["publishedAt"],
                view_count=view_count,
                daily_views_estimate=daily_views,
                video_url=f"[https://www.youtube.com/watch?v=](https://www.youtube.com/watch?v=){item['id']}"
            )
            trends.append(trend)

        trends.sort(key=lambda x: x.daily_views_estimate, reverse=True)
        return trends

    except Exception as e:
        print(f"❌ Error al consultar YouTube API: {e}")
        return []


def display_trends_summary(trends: List[TrendVideo]):
    """Muestra la tabla de resultados de tendencias."""
    if not trends:
        return

    print("=" * 85)
    print(" 📈 TEMAS Y VIDEOS TENDENCIA ENCONTRADOS")
    print("=" * 85)
    for idx, t in enumerate(trends, 1):
        print(f"[{idx}] {t.title}")
        print(f"    Canal: {t.channel_title} | Vistas Totales: {t.view_count:,} | ~{t.daily_views_estimate:,.1f} vistas/día")
        print(f"    URL: {t.video_url}\n")
    print("=" * 85)


def get_selected_topic(default_lang: str = TARGET_LANGUAGE) -> Tuple[str, str]:
    """
    Función interactiva principal para el flujo del sistema.
    """
    print("\n" + "=" * 85)
    print(" 🔎 INVESTIGACIÓN DE NICHO Y TENDENCIAS EN YOUTUBE")
    print("=" * 85)
    
    query_input = input("👉 Ingrese el NICHO, TEMA o URL de YouTube a investigar: ").strip()
    
    if query_input.startswith("http://") or query_input.startswith("https://") or "youtube.com" in query_input or "youtu.be" in query_input:
        video_url = query_input
        video_id = extract_video_id(video_url)
        details = get_video_details(video_id) if video_id else None
        title = details.get("title") if details else ""
        if not title:
            title_in = input("✍️ Ingrese el título/tema para este video (opcional): ").strip()
            title = title_in if title_in else "Video de referencia"

        print(f"\n✔ URL detectada: {video_url}")
        print(f"✔ Tema: '{title}'")
        
        analyze_video_reverse_prompting(video_url=video_url, title=title, language=default_lang)
        return title, video_url

    if not query_input:
        print("⚠️ No ingresaste una consulta de búsqueda.")
        fallback = input("✍️ Ingrese directamente el título/tema para el video: ").strip()
        fallback_topic = fallback if fallback else "Consejos para mejorar tu productividad"
        custom_url = input("🔗 Ingrese la URL del video (opcional, ENTER para omitir): ").strip()
        if custom_url:
            analyze_video_reverse_prompting(video_url=custom_url, title=fallback_topic, language=default_lang)
        return fallback_topic, custom_url

    days_input = input("⏳ Días hacia atrás a analizar [por defecto 30]: ").strip()
    days = int(days_input) if days_input.isdigit() else 30

    lang_input = input(f"🌐 Idioma (es/en/pt) [por defecto '{default_lang}']: ").strip().lower()
    lang = lang_input if lang_input in ["es", "en", "pt"] else default_lang

    results = fetch_niche_trends(query=query_input, max_results=10, days_back=days, language=lang)
    
    if results:
        display_trends_summary(results)
        print("🛑 INTERVENCIÓN HUMANA:")
        choice = input("👉 Selecciona el número [1-N] del tema elegido O escribe un título/URL personalizado: ").strip()
        
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(results):
                selected = results[idx]
                print(f"\n✔ Tema seleccionado de YouTube: '{selected.title}'")
                print(f"✔ URL del video: '{selected.video_url}'")
                
                os.makedirs("output", exist_ok=True)
                output_file = os.path.join("output", "selected_trend.json")
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(selected.model_dump(), f, ensure_ascii=False, indent=2)
                
                analyze_video_reverse_prompting(video_url=selected.video_url, title=selected.title, language=lang)
                return selected.title, selected.video_url

        elif len(choice) > 0:
            if choice.startswith("http://") or choice.startswith("https://") or "youtube.com" in choice or "youtu.be" in choice:
                custom_url = choice
                custom_title = input("✍️ Ingrese el título/tema para este video (ENTER para usar el término buscado): ").strip()
                topic_result = custom_title if custom_title else query_input
            else:
                topic_result = choice
                custom_url = input("🔗 Ingrese la URL del video de referencia (opcional, ENTER para omitir): ").strip()

            print(f"\n✔ Tema personalizado: '{topic_result}'")
            if custom_url:
                print(f"✔ URL ingresada: '{custom_url}'")
                analyze_video_reverse_prompting(video_url=custom_url, title=topic_result, language=lang)

            os.makedirs("output", exist_ok=True)
            output_file = os.path.join("output", "selected_trend.json")
            trend_data = {
                "video_id": extract_video_id(custom_url) or "",
                "title": topic_result,
                "channel_title": "",
                "published_at": datetime.utcnow().isoformat(),
                "view_count": 0,
                "daily_views_estimate": 0.0,
                "video_url": custom_url
            }
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(trend_data, f, ensure_ascii=False, indent=2)

            return topic_result, custom_url

    print("\n✍️ Ingrese un título personalizado o presione ENTER para usar el término buscado:")
    custom_title = input(f"👉 [{query_input}]: ").strip()
    topic_result = custom_title if custom_title else query_input
    custom_url = input("🔗 Ingrese la URL del video (opcional, ENTER para omitir): ").strip()

    if custom_url:
        analyze_video_reverse_prompting(video_url=custom_url, title=topic_result, language=lang)

    os.makedirs("output", exist_ok=True)
    output_file = os.path.join("output", "selected_trend.json")
    trend_data = {
        "video_id": extract_video_id(custom_url) or "",
        "title": topic_result,
        "channel_title": "",
        "published_at": datetime.utcnow().isoformat(),
        "view_count": 0,
        "daily_views_estimate": 0.0,
        "video_url": custom_url
    }
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(trend_data, f, ensure_ascii=False, indent=2)

    return topic_result, custom_url


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analizador de Tendencias e Ingeniería Inversa de YouTube para Faceless Engine")
    parser.add_argument("--query", type=str, help="Término o tema de búsqueda")
    parser.add_argument("--url", type=str, help="URL de video individual para análisis por Ingeniería Inversa")
    parser.add_argument("--days", type=int, default=30, help="Días hacia atrás")
    parser.add_argument("--lang", type=str, default=TARGET_LANGUAGE, help="Código de idioma (es, en, pt)")
    parser.add_argument("--model", type=str, default="google/gemini-3.7-flash", help="Modelo de Gemini en OpenRouter")
    
    args = parser.parse_args()

    if args.url:
        analyze_video_reverse_prompting(video_url=args.url, model=args.model, language=args.lang)
    elif args.query:
        trends = fetch_niche_trends(query=args.query, max_results=10, days_back=args.days, language=args.lang)
        display_trends_summary(trends)
    else:
        topic, video_url = get_selected_topic(default_lang=args.lang)
        print(f"\n🎯 Tema final seleccionado: '{topic}'")
        print(f"🔗 URL seleccionada / ingresada: '{video_url}'")