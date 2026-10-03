"""
Detección de personajes en los visual_prompts para inyección automática
del bloque de personaje en estilos stick.

El objetivo es evitar que los estilos stick (stick_classic_klein, stick_comic_pro,
etc.) añadan un personaje a escenas que NO lo piden (ej. una nube), mientras
que SÍ lo añaden a escenas que sí lo mencionan (ej. un hombre señalando).

Uso típico en apply_prompt_safeguards:

    if style_meta.get("character_prompt") and has_character(prompt):
        prompt = inject_character_block(prompt, style_meta["character_prompt"])
"""

import re
from typing import List


# --- Patrones que indican presencia de personaje ---
# Se buscan con word boundaries (\b) para evitar falsos positivos
# como "man" dentro de "managing" o "figure" dentro de "configure".
CHARACTER_KEYWORDS: List[str] = [
    # Términos inequívocos de stick figure
    "stick figure",
    "stick figures",
    "stickman",
    "stick-figure",
    "stick-figures",

    # Términos genéricos de persona
    "man",
    "woman",
    "person",
    "character",
    "human",
    "humanoid",
    "figure",
    "boy",
    "girl",
    "child",
    "kid",

    # Roles y profesiones
    "worker",
    "teacher",
    "scientist",
    "entrepreneur",
    "investor",
    "analyst",
    "engineer",
    "doctor",
    "cook",
    "chef",
    "farmer",
    "driver",
    "seller",
    "buyer",
    "customer",
    "client",
    "boss",
    "employee",
    "student",

    # Grupos
    "family",
    "group",
    "team",
    "crowd",
    "people",
    "audience",
]


def _build_pattern(keyword: str) -> re.Pattern:
    """
    Construye un patrón regex con word boundaries para una keyword.
    Trata espacios como separadores (ej. "stick figure" → \bstick\s+figure\b).
    """
    # Escapamos caracteres especiales y sustituimos espacios por \s+
    parts = keyword.split()
    escaped = r"\s+".join(re.escape(p) for p in parts)
    return re.compile(rf"\b{escaped}\b", re.IGNORECASE)


# Precompilar todos los patrones una sola vez al importar el módulo
_CHARACTER_PATTERNS: List[re.Pattern] = [_build_pattern(kw) for kw in CHARACTER_KEYWORDS]


def has_character(prompt: str) -> bool:
    """
    Detecta si el prompt describe un personaje (persona, stick figure, etc.).

    Retorna True si encuentra al menos uno de los patrones de CHARACTER_KEYWORDS
    como palabra completa (con word boundaries), sin distinguir mayúsculas.
    """
    if not prompt:
        return False

    for pattern in _CHARACTER_PATTERNS:
        if pattern.search(prompt):
            return True
    return False

def _has_character_block(prompt: str) -> bool:
    """
    Comprueba si el prompt ya contiene suficientes detalles del personaje
    como para no duplicar el bloque stick.

    Regla heurística: si aparecen al menos 2 conceptos clave (ojos, cabeza)
    en el prompt, se considera que el personaje ya está detallado.
    """
    if not prompt:
        return False

    p_lower = prompt.lower()

    # Conceptos clave que indican que el personaje ya está detallado
    detail_markers = [
        "dot eyes",
        "dotted eyes",
        "round head",
        "round white head",
        "small mouth",
        "curved mouth",
        "mitten hands",
    ]

    matches = sum(1 for m in detail_markers if m in p_lower)
    return matches >= 2

def inject_character_block(prompt: str, character_prompt: str) -> str:
    """
    Inyecta el bloque de personaje al final del prompt de escena.

    Ejemplo:
        prompt = "a stick figure holding a house"
        character_prompt = "round white head, dot eyes, simple mouth"
        resultado = "a stick figure holding a house, round white head, dot eyes, simple mouth"

    Si el prompt ya contiene el character_prompt (por ejemplo, si el LLM lo
    añadió por su cuenta), no lo duplica.
    """
    if not prompt or not character_prompt:
        return prompt

    # Evitar duplicación: si el prompt ya contiene detalles clave del personaje,
    # no lo añadimos otra vez.
    if _has_character_block(prompt):
        return prompt

    # Asegurar que el prompt termina en punto o coma para concatenar limpio
    prompt_clean = prompt.rstrip(" .,")
    return f"{prompt_clean}, {character_prompt}"