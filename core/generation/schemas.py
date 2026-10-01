"""
Schemas Pydantic para el pipeline de generación de guiones.
"""

from typing import List, Optional, Literal, Dict
from pydantic import BaseModel, Field


class OverlayContent(BaseModel):
    title: Optional[str] = Field(
        default=None,
        description="Título o cifra principal en MAYÚSCULAS para superponer mediante Python."
    )
    bullets: Optional[List[str]] = Field(
        default=None,
        description="Lista de 1 a 3 puntos clave o datos breves a superponer."
    )


class Scene(BaseModel):
    scene_number: int = Field(description="Número secuencial de la escena (1, 2, 3...)")
    narration_text: str = Field(description="Texto en español que dirá la voz en off para esta escena")
    layout_type: Literal["full_art", "split_right", "code_graphic", "code_graphic_visual"] = Field(
        default="full_art",
        description=(
            "full_art: Imagen completa 100% IA sin texto.\n"
            "split_right: Imagen IA encuadrada a la izquierda con 30% espacio negativo a la derecha para tarjeta de texto superpuesta por Python.\n"
            "code_graphic: Sin imagen de IA. Gráfico o tabla de datos generado 100% por Python.\n"
            "code_graphic_visual: Sin imagen de IA. Pizarra blanca con bullets grandes y figura explainer a un lado apuntando hacia ella."
        )
    )
    visual_prompt: Optional[str] = Field(
        default=None,
        description="Prompt visual ultradetallado en INGLÉS listo para FLUX.1 (None si layout_type es 'code_graphic')"
    )
    overlay_content: Optional[OverlayContent] = Field(
        default=None,
        description="Contenido de texto o cifras a renderizar mediante Python si layout_type es 'split_right' o 'code_graphic'"
    )
    is_interactive_cta: bool = Field(
        default=False,
        description="True únicamente si esta escena es una pregunta final condicional para generar interacción en los comentarios."
    )
    audio_file: Optional[str] = Field(default=None, description="Ruta al archivo MP3 de la escena")
    audio_duration_seconds: Optional[float] = Field(default=None, description="Duración exacta en segundos del audio")
    image_path: Optional[str] = Field(default=None, description="Ruta a la imagen o video generado para la escena")


class ScriptManifest(BaseModel):
    language: str = Field(default="es", description="Código de idioma del proyecto ('es', 'en', 'pt', etc.)")

    visual_style: str = Field(
        default="cartoon_2d_cellshaded",
        description="Clave del estilo visual aplicado (debe existir en core/styles.py)"
    )

    visual_style_fonts: Dict[str, str] = Field(
        default_factory=dict,
        description="Fuentes del estilo en el momento de generación (snapshot inmutable)."
    )

    visual_style_prompt: str = Field(
        default="",
        description="Fragmento de prompt en INGLÉS del estilo (snapshot para inmutabilidad del proyecto)"
    )

    allowed_layouts: List[str] = Field(
        default_factory=lambda: ["full_art", "split_right", "code_graphic", "code_graphic_visual"],
        description="Layouts permitidos por el estilo en el momento de generación (snapshot)."
    )

    title: str = Field(description="Título sugerido y atractivo para el video")
    video_type: str = Field(default="long", description="Tipo de video: 'short' o 'long'")
    aspect_ratio: str = Field(default="16:9", description="Relación de aspecto: '9:16' o '16:9'")
    target_duration_seconds: int = Field(description="Duración estimada del video completo en segundos")
    includes_interactive_cta: bool = Field(
        default=False,
        description="Indica si el guion incluye una escena final con pregunta de debate para los comentarios."
    )
    thumbnail_prompt: str = Field(
        description="Prompt visual ultradetallado en INGLÉS optimizado para la miniatura."
    )
    thumbnail_text: str = Field(
        description="Texto de gancho corto en MAYÚSCULAS en español para la miniatura (ej. '¡ERROR FATAL!', '¡NO HAGAS ESTO!')."
    )
    scenes: List[Scene] = Field(description="Lista ordenada de las escenas que componen el guion")
    total_audio_duration_seconds: Optional[float] = Field(default=None, description="Duración acumulada de los audios")