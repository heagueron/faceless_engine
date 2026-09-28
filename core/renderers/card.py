"""
Renderizador de tarjetas 'code_graphic' clásicas:
título + bullets centrados en un fondo blanco tipo página.
"""

import os
import textwrap
from typing import Optional, Dict, Any
from PIL import Image, ImageDraw, ImageFont

from core.fonts import load_font
from core.renderers.base import wrap_text_by_pixel_width


def render_code_graphic_card(
    output_path: str,
    scene_num: int,
    overlay_content: Optional[Dict[str, Any]],
    aspect_ratio: str = "16:9",
    fonts: Optional[Dict[str, str]] = None,
) -> None:
    """
    Renderiza una tarjeta visual de texto/código (layout 'code_graphic')
    como una página blanca limpia, con el contenido centrado y en tinta oscura.
    """
    if fonts is None:
        fonts = {"title": "DejaVuSans.ttf", "body": "DejaVuSans.ttf"}

    if aspect_ratio == "9:16":
        width, height = 1080, 1920
        max_title_chars = 18
        max_bullet_chars = 22
        font_size_title = max(38, int(height * 0.048))
        font_size_bullets = max(28, int(height * 0.034))
    else:
        width, height = 1920, 1080
        max_title_chars = 28
        max_bullet_chars = 36
        font_size_title = max(56, int(height * 0.065))
        font_size_bullets = max(40, int(height * 0.045))

    INK = (15, 23, 42)
    ACCENT = (250, 204, 21)

    img = Image.new('RGB', (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    title_font = load_font(fonts["title"], font_size_title)
    bullet_font = load_font(fonts["body"], font_size_bullets)

    title = overlay_content.get("title") if overlay_content else f"ESCENA {scene_num}"
    bullets = overlay_content.get("bullets", []) if overlay_content else []

    wrapped_title_lines = textwrap.wrap(title.upper(), width=max_title_chars) if title else []

    wrapped_bullet_items = []
    if bullets:
        for b in bullets:
            wrapped_bullet_items.append(textwrap.wrap(f"• {b}", width=max_bullet_chars))

    line_h_title = int(font_size_title * 1.35)
    line_h_bullet = int(font_size_bullets * 1.55)
    sep_space = int(height * 0.06)

    total_h = 0
    if wrapped_title_lines:
        total_h += (len(wrapped_title_lines) * line_h_title) + sep_space
    for item_lines in wrapped_bullet_items:
        total_h += (len(item_lines) * line_h_bullet) + int(height * 0.025)

    page_left = int(width * 0.10)
    page_right = int(width * 0.90)
    page_top = int(height * 0.12)
    page_bottom = int(height * 0.88)
    content_area_h = page_bottom - page_top

    curr_y = page_top + max(0, (content_area_h - total_h) // 2)
    center_x = (page_left + page_right) // 2

    if wrapped_title_lines:
        for line in wrapped_title_lines:
            draw.text(
                (center_x, curr_y + (line_h_title // 2)),
                line,
                font=title_font,
                fill=ACCENT,
                anchor="mm"
            )
            curr_y += line_h_title
        curr_y += sep_space

    if wrapped_bullet_items:
        max_line_len_px = 0
        for item_lines in wrapped_bullet_items:
            for line in item_lines:
                try:
                    bbox = bullet_font.getbbox(line)
                    w = bbox[2] - bbox[0]
                except AttributeError:
                    w = len(line) * (font_size_bullets * 0.55)
                if w > max_line_len_px:
                    max_line_len_px = w

        bullet_block_left = max(page_left, int(center_x - (max_line_len_px / 2)))

        for item_lines in wrapped_bullet_items:
            for idx, line in enumerate(item_lines):
                indent = 0 if idx == 0 else int(font_size_bullets * 0.8)
                draw.text(
                    (bullet_block_left + indent, curr_y),
                    line,
                    font=bullet_font,
                    fill=INK
                )
                curr_y += line_h_bullet
            curr_y += int(height * 0.025)

    fmt = "PNG" if output_path.lower().endswith(".png") else "JPEG"
    img.save(output_path, fmt, quality=95)
    print(f"   🎨 Tarjeta 'code_graphic' estilo página blanca: {output_path}")