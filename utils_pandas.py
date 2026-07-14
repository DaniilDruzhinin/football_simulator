# utils_pandas.py
import json
import random
import numpy as np
import pandas as pd
from pathlib import Path
from typing import List, Tuple, Optional

# Импортируем сущности (предполагаем, что структура проекта сохранена)
from core.entities.player import Player, Position
from core.entities.team import Team
from core.generators.player_generator import PlayerGenerator
from core.generators.team_generator import load_teams_from_json
from core.engine.match_simulator import simulate_match

# Пути к файлам данных
DATA_DIR = Path(__file__).parent / "data"
PLAYERS_FILE = Path(__file__).parent / "players.json"

# Глобальные переменные для кэширования
_teams_cache: Optional[List[Team]] = None
_players_cache: Optional[List[Player]] = None


def get_teams() -> List[Team]:
    """Возвращает список команд, загружая из JSON при необходимости."""
    global _teams_cache
    if _teams_cache is None:
        _teams_cache = load_teams_from_json()
    return _teams_cache


def load_players() -> List[Player]:
    """Загружает игроков из файла players.json."""
    global _players_cache
    if not PLAYERS_FILE.exists():
        return []
    with open(PLAYERS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    players = []
    for p_data in data:
        pos = next(pos for pos in Position if pos.value == p_data["position"])
        players.append(Player(
            id=p_data["id"],
            first_name=p_data["first_name"],
            last_name=p_data["last_name"],
            nation=p_data["nation"],
            age=p_data["age"],
            position=pos,
            rating=p_data["rating"],
            potential=p_data["potential"],
            team_id=p_data.get("team_id")
        ))
    _players_cache = players
    return players


def save_players(players: List[Player]) -> None:
    """Сохраняет список игроков в players.json."""
    data = []
    for p in players:
        data.append({
            "id": p.id,
            "first_name": p.first_name,
            "last_name": p.last_name,
            "nation": p.nation,
            "age": p.age,
            "position": p.position.value,
            "rating": p.rating,
            "potential": p.potential,
            "team_id": p.team_id
        })
    with open(PLAYERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    global _players_cache
    _players_cache = players


def generate_players(count: int = 100, distribute_to_teams: bool = True) -> List[Player]:
    """
    Генерирует заданное количество игроков.
    Если distribute_to_teams=True, случайно распределяет их по существующим командам.
    Возвращает список сгенерированных игроков.
    """
    teams = get_teams()
    gen = PlayerGenerator()
    existing = load_players()
    next_id = max([p.id for p in existing], default=0) + 1
    new_players = []
    for i in range(count):
        team_id = random.choice(teams).id if distribute_to_teams else None
        player = gen.generate(next_id + i, team_id=team_id)
        new_players.append(player)
    all_players = existing + new_players
    save_players(all_players)
    # Обновляем команды в кэше
    update_teams_players()
    return new_players


def update_teams_players() -> None:
    """Обновляет списки игроков внутри объектов команд."""
    teams = get_teams()
    players = load_players()
    for team in teams:
        team.players = [p for p in players if p.team_id == team.id]


def players_df(team_id: Optional[int] = None) -> pd.DataFrame:
    """
    Возвращает DataFrame со всеми игроками.
    Если указан team_id, фильтрует по команде.
    """
    players = load_players()
    if team_id is not None:
        players = [p for p in players if p.team_id == team_id]
    if not players:
        return pd.DataFrame()
    data = [{
        "ID": p.id,
        "Имя": p.full_name(),
        "Нация": p.nation,
        "Возраст": p.age,
        "Позиция": p.position.value,
        "Рейтинг": p.rating,
        "Потенциал": p.potential,
        "Команда ID": p.team_id
    } for p in players]
    df = pd.DataFrame(data)
    # Добавим название команды для удобства
    if team_id is None:
        teams_dict = {t.id: t.name for t in get_teams()}
        df["Команда"] = df["Команда ID"].map(teams_dict)
    return df


def teams_df() -> pd.DataFrame:
    """Возвращает DataFrame со списком команд и количеством игроков."""
    update_teams_players()
    teams = get_teams()
    data = [{
        "ID": t.id,
        "Название": t.name,
        "Город": t.city,
        "Стадион": t.stadium,
        "Кол-во игроков": len(t.players)
    } for t in teams]
    return pd.DataFrame(data)


def lineup_df(team_id: int) -> pd.DataFrame:
    teams = get_teams()
    team = next((t for t in teams if t.id == team_id), None)
    if not team:
        print(f"Команда с ID {team_id} не найдена.")
        return pd.DataFrame()
    update_teams_players()
    available, missing = team.check_lineup_availability()
    if not available:
        print(f"Состав 4-4-2 невозможен. Не хватает: {missing}")
        return pd.DataFrame()
    lineup = team.get_best_lineup()
    data = [{
        "Позиция": p.position.name,
        "Имя": p.full_name(),
        "Рейтинг": p.rating,
        "Возраст": p.age,
        "Нация": p.nation
    } for p in lineup]
    return pd.DataFrame(data)


def simulate_match_df(home_team_id: int, away_team_id: int) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Симулирует матч между двумя командами.
    Возвращает два DataFrame: результат матча и составы.
    """
    teams = get_teams()
    home_team = next((t for t in teams if t.id == home_team_id), None)
    away_team = next((t for t in teams if t.id == away_team_id), None)
    if not home_team or not away_team:
        print("Одна из команд не найдена.")
        return pd.DataFrame(), pd.DataFrame()

    update_teams_players()

    if len(home_team.players) < 11 or len(away_team.players) < 11:
        print("В одной из команд недостаточно игроков (нужно минимум 11).")
        return pd.DataFrame(), pd.DataFrame()

    home_goals, away_goals, home_lineup, away_lineup = simulate_match(home_team, away_team)

    # DataFrame с результатом
    result_df = pd.DataFrame([{
        "Хозяева": home_team.name,
        "Голы хозяев": home_goals,
        "Гости": away_team.name,
        "Голы гостей": away_goals,
        "Победитель": home_team.name if home_goals > away_goals else (away_team.name if away_goals > home_goals else "Ничья")
    }])

    # DataFrame с составами
    lineup_data = []
    for p in home_lineup:
        lineup_data.append({
            "Команда": home_team.name,
            "Имя": p.full_name(),
            "Позиция": p.position.value,
            "Рейтинг": p.rating
        })
    for p in away_lineup:
        lineup_data.append({
            "Команда": away_team.name,
            "Имя": p.full_name(),
            "Позиция": p.position.value,
            "Рейтинг": p.rating
        })
    lineup_df = pd.DataFrame(lineup_data)

    return result_df, lineup_df


def quick_simulate(home_team_name: str, away_team_name: str) -> None:
    """
    Быстрая симуляция по названиям команд с красивым выводом в консоль.
    """
    teams = get_teams()
    home_team = next((t for t in teams if t.name.lower() == home_team_name.lower()), None)
    away_team = next((t for t in teams if t.name.lower() == away_team_name.lower()), None)
    if not home_team or not away_team:
        print("Команда не найдена. Доступные команды:")
        print(teams_df()[["Название"]].to_string(index=False))
        return
    result_df, lineup_df = simulate_match_df(home_team.id, away_team.id)
    if result_df.empty:
        return
    print("\n" + "="*50)
    print(f"{result_df['Хозяева'][0]} {result_df['Голы хозяев'][0]} : {result_df['Голы гостей'][0]} {result_df['Гости'][0]}")
    print("="*50)
    print("\nСоставы:")
    print(lineup_df.to_string(index=False))


def reset_all_data() -> None:
    """Удаляет всех сгенерированных игроков и очищает файл players.json."""
    global _players_cache
    _players_cache = []
    if PLAYERS_FILE.exists():
        PLAYERS_FILE.unlink()
    teams = get_teams()
    for team in teams:
        team.players = []
    print("Все данные сброшены.")


# ============ Пример использования ============
if __name__ == "__main__":
    # При первом запуске сгенерируем игроков, если их нет
    if not PLAYERS_FILE.exists():
        print("Генерация 220 игроков (по 11 на команду)...")
        generate_players(220)

    print("\n=== Команды ===")
    print(teams_df())

    print("\n=== Состав Arsenal ===")
    arsenal_id = next(t.id for t in get_teams() if t.name == "Arsenal")
    print(lineup_df(arsenal_id))

    print("\n=== Симуляция матча Arsenal vs Liverpool ===")
    quick_simulate("Arsenal", "Liverpool")