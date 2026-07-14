from dataclasses import dataclass
from datetime import date
from typing import List, Tuple, Dict, Optional
from core.entities.player import Player, Position
import numpy as np
from scipy.optimize import linear_sum_assignment

FORMATIONS = {
    '4-4-2': [
        ((Position.GK,), 1),
        ((Position.CB,), 2), ((Position.FB,), 2),
        ((Position.CM, Position.DM), 2), ((Position.CM, Position.AM), 2),
        ((Position.WG, Position.ST), 2)
    ],
    '4-3-3': [
        ((Position.GK,), 1),
        ((Position.CB,), 2), ((Position.FB,), 2),
        ((Position.CM, Position.DM), 1), ((Position.CM, Position.AM), 2),
        ((Position.WG,), 2), ((Position.ST,), 1)
    ],
    '3-4-3': [
        ((Position.GK,), 1),
        ((Position.CB,), 3),
        ((Position.CM, Position.DM), 2), ((Position.CM, Position.AM), 2),
        ((Position.WG,), 2), ((Position.ST,), 1)
    ],
    '4-2-3-1': [
        ((Position.GK,), 1),
        ((Position.CB,), 2), ((Position.FB,), 2),
        ((Position.CM, Position.DM), 2),
        ((Position.CM, Position.AM), 3),
        ((Position.ST,), 1)
    ],
    '3-5-2': [
        ((Position.GK,), 1),
        ((Position.CB,), 3),
        ((Position.DM,), 1), ((Position.CM, Position.DM), 2), ((Position.CM, Position.AM), 2),
        ((Position.WG, Position.ST), 2)
    ]
}

POSITION_ORDER = [
    Position.GK, Position.CB, Position.FB,
    Position.DM, Position.CM, Position.AM,
    Position.WG, Position.ST
]

def _group_label(positions: Tuple[Position, ...]) -> str:
    if len(positions) == 1:
        return positions[0].name
    return '/'.join(p.name for p in positions)

@dataclass
class Team:
    id: int
    name: str
    city: str
    stadium: str
    players: List[Player] = None

    def __post_init__(self):
        if  self.players is None:
            self.players = []
        
    def add_players(self, player: Player):
        self.players.append(player)
    
    def check_lineup_availability(self) -> Tuple[bool, list]:
        all_missing = []
        for formation_name, groups in FORMATIONS.items():
            missing = {}
            possible = True
            for positions, req in groups:
                cnt = sum(1 for p in self.players if p.position in positions)
                if cnt < req:
                    possible = False
                    missing[_group_label(positions)] = req - cnt
            if possible:
                return True, []
            else:
                all_missing.append({
                    'formation': formation_name,
                    'missing': missing
                })

        return False, all_missing

    def _player_score(self, p: Player) -> float:
        pot = p.potential_value()
        pot = pot if pot != None else p.rating
        return p.rating + pot

    def get_best_lineup(self) -> List[Player]:
        best_formation = None
        best_lineup = []
        best_score = -1.0

        for formation, groups in FORMATIONS.items():
            lineup = self._solve_formation(groups)
            if lineup is None:
                continue
            total_score = sum(self._player_score(p) for p in lineup)
            if total_score > best_score:
                best_score = total_score
                best_formation = formation
                best_lineup = lineup

        return best_formation, best_lineup
    
    def _solve_formation(self, groups) -> Optional[List[Player]]:
        slots = []
        for positions, req in groups:
            for _ in range(req):
                slots.append(positions)
    
        n_players = len(self.players)
        if n_players < 11:
            return None
        
        for slot_positions in slots:
            if not any(p.position in slot_positions for p in self.players):
                return None
            
        n_slots = len(slots)
        n_total = n_players
        INF = 1e6

        cost = np.full((n_players, n_total), INF)
        
        for j, slot_positions in enumerate(slots):
            for i, p in enumerate(self.players):
                if p.position in slot_positions:
                    cost[i, j] = -self._player_score(p)
        
        if n_total > n_slots:
            cost[:, n_slots:] = 0.0
        
        row_ind, col_ind = linear_sum_assignment(cost)

        lineup = []
        for r, c in zip(row_ind, col_ind):
            if c < n_slots:
                lineup.append(self.players[r])
        
        return lineup if len(lineup) == 11 else None

            
    def get_stats(self, player_list: list[Player], ref_date: date = None) -> dict:
        if not player_list:
            return {'avg_rating': 0, 'std_rating': 0, 'avg_age': 0, 'std-age': 0}
        ratings = [p.rating_int() for p in player_list]
        if ref_date:
            ages = [p.age_curr(ref_date) for p in player_list]
            ages_float = []
            for p in player_list:
                if p.birth_date:
                    bd = date.fromisoformat(p.birth_date)
                    delta = ref_date - bd
                    ages_float.append(delta.days / 365.2425)
                else:
                    ages_float.append(float(p.age))
            avg_age_float = np.mean(ages_float)
            std_age_float = np.std(ages_float)
            return {
            'avg_rating': round(np.mean(ratings), 1),
            'std_rating': round(np.std(ratings), 1),
            'avg_age': round(avg_age_float, 1),
            'std_age': round(std_age_float, 1),
            } 

        ages = [p.age for p in player_list]
        return {
            'avg_rating': round(np.mean(ratings), 1),
            'std_rating': round(np.std(ratings), 1),
            'avg_age': round(np.mean(ages), 1),
            'std_age': round(np.std(ages), 1),
        } 

