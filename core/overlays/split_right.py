"""
Overlay 'split_right': tarjeta oscura con título y bullets superpuesta
sobre el 30% derecho de la imagen generada por IA.
"""

import os
from typing import Dict, Any, Optional
from PIL import Image, ImageDraw

from core.fonts import load_font
from core.renderers.base import wrap_text_by_pixel_width


def apply_split_right_overlay(
    image_path: str,
    overlay_content: Dict[str, Any],
    fonts: Optional[Dict[str, str]] = None,
) -> None:
    if not overlay_content or not os.path.exists(image_path):
        return

    if fonts is None:
        fonts = {"title": "DejaVuSans.ttf", "body": "DejaVuSans.ttf"}

    title = overlay_content.get("title")
    bullets = overlay_content.get("bullets", [])

    if not title and not bullets:
        return

    try:
        with Image.open(image_path) as base_img:
            img = base_img.convert("RGBA")
            width, height = img.size

            card_left = int(width * 0.67)
            card_top = int(height * 0.50) # antes 0.10
            card_right = int(width * 0.97)
            card_bottom = int(height * 0.90)

            card_overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
            draw_card = ImageDraw.Draw(card_overlay)

            draw_card.rounded_rectangle(
                [card_left, card_top, card_right, card_bottom],
                radius=18,
                fill=(15, 23, 42, 225),
                outline=(51, 65, 85, 255),
                width=0
            )

            img = Image.alpha_composite(img, card_overlay)
            draw = ImageDraw.Draw(img)

            font_size_title = max(24, int(height * 0.045))
            font_size_bullets = max(18, int(height * 0.032))

            title_font = load_font(fonts["title"], font_size_title)
            bullet_font = load_font(fonts["body"], font_size_bullets)

            padding_x = int(width * 0.02)
            padding_y = int(height * 0.04)
            curr_y = card_top + padding_y

            max_text_width_px = (card_right - card_left) - (padding_x * 2)

            if title:
                for word in title.split():
                    try:
                        w = title_font.getbbox(word.upper())[2] - title_font.getbbox(word.upper())[0]
                    except AttributeError:
                        w = len(word) * (font_size_title * 0.65)

                    if w > max_text_width_px:
                        font_size_title = int(font_size_title * (max_text_width_px / w) * 0.9)
                        title_font = load_font(fonts["title"], font_size_title)

                wrapped_title = wrap_text_by_pixel_width(title.upper(), title_font, max_text_width_px)

                for line in wrapped_title:
                    draw.text(
                        (card_left + padding_x, curr_y),
                        line,
                        font=title_font,
                        fill=(250, 204, 21)
                    )
                    curr_y += int(font_size_title * 1.3)

                curr_y += int(height * 0.015)
                draw.line(
                    [(card_left + padding_x, curr_y), (card_right - padding_x, curr_y)],
                    fill=(71, 85, 105, 255),
                    width=3
                )
                curr_y += int(height * 0.04)

            if bullets:
                for bullet in bullets:
                    bullet_text = f"• {bullet}"
                    wrapped_bullet = wrap_text_by_pixel_width(bullet_text, bullet_font, max_text_width_px)
                    for idx, line in enumerate(wrapped_bullet):
                        indent = padding_x if idx == 0 else padding_x + 18
                        draw.text(
                            (card_left + indent, curr_y),
                            line,
                            font=bullet_font,
                            fill=(241, 245, 249)
                        )
                        curr_y += int(font_size_bullets * 1.35)
                    curr_y += int(height * 0.025)

            final_img = img.convert("RGB")
            final_img.save(image_path, quality=95)
            print(f"   🎨 Overlay 'split_right' adaptado en píxeles: {image_path}")

    except Exception as e:
        print(f"   ⚠️ Error al estampar overlay en '{image_path}': {e}")