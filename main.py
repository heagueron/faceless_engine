import sys
import time
import os

# Importación de los 5 módulos de la tubería
from core.trend_analyzer import fetch_niche_trends, display_trends_summary
from core.script_generator import generate_faceless_script, get_user_topic_selection
from core.voice_generator import process_script_audio
from core.media_fetcher import process_scene_media
from core.video_composer import assemble_final_video


def run_pipeline():
    """
    Orquestador principal del motor de creación de videos (MVP).
    Ejecuta en secuencia:
    [ trend_analyzer ] ➔ [ script_generator ] ➔ [ voice_generator ] ➔ [ media_fetcher ] ➔ [ video_composer ]
    """
    print("\n" + "=" * 80)
    print("🚀 FACELESS ENGINE - INICIANDO PIPELINE DE CREACIÓN DE VIDEO")
    print("=" * 80)

    # -------------------------------------------------------------------------
    # PASO 0: BÚSQUEDA Y ANÁLISIS DE TENDENCIAS (YouTube Data API)
    # -------------------------------------------------------------------------
    print("\n[ PASO 0/4 ] Analizando tendencias en YouTube...")
    search_query = input("👉 Ingresa el nicho o tema a buscar en YouTube (Ej: 'finanzas personales'): ").strip()
    if not search_query:
        search_query = "finanzas personales"
        print(f"   Buscando término por defecto: '{search_query}'")

    try:
        raw_trends = fetch_niche_trends(query=search_query, max_results=10)
        display_trends_summary(raw_trends)
        
        # Extraer únicamente los títulos de los videos de la lista de objetos TrendVideo
        trend_titles = [video.title for video in raw_trends]
    except Exception as e:
        print(f"⚠️ No se pudieron obtener tendencias en vivo ({e}). Usando lista de respaldo.")
        trend_titles = [
            "Cómo Romper los Hábitos que te Hacen Pobre y Construir Riqueza | Brian Tracy",
            "5 Reglas de Oro para Gestionar tu Dinero en 2026",
            "Por qué la Clase Media se Queda Atrapada en la Carrera de Ratas"
        ]

    # Intervención Humana: Selección por número o texto personalizado
    selected_topic = get_user_topic_selection(trend_titles)

    start_time = time.time()

    # -------------------------------------------------------------------------
    # PASO 1: GENERACIÓN DE GUION (Gemini API con Fallback)
    # -------------------------------------------------------------------------
    print("\n[ PASO 1/4 ] Generando Guion con Gemini API...")
    script_manifest = generate_faceless_script(
        topic=selected_topic,
        target_duration=15,
        primary_model="models/gemini-3.7-flash"
    )

    os.makedirs("output", exist_ok=True)
    with open(os.path.join("output", "script_manifest.json"), "w", encoding="utf-8") as f:
        f.write(script_manifest.model_dump_json(indent=2))

    # -------------------------------------------------------------------------
    # PASO 2: GENERACIÓN DE VOZ Y DURAClONES (gTTS + Mutagen)
    # -------------------------------------------------------------------------
    print("\n[ PASO 2/4 ] Generando Audios y Calculando Metadatos (TTS)...")
    process_script_audio()

    # -------------------------------------------------------------------------
    # PASO 3: DESCARGA DE RECURSOS VISUALES (Media Fetcher)
    # -------------------------------------------------------------------------
    print("\n[ PASO 3/4 ] Descargando Recursos Visuales por Escena...")
    process_scene_media()

    # -------------------------------------------------------------------------
    # PASO 4: ENSAMBLADO Y RENDERIZADO DEL VIDEO (MoviePy MP4)
    # -------------------------------------------------------------------------
    print("\n[ PASO 4/4 ] Renderizando Video Final MP4 (9:16)...")
    assemble_final_video()

    total_time = round(time.time() - start_time, 2)

    print("\n" + "=" * 80)
    print(" ¡PROCESO COMPLETO FINALIZADO EXITOSAMENTE!")
    print(f"⏱  Tiempo total de procesamiento: {total_time} segundos")
    print("📁 Video final generado en: output/renders/final_short.mp4")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    try:
        run_pipeline()
    except KeyboardInterrupt:
        print("\n\n⚠️ Proceso interrumpido por el usuario.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error crítico en el pipeline: {e}")
        sys.exit(1)