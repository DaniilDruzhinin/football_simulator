import random
import numpy as np
from datetime import date, timedelta
from core.entities.player import Player, Position
from core.utils.data_loader import load_last_names, load_first_names, load_nations, load_positions

AGE_BASE = 16
AGE_END = 40

class PlayerGenerator:
    def __init__(self, date_today):
        self.first_names = load_first_names()
        self.last_names = load_last_names()
        self.nations = load_nations()
        self.positions = load_positions()
        self.date_today = date_today
    
    def generate(self, player_id: int, team_id: int = None) -> Player:
        nation = random.choices(
            population= list(self.nations.keys()),
            weights= list(self.nations.values()))[0]
        
        position = random.choices(
            population= list(Position),
            weights= list(self.positions.values()))[0]
        
        first = random.choice(self.first_names.get(nation, ['Unknown']))
        last = random.choice(self.last_names.get(nation, ['Unknown']))
        
        lam = 19
        gam = 1  #не влияет
        while True:
            age_start = np.random.gamma(2, gam)
            if  0 <= age_start <= (AGE_END - AGE_BASE)/(lam - AGE_BASE)*gam:
                age_start *= (lam - AGE_BASE)/gam
                age_start += AGE_BASE
                break
        
        while True:
            age_peak = np.random.normal(28, 2.5)
            if  AGE_BASE <= age_peak <= AGE_END:
                break

        r_base = np.clip(np.random.normal(10, 2.5), 0, 20)

        while True:
            r_plus = np.random.gamma(shape= 2, scale= 20)
            if  r_plus <= 100 - r_base:
                break
        
        r_peak = r_base + r_plus

        delta = age_peak - AGE_BASE
        if delta > 0:
            k = -2.0 * r_plus / (delta ** 2)
        else:
            k = 0.0
        
        r_parab = r_peak + (k / 2.0) * ((age_start - age_peak) ** 2)
        
        mean_factor = 1.0 - ((age_start - AGE_BASE) / (AGE_END - AGE_BASE))**0.5
        mean_rating = np.clip(mean_factor * r_parab, 0, 100)

        #r_start = np.clip(np.random.normal(mean_rating, 5), 0, 100)
        r_start = mean_rating

        if age_start < age_peak:
            r_peak -= (r_parab - r_start)
        else:
            r_peak = r_start
            

        
        delta_days = timedelta(days= 365.2425 * age_start)
        birth_date = (self.date_today - delta_days).isoformat()

        return Player(
            id=player_id,
            first_name=first,
            last_name=last,
            nation=nation,
            age=age_start,
            position=position,
            rating=r_start,
            team_id=team_id,
            birth_date=birth_date,
            age_peak=age_peak,
            k=k,
        )