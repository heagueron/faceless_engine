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
    max_results: int = 15,
    days_back: int = 30,
    language: str = "es",
    region_code: Optional[str] = None
) -> List[TrendVideo]:
    """
    Busca videos relevantes en YouTube publicados recientemente, ordenados por vistas.
    """
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        raise ValueError("Error: YOUTUBE_API_KEY no encontrada en las variables de entorno (.env).")

    youtube = build("youtube", "v3", developerKey=api_key)

    published_after = (datetime.utcnow() - timedelta(days=days_back)).isoformat() + "Z"

    print(f"\n Buscando tendencias para: '{query}'")
    print(f" Idioma: {language.upper()} | Últimos {days_back} días | Máx. resultados: {max_results}...\n")

    # Parámetros de búsqueda
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
        print(" No se encontraron videos con esos criterios.")
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


def display_trends_summary(trends: List[TrendVideo]):
    """Muestra la tabla de resultados de tendencias para la intervención humana."""
    if not trends:
        return

    print("=" * 85)
    print(" TEMAS Y VIDEOS TENDENCIA ENCONTRADOS")
    print("=" * 85)
    for idx, t in enumerate(trends, 1):
        print(f"[{idx}] {t.title}")
        print(f"    Canal: {t.channel_title} | Vistas Totales: {t.view_count:,} | ~{t.daily_views_estimate:,.1f} vistas/día")
        print(f"    URL: {t.video_url}\n")
    print("=" * 85)


def run_interactive_selection():
    """Modo interactivo en consola para ingresar búsqueda y seleccionar un tema."""
    print("\n--- ANALIZADOR DE TENDENCIAS (HUMAN-IN-THE-LOOP) ---")
    query_input = input(" Ingrese la frase/tema a investigar (ej: 'finanzas personales errores'): ").strip()
    
    if not query_input:
        print(" Búsqueda cancelada: No ingresaste ninguna consulta.")
        return None

    days_input = input(" Días hacia atrás a analizar [por defecto 30]: ").strip()
    days = int(days_input) if days_input.isdigit() else 30

    lang_input = input(" Idioma (es/en) [por defecto 'es']: ").strip().lower()
    lang = lang_input if lang_input in ["es", "en"] else "es"

    results = fetch_niche_trends(query=query_input, max_results=10, days_back=days, language=lang)
    
    if results:
        display_trends_summary(results)
        print("🛑 INTERVENCIÓN HUMANA:")
        choice = input(" Seleccione el número [1-N] del tema elegido (o Presione ENTER para omitir): ").strip()
        
        if choice.isdigit() and 1 <= int(choice) <= len(results):
            selected = results[int(choice) - 1]
            print(f"\n Tema seleccionado exitosamente:\n 👉 '{selected.title}'")
            
            # Guardar el tema seleccionado en un archivo JSON de intercambio
            os.makedirs("output", exist_ok=True)
            output_file = os.path.join("output", "selected_trend.json")
            
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(selected.model_dump(), f, ensure_ascii=False, indent=2)
                
            print(f" Saved: Tema guardado en '{output_file}' para alimentar a script_generator.py\n")
            return selected
    return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analizador de Tendencias de YouTube para Faceless Engine")
    parser.add_argument("--query", type=str, help="Término o tema de búsqueda")
    parser.add_argument("--days", type=int, default=30, help="Días hacia atrás")
    parser.add_argument("--lang", type=str, default="es", help="Código de idioma (es, en)")
    
    args = parser.parse_args()

    if args.query:
        # Ejecución por argumentos CLI
        trends = fetch_niche_trends(query=args.query, max_results=10, days_back=args.days, language=args.lang)
        display_trends_summary(trends)
    else:
        # Ejecución interactiva
        run_interactive_selection()