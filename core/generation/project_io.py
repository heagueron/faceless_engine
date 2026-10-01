"""
Utilidades de gestión de proyectos y archivos de estado para el pipeline
de generación de guiones.
"""

import os
import re
import json
from datetime import datetime
from typing import Optional, Dict, Any


def slugify(text: str, max_words: int = 4) -> str:
    """Convierte un título en un slug limpio usando las primeras N palabras."""
    clean_text = re.sub(r"[^\w\s]", "", text.lower(), flags=re.UNICODE)
    words = clean_text.split()[:max_words]
    return "_".join(words) if words else "proyecto_faceless"


def create_project_structure(title: str, base_projects_dir: str = "projects") -> str:
    """Crea la carpeta timestamped del proyecto e inicializa audio/ e images/."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder_slug = slugify(title)
    project_dir = os.path.join(base_projects_dir, f"{timestamp}_{folder_slug}")

    os.makedirs(os.path.join(project_dir, "audio"), exist_ok=True)
    os.makedirs(os.path.join(project_dir, "images"), exist_ok=True)

    os.makedirs("output", exist_ok=True)
    current_proj_path = os.path.join("output", "current_project.json")
    with open(current_proj_path, "w", encoding="utf-8") as f:
        json.dump({"project_dir": project_dir, "title": title}, f, indent=2, ensure_ascii=False)

    return project_dir


def load_selected_idea() -> Optional[Dict[str, Any]]:
    """Carga la idea seleccionada desde output/selected_idea.json."""
    idea_path = os.path.join("output", "selected_idea.json")
    if os.path.exists(idea_path):
        try:
            with open(idea_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                print(f"💡 Idea cargada desde '{idea_path}': '{data.get('selected_idea', {}).get('titulo', 'Sin título')}'")
                return data
        except Exception as e:
            print(f"⚠️ No se pudo leer '{idea_path}': {e}")
    return None


def load_reverse_analysis() -> Optional[Dict[str, Any]]:
    """Carga el análisis de ingeniería inversa si existe en output/."""
    analysis_path = os.path.join("output", "reverse_prompting_analysis.json")
    if os.path.exists(analysis_path):
        try:
            with open(analysis_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("analysis")
        except Exception as e:
            print(f"⚠️ No se pudo leer el análisis de ingeniería inversa: {e}")
    return None