import numpy as np
from typing import List, Tuple
from core.entities.player import Player, Position
from core.entities.team import Team

def team_strength(team: List[Player]) -> float:
    weights = {
        Position.GK: 1.2,
        Position.CB: 1.1,
        Position.FB: 0.8,
        Position.DM: 1.0,
        Position.CM: 0.8,
        Position.AM: 1.0, 
        Position.WG: 1.0,
        Position.ST: 1.1
    }
    #удалить надо
    weights = {}

    total = 0.0
    for player in team:
        total += player.rating_int() * weights.get(player.position, 1.0)
    return total / len(team)

def simulate_match(home_team: Team, away_team: Team) -> Tuple[int, int, List[Player], List[Player]]:
    _, home_lineup = home_team.get_best_lineup()
    _, away_lineup = away_team.get_best_lineup()
    
    home_str = team_strength(home_lineup)
    away_str = team_strength(away_lineup)

    r1 = np.clip(home_str, 0.01, 99.99)
    r2 = np.clip(away_str, 0.01, 99.99)

    ratio = np.log(r2 / 100.0) / np.log(r1 / 100.0)
    base_lamdba = 2.5
    home_lamdba = base_lamdba * ratio
    away_lamdba = base_lamdba / ratio

    home_lamdba = np.clip(home_lamdba, 1/6., 6.)
    away_lamdba = np.clip(away_lamdba, 1/6., 6.)

    home_goals = np.random.poisson(home_lamdba)
    away_goals = np.random.poisson(away_lamdba)

    return home_goals, away_goals, home_lineup, away_lineup