import os
import json
import argparse
from datetime import datetime, timedelta
from typing import List, Optional
from dotenv import load_dotenv
from googleapiclient.discovery import build
from pydantic import BaseModel, Field

load_dotenv()


class TrendVideo(BaseModel):
    video_id: str
    title: str
    channel_title: str
    published_at: str
    view_count: int
    daily_views_estimate: float = Field(description="Promedio de vistas diarias")
    video_url: str


def fetch_niche_trends(
    query: str,
    max_results: int = 10,
    days_back: int = 30,
    language: str = "es",
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

        # Consultar estadísticas exactas de reproducciones
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
                video_url=f"https://www.youtube.com/watch?v={item['id']}"
            )
            trends.append(trend)

        # Ordenar por reproducciones diarias estimadas
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


def get_selected_topic() -> str:
    """
    Función interactiva principal para main.py:
    1. Solicita el nicho/palabra clave a investigar.
    2. Consulta YouTube y muestra las estadísticas.
    3. Permite elegir un título de la lista o ingresar uno personalizado.
    """
    print("\n" + "=" * 85)
    print(" 🔎 INVESTIGACIÓN DE NICHO Y TENDENCIAS EN YOUTUBE")
    print("=" * 85)
    
    query_input = input("👉 Ingrese el NICHO o TEMA a investigar (ej: 'finanzas personales', 'productividad'): ").strip()
    
    if not query_input:
        print("⚠️ No ingresaste una consulta de búsqueda.")
        fallback = input("✍️ Ingrese directamente el título/tema para el video: ").strip()
        return fallback if fallback else "Consejos para mejorar tu productividad"

    days_input = input("⏳ Días hacia atrás a analizar [por defecto 30]: ").strip()
    days = int(days_input) if days_input.isdigit() else 30

    lang_input = input("🌐 Idioma (es/en) [por defecto 'es']: ").strip().lower()
    lang = lang_input if lang_input in ["es", "en"] else "es"

    results = fetch_niche_trends(query=query_input, max_results=10, days_back=days, language=lang)
    
    if results:
        display_trends_summary(results)
        print("🛑 INTERVENCIÓN HUMANA:")
        choice = input("👉 Selecciona el número [1-N] del tema elegido O escribe un título personalizado: ").strip()
        
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(results):
                selected = results[idx]
                print(f"\n✔ Tema seleccionado de YouTube: '{selected.title}'")
                
                # Guardar el tema en archivo de intercambio
                os.makedirs("output", exist_ok=True)
                output_file = os.path.join("output", "selected_trend.json")
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(selected.model_dump(), f, ensure_ascii=False, indent=2)
                
                return selected.title
        elif len(choice) > 0:
            print(f"\n✔ Tema personalizado ingresado: '{choice}'")
            return choice

    print("\n✍️ Ingrese un título personalizado o presione ENTER para usar el término buscado:")
    custom_title = input(f"👉 [{query_input}]: ").strip()
    return custom_title if custom_title else query_input


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analizador de Tendencias de YouTube para Faceless Engine")
    parser.add_argument("--query", type=str, help="Término o tema de búsqueda")
    parser.add_argument("--days", type=int, default=30, help="Días hacia atrás")
    parser.add_argument("--lang", type=str, default="es", help="Código de idioma (es, en)")
    
    args = parser.parse_args()

    if args.query:
        trends = fetch_niche_trends(query=args.query, max_results=10, days_back=args.days, language=args.lang)
        display_trends_summary(trends)
    else:
        topic = get_selected_topic()
        print(f"\n🎯 Tema final seleccionado: '{topic}'")