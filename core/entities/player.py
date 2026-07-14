from dataclasses import dataclass
from enum import Enum
from typing import Optional
from datetime import date, timedelta

class Position(Enum):
    GK = 'Goalkeeper'
    CB = 'Center Back'
    FB = 'Full Back'
    DM = 'Defense Midfielder'
    CM = 'Central Midfielder'
    AM = 'Attacking Midfielder'
    WG = 'Winger'
    ST = 'Striker'

@dataclass
class Player:
    id: int
    first_name: str
    last_name: str
    nation: str
    age: float
    position: Position
    rating: float = 0.0
    team_id: Optional[int] = None
    birth_date: Optional[str] = None  # ISO format 'YYYY-MM-DD'
    age_peak: float = 28.0
    k: float = 0.0

    def potential_value(self) -> Optional[int]:
        if  self.age >= self.age_peak:
            return None
        add = (-self.k / 2.0) * ((self.age_peak - self.age) ** 2)
        return max(0, min(100, self.rating + add))
    
    def potential_display(self) -> str:
        val = self.potential_value()
        return str(int(val)) if val != None else '-'

    def full_name(self) -> str:
        return f'{self.first_name} {self.last_name}'
    
    def rating_int(self) -> int:
        return int(self.rating)
    
    def exp_pct(self) -> int:
        frac = self.rating - int(self.rating)
        return round(100 * frac, 1)
    
    def age_curr(self, ref_date: date) -> int:
        bd = date.fromisoformat(self.birth_date)
        if not bd:
            return self.age
        
        return (ref_date - bd).days / 365.2425

    def age_str(self, ref_date: date) -> str:
        bd = date.fromisoformat(self.birth_date)
        if not bd:
            return f'{self.age} л.'
        
        years = ref_date.year - bd.year
        months = ref_date.month - bd.month

        if ref_date.day < bd.day:
            months -= 1
        if months < 0:
            years -= 1
            months += 12
        return f'{years} л. {months} мес.'
    
    def age_days(self, ref: date) -> int:
        bd = date.fromisoformat(self.birth_date)
        if not bd:
            return self.age * 365.2425
        
        return (ref - bd).days