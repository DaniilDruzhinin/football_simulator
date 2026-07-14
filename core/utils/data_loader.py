import json
import os
from pathlib import Path

def get_project_root() -> Path:
    """Возвращает абсолютный путь к корню проекта (где лежит папка core)."""
    # Файл data_loader.py находится в core/utils/
    return Path(__file__).parent.parent.parent

def load_json(file_name: str) -> dict:
    data_path = get_project_root() / "data" / file_name
    if not data_path.exists():
        raise FileNotFoundError(f"Файл не найден: {data_path}")
    with open(data_path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_first_names() -> dict:
    return load_json("first_names.json")

def load_last_names() -> dict:
    return load_json("last_names.json")

def load_nations() -> dict:
    return load_json("nations.json")

def load_positions() -> dict:
    return load_json('positions.json')

def load_teams() -> dict:
    return load_json('teams.json')