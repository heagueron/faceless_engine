import os
import re
import json
import time
import base64
import argparse
import textwrap
import requests
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

from core.config import get_language_directive

load_dotenv()

try:
    import fal_client
except ImportError:
    fal_client = None


# ==============================================================================
# CONFIGURACIÓN GENERAL Y PROVEEDOR POR DEFECTO
# ==============================================================================
DEFAULT_IMAGE_PROVIDER = "fal"

DEFAULT_MODELS = {
    "openrouter": "qwen/qwen-image-3",
    "fal": "fal-ai/flux-1/schnell"
}
# ==============================================================================




def parse_scene_input(scene_str: str) -> List[int]:
    """
    Soporta formatos:
    - Individual: '3' -> [3]
    - Rango: '1-10' -> [1, 2, ..., 10]
    - Lista: '1,3,5' -> [1, 3, 5]
    - Mixto: '1-3,5,8-10' -> [1, 2, 3, 5, 8, 9, 10]
    """
    scenes = set()
    for part in scene_str.split(','):
        part = part.strip()
        if not part:
            continue
        if '-' in part:
            try:
                start, end = part.split('-', 1)
                scenes.update(range(int(start), int(end) + 1))
            except ValueError:
                pass
        elif part.isdigit():
            scenes.add(int(part))
    return sorted(list(scenes))


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

def enforce_style_in_prompt(prompt: str, manifest: Dict[str, Any]) -> str:
    """
    Verifica que el prompt contenga el estilo declarado en el manifest.
    Si no, lo inyecta como prefijo. Esto protege contra:
      - LLMs que omiten el estilo
      - Ediciones manuales del manifest
      - Proyectos viejos sin 'visual_style_prompt'
    """
    if not prompt:
        return prompt

    style_prompt = manifest.get("visual_style_prompt", "").strip()
    if not style_prompt:
        return prompt

    # Heurística: primeras 30 chars del estilo deben aparecer en el prompt
    marker = style_prompt[:30].lower()
    if marker not in prompt.lower():
        print(f"   🔧 Estilo ausente en prompt. Inyectando: '{style_prompt[:50]}...'")
        prompt = f"{style_prompt} {prompt}"
    return prompt

def wrap_text_by_pixel_width(text: str, font: ImageFont.FreeTypeFont, max_width_px: int) -> List[str]:
    """
    Enuelve el texto midiendo el ancho real en píxeles de cada línea usando la fuente dada.
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
                # Si una sola palabra es más ancha que la tarjeta, la fuerza a entrar
                lines.append(word)
                current_line = []

    if current_line:
        lines.append(" ".join(current_line))

    return lines

def apply_split_right_overlay(image_path: str, overlay_content: Dict[str, Any]) -> None:
    if not overlay_content or not os.path.exists(image_path):
        return

    title = overlay_content.get("title")
    bullets = overlay_content.get("bullets", [])

    if not title and not bullets:
        return

    try:
        with Image.open(image_path) as base_img:
            img = base_img.convert("RGBA")
            width, height = img.size

            card_left = int(width * 0.67)
            card_top = int(height * 0.10)
            card_right = int(width * 0.97)
            card_bottom = int(height * 0.90)

            card_overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
            draw_card = ImageDraw.Draw(card_overlay)

            draw_card.rounded_rectangle(
                [card_left, card_top, card_right, card_bottom],
                radius=18,
                fill=(15, 23, 42, 225),
                outline=(51, 65, 85, 255),
                width=0 # sin borde (antes 3)
            )

            img = Image.alpha_composite(img, card_overlay)
            draw = ImageDraw.Draw(img)

            font_size_title = max(24, int(height * 0.045))
            font_size_bullets = max(18, int(height * 0.032))

            try:
                title_font = ImageFont.truetype("DejaVuSans-Bold.ttf", font_size_title)
                bullet_font = ImageFont.truetype("DejaVuSans.ttf", font_size_bullets)
            except IOError:
                try:
                    title_font = ImageFont.truetype("arial.ttf", font_size_title)
                    bullet_font = ImageFont.truetype("arial.ttf", font_size_bullets)
                except IOError:
                    title_font = ImageFont.load_default()
                    bullet_font = ImageFont.load_default()

            padding_x = int(width * 0.02)
            padding_y = int(height * 0.04)
            curr_y = card_top + padding_y

            # Calcular el ancho máximo disponible en píxeles dentro de la tarjeta
            max_text_width_px = (card_right - card_left) - (padding_x * 2)

            # 1. RENDERIZAR TÍTULO CON MEDICIÓN DE PÍXELES
            if title:
                # Ajuste automático del tamaño de fuente si una sola palabra no cabe
                for word in title.split():
                    try:
                        w = title_font.getbbox(word.upper())[2] - title_font.getbbox(word.upper())[0]
                    except AttributeError:
                        w = len(word) * (font_size_title * 0.65)
                    
                    if w > max_text_width_px:
                        # Reducir dinámicamente la fuente si hay palabras gigantes
                        font_size_title = int(font_size_title * (max_text_width_px / w) * 0.9)
                        title_font = ImageFont.truetype("DejaVuSans-Bold.ttf", font_size_title)

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

            # 2. RENDERIZAR BULLETS CON MEDICIÓN DE PÍXELES
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

def create_fallback_image(output_path: str, scene_num: int, text: str, aspect_ratio: str = "16:9"):
    """Crea una imagen local usando Pillow como respaldo infalible respetando la relación de aspecto."""
    if aspect_ratio == "9:16":
        width, height = 1080, 1920
    else:
        width, height = 1920, 1080

    img = Image.new('RGB', (width, height), color=(18, 22, 30))
    draw = ImageDraw.Draw(img)
    
    # Borde decorativo
    draw.rectangle([40, 40, width - 40, height - 40], outline=(60, 80, 110), width=6)
    
    # Texto descriptivo
    label = f"ESCENA {scene_num}" if scene_num > 0 else "THUMBNAIL"
    draw.text((width // 4, height // 2 - 50), label, fill=(255, 200, 80))
    
    fmt = "PNG" if output_path.lower().endswith(".png") else "JPEG"
    img.save(output_path, fmt, quality=90)


def generate_image_via_openrouter(
    prompt: str,
    output_path: str,
    model: str = "qwen/qwen-image-3",
    aspect_ratio: str = "16:9",
    max_retries: int = 3,
    retry_delay: float = 3.0,
    request_timeout: int = 120
) -> bool:
    """Genera una imagen utilizando la API de OpenRouter."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("   ❌ Error: OPENROUTER_API_KEY no encontrada en .env")
        return False

    lang_directive = get_language_directive()
    if "CRITICAL INSTRUCTION" not in prompt:
        prompt = f"{prompt.rstrip('.')}. {lang_directive}"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/faceless-engine",
        "X-Title": "Faceless Engine"
    }

    current_delay = retry_delay

    for attempt in range(1, max_retries + 1):
        try:
            url_img = "https://openrouter.ai/api/v1/images/generations"
            payload_img = {
                "model": model,
                "prompt": prompt,
                "aspect_ratio": aspect_ratio
            }
            
            res = requests.post(url_img, headers=headers, json=payload_img, timeout=request_timeout)

            if res.status_code == 200:
                data = res.json()
                items = data.get("data", [])
                if items:
                    first_item = items[0]
                    if "url" in first_item and first_item["url"]:
                        img_res = requests.get(first_item["url"], timeout=45)
                        if img_res.status_code == 200 and len(img_res.content) > 1000:
                            with open(output_path, "wb") as f:
                                f.write(img_res.content)
                            return True
                    elif "b64_json" in first_item:
                        b64_data = first_item["b64_json"]
                        with open(output_path, "wb") as f:
                            f.write(base64.b64decode(b64_data))
                        return True

            url_chat = "https://openrouter.ai/api/v1/chat/completions"
            payload_chat = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "modalities": ["image"]
            }
            res_chat = requests.post(url_chat, headers=headers, json=payload_chat, timeout=request_timeout)
            if res_chat.status_code == 200:
                chat_data = res_chat.json()
                choices = chat_data.get("choices", [])
                if choices:
                    msg = choices[0].get("message", {})
                    content = msg.get("content", "")
                    
                    urls = re.findall(r'https?://[^\s\)]+', content)
                    msg_images = msg.get("images", [])
                    if msg_images and isinstance(msg_images, list):
                        for img_obj in msg_images:
                            if isinstance(img_obj, dict) and "url" in img_obj:
                                urls.append(img_obj["url"])
                            elif isinstance(img_obj, str):
                                urls.append(img_obj)

                    for url_candidate in urls:
                        img_res = requests.get(url_candidate, timeout=45)
                        if img_res.status_code == 200 and len(img_res.content) > 1000:
                            with open(output_path, "wb") as f:
                                f.write(img_res.content)
                            return True

            if res.status_code == 429 or res_chat.status_code == 429:
                print(f"   ⏳ Rate Limit (429) en OpenRouter. Reintentando en {current_delay:.1f}s (Intento {attempt}/{max_retries})...")
            else:
                print(f"   ⚠️ OpenRouter status: {res.status_code} / chat status: {res_chat.status_code}")

        except requests.exceptions.Timeout:
            print(f"   ⏳ Timeout ({request_timeout}s alcanzado). Reintentando ({attempt}/{max_retries})...")
        except Exception as e:
            print(f"   ⚠️ Fallo en llamada OpenRouter (Intento {attempt}/{max_retries}): {e}")

        if attempt < max_retries:
            time.sleep(current_delay)
            current_delay *= 1.5

    return False


def generate_image_via_fal(
    prompt: str,
    output_path: str,
    model: str = "fal-ai/flux-1/schnell",
    aspect_ratio: str = "16:9",
    max_retries: int = 3,
    retry_delay: float = 3.0
) -> bool:
    """Solicita la generación de imagen a fal.ai."""
    fal_key = os.getenv("FAL_KEY") or os.getenv("FAL_API_KEY")
    if not fal_key:
        print("   ❌ Error: FAL_KEY o FAL_API_KEY no encontrada en .env")
        return False

    os.environ["FAL_KEY"] = fal_key

    lang_directive = get_language_directive()
    if "CRITICAL INSTRUCTION" not in prompt:
        prompt = f"{prompt.rstrip('.')}. {lang_directive}"

    image_size = "portrait_16_9" if aspect_ratio == "9:16" else "landscape_16_9"
    current_delay = retry_delay

    for attempt in range(1, max_retries + 1):
        try:
            if fal_client is not None:
                result = fal_client.subscribe(
                    model,
                    arguments={
                        "prompt": prompt,
                        "image_size": image_size,
                        "num_inference_steps": 4 if "schnell" in model else 28,
                        "enable_safety_checker": False
                    }
                )
                images = result.get("images", [])
                if images and "url" in images[0]:
                    img_url = images[0]["url"]
                    res = requests.get(img_url, timeout=30)
                    if res.status_code == 200 and len(res.content) > 1000:
                        with open(output_path, "wb") as f:
                            f.write(res.content)
                        return True
            else:
                url = f"https://fal.run/{model}"
                headers = {
                    "Authorization": f"Key {fal_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "prompt": prompt,
                    "image_size": image_size,
                    "num_inference_steps": 4 if "schnell" in model else 28,
                    "enable_safety_checker": False
                }
                res = requests.post(url, headers=headers, json=payload, timeout=60)
                if res.status_code == 200:
                    data = res.json()
                    images = data.get("images", [])
                    if images and "url" in images[0]:
                        img_url = images[0]["url"]
                        img_res = requests.get(img_url, timeout=30)
                        if img_res.status_code == 200 and len(img_res.content) > 1000:
                            with open(output_path, "wb") as f:
                                f.write(img_res.content)
                            return True
                elif res.status_code == 429:
                    print(f"   ⏳ Rate Limit (429) en fal.ai. Reintentando en {current_delay:.1f}s (Intento {attempt}/{max_retries})...")
                    time.sleep(current_delay)
                    current_delay *= 1.5
                    continue

        except Exception as e:
            print(f"   ⚠️ Fallo en llamada API (Intento {attempt}/{max_retries}): {e}")

        if attempt < max_retries:
            time.sleep(current_delay)
            current_delay *= 1.5

    return False


def is_valid_image_file(path: str) -> bool:
    """Verifica si un archivo existe y es una imagen válida de tamaño > 100 bytes."""
    if not os.path.exists(path):
        return False
    if os.path.getsize(path) < 100:
        return False
    try:
        with Image.open(path) as img:
            img.verify()
        return True
    except Exception:
        return False


def process_thumbnail(
    project_dir: str,
    manifest: Dict[str, Any],
    provider_key: str,
    selected_model: str,
    aspect_ratio: str,
    max_retries: int = 3,
    force: bool = False
) -> bool:
    """Procesa la imagen cruda de la miniatura (thumbnail_raw.jpg)."""
    thumbnail_prompt = manifest.get("thumbnail_prompt")
    if not thumbnail_prompt:
        print("⚠️ 'thumbnail_prompt' no encontrado en manifest.json. Omitiendo miniatura.")
        return False

    images_dir = os.path.join(project_dir, "images")
    output_path = os.path.join(images_dir, "thumbnail_raw.jpg")

    if not force and is_valid_image_file(output_path):
        print(f"\n⏭️ Miniatura ya existe y es válida ('thumbnail_raw.jpg'). Omitiendo por Checkpoint.")
        manifest["thumbnail_raw_path"] = output_path
        return True

    print("\n🖼️ Procesando Miniatura Cruda (Thumbnail)...")

    thumbnail_prompt = enforce_style_in_prompt(thumbnail_prompt, manifest)

    print(f"   Prompt: \"{thumbnail_prompt[:90]}...\"")

    if provider_key == "openrouter":
        success = generate_image_via_openrouter(
            prompt=thumbnail_prompt,
            output_path=output_path,
            model=selected_model,
            aspect_ratio=aspect_ratio,
            max_retries=max_retries
        )
    else:
        success = generate_image_via_fal(
            prompt=thumbnail_prompt,
            output_path=output_path,
            model=selected_model,
            aspect_ratio=aspect_ratio,
            max_retries=max_retries
        )

    if success:
        print(f"   ✔ Miniatura cruda generada con éxito ({provider_key.upper()}): {output_path}")
    else:
        print("   ⚠️ Falló la generación en línea tras reintentos. Generando respaldo local (Pillow)...")
        create_fallback_image(output_path, 0, manifest.get("thumbnail_text", "THUMBNAIL"), aspect_ratio=aspect_ratio)
        print(f"   ✔ Respaldo de miniatura guardado en: {output_path}")

    manifest["thumbnail_raw_path"] = output_path
    return True

def render_code_graphic_card(
    output_path: str,
    scene_num: int,
    overlay_content: Optional[Dict[str, Any]],
    aspect_ratio: str = "16:9"
) -> None:
    """
    Renderiza una tarjeta visual de texto/código (layout 'code_graphic')
    como una página blanca limpia, con el contenido centrado y en tinta oscura.
    """
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

    # Lienzo blanco puro, sin bordes ni marcos
    INK = (15, 23, 42)          # slate-900, tinta principal
    ACCENT = (250, 204, 21)     # amarillo de acento solo para el título

    # img = Image.new('RGB', (width, height), color=(255, 255, 255))
    img = Image.new('RGB', (width, height), color=(186, 171, 156))
    draw = ImageDraw.Draw(img)

    # Carga de fuentes
    try:
        title_font = ImageFont.truetype("DejaVuSans-Bold.ttf", font_size_title)
        bullet_font = ImageFont.truetype("DejaVuSans.ttf", font_size_bullets)
    except IOError:
        try:
            title_font = ImageFont.truetype("arial.ttf", font_size_title)
            bullet_font = ImageFont.truetype("arial.ttf", font_size_bullets)
        except IOError:
            title_font = ImageFont.load_default()
            bullet_font = ImageFont.load_default()

    title = overlay_content.get("title") if overlay_content else f"ESCENA {scene_num}"
    bullets = overlay_content.get("bullets", []) if overlay_content else []

    wrapped_title_lines = textwrap.wrap(title.upper(), width=max_title_chars) if title else []

    wrapped_bullet_items = []
    if bullets:
        for b in bullets:
            wrapped_bullet_items.append(textwrap.wrap(f"• {b}", width=max_bullet_chars))

    # --- CÁLCULO DE ALTURA TOTAL PARA CENTRADO VERTICAL ---
    line_h_title = int(font_size_title * 1.35)
    line_h_bullet = int(font_size_bullets * 1.55)
    sep_space = int(height * 0.06)

    total_h = 0
    if wrapped_title_lines:
        total_h += (len(wrapped_title_lines) * line_h_title) + sep_space
    for item_lines in wrapped_bullet_items:
        total_h += (len(item_lines) * line_h_bullet) + int(height * 0.025)

    # Área útil de la "página" (márgenes generosos, sin marcos)
    page_left = int(width * 0.10)
    page_right = int(width * 0.90)
    page_top = int(height * 0.12)
    page_bottom = int(height * 0.88)
    content_area_h = page_bottom - page_top

    curr_y = page_top + max(0, (content_area_h - total_h) // 2)
    center_x = (page_left + page_right) // 2

    # 1. TÍTULO (centrado horizontal, con acento de color)
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

    # 2. BULLETS (bloque centrado, tinta oscura)
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

def process_scene_media(
    project_dir: str,
    provider: str = DEFAULT_IMAGE_PROVIDER,
    model: Optional[str] = None,
    max_retries: int = 3,
    target_scenes: Optional[List[int]] = None,
    only_thumbnail: bool = False,
    force: bool = False,
    rate_limit_delay: float = 1.0
):
    """Procesa escenas y/o miniatura del manifest.json aplicando overlays de texto según el layout."""
    
    provider_key = provider.lower().strip()
    if provider_key not in ["openrouter", "fal"]:
        print(f"⚠️ Proveedor '{provider}' no válido. Usando '{DEFAULT_IMAGE_PROVIDER}'.")
        provider_key = DEFAULT_IMAGE_PROVIDER

    selected_model = model or DEFAULT_MODELS[provider_key]

    manifest_path = os.path.join(project_dir, "manifest.json")
    if not os.path.exists(manifest_path):
        raise FileNotFoundError(f"No se encontró manifest.json en: {project_dir}")

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    images_dir = os.path.join(project_dir, "images")
    os.makedirs(images_dir, exist_ok=True)

    aspect_ratio = manifest.get("aspect_ratio", "16:9")

    if manifest.get("visual_style"):
        print(f"🎨 Estilo del proyecto: '{manifest['visual_style']}'")
    else:
        print("⚠️ manifest.json no tiene 'visual_style'. Se asume estilo legacy.")

    print("\n" + "=" * 80)
    print(f" 🖼️ GENERANDO RECURSOS VISUALES MEDIANTE {provider_key.upper()} ({selected_model})")
    print(f" 📐 Aspect Ratio: {aspect_ratio}")
    if only_thumbnail:
        print(" 🎯 MODO SOLO MINIATURA (--only-thumbnail) ACTIVADO")
    elif target_scenes:
        print(f" 🎯 MODO SELECCIÓN DE ESCENAS: Procesando {len(target_scenes)} escena(s): {target_scenes}")
    if force:
        print(" 🔄 Modo FORCED activado: Re-generando imágenes seleccionadas.")
    print("=" * 80)

    if only_thumbnail:
        process_thumbnail(project_dir, manifest, provider_key, selected_model, aspect_ratio, max_retries, force)
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        print("\n✔ Procesamiento de miniatura finalizado.")
        return

    all_scenes = manifest.get("scenes", [])
    if not all_scenes:
        print("⚠️ No hay escenas en manifest.json")
        return

    if target_scenes:
        scenes_to_process = [s for s in all_scenes if s.get("scene_number") in target_scenes]
        if not scenes_to_process:
            print(f"❌ Ninguna de las escenas solicitadas ({target_scenes}) existe en el manifest.")
            return
    else:
        scenes_to_process = all_scenes

    processed_count = 0
    skipped_count = 0

    for scene in scenes_to_process:
        idx = scene.get("scene_number", 1)
        layout_type = scene.get("layout_type", "full_art")
        visual_prompt = scene.get("visual_prompt") or "minimalist 2D vector graphic"
        narration = scene.get("narration_text", "")
        overlay_content = scene.get("overlay_content")
        image_filename = f"scene_{idx}.jpg"
        image_path = os.path.join(images_dir, image_filename)

        # En process_scene_media, dentro del loop:
        

        # Checkpoint: Si la imagen existe y es válida, verificamos si requiere estampado de overlay antes de omitir
        if not force and is_valid_image_file(image_path):
            if layout_type == "split_right" and overlay_content:
                apply_split_right_overlay(image_path, overlay_content)
            print(f"\n⏭️ Escena {idx}: Imagen lista ('{image_filename}'). Omitiendo por Checkpoint.")
            scene["image_path"] = image_path
            skipped_count += 1
            continue

        print(f"\n🖼️ Procesando Escena {idx} [{layout_type.upper()}]...")

        visual_prompt = enforce_style_in_prompt(visual_prompt, manifest)

        if layout_type == "code_graphic":
            print("   📊 Escena tipo 'code_graphic'. Generando tarjeta de texto...")
            render_code_graphic_card(image_path, idx, overlay_content, aspect_ratio=aspect_ratio)
            success = True
        else:
            print(f"   Prompt: \"{visual_prompt[:90]}...\"")
            if provider_key == "openrouter":
                success = generate_image_via_openrouter(
                    prompt=visual_prompt,
                    output_path=image_path,
                    model=selected_model,
                    aspect_ratio=aspect_ratio,
                    max_retries=max_retries
                )
            else:
                success = generate_image_via_fal(
                    prompt=visual_prompt,
                    output_path=image_path,
                    model=selected_model,
                    aspect_ratio=aspect_ratio,
                    max_retries=max_retries
                )

        if success:
            print(f"   ✔ Imagen base generada ({provider_key.upper()}): {image_path}")
        else:
            print("   ⚠️ Falló la generación en línea. Generando respaldo local (Pillow)...")
            create_fallback_image(image_path, idx, narration, aspect_ratio=aspect_ratio)

        # Estampar la tarjeta overlay si la escena es split_right
        if layout_type == "split_right" and overlay_content:
            apply_split_right_overlay(image_path, overlay_content)

        scene["image_path"] = image_path
        processed_count += 1

        if rate_limit_delay > 0 and (processed_count < len(scenes_to_process)):
            time.sleep(rate_limit_delay)

    if not target_scenes:
        process_thumbnail(project_dir, manifest, provider_key, selected_model, aspect_ratio, max_retries, force)

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 80)
    print(f" ✔ Proceso completado. Imágenes procesadas: {processed_count} | Omitidas (Checkpoint): {skipped_count}")
    print(" ✔ Manifest.json actualizado con éxito.")
    print("=" * 80)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Módulo Visual para Faceless Engine")
    parser.add_argument("--project_dir", type=str, default=None, help="Directorio del proyecto")
    parser.add_argument("--provider", type=str, default=DEFAULT_IMAGE_PROVIDER, choices=["openrouter", "fal"], help="Proveedor de imágenes")
    parser.add_argument("--model", type=str, default=None, help="Modelo específico")
    parser.add_argument("--retries", type=int, default=3, help="Reintentos por escena")
    parser.add_argument("--scene", type=str, default=None, help="Escenas a regenerar")
    parser.add_argument("--only-thumbnail", action="store_true", help="Genera ÚNICAMENTE la miniatura")
    parser.add_argument("--force", action="store_true", help="Fuerza la regeneración")
    parser.add_argument("--delay", type=float, default=1.0, help="Pausa en segundos entre peticiones API")

    args = parser.parse_args()
    target_project_dir = args.project_dir or get_current_project_dir()
    target_scenes = parse_scene_input(args.scene) if args.scene else None

    process_scene_media(
        project_dir=target_project_dir,
        provider=args.provider,
        model=args.model,
        max_retries=args.retries,
        target_scenes=target_scenes,
        only_thumbnail=args.only_thumbnail,
        force=args.force,
        rate_limit_delay=args.delay
    )