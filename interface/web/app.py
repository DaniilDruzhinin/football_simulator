import json
import random
import numpy as np
from datetime import date, timedelta
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader
from core.generators.player_generator import PlayerGenerator
from core.generators.team_generator import load_teams_from_json
from core.engine.match_simulator import simulate_match
from core.entities.player import Player, Position
from core.entities.team import Team

BASE_DIR = Path.cwd()
TEMPLATES_DIR = BASE_DIR / "interface" / "web" / "templates"
STATIC_DIR = BASE_DIR / "interface" / "web" / "static"

app = FastAPI(title="Football Simulator")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
jinja_env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))

GAMES_PER_SEASON = 38
SEASON_START_REFERENCE = date(2026, 8, 15)

# Глобальные данные
TEAMS = load_teams_from_json()
players_db: list[Player] = []
PLAYERS_FILE = BASE_DIR / "players.json"
SEASONS_FILE = BASE_DIR / 'seasons.json'



# ==================== Утилиты ====================
def sync_teams_players():
    for team in TEAMS:
        team.players = [p for p in players_db if p.team_id == team.id]

sync_teams_players()

def load_players() -> list[Player]:
    global players_db
    if not PLAYERS_FILE.exists():
        return []
    with open(PLAYERS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    players_db = []
    for p_data in data:
        pos = next(pos for pos in Position if pos.value == p_data["position"])
        
        bdate = p_data.get('birth_date')
        age = p_data['age']
        if not bdate:
            delta = timedelta(days= 365*age + random.randint(0, 364))
            bdate = (SEASON_START_REFERENCE - delta).isoformat()

        players_db.append(Player(
            id=p_data["id"],
            first_name=p_data["first_name"],
            last_name=p_data["last_name"],
            nation=p_data["nation"],
            age=p_data["age"],
            position=pos,
            rating=p_data["rating"],
            team_id=p_data.get('team_id'),
            birth_date=bdate,
            age_peak=p_data['age_peak'],
            k=p_data['k']
        ))
    return players_db

def save_players(players: list[Player]):
    data = []
    for p in players:
        bd = p.birth_date if isinstance(p.birth_date, str) else str(p.birth_date)
        data.append({
            "id": p.id,
            "first_name": p.first_name,
            "last_name": p.last_name,
            "nation": p.nation,
            "age": p.age,
            "position": p.position.value,
            "rating": p.rating,
            'team_id': p.team_id,
            'birth_date': bd,
            'age_peak': p.age_peak,
            'k': p.k
        })
    with open(PLAYERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_teams_stats_json():
    teams_stats = {}
    for team in TEAMS:
        formation, lineup = team.get_best_lineup()
        if lineup:
            teams_stats[team.id] = team.get_stats(lineup)
        else:
            teams_stats[team.id] = None
    return json.dumps(teams_stats)

def get_teams_data_json():
    teams_data = [{'id': t.id, 'name': t.name} for t in TEAMS]
    return json.dumps(teams_data)

def get_teams_lineup_stats(ref_date: date = None):
    stats = {}
    for team in TEAMS:
        formation, lineup = team.get_best_lineup()
        if lineup:
            stats[team.id] = team.get_stats(lineup, ref_date)
        else:
            stats[team.id] = None
    return stats

def sort_key(item):
    t_id, x = item
    return (-x['points'], -(x['goals_for'] - x['goals_against']), -x['goals_for'])

def render_template(template_name: str, context: dict) -> HTMLResponse:
    template = jinja_env.get_template(template_name)
    return HTMLResponse(content=template.render(context))

load_players()

def get_team_form(team_id, matches_played, tour_idx):
    team_matches = [m for m in matches_played if m['tour'] <= tour_idx and team_id in (m['home'], m['away'])]
    team_matches.sort(key=lambda m: m['tour'])
    form = []
    for m in team_matches[-5:]:
        hg, ag = m['home_goals'], m['away_goals']
        (gf, ga) = [(hg, ag), (ag, hg)][m['home'] != team_id]
        wdl = 'W' if gf > ga else ('D' if gf == ga else 'L')
        form.append(wdl)
    while len(form) < 5:
        form.insert(0, '-')
    return form [-5:]

# ==================== Сезоны ====================
def _convert_season_keys(season):
    state = season.get('state')
    if not state:
        return
    
    if 'schedule' in state:
        state['schedule'] = [
            [(int(h), int(a)) for h, a in tour]
            for tour in state['schedule']
        ]
    if 'table_history' in state:
        state['table_history'] = [
            {int(k): v for k, v in table.items()}
            for table in state['table_history']
        ]
    if 'team_form' in state:
        state['team_form'] = {int(k): v for k, v in state['team_form'].items()}
    if 'matches_played' in state:
        for m in state['matches_played']:
            m['home'] = int(m['home'])
            m['away'] = int(m['away'])
            m['tour'] = int(m['tour'])
    state['current_tour'] = int(state['current_tour'])

def load_seasons():
    if not SEASONS_FILE.exists():
        print('seasons.json не найден, создается новый')
        return {'seasons': [], 'active_season_id': None}
    with open(SEASONS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    team_ids = {t.id for t in TEAMS}
    valid = []
    for s in data.get('seasons', []):
        _convert_season_keys(s)
        if  _is_season_valid(s, team_ids):
            valid.append(s)
    data['seasons'] = valid

    if data['active_season_id'] and not any(s['id'] == data['active_season_id'] for s in valid):
        data['active_season_id'] = None
    return data

def _is_season_valid(season, team_ids):
    state = season.get('state')
    if not state:
        return False
    for tour in state.get('schedule', []):
        for home, away in tour:
            if home not in team_ids or away not in team_ids:
                return False
    return True

def save_seasons(data):
    with open(SEASONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

seasons_data = load_seasons()

def get_active_season():
    if seasons_data['active_season_id'] is None:
        return None
    for s in seasons_data['seasons']:
        if s['id'] == seasons_data['active_season_id']:
            return s
    return None

def generate_round_robin_schedule(team_ids):
    n = len(team_ids)
    if n % 2 == 1:
        team_ids.append(None)
        n += 1
    
    schedule_first = []
    mid = n // 2
    teams = team_ids[:]
    for _ in range(n - 1):
        round_matches = []
        for i in range(mid):
            home = teams[i]
            away = teams[n - 1 - i]
            if home is not None and away is not None:
                round_matches.append((home, away))
        schedule_first.append(round_matches)
        teams = [teams[0]] + [teams[-1]] + teams[1:-1]
    
    schedule_second = [[(away, home) for (home, away) in r] for r in schedule_first]

    return schedule_first + schedule_second

def generate_tour_dates(season_start_year: int, num_tours: int):
    first = date(season_start_year, SEASON_START_REFERENCE.month, SEASON_START_REFERENCE.day)
    dates = []
    for i in range(num_tours):
        dates.append((first + timedelta(days= 8*i)).isoformat())
    return dates

def get_reference_date() -> date:
    active = get_active_season()
    if active:
        state = active['state']
        tour_dates = state.get('tour_dates', [])
        current_tour = state['current_tour']
        if tour_dates:
            idx = max(0, current_tour - 1)
            if idx < len(tour_dates):
                return date.fromisoformat(tour_dates[idx])
    return SEASON_START_REFERENCE

def award_top_teams(state):
    final_table = state['table_history'][-1]
    sorted_teams = sorted(final_table.items(), key=sort_key)
    top_ids = [t_id for t_id, _ in sorted_teams[:3]]
    bonuses = {top_ids[0]: 3, top_ids[1]: 2, top_ids[2]: 1}
    #удалить надо
    #bonuses = {}

    for team_id, bonus in bonuses.items():
        team = next((t for t in TEAMS if t.id == team_id), None)
        if not team:
            continue
        formation, lineup = team.get_best_lineup()
        for player in lineup:
            idx = next((i for i, p in enumerate(players_db) if p.id == player.id), None)
            if idx is not None:
                p = players_db[idx]
                p.rating = min(100, p.rating + bonus)
                #p.potential = min(100, p.potential + bonus)
                players_db[idx] = p
        for idx, p in enumerate(players_db):
            if  p.team_id == team_id and p not in lineup:
                extra = max(0, bonus - 1)
                players_db[idx].rating = min(100, players_db[idx].rating + extra)
                #players_db[idx].potential = min(100, players_db[idx].potential + extra)

def generate_new_players_after_season(final_standings):
    active = get_active_season()
    ref_date = SEASON_START_REFERENCE
    if active:
        start_year = int(active['id'].split('-')[0]) + 1
        ref_date = date(start_year, SEASON_START_REFERENCE.month, SEASON_START_REFERENCE.day)

    gen = PlayerGenerator(ref_date)
    next_id = max([p.id for p in players_db], default=0) + 1
    new_players = []
    for i, team_id in enumerate(final_standings):
        a, b = 5, 20
        q = 19
        cnt = round((b-a)/q**2 * (i-q)**2 + a)
        #удалить надо
        #cnt = 0
        for _ in range(cnt):
            player = gen.generate(next_id, team_id=team_id)
            new_players.append(player)
            next_id += 1
    players_db.extend(new_players)
    sync_teams_players()

def age_players_to_date(ref_date: date):
    global players_db
    new_db = []
    removed = False
    for p in players_db:
        new_age = p.age_curr(ref_date)
        if new_age >= 40 or p.rating <= 1:
            removed = True
            continue
        p.age = new_age
        new_db.append(p)
    if removed:
        players_db = new_db
    save_players(players_db)
    sync_teams_players()

def apply_match_growth(home_lineup, away_lineup, home_team, away_team, home_goals, away_goals):
    if  home_goals > away_goals:
        home_pts = 3
    elif home_goals == away_goals:
        home_pts = 1
    else:
        home_pts = 0
    away_pts = 3 - home_pts if home_pts != 1 else 1

    AVG_POINTS = 1.45
    pts_growth = {0: 0.25, 1: 1, 3: 3}
    pts_reces = {0: 3.5, 1: 1.5, 3: 0.5}

    pts_growth_banq = {0: 0.5, 1: 1, 3: 1.5}
    pts_reces_banq = {0: 2, 1: 1, 3: 0.25}

    for player in home_team:
        age, age_peak = player.age, player.age_peak
        base_rate = player.k * (age - age_peak)  #изменение рейтинга в год!
        if player in home_lineup:
            if age <= age_peak:
                pts = pts_growth[home_pts]
            else:
                pts = pts_reces[home_pts]
        else:
            if age <= age_peak:
                pts = pts_growth_banq[home_pts]
            else:
                pts = pts_reces_banq[home_pts]
        coeff = pts / AVG_POINTS
        
        boost = coeff * (base_rate / GAMES_PER_SEASON)
        player.rating = np.clip(player.rating + boost, 0, 100)

    for player in away_team:
        age, age_peak = player.age, player.age_peak
        base_rate = player.k * (age - age_peak)

        if player in away_lineup:
            if age <= age_peak:
                pts = pts_growth[away_pts]
            else:
                pts = pts_reces[away_pts]
        else:
            if age <= age_peak:
                pts = pts_growth_banq[away_pts]
            else:
                pts = pts_reces_banq[away_pts]
        coeff = pts / AVG_POINTS

        boost = coeff * (base_rate / GAMES_PER_SEASON)
        player.rating = np.clip(player.rating + boost, 0, 100)

DESIRED_ORDER = [
    "Fulham", "Aston Villa", "Chelsea", "Ipswich Town", "Nottingham Forest",
    "Liverpool", "Newcastle United", "Arsenal", "Manchester City", "Bournemouth",
    "Tottenham Hotspur", "Leicester City", "Brentford", "West Ham United",
    "Brighton & Hove Albion", "Wolverhampton Wanderers", "Everton",
    "Southampton", "Crystal Palace", "Manchester United"
]

def reorder_teams_by_desired_order():
    global players_db
    sync_teams_players()
    teams_avg = []
    for team in TEAMS:
        formation, lineup = team.get_best_lineup()
        if lineup:
            avg = sum(p.rating_int() for p in lineup) / len(lineup)
        else:
            avg = 0
        teams_avg.append((team.id, avg))
    teams_avg.sort(key= lambda x: -x[1])
    
    mapping = {}
    for rank, (orig_team_id, _) in enumerate(teams_avg):
        desired_team = next(t for t in TEAMS if t.name == DESIRED_ORDER[rank])
        mapping[orig_team_id] = desired_team.id
    
    for player in players_db:
        if player.team_id in mapping:
            player.team_id = mapping[player.team_id]
    
    save_players(players_db)
    sync_teams_players()

# ==================== Маршруты ====================
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return render_template("index.html", {"request": request, 'teams': TEAMS})

@app.get("/teams", response_class=HTMLResponse)
async def list_teams(request: Request):
    sync_teams_players()
    ref_date = get_reference_date()
    return render_template("teams.html", {
        "request": request,
        'teams': TEAMS,
        'lineup_stats': get_teams_lineup_stats(ref_date)
    })

@app.get("/team/{team_id}", response_class=HTMLResponse)
async def team_detail(request: Request, team_id: int):
    sync_teams_players()
    team = next((t for t in TEAMS if t.id == team_id), None)
    if  not team:
        return HTMLResponse('Team not found', status_code=404)
    
    ref_date = get_reference_date()
    all_stats = team.get_stats(team.players, ref_date)

    best_formation, lineup = team.get_best_lineup()
    available = best_formation is not None
    lineup_stats = team.get_stats(lineup, ref_date) if available else None
    
    _, missing = team.check_lineup_availability() if not available else None, None
    
    return render_template('team_detail.html', {
        'request': request,
        'team': team,
        'all_stats': all_stats,
        'lineup_available': available,
        'best_formation': best_formation,
        'lineup': lineup,
        'missing_list': missing,
        'lineup_stats': lineup_stats,
        'reference_date': ref_date
    })

@app.get("/players", response_class=HTMLResponse)
async def list_players(request: Request):
    return render_template("players.html", {
        "request": request,
        "players": players_db,
        "count": len(players_db),
        'teams': TEAMS,
        'reference_date': get_reference_date()
    })

@app.post("/generate", response_class=HTMLResponse)
async def generate_players(request: Request, count: int = Form(100), team_id: str = Form('random')):
    global seasons_data
    gen = PlayerGenerator(get_reference_date())
    next_id = max([p.id for p in players_db], default=0) + 1
    new_players = []
    if team_id == 'random':
        for i in range(count):
            team = random.choice(TEAMS)
            player = gen.generate(next_id + i, team_id=team.id)
            new_players.append(player)
    else:
        target_team_id = int(team_id)
        for i in range(count):
            player = gen.generate(next_id + i, team_id=target_team_id)
            new_players.append(player)

    players_db.extend(new_players)
    if len(players_db) == count:
        reorder_teams_by_desired_order()
    
    save_players(players_db)
    sync_teams_players()
    return render_template("players.html", {
        "request": request,
        "players": players_db,
        "count": len(players_db),
        'teams': TEAMS,
        'reference_date': get_reference_date(),
        "message": f"Сгенерировано {count} игроков",
        'last_count': count,
        'last_team_id': team_id
    })

@app.post('/delete', response_class=HTMLResponse)
async def delete_players(request: Request, scope: str = Form(...), team_id: Optional[int] = Form(None)):
    global players_db, seasons_data

    if scope == 'all':
        players_db.clear()
        message = 'Все игроки удалены'
    elif scope == 'team':
        if team_id is None:
            return render_template('players.html', {
                'request': request,
                'players': players_db,
                'count': len(players_db),
                'teams': TEAMS,
                'reference_date': get_reference_date(),
                'error': 'Выберите команду для удаления'
            })
        players_db = [p for p in players_db if p.team_id != team_id]
        team_name = next((t for t in TEAMS if t.id == team_id), 'Неизвестная')
        message = f'Игроки команды {team_name} удалены'
    else:
        return render_template('players.html', {
            'request': request,
            'players': players_db,
            'count': len(players_db),
            'teams': TEAMS,
            'reference_date': get_reference_date(),
            'error': 'Неверный параметр'
        })
    
    save_players(players_db)
    sync_teams_players()
    return render_template('players.html', {
        'request': request,
        'players': players_db,
        'count': len(players_db),
        'teams': TEAMS,
        'reference_date': get_reference_date(),
        'message': message,
        'last_count': 0,
        'last_team_id': 'random'
    })

@app.get("/match", response_class=HTMLResponse)
async def match_form(request: Request):
    sync_teams_players()
    default_home = TEAMS[0].id if len(TEAMS) > 0 else None
    default_away = TEAMS[1].id if len(TEAMS)> 1 else default_home

    return render_template("match.html", {
        "request": request,
        "teams": TEAMS,
        "result": None,
        'selected_home': default_home,
        'selected_away': default_away,
        'teams_stats_json': get_teams_stats_json(),
        'teams_data_json': get_teams_data_json()
    })

@app.post("/simulate", response_class=HTMLResponse)
async def simulate(request: Request, home_team_id: int = Form(...), away_team_id: int = Form(...)):
    sync_teams_players()
    if  home_team_id == away_team_id:
        return render_template('match.html', {
            'request': request,
            'teams': TEAMS,
            'error': 'Нельзя выбрать одну и ту же команду',
            'selected_home': home_team_id,
            'selected_away': away_team_id,
            'home_stats': None,
            'away_stats': None,
            'teams_stats_json': get_teams_stats_json(),
            'teams_data_json': get_teams_data_json()
        })
    
    home_team = next(t for t in TEAMS if t.id == home_team_id)
    away_team = next(t for t in TEAMS if t.id == away_team_id)

    home_team.players = [p for p in players_db if p.team_id == home_team_id]
    away_team.players = [p for p in players_db if p.team_id == away_team_id]

    home_available, home_missing = home_team.check_lineup_availability()
    away_available, away_missing = away_team.check_lineup_availability()

    if not home_available or not away_available:
        error_msg = []
        if not home_available:
            missing_str = ", ".join([f'{k}: {v}' for k, v in home_missing.items()])
            error_msg.append(f'{home_team.name}: не хватает игроков ({missing_str})')
        if not away_available:
            missing_str = ", ".join([f'{k}: {v}' for k, v in away_missing.items()])
            error_msg.append(f'{away_team.name}: не хватает игроков ({missing_str})')
        
        home_stats = home_team.get_stats(home_team.players) if home_team.players else None
        away_stats = away_team.get_stats(away_team.players) if away_team.players else None


        return render_template('match.html', {
            'request': request,
            'teams': TEAMS,
            'error': 'Невозможно провести матч. ' + '; '.join(error_msg),
            'selected_home': home_team_id,
            'selected_away': away_team_id,
            'home_stats': home_stats,
            'away_stats': away_stats,
            'teams_stats_json': get_teams_stats_json(),
            'teams_data_json': get_teams_data_json()
        })

    home_goals, away_goals, home_lineup, away_lineup = simulate_match(home_team, away_team)

    home_stats = home_team.get_stats(home_lineup)
    away_stats = away_team.get_stats(away_lineup)

    home_lineup_info = [{'name': p.full_name(), 'pos': p.position.name, 'rating': p.rating} for p in home_lineup]
    away_lineup_info = [{'name': p.full_name(), 'pos': p.position.name, 'rating': p.rating} for p in away_lineup]

    result = {
        "home_goals": home_goals,
        "away_goals": away_goals,
        "home_team": home_team.name,
        "away_team": away_team.name,
        'home_lineup': home_lineup_info,
        'away_lineup': away_lineup_info
    }

    return render_template("match.html", {
        "request": request,
        'teams': TEAMS,
        "result": result,
        'selected_home': home_team_id,
        'selected_away': away_team_id,
        'home_stats': home_stats,
        'away_stats': away_stats,
        'teams_stats_json': get_teams_stats_json(),
        'teams_data_json': get_teams_data_json()
    })

@app.post('/simulate_batch', response_class=HTMLResponse)
async def simulate_batch(request: Request, home_team_id: int = Form(...),
        away_team_id: int = Form(...), n: int = Form(100)):
    sync_teams_players()
    if  home_team_id == away_team_id:
        return HTMLResponse('<div class="error">Нельзя выбрать одну и ту же команду</div>')
    
    home_team = next((t for t in TEAMS if t.id == home_team_id), None)
    away_team = next((t for t in TEAMS if t.id == away_team_id), None)
    if not home_team or not away_team:
        return HTMLResponse('<div class="error">Команда не найдена</div>', status_code=404)

    home_team.players = [p for p in players_db if p.team_id == home_team_id]
    away_team.players = [p for p in players_db if p.team_id == away_team_id]

    home_available, home_missing = home_team.check_lineup_availability()
    away_available, away_missing = away_team.check_lineup_availability()

    if not home_available or not away_available:
        error_msg = []
        if not home_available:
            missing_str = ", ".join([f'{k}: {v}' for k, v in home_missing.items()])
            error_msg.append(f'{home_team.name}: не хватает игроков ({missing_str})')
        if not away_available:
            missing_str = ", ".join([f'{k}: {v}' for k, v in away_missing.items()])
            error_msg.append(f'{away_team.name}: не хватает игроков ({missing_str})')
        return HTMLResponse(f'<div class="error">Невозможно провести матч. {"; ".join(error_msg)}</div>')
    
    home_wins = away_wins = draws = 0
    total_home_goals = total_away_goals = 0
    for _ in range(n):
        hg, ag, _, _ = simulate_match(home_team, away_team)
        total_home_goals += hg
        total_away_goals += ag
        if hg > ag:
            home_wins += 1
        elif ag > hg:
            away_wins += 1
        else:
            draws += 1
    
    stats = {
        'home_wins': home_wins,
        'away_wins': away_wins,
        'draws': draws,
        'avg_home_goals': total_home_goals / n,
        'avg_away_goals': total_away_goals / n,
        'home_wins_pct': home_wins / n * 100,
        'away_wins_pct': away_wins / n *100,
        'draws_pct': draws / n * 100
    }

    return render_template('batch_result.html', {
        'request': request,
        'batch_stats': stats,
        'n_sim': n
    })




# ==================== Чемпионат ====================
@app.get('/league', response_class=HTMLResponse)
async def league_page(request: Request, tour: Optional[int] = None, 
                        season_id: Optional[str] = None):
    global seasons_data
    sync_teams_players()

    if season_id:
        season = next((s for s in seasons_data['seasons'] if s['id'] == season_id), None)
        if not season:
            return HTMLResponse('Сезон не найден', status_code=404)
        active = season
    else:
        active = get_active_season()

    if active is None:
        can_start = all(t.check_lineup_availability()[0] for t in TEAMS)
        return render_template('league.html', {
            'request': request,
            'teams': TEAMS,
            'seasons': seasons_data['seasons'],
            'league_started': False,
            'can_start': can_start,
            'selected_season_id': None
        })
    
    state = active['state']
    total_tours = len(state['schedule'])
    current_tour = state['current_tour']
    finished = active.get('completed', False) or current_tour >= total_tours
    view_tour = tour if tour is not None else current_tour
    view_tour = max(0, min(view_tour, current_tour))
    
    table = state['table_history'][view_tour] if view_tour > 0 else state['table_history'][0]
    sorted_items = sorted(table.items(), key= sort_key)

    sorted_table = []
    prev_table = state['table_history'][view_tour - 1] if view_tour > 0 else None

    prev_positions = {}
    if prev_table:
        sorted_prev = sorted(prev_table.items(), key=sort_key)
        for pos, (t_id, _) in enumerate(sorted_prev, start=1):
            prev_positions[t_id] = pos

    curr_table = state['table_history'][-1]
    curr_sorted = sorted(curr_table.items(), key=sort_key)
    curr_positions = {t_id: pos for pos, (t_id, _) in enumerate(curr_sorted, start=1)}
    for idx, (t_id, row) in enumerate(sorted_items, start=1):
        r = row.copy()
        r['id'] = t_id
        r['position'] = idx
        r['position_change'] = prev_positions.get(t_id, idx) - idx
        r['goal_diff'] = r['goals_for'] - r['goals_against']
        r['form'] = get_team_form(t_id, state['matches_played'], view_tour - 1 if view_tour > 0 else -1)
        sorted_table.append(r)

    matches = [m for m in state['matches_played'] if m['tour'] == view_tour - 1] if view_tour > 0 else []
    
    tour_dates = state.get('tour_dates', [])
    view_tour_date = tour_dates[view_tour - 1] if 0 < view_tour <= len(tour_dates) else None
    
    next_match_info = {}
    if not finished and view_tour == current_tour:
        for home_id, away_id in state['schedule'][current_tour]:
            opp_home = next((t.name for t in TEAMS if t.id == away_id), '?')
            opp_away = next((t.name for t in TEAMS if t.id == home_id), '?')
            pos_home = curr_positions.get(away_id, '?')
            pos_away = curr_positions.get(home_id, '?')
            next_match_info[home_id] = f'{opp_home} ({pos_home})'
            next_match_info[away_id] = f'{opp_away} ({pos_away})'
    
    team_form = state.get('team_form', {})
    
    return render_template('league.html', {
        'request': request,
        'teams': TEAMS,
        'seasons': seasons_data['seasons'],
        'active_season': active,
        'selected_season_id': active['id'],
        'league_started': True,
        'finished': finished,
        'table': sorted_table,
        'current_tour': current_tour,
        'view_tour': view_tour,
        'total_tours': total_tours,
        'matches': matches,
        'next_match_info': next_match_info,
        'view_tour_date': view_tour_date,
        'can_start_new': finished
    })

@app.post('/league/start_new_season', response_class=HTMLResponse)
async def start_new_season(request: Request):
    global seasons_data, players_db
    sync_teams_players()
    for team in TEAMS:
        available, missing = team.check_lineup_availability()
        if not available:
            return render_template('league.html', {
                'request': request,
                'teams': TEAMS,
                'seasons': seasons_data['seasons'],
                'league_started': False,
                'can_start': False,
                'error': f'Команда {team.name} не может выставить основной состав: не хватает {missing}'
            })
    
    active = get_active_season()
    if active and not active.get('completed', False):
        state = active['state']
        if state['current_tour'] < len(state['schedule']):
            active['completed'] = True
            award_top_teams(state)
            final_table = state['table_history'][-1]
            sorted_table = sorted(final_table.items(), key=sort_key)
            final_order = [t_id for t_id, _ in sorted_table]
            generate_new_players_after_season(final_order)
            save_players(players_db)
            sync_teams_players()
        save_seasons(seasons_data)


    existing = seasons_data['seasons']
    if existing:
        start_year = int(existing[-1]['id'].split('-')[0]) + 1
    else:
        start_year = SEASON_START_REFERENCE.year
    new_id = f'{start_year}-{str(start_year + 1)[-2:]}'
    
    team_ids = [t.id for t in TEAMS]
    random.shuffle(team_ids)
    schedule = generate_round_robin_schedule(team_ids)
    initial_table = {t.id: {
        'name': t.name, 'played': 0, 'wins': 0, 'draws': 0, 'losses': 0, 
        'goals_for': 0, 'goals_against': 0, 'points': 0
    } for t in TEAMS}

    tour_dates = generate_tour_dates(start_year, len(schedule))
    team_form = {t.id: [''] * 5 for t in TEAMS}

    new_season = {
        'id': new_id,
        'state': {
            'schedule': schedule,
            'current_tour': 0,
            'table_history': [initial_table],
            'matches_played': [],
            'tour_dates': tour_dates,
            'team_form': team_form
        },
        'completed': False
    }

    seasons_data['seasons'].append(new_season)
    seasons_data['active_season_id'] = new_id

    try:
        save_seasons(seasons_data)
    except Exception as e: 
        print(f'Ошибка сохранения сезона в start_new: {e}')
    
    return RedirectResponse(url='/league', status_code=303)

@app.post('/league/next_tour', response_class=HTMLResponse)
async def next_tour(request: Request):
    global seasons_data, players_db
    active = get_active_season()
    if not active:
        return RedirectResponse(url='/league', status_code=303)
    
    state = active['state']
    current_tour = state['current_tour']
    total_tours = len(state['schedule'])
    if current_tour >= total_tours:
        return RedirectResponse(url='/league', status_code=303)
    
    tour_dates = state.get('tour_dates', [])
    if current_tour < len(tour_dates):
        ref_date = date.fromisoformat(tour_dates[current_tour])
    else:
        ref_date = SEASON_START_REFERENCE

    age_players_to_date(ref_date)

    sync_teams_players()

    tour_matches = state['schedule'][current_tour]
    last_table = state['table_history'][-1].copy()

    team_form = {t_id: state['team_form'][t_id][:] for t_id in state['team_form']}

    for home_id, away_id in tour_matches:
        home_team = next((t for t in TEAMS if t.id == home_id), None)
        away_team = next((t for t in TEAMS if t.id == away_id), None)
        if not home_team or not away_team:
            continue
        
        hg, ag, home_lineup, away_lineup = simulate_match(home_team, away_team)
        state['matches_played'].append({
            'tour': current_tour,
            'home': home_id,
            'away': away_id,
            'home_goals': hg,
            'away_goals': ag
        })

        apply_match_growth(home_lineup, away_lineup, home_team.players, away_team.players, hg, ag)

        for team_id, gf, ga in [(home_id, hg, ag), (away_id, ag, hg)]:
            is_home = (home_id == team_id)

            points = 3 if gf > ga else (1 if gf == ga else 0)
            wins = 1 if gf > ga else 0
            draws = 1 if gf == ga else 0
            losses = 1 if gf < ga else 0

            result = 'W' if wins else ('D' if draws else 'L')
            form_list = team_form[team_id]
            form_list.pop(0)
            form_list.append(result)

            record = last_table.get(team_id, {
                'name': next((t.name for t in TEAMS if t.id == team_id), '?'),
                'played': 0, 'wins': 0, 'draws': 0, 'losses': 0,
                'goals_for': 0, 'goals_against': 0, 'points': 0
            }).copy()
            record['played'] += 1
            record['wins'] += wins
            record['draws'] += draws
            record['losses'] += losses
            record['goals_for'] += gf
            record['goals_against'] += ga
            record['points'] += points
            last_table[team_id] = record
    
    state['table_history'].append(last_table)
    state['current_tour'] += 1
    state['team_form'] = team_form

    if state['current_tour'] >= total_tours:
        active['completed'] = True
        try:
            award_top_teams(state)
            final_table = state['table_history'][-1]
            sorted_table = sorted(final_table.items(), key=sort_key)
            final_order = [t_id for t_id, _ in sorted_table]
            generate_new_players_after_season(final_order)
            save_players(players_db)
            sync_teams_players()
        except Exception as e: 
            print(f'Ошибка при завершении сезона в next_tour: {e}')
    
    try:
        save_seasons(seasons_data)
    except Exception as e:
        print(f'Не удалось сохранить сезоны в next_tour: {e}')

    return RedirectResponse(url='/league', status_code=303)
    