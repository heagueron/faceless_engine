"""
Utilidades de fuentes para Faceless Engine.

Centraliza la carga de fuentes con fallback en cascada:
  1. La fuente solicitada en assets/fonts/
  2. El fallback global (DejaVu) en assets/fonts/
  3. El fallback global del sistema (rutas estándar de Pillow)
  4. La fuente por defecto de Pillow (último recurso)

Documentado en ARCHITECTURE.md sección 5.
"""

import os
from PIL import ImageFont

from core.styles import GLOBAL_FALLBACK_FONT

# --- Rutas del proyecto ---
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_FONTS_DIR = os.path.join(_PROJECT_ROOT, "assets", "fonts")


def get_project_root() -> str:
    """Retorna la raíz del proyecto (útil para otros módulos)."""
    return _PROJECT_ROOT


def get_fonts_dir() -> str:
    """Retorna el directorio de fuentes."""
    return _FONTS_DIR


def load_font(font_filename: str, size: int) -> ImageFont.FreeTypeFont:
    """
    Carga una fuente desde assets/fonts/ con fallback en cascada.
    Ver docstring del módulo para detalles.
    """
    candidates = [
        os.path.join(_FONTS_DIR, font_filename),
        os.path.join(_FONTS_DIR, GLOBAL_FALLBACK_FONT),
        GLOBAL_FALLBACK_FONT,  # Pillow buscará en /usr/share/fonts, ~/.fonts, etc.
    ]

    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except (IOError, OSError):
            continue

    print(f"   ⚠️ No se pudo cargar '{font_filename}' ni el fallback. Usando fuente por defecto de Pillow.")
    return ImageFont.load_default()