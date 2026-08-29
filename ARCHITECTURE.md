# Faceless Engine - Guía del Proyecto

## Objetivo
Motor de automatización integral para la producción de videos cortos sin rostro (Shorts, Reels, TikTok) educativos y de entretenimiento, utilizando IA para análisis de tendencias, ideación viral, guionado, locución neural, generación visual y renderizado animado.

## Arquitectura y Módulos
- `main.py`: Orquestador principal del pipeline automatizado de 5 pasos.
- `core/trend_analyzer.py`: Investigación de tendencias en YouTube y análisis de ingeniería inversa (Reverse Prompting) con Gemini vía OpenRouter.
- `core/ideas.py`: Generación de 3 ángulos virales (gancho, premisa, remate) con selección interactiva en consola.
- `core/script_generator.py`: Generación de guiones estructurados en JSON (`manifest.json`) enfocados en animaciones 2D minimalistas.
- `core/voice_generator.py`: Síntesis de voz neural (TTS) en formato MP3 por escena utilizando Microsoft Edge TTS (`edge-tts`).
- `core/media_fetcher.py`: Generación de ilustraciones vectoriales estilo 2D stick figure a través de OpenRouter (`google/gemini-3.1-flash-image`).
- `core/video_composer.py`: Ensamblado y renderizado final en formato MP3/MP4 (9:16 vertical) con efectos de movimiento Ken Burns mediante MoviePy.

## Flujo del Pipeline (5 Pasos)
1. **Tendencias e Ingeniería Inversa (`trend_analyzer.py`):** Selección de tema y extracción de patrones de retención de YouTube.
2. **Ángulos Virales (`ideas.py`):** Elección interactiva entre 3 propuestas creativas antes de redactar el guion.
3. **Guion Estructurado (`script_generator.py`):** Creación del manifiesto del proyecto con descripciones visuales e instrucciones de locución.
4. **Locución Neural (`voice_generator.py`):** Generación de audios por escena y cálculo de tiempos precisos.
5. **Recursos Visuales (`media_fetcher.py`):** Creación de imágenes vectoriales adaptadas a cada escena.
6. **Composición y Render (`video_composer.py`):** Edición final con animación Ken Burns y sincronización audio-imagen.

## Reglas de Código y Convenciones
- Nombres de carpetas y archivos en formato ASCII estricto (slugify sin acentos ni caracteres especiales).
- Control centralizado del proyecto activo mediante `output/current_project.json`.
- Validación de esquemas de datos con Pydantic.
- Sanitización estricta de parámetros en llamados a APIs externas y manejo de reintentos con `try/except`.