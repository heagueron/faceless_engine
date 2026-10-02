"""
Módulo visual de Faceless Engine.

Orquesta la generación de imágenes para las escenas del manifest,
delegando a:
  - core.providers.* para generación vía API (fal.ai, OpenRouter)
  - core.renderers.card para code_graphic clásico
  - core.overlays.split_right para el overlay derecho
  - core.fonts para la carga de fuentes

Este módulo NO contiene lógica de dibujo ni de red; solo orquesta.
"""

import os
import json
import time
import argparse
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
from PIL import Image

# --- Dependencias del proyecto ---
from core.fonts import load_font, get_project_root, get_fonts_dir
from core.renderers.base import wrap_text_by_pixel_width
from core.renderers.card import render_code_graphic_card
from core.renderers.whiteboard import render_whiteboard

from core.overlays.split_right import apply_split_right_overlay
from core.providers.fal import generate_image_via_fal
from core.providers.openrouter import generate_image_via_openrouter
from core.providers.nvidia import generate_image_via_nvidia
from core.providers.fallback import create_fallback_image
from core.styles import get_style_fonts, GLOBAL_FALLBACK_FONT, STYLE_PROMPTS


load_dotenv()


# ==============================================================================
# CONFIGURACIÓN GENERAL Y PROVEEDOR POR DEFECTO
# ==============================================================================
DEFAULT_IMAGE_PROVIDER = "fal"

DEFAULT_MODELS = {
    "openrouter": "qwen/qwen-image-3",
    "fal": "fal-ai/flux-1/schnell",
    "nvidia": "black-forest-labs/flux.2-klein-4b",
}

def resolve_effective_provider(
    cli_provider: str,
    manifest: Dict[str, Any],
    cli_model: Optional[str] = None,
) -> tuple[str, str, int]:
    """
    Determina el proveedor y modelo efectivos para un proyecto.

    Reglas de decisión:
      1. Si el usuario pasó --provider explícito (distinto del default),
         ese gana, ignorando preferencias del estilo.
      2. Si el estilo declara 'preferred_provider', se usa ese.
      3. Si ninguno de los anteriores, se usa el proveedor por CLI.

    Retorna:
        (provider_efectivo, modelo_efectivo, seed_efectivo)
    """
    style_key = manifest.get("visual_style", "cartoon_2d_cellshaded")
    style_meta = STYLE_PROMPTS.get(style_key, {})

    preferred_provider = style_meta.get("preferred_provider")
    preferred_model = style_meta.get("preferred_model")
    preferred_seed = style_meta.get("preferred_seed", 100)

    # ¿El usuario forzó un proveedor explícito?
    explicit_provider = cli_provider != DEFAULT_IMAGE_PROVIDER

    if explicit_provider:
        # El CLI gana. Modelo: el del CLI si lo dio, si no el default del proveedor.
        provider = cli_provider.lower().strip()
        model = cli_model or DEFAULT_MODELS.get(provider, "")
        seed = preferred_seed
    elif preferred_provider:
        # El estilo manda.
        provider = preferred_provider.lower().strip()
        model = cli_model or preferred_model or DEFAULT_MODELS.get(provider, "")
        seed = preferred_seed
    else:
        # Fallback: usar el provider por CLI (o default).
        provider = cli_provider.lower().strip()
        model = cli_model or DEFAULT_MODELS.get(provider, "")
        seed = preferred_seed

    return provider, model, seed

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
    """Carga la ruta del proyecto activo desde output/current_project.json."""
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

def enforce_style_in_prompt(prompt: Optional[str], manifest: Dict[str, Any]) -> Optional[str]:
    """Refuerza el estilo declarado en el manifest si el prompt no lo contiene.
    Retorna None si el prompt es None (escenas code_graphic* no lo usan)."""
    if not prompt:
        return prompt

    style_prompt = manifest.get("visual_style_prompt", "").strip()
    if not style_prompt:
        return prompt

    marker = style_prompt[:30].lower()
    if marker not in prompt.lower():
        print(f"   🔧 Estilo ausente en prompt. Inyectando: '{style_prompt[:50]}...'")
        prompt = f"{style_prompt} {prompt}"
    return prompt

def print_style_banner(manifest: Dict[str, Any]) -> None:
    """Muestra el estilo visual declarado en el manifest."""
    style_key = manifest.get("visual_style")
    if style_key:
        print(f" 🎨 Estilo del proyecto: '{style_key}'")
    else:
        print(" ⚠️ manifest.json no tiene 'visual_style'. Se asume estilo legacy.")

def is_valid_image_file(path: str) -> bool:
    """Verifica si un archivo existe y es una imagen válida > 100 bytes."""
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
    """Procesa escenas y/o miniatura del manifest.json."""
    # 1. Validar proveedor pedido por CLI
    cli_provider = provider.lower().strip()
    if cli_provider not in ["openrouter", "fal", "nvidia"]:
        print(f"⚠️ Proveedor '{provider}' no válido. Usando '{DEFAULT_IMAGE_PROVIDER}'.")
        cli_provider = DEFAULT_IMAGE_PROVIDER

    # 2. Cargar el manifest (necesario para decidir proveedor efectivo)
    manifest_path = os.path.join(project_dir, "manifest.json")
    if not os.path.exists(manifest_path):
        raise FileNotFoundError(f"No se encontró manifest.json en: {project_dir}")
    
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # 3. Resolver proveedor y modelo efectivos (considera preferencias del estilo)
    provider_key, selected_model, effective_seed = resolve_effective_provider(
        cli_provider, manifest, model
    )

    images_dir = os.path.join(project_dir, "images")
    os.makedirs(images_dir, exist_ok=True)

    aspect_ratio = manifest.get("aspect_ratio", "16:9")

    # Fuentes: preferir el snapshot del manifest, caer a styles.py si no existe
    fonts = manifest.get("visual_style_fonts")
    if not fonts or not isinstance(fonts, dict):
        print("   ⚠️ manifest.json no tiene 'visual_style_fonts'. Consultando styles.py...")
        fonts = get_style_fonts(manifest.get("visual_style", "cartoon_2d_cellshaded"))

    print("\n" + "=" * 80)
    print(f" 🖼️ GENERANDO RECURSOS VISUALES MEDIANTE {provider_key.upper()} ({selected_model})")
    print(f" 📐 Aspect Ratio: {aspect_ratio}")
    print_style_banner(manifest)
    print(f"   🔤 Fuentes del estilo: title='{fonts['title']}', body='{fonts['body']}'")
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

        visual_prompt = scene.get("visual_prompt")
        
        narration = scene.get("narration_text", "")
        overlay_content = scene.get("overlay_content")
        image_filename = f"scene_{idx}.jpg"
        image_path = os.path.join(images_dir, image_filename)

        if not force and is_valid_image_file(image_path):
            if layout_type == "split_right" and overlay_content:
                apply_split_right_overlay(image_path, overlay_content, fonts=fonts)
            print(f"\n⏭️ Escena {idx}: Imagen lista ('{image_filename}'). Omitiendo por Checkpoint.")
            scene["image_path"] = image_path
            skipped_count += 1
            continue

        print(f"\n🖼️ Procesando Escena {idx} [{layout_type.upper()}]...")

        visual_prompt = enforce_style_in_prompt(visual_prompt, manifest)

        if layout_type == "code_graphic":
            print("   📊 Escena tipo 'code_graphic'. Generando tarjeta de texto...")
            render_code_graphic_card(
                image_path, idx, overlay_content,
                aspect_ratio=aspect_ratio,
                fonts=fonts,
            )
            success = True
        elif layout_type == "code_graphic_visual":
            print("   🖼️ Escena tipo 'code_graphic_visual'. Generando pizarra con explainer...")
            render_whiteboard(
                image_path, idx, overlay_content,
                aspect_ratio=aspect_ratio,
                fonts=fonts,
                explainer_style=manifest.get("visual_style", "cartoon_2d_cellshaded"),
                explainer_channel=manifest.get("channel"),    # ← NUEVO
            )
            success = True
        else:
            visual_prompt = visual_prompt or "minimalist 2D vector graphic"
            visual_prompt = enforce_style_in_prompt(visual_prompt, manifest) or visual_prompt
            
            if provider_key == "openrouter":
                success = generate_image_via_openrouter(
                    prompt=visual_prompt,
                    output_path=image_path,
                    model=selected_model,
                    aspect_ratio=aspect_ratio,
                    max_retries=max_retries
                )
            elif provider_key == "nvidia":
                success = generate_image_via_nvidia(
                    prompt=visual_prompt,
                    output_path=image_path,
                    model=selected_model,
                    aspect_ratio=aspect_ratio,
                    seed=effective_seed,
                    max_retries=max_retries,
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

        if layout_type == "split_right" and overlay_content:
            apply_split_right_overlay(image_path, overlay_content, fonts=fonts)

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
    
    parser.add_argument("--provider", type=str, default=DEFAULT_IMAGE_PROVIDER, choices=["openrouter", "fal", "nvidia"], help="Proveedor de imágenes")
    
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