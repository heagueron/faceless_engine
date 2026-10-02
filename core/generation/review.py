"""
Interfaz interactiva de revisión del guion y selección de estilo visual.

Contiene las funciones que se comunican con el usuario por consola durante
el pipeline de generación.
"""

import sys
from typing import Optional

from core.generation.schemas import ScriptManifest
from core.styles import list_available_styles, DEFAULT_STYLE_KEY


def display_and_review_script(manifest: ScriptManifest) -> ScriptManifest:
    """Muestra el guion en consola y permite ajustes manuales directos."""
    data = manifest.model_dump()

    while True:
        cta_badge = " [💬 INCLUYE PREGUNTA Y GLOBO DE TEXTO]" if data.get("includes_interactive_cta") else ""
        print("\n" + "=" * 85)
        print(f" 📜 GUION GENERADO: '{data['title']}' ({data['target_duration_seconds']}s | {data['video_type'].upper()} {data['aspect_ratio']}){cta_badge}")
        print(f" 🎬 Total Escenas: {len(data['scenes'])}")
        print("=" * 85)

        print(f"\n 🖼️  METADATOS DE MINIATURA (THUMBNAIL):")
        print(f"    💬 Texto Gancho (ES): \"{data.get('thumbnail_text', '')}\"")
        print(f"    🎨 Visual Prompt (EN): {data.get('thumbnail_prompt', '')}")
        print("-" * 85)

        for sc in data["scenes"]:
            tag_cta = " 💬 [PREGUNTA INTERACTIVA CON GLOBO]" if sc.get("is_interactive_cta") else ""
            layout = sc.get("layout_type", "full_art").upper()
            print(f"\n🎬 ESCENA {sc['scene_number']} [{layout}]{tag_cta}:")
            print(f"   🗣️  Locución (ES): \"{sc['narration_text']}\"")

            if sc.get("layout_type") == "code_graphic":
                print("   🖼️  Visual Prompt: [GRÁFICO GENERADO 100% POR CÓDIGO PYTHON]")
            else:
                print(f"   🖼️  Visual Prompt (EN): {sc.get('visual_prompt', '')}")

            if sc.get("overlay_content"):
                ov = sc["overlay_content"]
                if ov.get("title"):
                    print(f"   📝 Texto Overlay Título: \"{ov['title']}\"")
                if ov.get("bullets"):
                    print(f"   📝 Texto Overlay Bullets: {ov['bullets']}")

        print("\n" + "=" * 85)
        print("🛑 REVISIÓN E INTERVENCIÓN HUMANA:")
        print("👉 Presiona [ENTER] o '1' para APROBAR el guion.")
        print("👉 Escribe '2' para editar una escena específica.")
        print("👉 Escribe '3' para cambiar el título del video.")
        print("👉 Escribe '4' para editar los metadatos de la miniatura (Texto / Prompt).")

        opt = input("\nSelección: ").strip()

        if opt in ["", "1"]:
            print("\n✔ Guion aprobado sin cambios.")
            break
        elif opt == "2":
            scene_num = input("Número de escena a editar (ej. 1): ").strip()
            if scene_num.isdigit():
                idx = int(scene_num) - 1
                if 0 <= idx < len(data["scenes"]):
                    target_sc = data["scenes"][idx]
                    print(f"\n--- Editando Escena {target_sc['scene_number']} ---")

                    new_narr = input("Nueva locución [ENTER para mantener]: ").strip()
                    if new_narr:
                        target_sc["narration_text"] = new_narr

                    if target_sc.get("layout_type") != "code_graphic":
                        new_vis = input("Nuevo prompt visual [ENTER para mantener]: ").strip()
                        if new_vis:
                            target_sc["visual_prompt"] = new_vis

                    print(f"✔ Escena {target_sc['scene_number']} actualizada.")
                else:
                    print("⚠️ Número de escena fuera de rango.")
            else:
                print("⚠️ Número inválido.")
        elif opt == "3":
            new_title = input("Nuevo título para el video: ").strip()
            if new_title:
                data["title"] = new_title
                print(f"✔ Título actualizado a: '{new_title}'")
        elif opt == "4":
            print("\n--- Editando Metadatos de la Miniatura ---")
            new_th_text = input(f"Nuevo texto de gancho ({data.get('thumbnail_text', '')}) [ENTER para mantener]: ").strip()
            if new_th_text:
                data["thumbnail_text"] = new_th_text.upper()

            new_th_prompt = input("Nuevo visual prompt para la miniatura [ENTER para mantener]: ").strip()
            if new_th_prompt:
                data["thumbnail_prompt"] = new_th_prompt

            print("✔ Metadatos de miniatura actualizados.")

    return ScriptManifest.model_validate(data)


def _prompt_style_interactive() -> Optional[str]:
    """Pregunta al usuario qué estilo visual usar si el script corre en TTY."""
    if not sys.stdin.isatty():
        return None

    styles = list_available_styles()
    print("\n" + "=" * 70)
    print(" 🎨 SELECCIÓN DE ESTILO VISUAL")
    print("=" * 70)
    for i, (key, desc) in enumerate(styles.items(), 1):
        default_marker = " [DEFAULT]" if key == DEFAULT_STYLE_KEY else ""
        print(f"  [{i}] {key}{default_marker}")
        print(f"      {desc}")
    print("=" * 70)

    choice = input(
        f"\n👉 Elige estilo por número o clave "
        f"[ENTER = default '{DEFAULT_STYLE_KEY}']: "
    ).strip()

    if not choice:
        return DEFAULT_STYLE_KEY

    if choice.isdigit():
        keys = list(styles.keys())
        idx = int(choice) - 1
        if 0 <= idx < len(keys):
            return keys[idx]
        print(f"⚠️ Número fuera de rango. Usando default.")
        return DEFAULT_STYLE_KEY

    if choice in styles:
        return choice

    print(f"⚠️ Estilo '{choice}' no reconocido. Usando default.")
    return DEFAULT_STYLE_KEY

def _prompt_channel_interactive() -> Optional[str]:
    """
    Pregunta al usuario qué canal usar si el script corre en TTY.
    Descubre los canales disponibles escaneando assets/channels/.
    Retorna None si el usuario elige "sin canal específico".
    """
    if not sys.stdin.isatty():
        return None

    import os
    channels_dir = os.path.join("assets", "channels")
    if not os.path.isdir(channels_dir):
        return None

    available = sorted([
        d for d in os.listdir(channels_dir)
        if os.path.isdir(os.path.join(channels_dir, d))
    ])
    if not available:
        return None

    print("\n" + "=" * 60)
    print(" 📺 SELECCIÓN DE CANAL")
    print("=" * 60)
    for i, name in enumerate(available, 1):
        print(f"  [{i}] {name}")
    print("  [0] Sin canal específico (usar explainer genérico)")
    print("=" * 60)

    choice = input("\n👉 Selecciona canal [ENTER = 0]: ").strip()
    if not choice or choice == "0":
        return None

    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(available):
            return available[idx]
        print("⚠️ Número fuera de rango. Se usará sin canal.")
        return None

    if choice in available:
        return choice

    print(f"⚠️ Canal '{choice}' no reconocido. Se usará sin canal.")
    return None