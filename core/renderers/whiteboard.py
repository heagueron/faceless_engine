"""
Renderizador 'code_graphic_visual': pizarra blanca con bullets grandes
y figura explainer opcional a un lado.
"""

import os
from typing import Optional, Dict, Any, List
from PIL import Image, ImageDraw

from core.fonts import load_font, get_project_root
from core.renderers.base import wrap_text_by_pixel_width


# --- Configuración de estilo de la pizarra ---
COLOR_BG = (250, 248, 243)            # crema muy claro de fondo
COLOR_BOARD = (255, 255, 255)         # blanco puro de la pizarra
COLOR_BOARD_OUTLINE = (40, 40, 40)    # borde negro de la pizarra
COLOR_BULLET_TEXT = (30, 30, 30)      # tinta oscura del texto

# --- Configuración del explainer ---
_EXPLAINERS_DIR = os.path.join(get_project_root(), "assets", "explainers")
DEFAULT_EXPLAINER_STYLE = "cartoon_2d_cellshaded"
DEFAULT_EXPLAINER_POSE = "pointer.png"


def _load_explainer(style: str, pose_filename: str) -> Optional[Image.Image]:
    """Carga el PNG del explainer con transparencia. Retorna None si no existe."""
    path = os.path.join(_EXPLAINERS_DIR, style, pose_filename)
    if not os.path.exists(path):
        print(f"   ⚠️ Explainer no encontrado en: {path}")
        return None
    try:
        return Image.open(path).convert("RGBA")
    except Exception as e:
        print(f"   ⚠️ Error al cargar explainer '{path}': {e}")
        return None


def render_whiteboard(
    output_path: str,
    scene_num: int,
    overlay_content: Optional[Dict[str, Any]],
    aspect_ratio: str = "16:9",
    fonts: Optional[Dict[str, str]] = None,
    explainer_style: str = DEFAULT_EXPLAINER_STYLE,
    explainer_pose: str = DEFAULT_EXPLAINER_POSE,
) -> None:
    """
    Renderiza una pizarra blanca con bullets grandes a la derecha del frame
    y una figura explainer a la izquierda apuntando a la pizarra.

    Si no hay explainer disponible, se comporta como un code_graphic simple.
    """
    if fonts is None:
        fonts = {"title": "DejaVuSans.ttf", "body": "DejaVuSans.ttf"}

    # --- Dimensiones ---
    if aspect_ratio == "9:16":
        width, height = 1080, 1920
    else:
        width, height = 1920, 1080

    # --- Cargar explainer ---
    explainer_img = _load_explainer(explainer_style, explainer_pose)
    has_explainer = explainer_img is not None

    # --- Distribución horizontal según presencia del explainer ---
    if has_explainer:
        # Explainer: 4% - 26% del ancho. Separación: 26% - 32%.
        # Pizarra: 32% - 82% (deja 18% de margen a la derecha).
        explainer_left = int(width * 0.04)
        explainer_zone_w = int(width * 0.22)
        board_left = int(width * 0.32)
        board_right = int(width * 0.80)
    else:
        # Sin explainer, la pizarra ocupa una franja centrada y más estrecha.
        board_left = int(width * 0.15)
        board_right = int(width * 0.85)

    board_top = int(height * 0.12)
    board_bottom = int(height * 0.88)
    board_w = board_right - board_left
    board_h = board_bottom - board_top

    # --- Crear lienzo ---
    img = Image.new("RGB", (width, height), COLOR_BG)
    draw = ImageDraw.Draw(img)

    # --- Pegar explainer primero (queda por debajo en z-order) ---
    if has_explainer:
        target_h = int(board_h * 0.80)
        orig_w, orig_h = explainer_img.size
        scale = target_h / orig_h
        target_w = int(orig_w * scale)
        explainer_img = explainer_img.resize((target_w, target_h), Image.LANCZOS)

        explainer_y = board_top + (board_h - target_h) // 2
        explainer_x = explainer_left + (explainer_zone_w - target_w) // 2

        img.paste(explainer_img, (explainer_x, explainer_y), explainer_img)
        print(f"   ✔ Explainer pegado en ({explainer_x}, {explainer_y}), tamaño {target_w}x{target_h}")

    # --- Dibujar la pizarra ---
    outline_w = max(4, int(height * 0.006))
    draw.rectangle(
        [board_left, board_top, board_right, board_bottom],
        fill=COLOR_BOARD,
        outline=COLOR_BOARD_OUTLINE,
        width=outline_w,
    )

    # --- Renderizar bullets ---
    bullets: List[str] = []
    if overlay_content:
        bullets = overlay_content.get("bullets") or []
        # Aceptar también el formato antiguo con título y bullets
        # (por si algún LLM devuelve estructura mixta)
        legacy_title = overlay_content.get("title")
        if not bullets and legacy_title:
            bullets = [legacy_title]

    if not bullets:
        print(f"   ⚠️ Escena {scene_num}: code_graphic_visual sin bullets. Pizarra vacía.")

    # --- Configuración tipográfica ---
    font_size_bullet = max(38, int(height * 0.050))     # bullets grandes
    bullet_font = load_font(fonts["body"], font_size_bullet)

    # Padding interno de la pizarra
    padding_x = int(board_w * 0.06)
    padding_y = int(board_h * 0.08)
    max_text_w = board_w - (padding_x * 2)

    # --- Envolver y medir todas las líneas ---
    line_h = int(font_size_bullet * 1.6)
    wrapped_items: List[List[str]] = []
    for bullet in bullets:
        # Prefijar con guión grande para que se vea como una lista en pizarra
        bullet_text = f"— {bullet}" if not bullet.startswith("—") else bullet
        wrapped_items.append(
            wrap_text_by_pixel_width(bullet_text, bullet_font, max_text_w)
        )

    total_lines = sum(len(item) for item in wrapped_items)
    gap_between_bullets = int(line_h * 0.6)
    total_text_h = total_lines * line_h
    if len(wrapped_items) > 1:
        total_text_h += (len(wrapped_items) - 1) * gap_between_bullets

    # --- Centrado vertical dentro del área útil (descontando padding) ---
    usable_top = board_top + padding_y
    usable_bottom = board_bottom - padding_y
    usable_h = usable_bottom - usable_top
    curr_y = usable_top + max(0, (usable_h - total_text_h) // 2)

    # --- Centrado horizontal: medir el ancho máximo de las líneas envueltas ---
    max_line_w = 0
    for item_lines in wrapped_items:
        for line in item_lines:
            try:
                bbox = bullet_font.getbbox(line)
                w = bbox[2] - bbox[0]
            except AttributeError:
                w = len(line) * (font_size_bullet * 0.55)
            if w > max_line_w:
                max_line_w = w

    # Centrar el bloque completo dentro de la pizarra
    text_x = board_left + (board_w - max_line_w) // 2

    # --- Dibujar cada bullet ---
    for item_lines in wrapped_items:
        for idx, line in enumerate(item_lines):
            indent = 0 if idx == 0 else int(font_size_bullet * 0.6)
            draw.text(
                (text_x + indent, curr_y),
                line,
                font=bullet_font,
                fill=COLOR_BULLET_TEXT,
            )
            curr_y += line_h
        curr_y += gap_between_bullets

    # --- Guardar ---
    fmt = "PNG" if output_path.lower().endswith(".png") else "JPEG"
    img.save(output_path, fmt, quality=95)
    print(f"   🎨 Pizarra 'code_graphic_visual' generada: {output_path}")