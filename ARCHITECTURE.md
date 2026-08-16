Documento de Diseño Global 
(Software Design Document - SDD)

Proyecto: FacelessEngine 
(Pipeline Semi-Automatizado de Producción de Video)
Versión: 1.0.0

Fecha: Agosto 2026

Estado: Especificación de Arquitectura (Pre-Desarrollo)

1. Resumen Ejecutivo y Objetivos
FacelessEngine es un sistema modular desarrollado en Python diseñado para automatizar el 80% de las tareas operativas de creación, edición y preparación de contenido en formato faceless para plataformas de video (YouTube, TikTok, Instagram Reels).

Objetivos Principales:

Eficiencia Operativa: Reducir el tiempo de creación por video a un máximo de 30 a 45 minutos de atención humana.

Cumplimiento de Políticas: Incorporar puntos explícitos de supervisión (Human-in-the-Loop) para garantizar la originalidad del contenido y cumplir con las políticas de contenido de YouTube.

Arquitectura Multicanal: Permitir la gestión de múltiples canales/nichos desacoplando el código del contenido mediante archivos de configuración.

2. Arquitectura General del Sistema
El sistema opera bajo un modelo de Pipeline Modular por Fases. Cada fase es autónoma, lee datos de la fase anterior a través de esquemas JSON estrictos y guarda sus resultados en el sistema de archivos local.

[ 01. Trend Analyzer ]
          │ (JSON: Topic & Keywords)
          ▼
[ 02. Script Generator (Claude API) ] ──> [ 🛑 HUMAN CHECK 1: Guion & Hooks ]
          │ (JSON: Structured Script)
          ▼
[ 03. Voice Engine (ElevenLabs API) ]
          │ (MP3 + Timestamps)
          ▼
[ 04. Asset Collector (Pexels / Flux API) ] ──> [ 🛑 HUMAN CHECK 2: Curaduría Visual ]
          │ (Media Files: MP4 / JPG)
          ▼
[ 05. Render Engine (MoviePy / FFmpeg) ]
          │ (Final MP4 + SRT Subtitles)
          ▼
[ 06. Uploader (YouTube Data API) ] ──> [ 🛑 HUMAN CHECK 3: Miniatura & Release ]


3. Especificación Modular del Pipeline

Módulo 1: trend_analyzer

Función: Consultar fuentes de tendencias y seleccionar un tema de alto interés.

Entradas: Configuración del canal (palabras clave del nicho).

Salida: topic_data.json (Tema seleccionado, ángulo narrativo, palabras clave).

Herramientas: YouTube Data API v3, Google Trends API / PyTrends.


Módulo 2: script_generator

Función: Transformar el tema en un guion estructurado segundo a segundo optimizado para la retención.

Entradas: topic_data.json, channel_config.json (System Prompt con tono del canal).

Salida: script_manifest.json.

Herramientas: Anthropic API (claude-3-5-sonnet).

🛑 Human Check 1: Edición rápida del guion para eliminar clichés de IA, ajustar ganchos (hooks) y dar aprobación.


Módulo 3: voice_engine

Función: Convertir el texto del guion validado en un archivo de audio hiperrealista con marcas de tiempo.

Entradas: script_manifest.json (sección de locución).

Salida: narration.mp3 y alineación temporal de palabras/oraciones.

Herramientas: ElevenLabs API (o OpenAI TTS API).


Módulo 4: asset_collector

Función: Obtener los recursos visuales (clips de stock e imágenes generadas) requeridos para cada bloque del guion.

Entradas: script_manifest.json (prompts de imágenes y palabras clave de búsqueda).

Salida: Carpeta local /assets/ con archivos organizados cronológicamente (scene_01.jpg, scene_02.mp4).

Herramientas: Pexels API, Replicate API (Flux.1) / Midjourney.

🛑 Human Check 2: Previsualización rápida de la galería de medios. Reemplazo manual de 2-3 archivos que no cumplan con la calidad deseada.


Módulo 5: render_engine

Función: Ensamblar audio, video/imágenes, transiciones, efecto Ken Burns (zoom progresivo) y subtítulos dinámicos en un archivo de video único.

Entradas: narration.mp3, carpeta /assets/, script_manifest.json.

Salida: master_video.mp4 (16:9) y opcionalmente short_version.mp4 (9:16).

Herramientas: Python (moviepy, ffmpeg-python), FFmpeg CLI.


Módulo 6: uploader_and_analytics

Función: Subir el video a la plataforma objetivo en estado borrador o privado y preparar los metadatos SEO.

Entradas: master_video.mp4, script_manifest.json (título, descripción, tags sugeridos).

Salida: Video cargado en YouTube Creator Studio.

Herramientas: YouTube Data API v3.

🛑 Human Check 3: Carga de la miniatura personalizada (diseñada previamente), verificación del indicador de contenido sintético/IA y programación de la fecha/hora de publicación.


4. Estructura del Proyecto y Definición de Datos

Estructura de Directorios Sugerida:

faceless_engine/
├── config/
│   ├── global_settings.json       # API Keys y rutas globales
│   └── channels/
│       ├── finanzas_us.json       # Configuración específica Canal 1
│       └── saas_tech.json         # Configuración específica Canal 2
├── core/
│   ├── __init__.py
│   ├── trend_analyzer.py
│   ├── script_generator.py
│   ├── voice_engine.py
│   ├── asset_collector.py
│   ├── render_engine.py
│   └── uploader.py
├── projects/                      # Generado dinámicamente por proyecto
│   └── PROJECT_20260814_001/
│       ├── script_manifest.json
│       ├── narration.mp3
│       ├── assets/
│       ├── subtitles.srt
│       └── output/
│           └── final_video.mp4
├── utils/
│   ├── ffmpeg_helpers.py
│   └── logger.py
├── .env
├── main.py                        # Orquestador principal CLI
└── requirements.txt


Contrato de Datos Fundamental (script_manifest.json)
Este es el esquema que servirá como fuente de verdad para todo el pipeline:

JSON
{
  "project_id": "PROJECT_20260814_001",
  "channel_id": "finanzas_us",
  "meta": {
    "title_suggestions": ["How to Invest $1,000 in 2026", "The 2026 Passive Income Guide"],
    "description": "In this video we analyze...",
    "tags": ["finance", "investing", "2026"]
  },
  "timeline": [
    {
      "scene_id": 1,
      "duration_seconds": 5,
      "narration_text": "If you have $1,000 sitting in a bank account today, you are losing money every single hour.",
      "visual_prompt": "High concept cinematic shot of money burning slowly on a dark table",
      "stock_keywords": ["money bank inflation"],
      "asset_file": "assets/scene_01.png",
      "transition_in": "fade"
    },
    {
      "scene_id": 2,
      "duration_seconds": 7,
      "narration_text": "Here is the exact strategy smart investors are using this year to beat inflation.",
      "visual_prompt": "Futuristic financial chart going up, dark clean aesthetic",
      "stock_keywords": ["stock market graph green"],
      "asset_file": "assets/scene_02.mp4",
      "transition_in": "crossfade"
    }
  ]
}



5. Especificaciones Técnicas y Requisitos del Entorno
Lenguaje: Python 3.11+.

Entorno de Desarrollo: VS Code en entorno Linux (Debian / Crostini) o WSL2.

Sistemas/Herramientas de Sistema: FFmpeg instalado globalmente y accesible vía CLI.

Librerías Python Principales:



anthropic (SDK de Claude)

elevenlabs (SDK de ElevenLabs)

moviepy / ffmpeg-python (Manipulación de medios)

pydantic (Validación de datos JSON)

google-api-python-client / google-auth-oauthlib (YouTube API)

python-dotenv (Gestión de variables de entorno)
