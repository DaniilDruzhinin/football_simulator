import json
import argparse
from rich.console import Console
from rich.table import Table
from core.generators.player_generator import PlayerGenerator
from core.engine.match_simulator import simulate_match

console = Console()

def cmd_generate_players(args):
    gen = PlayerGenerator()
    players = [gen.generate(i) for i in range(1, args.count +1)]

    players_data = []
    for p in players:
        players_data.append({
            'id': p.id,
            'first_name': p.first_name,
            'last_name': p.last_name,
            'nation': p.nation,
            'age': p.age,
            'position': p.position.value,
            'rating': p.rating,
            'potential': p.potential
        })
    
    with open('players.json', 'w', encoding='utf-8') as f:
        json.dump(players_data, f, indent=2, ensure_ascii=False)
    
    table = Table(title=f'Сгенерировано {args.count} игроков')
    table.add_column('ID', style='cyan')
    table.add_column('Имя', style='green')
    table.add_column('')
    table.add_column('Нация')
    table.add_column('Возраст')
    table.add_column('Пол')
    table.add_column('Поз.')
    table.add_column('Рейт.')
    table.add_column('Пот.')

    for p in players[:20]:
        table.add_row(
            str(p.id),
            p.full_name(),
            p.nation,
            str(p.age),
            p.position.value[:2],
            str(p.rating),
            str(p.potential)
        )
    console.print(table)

def cmd_simulate(args):
    try:
        with open('players.json', 'r', encoding='utf-8') as f:
            players_data = json.load(f)
    except FileNotFoundError:
        console.print("[red]Файл players.json не найден. Сначала сгенерируйте игроков командой 'generate'.[/red]")
        return
    
    import random
    from core.entities.player import Player, Position

    all_players = []
    for data in players_data:
        pos = next(p for p in Position if p.value == data['position'])
        all_players.append(Player(
            id=data['id'],
            first_name= data['first_name'],
            last_name= data['last_name'],
            nation = data['nation'],
            age = data['age'],
            position= pos,
            rating= data['rating'],
            potential= data['potential']
        ))
    
    if  len(all_players) < 22:
        console.print("[red]Недостаточно игроков для двух команд (нужно минимум 22).[/red]")
        return
    
    random.shuffle(all_players)
    home_team = all_players[:11]
    away_team = all_players[11:22]

    home_goals, away_goals = simulate_match(home_team, away_team)

    console.print(f'[bold]Результат мматча:[/bold] {home_goals} : {away_goals}')