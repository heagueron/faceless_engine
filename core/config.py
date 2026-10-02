import os
from dotenv import load_dotenv

load_dotenv()

TARGET_LANGUAGE = os.getenv("TARGET_LANGUAGE", "es").lower()

LANGUAGE_DIRECTIVES = {
    "es": "CRITICAL INSTRUCTION: All text, labels, signs, callouts, diagram boxes, or annotations rendered inside the image MUST be written strictly in SPANISH language.",
    "en": "CRITICAL INSTRUCTION: All text, labels, signs, callouts, diagram boxes, or annotations rendered inside the image MUST be written strictly in ENGLISH language.",
    "pt": "CRITICAL INSTRUCTION: All text, labels, signs, callouts, diagram boxes, or annotations rendered inside the image MUST be written strictly in PORTUGUESE language."
}

def get_language_directive() -> str:
    return LANGUAGE_DIRECTIVES.get(TARGET_LANGUAGE, LANGUAGE_DIRECTIVES["es"])

# --- PROPORCIONES DE LAYOUT ---
# Guía para el LLM sobre cuántas escenas de cada layout debería generar.
# Se usa tanto en el prompt del LLM como en la validación post-generación.
# Los valores son (min, max) como fracciones del total de escenas.

LAYOUT_PROPORTION_GUIDE = {
    "full_art":             (0.60, 0.75),
    "split_right":          (0.05, 0.10),
    "code_graphic":         (0.05, 0.15),
    "code_graphic_visual":  (0.10, 0.20),
}

# Umbral duro: si tras la generación 'full_art' está por debajo de este ratio,
# se fuerza la conversión de otros layouts a 'full_art'.
MIN_FULL_ART_RATIO = 0.60