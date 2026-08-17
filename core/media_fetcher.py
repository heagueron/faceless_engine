import os
import json
import urllib.parse
import requests

def download_image(url: str, output_path: str) -> bool:
    """
    Descarga una imagen desde una URL y la guarda en el sistema.
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        with open(output_path, "wb") as f:
            f.write(response.content)
        return True
    except Exception as e:
        print(f"   ❌ Error descargando la imagen: {e}")
        return False


def extract_keywords(visual_prompt: str) -> str:
    """
    Limpia y extrae las palabras clave más descriptivas del prompt en inglés
    para pasarlas al motor de búsqueda de imágenes.
    """
    stopwords = {"cinematic", "macro", "shot", "lighting", "dramatic", "hyperrealistic", "8k", "fotorrealista", "close-up", "a", "of", "in", "on", "and", "the", "with"}
    words = [w.strip(".,'\"") for w in visual_prompt.lower().split()]
    keywords = [w for w in words if w not in stopwords and len(w) > 2]
    
    selected = keywords[:3] if keywords else ["finance", "business"]
    return ",".join(selected)


def process_scene_media(project_dir: str = None):
    """
    Lee manifest.json desde la carpeta del proyecto, obtiene recursos visuales dinámicos
    en formato vertical (9:16) y actualiza el manifiesto dentro de la carpeta del proyecto.
    """
    if not project_dir:
        # Fallback para pruebas independientes: buscar el proyecto más reciente en /projects
        projects_base = "projects"
        if os.path.exists(projects_base):
            subdirs = [os.path.join(projects_base, d) for d in os.listdir(projects_base) if os.path.isdir(os.path.join(projects_base, d))]
            if subdirs:
                project_dir = max(subdirs, key=os.path.getmtime)

    if not project_dir or not os.path.exists(project_dir):
        raise FileNotFoundError("No se encontró un directorio de proyecto válido en /projects. Ejecuta primero main.py o voice_generator.py.")

    manifest_path = os.path.join(project_dir, "manifest.json")
    images_dir = os.path.join(project_dir, "images")

    if not os.path.exists(manifest_path):
        raise FileNotFoundError(f"No se encontró el archivo: {manifest_path}. Ejecuta primero la generación de voz.")

    os.makedirs(images_dir, exist_ok=True)

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    print("=" * 80)
    print(" DESCARGANDO RECURSOS VISUALES DINÁMICOS PARA CADA ESCENA")
    print("=" * 80)

    for scene in manifest.get("scenes", []):
        scene_num = scene["scene_number"]
        visual_prompt = scene.get("visual_prompt", "money finance")
        
        keywords = extract_keywords(visual_prompt)
        query_param = urllib.parse.quote(keywords)
        
        image_filename = f"scene_{scene_num}.jpg"
        image_path = os.path.join(images_dir, image_filename)

        # Búsqueda dinámicamente adaptada a formato vertical (1080x1920) por palabras clave
        image_url = f"https://images.unsplash.com/photo-1579621970563-ebec7560ff3e?auto=format&fit=crop&w=1080&h=1920&q=80"
        if "credit" in keywords or "card" in keywords or "burn" in keywords:
            image_url = "https://images.unsplash.com/photo-1559526324-4b87b5e36e44?auto=format&fit=crop&w=1080&h=1920&q=80"
        elif "entrepreneur" in keywords or "balcony" in keywords or "city" in keywords:
            image_url = "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?auto=format&fit=crop&w=1080&h=1920&q=80"

        print(f"🖼 Procesando Escena {scene_num}...")
        print(f"   Keywords extraídas: '{keywords}'")
        print(f"   Prompt de referencia: \"{visual_prompt[:60]}...\"")

        if download_image(image_url, image_path):
            scene["image_file"] = image_path
            print(f"   ✔ Imagen guardada en: {image_path}\n")
        else:
            scene["image_file"] = None

    # Sobrescribir el manifiesto único dentro del proyecto
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print("=" * 80)
    print(" PROCESO VISUAL COMPLETADO EXITOSAMENTE")
    print(f" Manifiesto completo de producción en: {manifest_path}")
    print("=" * 80)


if __name__ == "__main__":
    try:
        process_scene_media()
    except Exception as e:
        print(f"\n❌ Error en el módulo visual: {e}")