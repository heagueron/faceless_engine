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