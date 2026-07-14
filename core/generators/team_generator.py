import json
from pathlib import Path
from core.entities.team import Team
from core.utils.data_loader import load_teams

def load_teams_from_json():
    teams_data = load_teams()
    teams = []
    for td in teams_data:
        teams.append(Team(
            id= td['id'],
            name= td['name'],
            city= td['city'],
            stadium= td['stadium'],
        ))
    return teams