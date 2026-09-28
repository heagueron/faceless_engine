"""
Helpers comunes a todos los renderizadores de escenas Python.
"""

from typing import List
from PIL import ImageFont


def wrap_text_by_pixel_width(
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width_px: int
) -> List[str]:
    """
    Envuelve el texto midiendo el ancho real en píxeles de cada línea
    usando la fuente dada.
    """
    words = text.split()
    if not words:
        return []

    lines = []
    current_line = []

    for word in words:
        test_line = " ".join(current_line + [word])
        try:
            bbox = font.getbbox(test_line)
            line_width = bbox[2] - bbox[0]
        except AttributeError:
            line_width = len(test_line) * (font.size * 0.65)

        if line_width <= max_width_px:
            current_line.append(word)
        else:
            if current_line:
                lines.append(" ".join(current_line))
                current_line = [word]
            else:
                # Si una sola palabra es más ancha que el contenedor,
                # la forzamos a entrar en su propia línea.
                lines.append(word)
                current_line = []

    if current_line:
        lines.append(" ".join(current_line))

    return lines