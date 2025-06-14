from flask import Flask, request, jsonify
import requests
import datetime
import csv
import os

app = Flask(__name__)

# Today's date
TODAY = datetime.datetime.now().strftime('%Y-%m-%d')
DATA_DIR = os.path.expanduser("~/Box/MLB_Stats_Snapshots")
os.makedirs(DATA_DIR, exist_ok=True)

# Convert UTC time to CST (no daylight saving)
def convert_to_cst(utc_time_str):
    utc_time = datetime.datetime.fromisoformat(utc_time_str.replace('Z', '+00:00'))
    cst_time = utc_time - datetime.timedelta(hours=6)
    return cst_time.replace(tzinfo=None)

# MLB Stats API: Fetch all games for today
def get_all_games():
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={TODAY}&hydrate=probablePitcher"
    response = requests.get(url)
    data = response.json()
    games = []
    for game in data.get('dates', [])[0].get('games', []):
        game_time = convert_to_cst(game['gameDate'])
        games.append({
            'gamePk': game['gamePk'],
            'home': game['teams']['home']['team']['name'],
            'away': game['teams']['away']['team']['name'],
            'time_cst': game_time.strftime('%Y-%m-%d %H:%M'),
            'datetime_obj': game_time
        })
    return games

# Get OBP for a player by ID
def get_player_obp(player_id):
    url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats?stats=season&season=2024"
    response = requests.get(url)
    stats = response.json()
    try:
        splits = stats['stats'][0]['splits'][0]['stat']
        return float(splits.get('onBasePercentage', 0))
    except:
        return 0.0

# Build OBP leaderboard for players in all today's games
def get_remaining_game_obp_leaders(limit=10):
    games = get_all_games()
    now_cst = datetime.datetime.now() - datetime.timedelta(hours=6)
    players = []
    for game in games:
        game_time = game['datetime_obj']
        if game_time < now_cst:
            continue  # Skip games already mostly completed
        box_url = f"https://statsapi.mlb.com/api/v1.1/game/{game['gamePk']}/boxscore"
        response = requests.get(box_url)
        box = response.json()
        if 'teams' not in box:
            continue
        for side in ['home', 'away']:
            if side not in box['teams']:
                continue
            for player_data in box['teams'][side].get('players', {}).values():
                person = player_data.get('person', {})
                if player_data.get('position', {}).get('code') != '1':  # Exclude pitchers
                    obp = get_player_obp(person['id'])
                    players.append({
                        "Name": person['fullName'],
                        "Team": game[side],
                        "Stat": obp,
                        "Day": TODAY,
                        "VS": game['away'] if side == 'home' else game['home'],
                        "Game Time (CST)": game['datetime_obj'].strftime('%H:%M'),
                        "O/U Odds": "-",
                        "Notes": "Playing later today"
                    })
    sorted_players = sorted(players, key=lambda x: x['Stat'], reverse=True)
    return sorted_players[:limit]

@app.route('/mlb-obp-remaining', methods=['GET'])
def mlb_obp_remaining():
    players = get_remaining_game_obp_leaders()
    return jsonify(players)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
