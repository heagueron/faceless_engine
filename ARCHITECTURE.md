# Guía de Desarrollo para Faceless Engine

Este archivo es la guía central del proyecto **Faceless Engine**. Define la arquitectura, flujos de trabajo, estándares de código y procedimientos de desarrollo.

---

## 1. Project Overview

**Faceless Engine** es un motor de automatización integral en Python diseñado para la producción automatizada y semi-asistida de videos educativos y de entretenimiento ("Faceless Videos") para plataformas como **YouTube (Horizontal 16:9 y Shorts 9:16), TikTok e Instagram Reels**.

### Tecnologías Clave
- **Lenguaje:** Python 3.10+
- **Modelos de Lenguaje & Visión (LLM/VLM):** Gemini 2.0/3.7 (vía OpenRouter / Google GenAI SDK)
- **Generación de Imágenes:** Fal.ai (FLUX.1 Schnell/Dev) y OpenRouter (Qwen Image / Gemini Image)
- **Síntesis de Voz (TTS):** Microsoft Edge TTS (`edge-tts`) con soporte multilingüe (`es`, `en`, `pt`)
- **Procesamiento de Video & Composición:** MoviePy (v1/v2), FFmpeg, NumPy
- **Manipulación Gráfica:** Pillow (PIL) para tarjetas de datos, overlays y miniaturas
- **Esquemas & Validación:** Pydantic v2
- **APIs Externas:** YouTube Data API v3, OpenRouter API, Fal.ai API

### Arquitectura de Alto Nivel
```
                                ┌──────────────────────────┐
                                │   trend_analyzer.py      │
                                │ (YouTube API/OpenRouter) │
                                └────────────┬─────────────┘
                                             │
                                ┌────────────▼─────────────┐
                                │         ideas.py         │
                                │  (5 Ángulos Virales LLM) │
                                └────────────┬─────────────┘
                                             │
                                ┌────────────▼─────────────┐
                                │   script_generator.py    │
                                │ (Escaleta + Batch JSON)  │
                                └────────────┬─────────────┘
                                             │
                       ┌─────────────────────┴─────────────────────┐
                       │                                           │
          ┌────────────▼─────────────┐                ┌────────────▼─────────────┐
          │    voice_generator.py    │                │     media_fetcher.py     │
          │   (edge-tts -> MP3)      │                │  (FLUX/Qwen/Pillow Cards)│
          └────────────┬─────────────┘                └────────────┬─────────────┘
                       │                                           │
                       └─────────────────────┬─────────────────────┘
                                             │
                                ┌────────────▼─────────────┐
                                │    video_composer.py     │
                                │ (Ken Burns Anim + Audio) │
                                └────────────┬─────────────┘
                                             │
                       ┌─────────────────────┴─────────────────────┐
                       │                                           │
          ┌────────────▼─────────────┐                ┌────────────▼─────────────┐
          │   thumbnail_builder.py   │                │   caption_generator.py   │
          │  (Pillow + Text Stroke)  │                │   & description_gen.py   │
          └──────────────────────────┘                └──────────────────────────┘
```

---

## 2. Getting Started

### Prerrequisitos
- Python 3.10 o superior.
- **FFmpeg** instalado en el sistema operativo y disponible en el `PATH`.
- Fuentes TrueType en el sistema (ej. `DejaVuSans`, `LiberationSans` o `Impact`).

### Variables de Entorno (`.env`)
Crea un archivo `.env` en la raíz del proyecto con las siguientes claves:

```env
OPENROUTER_API_KEY=tu_api_key_de_openrouter
YOUTUBE_API_KEY=tu_api_key_de_youtube_data_v3
FAL_KEY=tu_api_key_de_fal_ai            # O FAL_API_KEY
GEMINI_API_KEY=tu_api_key_de_gemini     # Opcional (para SDK directo)
ELEVENLABS_API_KEY=tu_api_key           # Opcional
```

### Instalación
```bash
# 1. Clonar el repositorio
git clone <repo-url>
cd faceless_engine

# 2. Crear entorno virtual y activarlo
python3 -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate

# 3. Instalar dependencias
pip install --upgrade pip
pip install -r requirements.txt
```

### Uso Básico
Ejecutar el pipeline completo interactivo:
```bash
python main.py
```

---

## 3. Project Structure

```
faceless_engine/
├── .continue/
│   └── rules/
│       └── CONTINUE.md          # Este archivo de directrices
├── config/
│   ├── channels/                # Configuraciones por canal
│   └── global_settings.json     # Ajustes globales
├── core/
│   ├── __init__.py
│   ├── caption_generator.py     # Generación de subtítulos .SRT sincronizados
│   ├── config.py                # Configuración de idiomas y directivas de prompts
│   ├── description_generator.py # Generación de SEO, descripción, tags y pinned comments
│   ├── ideas.py                 # Ideación de 5 ángulos virales interactivos
│   ├── media_fetcher.py         # Generación visual (FLUX.1/Qwen), layouts split y code_graphic
│   ├── script_generator.py      # Generador de escaleta y guion estructurado por lotes
│   ├── styles.py                # Estilos visuales predefinidos
│   ├── thumbnail_builder.py     # Compositor tipográfico de miniaturas de alto impacto
│   ├── trend_analyzer.py        # Búsqueda en YouTube e Ingeniería Inversa (Reverse Prompting)
│   ├── uploader.py              # Módulo de publicación automática (YouTube API)
│   ├── video_composer.py        # Ensamblado con efecto Ken Burns y sincronización
│   └── voice_generator.py       # Síntesis neural con edge-tts y cálculo de duraciones
├── output/                      # Estado temporal e intercambio entre pasos
│   ├── current_project.json     # Puntero activo al proyecto actual
│   ├── reverse_prompting_analysis.json
│   ├── selected_idea.json
│   └── selected_trend.json
├── projects/                    # Directorio de salida por proyecto (timestamped)
│   └── YYYYMMDD_HHMMSS_slug/
│       ├── audio/               # scene_1.mp3, scene_2.mp3...
│       ├── images/              # scene_1.jpg, thumbnail_raw.jpg, thumbnail.png
│       ├── manifest.json        # Manifiesto central del proyecto
│       ├── final.mp4            # Video renderizado final
│       ├── subtitles.srt        # Subtítulos estándar
│       ├── description.txt      # Descripción formateada para YouTube
│       ├── pinned_comment.txt   # Comentario fijado para debate
│       └── metadata.json        # Metadatos para la API de YouTube
├── ARCHITECTURE.md              # Documentación de arquitectura técnica
├── main.py                      # Orquestador del pipeline
├── requirements.txt             # Dependencias del proyecto
└── README.md                    # Resumen y guía rápida
```

---

## 4. Development Workflow

### Estándares de Código y Convenciones
1. **Nombres de Archivos y Carpetas:** Estrictamente formato ASCII (`slugify`, sin tildes, ñ ni caracteres especiales).
2. **Esquemas Tipados:** Todo intercambio de datos entre módulos o APIs se modela mediante **Pydantic** (`BaseModel`).
3. **Manejo de Idiomas:** Centralizado en `core/config.py`. Los prompts visuales para IA se generan siempre en **INGLÉS**, mientras que las locuciones, textos superpuestos y metadatos se generan en el idioma objetivo (`es`, `en`, `pt`).
4. **Resiliencia en Red:** Todas las llamadas a OpenRouter, Fal.ai y YouTube API deben implementar `try/except`, timeouts y reintentos exponenciales con respaldo a generadores locales (Pillow).
5. **Estado Centralizado:** Cada ejecución actualiza `output/current_project.json` permitiendo reanudar o ejecutar módulos individuales de forma desacoplada sin reescribir argumentos.

---

## 5. Key Concepts & Layouts

- **Manifiesto del Proyecto (`manifest.json`):** Es la fuente de verdad única de cada video. Contiene la lista de escenas, textos de locución, prompts visuales, duraciones de audio y rutas a activos.
- **Tipos de Layout Visual (`layout_type`):**
  1. `full_art`: Imagen completa generada por IA (100% libre de tipografía en el arte crudo).
  2. `split_right`: Imagen IA encuadrada en el 70% izquierdo dejando el 30% derecho con espacio negativo para una tarjeta de datos estReadable superpuesta por Pillow.
  3. `code_graphic`: Tarjeta visual de datos, código o lista de viñetas generada 100% mediante Python (Pillow), sin consumo de API de imagen.
- **Efecto Ken Burns:** Movimiento suave de cámara alternado (Zoom-In en escenas impares, Zoom-Out en escenas pares) aplicado en MoviePy para mantener el dinamismo visual.
- **Stateful Batching:** Los videos largos dividen la generación del guion en: (1) Escaleta Maestra global y (2) Lotes de escenas con contexto previo para evitar desbordamiento de ventana de contexto en el LLM.


### Fuentes por Estilo (`visual_style_fonts`)

Cada estilo en `core/styles.py` puede declarar opcionalmente un campo `fonts` con
dos claves: `title` y `body`. Los nombres de archivo son relativos a
`assets/fonts/` en la raíz del proyecto.

```python
"cartoon_2d_cellshaded": {
    # ... otros campos
    "fonts": {
        "title": "PatrickHand-Regular.ttf",
        "body": "PatrickHand-Regular.ttf",
    },
    "allowed_layouts": ["full_art", "split_right", "code_graphic"],
},
---

## 6. Common Tasks

### 1. Ejecutar el Pipeline Completo
```bash
python main.py
```

### 2. Analizar una URL de YouTube con Reverse Prompting
```bash
python core/trend_analyzer.py --url "https://www.youtube.com/watch?v=EXAMPLE_ID"
```

### 3. Regenerar solo el Guion para un tema específico
```bash
python core/script_generator.py --duration 60 --type short --ratio 9:16 --lang es
```

### 4. Regenerar el Audio de una Escena Específica
```bash
python core/voice_generator.py --scene 3 --rate "+5%"
```

### 5. Regenerar Imágenes de un Rango de Escenas
```bash
python core/media_fetcher.py --scene "2-5" --force
```

### 6. Componer la Miniatura Gráfica
```bash
python core/thumbnail_builder.py --text "¡ERROR FATAL!" --color "#FFDE00" --position top
```

### 7. Renderizar únicamente el Video Final
```bash
python core/video_composer.py --fps 24 --preset fast
```

---

## 7. Troubleshooting

| Síntoma | Causa Probable | Solución |
|---|---|---|
| `OPENROUTER_API_KEY no encontrada` | Falta archivo `.env` o variable no cargada | Crea el `.env` con las claves indicadas en la sección 2. |
| `MoviePy / FFmpeg error: file not found` | FFmpeg no está instalado en el sistema | Instala FFmpeg (`sudo apt-get install ffmpeg` o vía gestor de paquetes de tu SO). |
| `Rate Limit 429 en OpenRouter/Fal` | Exceso de peticiones concurrentes | El sistema incluye reintentos automáticos. Puedes aumentar el delay con `--delay 2.0`. |
| Las imágenes tienen texto no deseado | El prompt de IA generó letras aleatorias | El estilo visual incluye salvaguardas de limpieza. Utiliza `layout_type="split_right"` o `code_graphic` para texto legible generado por Pillow. |
| Los números se leen raro en TTS | Puntos de miles interpretados como decimales | `voice_generator.py` incluye la función `normalize_numbers_for_tts()` para limpiar puntuaciones numéricas. |

---

## 8. References

- [OpenRouter API Documentation](https://openrouter.ai/docs)
- [Fal.ai FLUX Models](https://fal.ai/models)
- [Microsoft Edge TTS (edge-tts)](https://github.com/rany2/edge-tts)
- [MoviePy Documentation](https://zulko.github.io/moviepy/)
- [Pillow (PIL) Documentation](https://pillow.readthedocs.io/)
