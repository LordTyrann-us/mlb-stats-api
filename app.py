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
    print(f"Fetched {len(games)} games")
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

# Fetch roster and build OBP leaderboard
def get_remaining_game_obp_leaders(limit=10):
    games = get_all_games()
    now_cst = datetime.datetime.now() - datetime.timedelta(hours=6)
    now_cst = now_cst.replace(tzinfo=None)
    players = []
    for game in games:
        game_time = game['datetime_obj']
        print(f"Checking game at {game_time} vs now {now_cst}")
        if game_time < now_cst:
            continue
        for team_side in ['home', 'away']:
            team_name = game[team_side]
            team_url = f"https://statsapi.mlb.com/api/v1/teams?sportId=1"
            teams_data = requests.get(team_url).json()
            team_id = None
            for t in teams_data['teams']:
                if t['name'] == team_name:
                    team_id = t['id']
                    break
            if not team_id:
                continue
            roster_url = f"https://statsapi.mlb.com/api/v1/teams/{team_id}/roster"
            roster_data = requests.get(roster_url).json()
            for player in roster_data.get('roster', []):
                if player['position']['code'] != '1':
                    player_id = player['person']['id']
                    obp = get_player_obp(player_id)
                    players.append({
                        "Name": player['person']['fullName'],
                        "Team": team_name,
                        "Stat": obp,
                        "Day": TODAY,
                        "VS": game['away'] if team_side == 'home' else game['home'],
                        "Game Time (CST)": game_time.strftime('%H:%M'),
                        "O/U Odds": "-",
                        "Notes": "Expected to play"
                    })
    sorted_players = sorted(players, key=lambda x: x['Stat'], reverse=True)
    return sorted_players[:limit]

@app.route('/mlb-obp-remaining', methods=['GET'])
def mlb_obp_remaining():
    players = get_remaining_game_obp_leaders()
    return jsonify(players)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
