# Faceless Engine - Guía del Proyecto

## Objetivo
Motor de automatización para generar videos educativos y de entretenimiento usando IA (Gemini, Pollinations, MoviePy).

## Arquitectura y Módulos
- `main.py`: Orquestador principal del pipeline.
- `core/trend_analyzer.py`: Investigación de tendencias en YouTube.
- `core/script_generator.py`: Generación de guiones en JSON usando Gemini.
- `core/voice_generator.py`: Síntesis de voz (TTS) para cada escena.
- `core/media_fetcher.py`: Descarga y generación de imágenes (estilo 2D stick figure / cartoon).
- `core/video_composer.py`: Renderizado final MP4 con animación Ken Burns.

## Reglas de Código
- Mantener nombres de carpeta en formato ASCII estricto (sin acentos).
- Manejar siempre excepciones y reintentos en llamadas a APIs externas.