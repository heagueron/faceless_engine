"""
Generador de respaldo local (Pillow) cuando el proveedor remoto falla.
"""

from PIL import Image, ImageDraw


def create_fallback_image(
    output_path: str,
    scene_num: int,
    text: str,
    aspect_ratio: str = "16:9"
) -> None:
    """Crea una imagen local usando Pillow como respaldo infalible."""
    if aspect_ratio == "9:16":
        width, height = 1080, 1920
    else:
        width, height = 1920, 1080

    img = Image.new('RGB', (width, height), color=(18, 22, 30))
    draw = ImageDraw.Draw(img)

    draw.rectangle([40, 40, width - 40, height - 40], outline=(60, 80, 110), width=6)

    label = f"ESCENA {scene_num}" if scene_num > 0 else "THUMBNAIL"
    draw.text((width // 4, height // 2 - 50), label, fill=(255, 200, 80))

    fmt = "PNG" if output_path.lower().endswith(".png") else "JPEG"
    img.save(output_path, fmt, quality=90)