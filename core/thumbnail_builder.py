import os
import json
import argparse
from typing import Optional, Tuple, List
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance


# ==============================================================================
# CONFIGURACIÓN GENERAL Y BUSCADOR DE FUENTES
# ==============================================================================
DEFAULT_TEXT_COLOR = "#FFDE00"  # Amarillo vibrante de alto impacto
DEFAULT_STROKE_COLOR = "#000000"  # Trazo negro
DEFAULT_POSITION = "top"  # 'top', 'bottom', 'center'

# Búsqueda de fuentes gruesas sin serifa en el sistema (compatible con Linux/Debian/Crostini y Windows)
SYSTEM_FONT_PATHS = [
    # Linux / Crostini (Debian)
    "/usr/share/fonts/truetype/msttcorefonts/Impact.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    # Windows
    "C:\\Windows\\Fonts\\impact.ttf",
    "C:\\Windows\\Fonts\\ariblk.ttf",
    "C:\\Windows\\Fonts\\arialbd.ttf",
    # macOS
    "/Library/Fonts/Impact.ttf",
    "/System/Library/Fonts/Supplemental/Arial Black.ttf",
]


def get_current_project_dir() -> str:
    """Carga automáticamente la ruta del proyecto activo desde output/current_project.json."""
    current_json_path = os.path.join("output", "current_project.json")
    if os.path.exists(current_json_path):
        try:
            with open(current_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                project_dir = data.get("project_dir")
                if project_dir and os.path.exists(project_dir):
                    print(f"📁 Proyecto activo cargado automáticamente: '{project_dir}'")
                    return project_dir
        except Exception as e:
            print(f"⚠️ Error al leer '{current_json_path}': {e}")

    raise FileNotFoundError(
        "No se especificó --project_dir y no se encontró un proyecto válido en 'output/current_project.json'."
    )


def load_heavy_font(font_size: int, custom_font_path: Optional[str] = None) -> ImageFont.FreeTypeFont:
    """Intenta cargar una fuente Sans-Serif gruesa o regresa la fuente por defecto de Pillow."""
    if custom_font_path and os.path.exists(custom_font_path):
        try:
            return ImageFont.truetype(custom_font_path, font_size)
        except Exception:
            pass

    for path in SYSTEM_FONT_PATHS:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, font_size)
            except Exception:
                continue

    # Si no se encuentra ninguna fuente vectorial en el sistema, intenta cargar por defecto
    try:
        return ImageFont.load_default(size=font_size)
    except TypeError:
        return ImageFont.load_default()


# ==============================================================================
# ALGORITMO DE ENVOLTURA Y AJUSTE DINÁMICO DE TEXTO
# ==============================================================================
def wrap_text_to_lines(text: str, font: ImageFont.ImageFont, max_width: int, draw: ImageDraw.ImageDraw) -> List[str]:
    """Divide el texto en múltiples líneas si excede el ancho máximo."""
    words = text.strip().upper().split()
    if not words:
        return []

    lines = []
    current_line = []

    for word in words:
        test_line = " ".join(current_line + [word])
        bbox = draw.textbbox((0, 0), test_line, font=font)
        line_width = bbox[2] - bbox[0]

        if line_width <= max_width or not current_line:
            current_line.append(word)
        else:
            lines.append(" ".join(current_line))
            current_line = [word]

    if current_line:
        lines.append(" ".join(current_line))

    return lines


def calculate_dynamic_font(
    text: str,
    img_width: int,
    img_height: int,
    draw: ImageDraw.ImageDraw,
    max_width_ratio: float = 0.85,
    max_height_ratio: float = 0.35,
    custom_font_path: Optional[str] = None
) -> Tuple[ImageFont.FreeTypeFont, List[str], int, int]:
    """
    Calcula dinámicamente el tamaño de fuente óptimo para que el texto ocupe el área
    deseada sin desbordarse ni tapar la escena.
    """
    max_width = int(img_width * max_width_ratio)
    max_height = int(img_height * max_height_ratio)

    font_size = int(img_height * 0.16)  # Tamaño inicial grande
    min_font_size = 28

    while font_size >= min_font_size:
        font = load_heavy_font(font_size, custom_font_path)
        lines = wrap_text_to_lines(text, font, max_width, draw)

        if not lines:
            break

        # Calcular dimensiones totales del bloque de texto
        total_height = 0
        max_line_w = 0
        line_heights = []

        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            if w > max_line_w:
                max_line_w = w
            line_heights.append(h)

        line_spacing = int(font_size * 0.15)
        total_height = sum(line_heights) + (len(lines) - 1) * line_spacing

        if max_line_w <= max_width and total_height <= max_height:
            return font, lines, max_line_w, total_height

        font_size -= 4

    # Respaldo con tamaño mínimo
    font = load_heavy_font(min_font_size, custom_font_path)
    lines = wrap_text_to_lines(text, font, max_width, draw)
    return font, lines, max_width, int(img_height * 0.1)


# ==============================================================================
# COMPOSICIÓN Y RENDERIZADO VISUAL
# ==============================================================================
def render_thumbnail(
    raw_image_path: str,
    output_image_path: str,
    text: str,
    position: str = DEFAULT_POSITION,
    text_color: str = DEFAULT_TEXT_COLOR,
    stroke_color: str = DEFAULT_STROKE_COLOR,
    custom_font_path: Optional[str] = None
) -> bool:
    """Compone la miniatura añadiendo tipografía gruesa, trazo exterior y sombra paralela."""
    if not os.path.exists(raw_image_path):
        print(f"❌ Error: No se encontró la imagen de origen '{raw_image_path}'.")
        return False

    if not text.strip():
        print("⚠️ Advertencia: 'thumbnail_text' está vacío. Copiando imagen cruda sin modificaciones.")
        img = Image.open(raw_image_path)
        img.save(output_image_path, "PNG")
        return True

    try:
        base_img = Image.open(raw_image_path).convert("RGBA")
        width, height = base_img.size

        # Crear capa transparente para renderizado de texto y efectos
        text_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(text_layer)

        # 1. Ajustar fuente y líneas dinámicamente
        font, lines, text_block_w, text_block_h = calculate_dynamic_font(
            text, width, height, draw, custom_font_path=custom_font_path
        )

        font_size = getattr(font, "size", int(height * 0.1))
        stroke_width = max(4, int(font_size * 0.08))  # Trazo proporcional grueso
        shadow_offset = max(5, int(font_size * 0.06))  # Desplazamiento de sombra

        # 2. Determinar coordenada Y según posición
        # Nota: En YouTube, el timestamp cubre el extremo inferior derecho; por defecto "top" o "bottom" ajustado es ideal.
        if position == "top":
            y_start = int(height * 0.08)
        elif position == "center":
            y_start = (height - text_block_h) // 2
        else:  # bottom
            y_start = height - text_block_h - int(height * 0.12)

        line_spacing = int(font_size * 0.15)
        current_y = y_start

        # 3. Dibujar sombra paralela suave
        shadow_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow_layer)

        for line in lines:
            bbox = shadow_draw.textbbox((0, 0), line, font=font)
            line_w = bbox[2] - bbox[0]
            line_h = bbox[3] - bbox[1]
            x = (width - line_w) // 2  # Centrado horizontal

            # Dibujar sombra desplazada
            shadow_draw.text(
                (x + shadow_offset, current_y + shadow_offset),
                line,
                font=font,
                fill=(0, 0, 0, 210),
                stroke_width=stroke_width,
                stroke_fill=(0, 0, 0, 210),
                align="center"
            )
            current_y += line_h + line_spacing

        # Aplicar desenfoque leve a la sombra para suavizar bordes
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=3))

        # 4. Dibujar texto principal con trazo (stroke)
        current_y = y_start
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            line_w = bbox[2] - bbox[0]
            line_h = bbox[3] - bbox[1]
            x = (width - line_w) // 2

            draw.text(
                (x, current_y),
                line,
                font=font,
                fill=text_color,
                stroke_width=stroke_width,
                stroke_fill=stroke_color,
                align="center"
            )
            current_y += line_h + line_spacing

        # 5. Fusionar capas (Base + Sombra + Texto)
        final_img = Image.alpha_composite(base_img, shadow_layer)
        final_img = Image.alpha_composite(final_img, text_layer).convert("RGB")

        # Guardar en formato PNG listo para publicar
        final_img.save(output_image_path, "PNG", quality=95)
        print(f"   ✔ Miniatura final compuesta con éxito: {output_image_path}")
        return True

    except Exception as e:
        print(f"❌ Error al componer la miniatura: {e}")
        return False


# ==============================================================================
# PROCESO PRINCIPAL
# ==============================================================================
def build_project_thumbnail(
    project_dir: str,
    text_override: Optional[str] = None,
    position: str = DEFAULT_POSITION,
    text_color: str = DEFAULT_TEXT_COLOR,
    custom_font: Optional[str] = None
):
    """Carga manifest.json del proyecto y procesa la miniatura final."""
    manifest_path = os.path.join(project_dir, "manifest.json")
    if not os.path.exists(manifest_path):
        raise FileNotFoundError(f"No se encontró manifest.json en: {project_dir}")

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    images_dir = os.path.join(project_dir, "images")
    os.makedirs(images_dir, exist_ok=True)

    # Identificar la imagen cruda de origen
    raw_path_candidates = [
        manifest.get("thumbnail_raw_path"),
        os.path.join(images_dir, "thumbnail_raw.png"),
        os.path.join(images_dir, "thumbnail_raw.jpg"),
        os.path.join(images_dir, "scene_1.jpg")  # Respaldo de emergencia si no existe thumbnail_raw
    ]

    raw_image_path = None
    for candidate in raw_path_candidates:
        if candidate and os.path.exists(candidate):
            raw_image_path = candidate
            break

    if not raw_image_path:
        raise FileNotFoundError("No se encontró ninguna imagen 'thumbnail_raw' ni 'scene_1.jpg' en el proyecto.")

    thumbnail_text = text_override or manifest.get("thumbnail_text", "")

    # Rutas de salida para el resultado final
    final_thumbnail_path_images = os.path.join(images_dir, "thumbnail.png")
    final_thumbnail_path_root = os.path.join(project_dir, "thumbnail.png")

    print("\n" + "=" * 80)
    print(" 🎨 COMPONIENDO MINIATURA GRÁFICA (thumbnail.png)")
    print(f" 📂 Imagen Origen: {os.path.basename(raw_image_path)}")
    print(f" 🔤 Texto del Gancho: \"{thumbnail_text}\"")
    print(f" 📍 Posición: {position.upper()} | Color: {text_color}")
    print("=" * 80)

    success = render_thumbnail(
        raw_image_path=raw_image_path,
        output_image_path=final_thumbnail_path_images,
        text=thumbnail_text,
        position=position,
        text_color=text_color,
        custom_font_path=custom_font
    )

    if success:
        # Copiar también a la raíz del directorio del proyecto para acceso rápido
        if os.path.exists(final_thumbnail_path_images):
            Image.open(final_thumbnail_path_images).save(final_thumbnail_path_root, "PNG")

        # Actualizar manifest.json con la ubicación oficial
        manifest["thumbnail_path"] = final_thumbnail_path_images
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

        print("\n✔ Guardada en:")
        print(f"   • {final_thumbnail_path_images}")
        print(f"   • {final_thumbnail_path_root}")
        print("✔ Manifest.json actualizado con 'thumbnail_path'.")
    print("=" * 80)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compositor Gráfico de Miniaturas para Faceless Engine")
    parser.add_argument("--project_dir", type=str, default=None, help="Directorio del proyecto")
    parser.add_argument("--text", type=str, default=None, help="Anular texto del gancho de la miniatura")
    parser.add_argument("--position", type=str, default=DEFAULT_POSITION, choices=["top", "center", "bottom"], help="Ubicación del texto")
    parser.add_argument("--color", type=str, default=DEFAULT_TEXT_COLOR, help="Color del texto en formato HEX (ej. #FFDE00)")
    parser.add_argument("--font", type=str, default=None, help="Ruta a archivo .ttf o .otf personalizado")

    args = parser.parse_args()
    target_project_dir = args.project_dir or get_current_project_dir()

    build_project_thumbnail(
        project_dir=target_project_dir,
        text_override=args.text,
        position=args.position,
        text_color=args.color,
        custom_font=args.font
    )