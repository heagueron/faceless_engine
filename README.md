PROYECTO: faceless_engine

Propósito
Motor en Python para la creación automatizada de videos cortos en formato vertical (9:16) destinados a YouTube Shorts, TikTok y Reels. Cubre todo el ciclo: desde el análisis de tendencias en YouTube hasta la generación de guion por IA, síntesis de voz, obtención de imágenes y renderizado final en .mp4.

Flujo de Trabajo (Pipeline Principal)

PASO 0: core/trend_analyzer.py -> Consulta la API de YouTube para identificar temas virales dentro de un nicho.


PASO 1: core/script_generator.py -> Solicita a la API de Google Gemini un guion estructurado en JSON.


PASO 2: core/voice_generator.py -> Genera audios .mp3 con gTTS y mide duraciones exactas con mutagen.


PASO 3: core/media_fetcher.py -> Descarga imágenes verticales (9:16) basadas en prompts de cada escena.


PASO 4: core/video_composer.py -> Sincroniza audio, imagen y duraciones con MoviePy para exportar el archivo .mp4.


Descripción de Archivos y Funcionalidades

main.py
Punto de entrada ejecutable CLI (python main.py). Coordina la ejecución secuencial de los 5 módulos del pipeline, gestiona la captura de entradas del usuario, controla el flujo y maneja errores globales.


core/trend_analyzer.py
Modulo de búsqueda de contenido en YouTube Data API. Incluye fetch_niche_trends para consultar videos recientes en un nicho ordenados por relevancia, y display_trends_summary para imprimir en consola los títulos, canales y métricas de vistas encontradas.


core/script_generator.py
Módulo de generación de guiones mediante la API de Google Gemini. Utiliza modelos Pydantic (Scene, ScriptManifest) para garantizar una estructura JSON estricta. Permite al usuario seleccionar la tendencia deseada (get_user_topic_selection) y genera 3 a 4 escenas con locución en español (narration_text) y descripción visual en inglés (visual_prompt). Produce el archivo script_manifest.json.


core/voice_generator.py
Módulo de síntesis de voz (TTS). Convierte el texto de locución de cada escena a audio con gTTS (generate_scene_audio) y calcula la duración exacta del audio usando mutagen.mp3. Guarda los audios en output/audio/scene_X.mp3 y actualiza las duraciones en script_manifest_with_audio.json.


core/media_fetcher.py
Módulo para la recolección de recursos visuales. Extrae palabras clave de los visual_prompt de cada escena (extract_keywords) y descarga imágenes en formato vertical (1080x1920) acordes al contexto (download_image_from_source). Almacena los archivos en output/images/scene_X.jpg y genera script_manifest_complete.json.


core/video_composer.py
Módulo de edición y renderizado. Toma el manifiesto completo y utiliza MoviePy (assemble_final_video) para acoplar la imagen estática (ImageClip) con su respectivo audio (AudioFileClip) ajustando la duración exacta por escena. Concatena el conjunto de clips y exporta el video final vertical a 30fps (output/renders/final_short.mp4).


Ciclo de Vida del Manifiesto JSON (script_manifest.json)

Fase 1 (Guion): Contiene título, tema, duración objetivo y la lista de escenas con narration_text y visual_prompt.


Fase 2 (Audio): Incorpora por escena la ruta del archivo audio_file y su duración en segundos audio_duration_seconds.


Fase 3 (Imágenes): Asigna a cada escena la ruta local de la imagen descargada image_file.


Fase 4 (Render): Es consumido como referencia final por MoviePy para construir el montaje del archivo .mp4.
