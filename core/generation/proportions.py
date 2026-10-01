"""
Validación y corrección de proporciones de layout en el manifest.

Se asegura de que 'full_art' sea el layout dominante, convirtiendo
escenas de otros layouts si es necesario.
"""

from typing import List, Dict, Any

from core.config import MIN_FULL_ART_RATIO


def _enforce_layout_proportions(
    scenes: List[Dict[str, Any]],
    allowed_layouts: List[str],
    min_full_art_ratio: float = MIN_FULL_ART_RATIO,
) -> List[Dict[str, Any]]:
    """
    Audita la proporción de layouts. Si 'full_art' está por debajo del
    mínimo, convierte los layouts sobrantes a 'full_art'.

    Prioridad de conversión (primero los que menos peso narrativo tienen):
      1. code_graphic_visual (nunca debería estar en exceso)
      2. code_graphic
      3. split_right
    """
    if "full_art" not in allowed_layouts:
        return scenes

    total = len(scenes)
    if total == 0:
        return scenes

    min_full_art_count = int(total * min_full_art_ratio)
    current_full_art = sum(1 for s in scenes if s.get("layout_type") == "full_art")

    if current_full_art >= min_full_art_count:
        return scenes

    deficit = min_full_art_count - current_full_art
    print(f"   🔧 Proporción de layouts: {current_full_art}/{total} full_art. "
          f"Faltan {deficit} para alcanzar el mínimo de {min_full_art_count}.")

    # Prioridad de conversión
    conversion_priority = ["code_graphic_visual", "code_graphic", "split_right"]

    for target_layout in conversion_priority:
        if deficit <= 0:
            break
        for scene in scenes:
            if deficit <= 0:
                break
            if scene.get("layout_type") == target_layout:
                # No convertir la primera ni la última escena si son code_graphic
                # (aunque en la práctica no deberían serlo)
                idx = scene.get("scene_number", 0)
                if idx == 1 or idx == total:
                    continue

                print(f"   🔧 Escena {idx}: '{target_layout}' → 'full_art' "
                      f"(por proporción).")
                scene["layout_type"] = "full_art"
                # Limpiar overlay_content si pasa a full_art
                scene["overlay_content"] = None
                # Mantener el visual_prompt original si existe; si no, un default
                if not scene.get("visual_prompt"):
                    scene["visual_prompt"] = (
                        "Simple abstract conceptual illustration representing "
                        "the narration"
                    )
                deficit -= 1

    return scenes