
# Guía de Desarrollo para Faceless Engine

Este archivo es la guía central del proyecto **Faceless Engine**. Define la arquitectura, flujos de trabajo, estándares de código y procedimientos de desarrollo.

---

## 1. Project Overview

**Faceless Engine** es un motor de automatización integral en Python diseñado para la producción automatizada y semi-asistida de videos educativos y de entretenimiento ("Faceless Videos") para plataformas como **YouTube (Horizontal 16:9 y Shorts 9:16), TikTok e Instagram Reels**.

### Tecnologías Clave
- **Lenguaje:** Python 3.10+
- **Modelos de Lenguaje & Visión (LLM/VLM):** Gemini 2.0/3.7 (vía OpenRouter / Google GenAI SDK)
- **Generación de Imágenes:** Fal.ai (FLUX.1 Schnell/Dev), NVIDIA Build (FLUX.2 Klein, FLUX.1 Dev), OpenRouter (Qwen Image / Gemini Image)
- **Síntesis de Voz (TTS):** Microsoft Edge TTS (`edge-tts`) con soporte multilingüe (`es`, `en`, `pt`)
- **Procesamiento de Video & Composición:** MoviePy (v1/v2), FFmpeg, NumPy
- **Manipulación Gráfica:** Pillow (PIL) para tarjetas de datos, overlays y miniaturas
- **Esquemas & Validación:** Pydantic v2
- **APIs Externas:** YouTube Data API v3, OpenRouter API, Fal.ai API, NVIDIA Build API

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
          │   (edge-tts -> MP3)      │                │  (Orquestador Visual)    │
          └────────────┬─────────────┘                └────────────┬─────────────┘
                       │                                           │
                       │                                           ├─ providers/ (fal, nvidia, openrouter)
                       │                                           ├─ renderers/ (card, whiteboard)
                       │                                           ├─ overlays/ (split_right)
                       │                                           └─ fonts.py
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
- Fuentes TrueType en `assets/fonts/` (Patrick Hand para estilos cartoon; DejaVu como fallback).

### Variables de Entorno (`.env`)
Crea un archivo `.env` en la raíz del proyecto con las siguientes claves:

```env
OPENROUTER_API_KEY=tu_api_key_de_openrouter
YOUTUBE_API_KEY=tu_api_key_de_youtube_data_v3
FAL_KEY=tu_api_key_de_fal_ai            # O FAL_API_KEY
NVIDIA_API_KEY=nvapi-tu_api_key_de_nvidia_build
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
├── assets/
│   ├── fonts/                   # Fuentes TTF (Patrick Hand, DejaVu, etc.)
│   │   └── PatrickHand-Regular.ttf
│   └── explainers/              # PNGs de personajes explicadores
│       └── cartoon_2d_cellshaded/
│           └── pointer.png
├── config/
│   ├── channels/                # Configuraciones por canal
│   └── global_settings.json     # Ajustes globales
├── core/
│   ├── __init__.py
│   ├── caption_generator.py     # Generación de subtítulos .SRT sincronizados
│   ├── config.py                # Configuración de idiomas y proporciones de layout
│   ├── description_generator.py # Generación de SEO, descripción, tags y pinned comments
│   ├── fonts.py                 # Carga de fuentes con fallback en cascada
│   ├── ideas.py                 # Ideación de 5 ángulos virales interactivos
│   ├── media_fetcher.py         # Orquestador de recursos visuales (delega a subpaquetes)
│   ├── script_generator.py      # Generador de escaleta y guion estructurado por lotes
│   ├── styles.py                # Catálogo de estilos visuales
│   ├── thumbnail_builder.py     # Compositor tipográfico de miniaturas
│   ├── trend_analyzer.py        # Búsqueda en YouTube e Ingeniería Inversa
│   ├── uploader.py              # Módulo de publicación automática (YouTube API)
│   ├── video_composer.py        # Ensamblado con efecto Ken Burns y sincronización
│   ├── voice_generator.py       # Síntesis neural con edge-tts
│   ├── overlays/                # Overlays aplicados sobre imágenes de IA
│   │   ├── __init__.py
│   │   └── split_right.py       # Tarjeta superpuesta en el 30% derecho
│   ├── providers/               # Proveedores de generación de imágenes
│   │   ├── __init__.py
│   │   ├── fal.py               # fal.ai (FLUX Schnell, FLUX Dev)
│   │   ├── openrouter.py        # OpenRouter (Qwen, Gemini vía API)
│   │   ├── nvidia.py            # NVIDIA Build NIM (FLUX.2 Klein, FLUX.1 Dev)
│   │   └── fallback.py          # Imágenes de respaldo con Pillow
│   └── renderers/               # Renderizadores de escenas Python
│       ├── __init__.py
│       ├── base.py              # Helpers comunes (wrap_text_by_pixel_width)
│       ├── card.py              # code_graphic clásico (título + bullets)
│       └── whiteboard.py        # code_graphic_visual (pizarra + explainer)
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
4. **Resiliencia en Red:** Todas las llamadas a OpenRouter, Fal.ai, NVIDIA y YouTube API deben implementar `try/except`, timeouts y reintentos exponenciales con respaldo a generadores locales (Pillow).
5. **Estado Centralizado:** Cada ejecución actualiza `output/current_project.json` permitiendo reanudar o ejecutar módulos individuales de forma desacoplada sin reescribir argumentos.
6. **Separación de Responsabilidades:** Los módulos que orquestan (como `media_fetcher.py`) no contienen lógica de negocio. Delegan a subpaquetes especializados.

---

## 5. Key Concepts & Layouts

- **Manifiesto del Proyecto (`manifest.json`):** Es la fuente de verdad única de cada video. Contiene la lista de escenas, textos de locución, prompts visuales, duraciones de audio y rutas a activos. **Es un snapshot inmutable**: contiene los campos `visual_style`, `visual_style_prompt`, `visual_style_fonts` y `allowed_layouts` en el momento de generación, para que los proyectos sean reproducibles incluso si `styles.py` cambia después.

- **Tipos de Layout Visual (`layout_type`):**
  1. `full_art`: Imagen completa generada por IA (100% libre de tipografía en el arte crudo).
  2. `split_right`: Imagen IA encuadrada en el 70% izquierdo dejando el 30% derecho con espacio negativo para una tarjeta de datos superpuesta por Pillow.
  3. `code_graphic`: Tarjeta visual de datos, código o lista de viñetas generada 100% mediante Python (Pillow), sin consumo de API de imagen.
  4. `code_graphic_visual`: Pizarra blanca con bullets grandes y figura explainer a un lado apuntando hacia ella. Generada 100% con Pillow.

- **Efecto Ken Burns:** Movimiento suave de cámara alternado (Zoom-In en escenas impares, Zoom-Out en escenas pares) aplicado en MoviePy para mantener el dinamismo visual.

- **Stateful Batching:** Los videos largos dividen la generación del guion en: (1) Escaleta Maestra global y (2) Lotes de escenas con contexto previo para evitar desbordamiento de ventana de contexto en el LLM.

### 5.1 Fuentes por Estilo (`visual_style_fonts`)

Cada estilo en `core/styles.py` puede declarar opcionalmente un campo `fonts` con dos claves: `title` y `body`. Los nombres de archivo son relativos a `assets/fonts/`.

```python
"cartoon_2d_cellshaded": {
    # ... otros campos
    "fonts": {
        "title": "PatrickHand-Regular.ttf",
        "body": "PatrickHand-Regular.ttf",
    },
    "allowed_layouts": ["full_art", "split_right", "code_graphic"],
},
```

**Aplicación:** Las fuentes solo afectan a los layouts que renderiza Python: `code_graphic` y `code_graphic_visual`. Los prompts visuales enviados a proveedores de IA no las usan.

**Snapshot inmutable:** Cuando `script_generator.py` crea un proyecto, copia las fuentes al manifest bajo `visual_style_fonts`. Esto garantiza reproducibilidad histórica.

**Fallback en cascada** (`core/fonts.py::load_font`):
1. Fuente declarada por el estilo, en `assets/fonts/`.
2. Fallback global (`DejaVuSans.ttf`) en `assets/fonts/`.
3. Fallback global del sistema (rutas estándar de Pillow).
4. Fuente por defecto de Pillow.

### 5.2 Arquitectura de `media_fetcher` (refactor 2026-09)

`media_fetcher.py` fue refactorizado para delegar responsabilidades a módulos especializados. El archivo principal ahora actúa solo como **orquestador**.

#### Módulos especializados

| Módulo | Responsabilidad |
|---|---|
| `core/fonts.py` | Carga de fuentes con fallback en cascada |
| `core/renderers/base.py` | Helpers comunes (`wrap_text_by_pixel_width`) |
| `core/renderers/card.py` | Renderizador de tarjetas `code_graphic` clásicas |
| `core/renderers/whiteboard.py` | Renderizador de pizarras `code_graphic_visual` con explainer |
| `core/overlays/split_right.py` | Overlay de tarjeta oscura sobre el 30% derecho |
| `core/providers/fal.py` | Generación vía fal.ai (FLUX Schnell, FLUX Dev) |
| `core/providers/openrouter.py` | Generación vía OpenRouter (Qwen Image, Gemini Image) |
| `core/providers/nvidia.py` | Generación vía NVIDIA Build NIM (FLUX.2 Klein, FLUX.1 Dev) |
| `core/providers/fallback.py` | Imagen de respaldo con Pillow |

#### Selección dinámica de proveedor

Cada estilo en `styles.py` puede declarar `preferred_provider` y `preferred_model`. La función `resolve_effective_provider()` en `media_fetcher.py` decide qué proveedor usar según esta lógica:

1. Si el usuario pasó `--provider X` explícitamente (distinto del default), ese gana.
2. Si el estilo declara `preferred_provider`, se usa ese.
3. Si no, se usa el proveedor por defecto (`fal`).

#### Rate limiting (NVIDIA)

El proveedor `nvidia.py` implementa un throttle interno con `_throttle()` que garantiza un intervalo mínimo de ~1.67s entre llamadas (36 req/min efectivas, margen frente al límite de 40 rpm de NVIDIA). Los errores 429 disparan retry con backoff exponencial.

#### Límite de prompt de NVIDIA

NVIDIA NIM impone un límite de **800 caracteres** por prompt. La función `_compress_prompt_for_nvidia()` normaliza y recorta prompts largos antes de enviarlos. En la práctica, con los prompts cortos que ahora usamos, el límite rara vez se alcanza.

### 5.3 Reglas de diseño para prompts visuales

Estas reglas se derivaron de experimentos sistemáticos con múltiples modelos (FLUX Schnell, FLUX Dev, FLUX.2 Klein, Gemini Image) y son **críticas** para que la composición de las escenas se respete.

#### Regla 1 — Prompts cortos son mejores

Los modelos de generación se **diluyen** con prompts largos. Cuando el prompt supera ~200 caracteres, el modelo prioriza las primeras palabras y colapsa la escena al sujeto principal. Con prompts de ~100-150 caracteres, el modelo respeta la escena completa.

**Aplicación:** el `visual_prompt` de cada escena debe ser **una sola frase** de máximo 150 caracteres. El estilo NO debe incluirse en el `visual_prompt`; el pipeline lo añade automáticamente después.

#### Regla 2 — Escena primero, estilo después

En `apply_prompt_safeguards`, el estilo se añade **al final** del prompt de escena, no al principio. Los modelos atienden más a lo que aparece primero.

**Aplicación:** si el `visual_prompt` no contiene el estilo, se concatena como sufijo: `"[escena]. [estilo]. [reglas]"`.

#### Regla 3 — Los estilos deben caber en ~100-150 caracteres

Los `prompt` de estilos en `styles.py` deben ser cortos para que, sumados a la escena, el prompt final no pase de 300-400 caracteres.

Estilos problemáticos históricamente:
- `cartoon_2d_cellshaded` (~230 chars → ignora estilo y composición).
- `doodle_cartoon_landscape` (~500 chars → ignora todo).
- `stick_classic_klein` (reducido a 99 chars → funciona bien).

#### Regla 4 — La aleatoriedad del modelo es inevitable

El mismo prompt con distinto seed produce variaciones. Para mantener consistencia entre escenas, se puede fijar el seed (`preferred_seed`). Por defecto, `stick_classic_klein` usa seed=100.

**Cuidado:** el mismo seed con distinto prompt produce resultados distintos. El seed fija el ruido inicial, no la composición final.

#### Regla 5 — Klein para escenas simples, Gemini para complejas

FLUX.2 Klein 4B (NVIDIA) es excelente para **personajes aislados o escenas muy simples**. Falla en composiciones complejas con múltiples elementos interactuando.

Para escenas complejas, Gemini Image es más fiable, pero también más caro (~$0.04 por imagen vs $0.003 de Schnell).

**Estrategia recomendada:** Schnell o Klein como motor principal, Gemini como respaldo puntual cuando la composición sea crítica.

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

### 8. Regenerar una escena con NVIDIA Klein
```bash
python -m core.media_fetcher --provider nvidia --scene 3 --force
```

### 9. Regenerar una escena con OpenRouter (Gemini)
```bash
python -m core.media_fetcher --provider openrouter --model google/gemini-3.7-flash --scene 3 --force
```

### 10. Ejecutar el test de proveedores NVIDIA
```bash
NVIDIA_TEST_SUITE=classic_fullbody python core/test_nvidia_models.py
```

### 11. Ajustar las proporciones de layout
Editar `core/config.py`:
```python
LAYOUT_PROPORTION_GUIDE = {
    "full_art": (0.60, 0.75),
    "split_right": (0.10, 0.20),
    "code_graphic": (0.05, 0.15),
    "code_graphic_visual": (0.00, 0.10),
}
MIN_FULL_ART_RATIO = 0.60
```

---

## 7. Troubleshooting

| Síntoma | Causa Probable | Solución |
|---|---|---|
| `OPENROUTER_API_KEY no encontrada` | Falta archivo `.env` o variable no cargada | Crea el `.env` con las claves indicadas en la sección 2. |
| `MoviePy / FFmpeg error: file not found` | FFmpeg no está instalado en el sistema | Instala FFmpeg (`sudo apt-get install ffmpeg`). |
| `Rate Limit 429 en OpenRouter/Fal` | Exceso de peticiones concurrentes | El sistema incluye reintentos automáticos. Aumenta el delay con `--delay 2.0`. |
| Las imágenes tienen texto no deseado | El prompt de IA generó letras aleatorias | Utiliza `layout_type="split_right"` o `code_graphic` para texto legible generado por Pillow. |
| Los números se leen raro en TTS | Puntos de miles interpretados como decimales | `voice_generator.py` incluye `normalize_numbers_for_tts()`. |
| `NVIDIA_API_KEY no encontrada` | Falta la variable en `.env` | Añadir `NVIDIA_API_KEY=nvapi-...` al `.env`. |
| `HTTP 422 - String should have at most 800 characters` | Prompt demasiado largo para NVIDIA NIM | El pipeline comprime automáticamente. Si persiste, reducir el `prompt` del estilo en `styles.py`. |
| `Timeout en NVIDIA` tras varios intentos | Rate limit o servicio lento | El proveedor reintenta con backoff. Si persiste, esperar unos minutos o usar `--provider fal`. |
| Imagen en blanco (todo blanco) con NVIDIA | FLUX.1-dev con prompt problemático en NVIDIA | Usar `flux.2-klein-4b` en su lugar (el proveedor `nvidia` ya lo selecciona por defecto). |
| `cannot access local variable 'manifest'` | Referencia a `manifest` antes de cargarlo | Ordenar el código: cualquier función que lea del manifest debe ejecutarse después del `json.load()`. |

---

## 8. References

- [OpenRouter API Documentation](https://openrouter.ai/docs)
- [Fal.ai FLUX Models](https://fal.ai/models)
- [NVIDIA Build (NIM)](https://build.nvidia.com)
- [Microsoft Edge TTS (edge-tts)](https://github.com/rany2/edge-tts)
- [MoviePy Documentation](https://zulko.github.io/moviepy/)
- [Pillow (PIL) Documentation](https://pillow.readthedocs.io/)
```

---

## Resumen de cambios respecto al anterior

| Sección | Cambio |
|---|---|
| **1** | Añadido NVIDIA Build a Tecnologías Clave y APIs Externas. Diagrama actualizado con `media_fetcher` orquestador. |
| **2** | Añadida `NVIDIA_API_KEY` al `.env`. Mención a `assets/fonts/` en prerrequisitos. |
| **3** | Estructura completa con `assets/`, `overlays/`, `providers/`, `renderers/`, `fonts.py`. |
| **4** | Añadido estándar 6 (separación de responsabilidades). |
| **5** | Ampliada con 5.1 (fuentes), 5.2 (media_fetcher refactor), 5.3 (reglas de prompts). Añadido `code_graphic_visual` como layout. |
| **6** | Comandos 8-11 (NVIDIA, OpenRouter, tests, configuración). |
| **7** | Añadidas 5 filas nuevas de troubleshooting. |
| **8** | Añadido NVIDIA Build a referencias. |

