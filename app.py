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

ODDS_API_KEY = '803756147f1055030d8f479b0000351c'

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
            'datetime_obj': game_time,
            'probablePitchers': game['teams'].get('home', {}).get('probablePitcher', {}).get('fullName', '') + ' vs ' + game['teams'].get('away', {}).get('probablePitcher', {}).get('fullName', '')
        })
    print(f"Fetched {len(games)} games")
    return games

# Get player stats (generic)
def get_player_stat(player_id, stat_type='homeRuns'):
    url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats?stats=season&season=2024"
    response = requests.get(url)
    stats = response.json()
    try:
        splits = stats['stats'][0]['splits'][0]['stat']
        return float(splits.get(stat_type, 0))
    except:
        return 0

# Fetch betting odds

def get_odds(player_name, market_type='HR'):
    url = f"https://api.the-odds-api.com/v4/sports/baseball_mlb/odds?regions=us&markets=player_props&apiKey={ODDS_API_KEY}"
    response = requests.get(url)
    if response.status_code != 200:
        return "-"
    try:
        odds_data = response.json()
        for game in odds_data:
            for bookmaker in game.get('bookmakers', []):
                for market in bookmaker.get('markets', []):
                    if market['key'] == 'player_home_runs':
                        for outcome in market.get('outcomes', []):
                            if player_name.lower() in outcome['name'].lower():
                                return f"O{outcome.get('line', '?')} {outcome.get('price', '')}"
    except:
        return "-"
    return "-"

# Fetch OBP leaders for remaining games
def get_remaining_game_obp_leaders(limit=10):
    games = get_all_games()
    now_cst = datetime.datetime.now() - datetime.timedelta(hours=6)
    now_cst = now_cst.replace(tzinfo=None)
    players = []
    for game in games:
        game_time = game['datetime_obj']
        if game_time < now_cst:
            continue
        for team_side in ['home', 'away']:
            team_name = game[team_side]
            team_url = f"https://statsapi.mlb.com/api/v1/teams?sportId=1"
            teams_data = requests.get(team_url).json()
            team_id = next((t['id'] for t in teams_data['teams'] if t['name'] == team_name), None)
            if not team_id:
                continue
            roster_url = f"https://statsapi.mlb.com/api/v1/teams/{team_id}/roster"
            roster_data = requests.get(roster_url).json()
            for player in roster_data.get('roster', []):
                if player['position']['code'] != '1':
                    player_id = player['person']['id']
                    name = player['person']['fullName']
                    obp = get_player_stat(player_id, 'onBasePercentage')
                    players.append({
                        "Name": name,
                        "Team": team_name,
                        "Stat": obp,
                        "Day": TODAY,
                        "VS": game['away'] if team_side == 'home' else game['home'],
                        "Game Time (CST)": game_time.strftime('%H:%M'),
                        "O/U Odds": get_odds(name, market_type='OBP'),
                        "Notes": "Expected to play"
                    })
    sorted_players = sorted(players, key=lambda x: x['Stat'], reverse=True)
    return sorted_players[:limit]

# Fetch HR leaders
def get_remaining_game_hr_leaders(limit=10):
    games = get_all_games()
    now_cst = datetime.datetime.now() - datetime.timedelta(hours=6)
    now_cst = now_cst.replace(tzinfo=None)
    players = []
    for game in games:
        game_time = game['datetime_obj']
        if game_time < now_cst:
            continue
        for team_side in ['home', 'away']:
            team_name = game[team_side]
            team_url = f"https://statsapi.mlb.com/api/v1/teams?sportId=1"
            teams_data = requests.get(team_url).json()
            team_id = next((t['id'] for t in teams_data['teams'] if t['name'] == team_name), None)
            if not team_id:
                continue
            roster_url = f"https://statsapi.mlb.com/api/v1/teams/{team_id}/roster"
            roster_data = requests.get(roster_url).json()
            for player in roster_data.get('roster', []):
                if player['position']['code'] != '1':
                    player_id = player['person']['id']
                    name = player['person']['fullName']
                    hr = get_player_stat(player_id, 'homeRuns')
                    players.append({
                        "Name": name,
                        "Team": team_name,
                        "Stat": hr,
                        "Day": TODAY,
                        "VS": game['away'] if team_side == 'home' else game['home'],
                        "Game Time (CST)": game_time.strftime('%H:%M'),
                        "O/U Odds": get_odds(name, market_type='HR'),
                        "Notes": "Expected to play"
                    })
    sorted_players = sorted(players, key=lambda x: x['Stat'], reverse=True)
    return sorted_players[:limit]

@app.route('/mlb-obp-remaining', methods=['GET'])
def mlb_obp_remaining():
    players = get_remaining_game_obp_leaders()
    return jsonify(players)

@app.route('/mlb-hr-remaining', methods=['GET'])
def mlb_hr_remaining():
    players = get_remaining_game_hr_leaders()
    return jsonify(players)

@app.route('/mlb-k-leaders', methods=['GET'])
def mlb_k_leaders():
    games = get_all_games()
    now_cst = datetime.datetime.now() - datetime.timedelta(hours=6)
    now_cst = now_cst.replace(tzinfo=None)
    pitchers = []
    for game in games:
        if game['datetime_obj'] < now_cst:
            continue
        for team in ['home', 'away']:
            pitcher_name = game['probablePitchers'].split(' vs ')[0 if team == 'home' else 1]
            if pitcher_name and pitcher_name != 'None':
                pitchers.append({
                    "Name": pitcher_name,
                    "Team": game[team],
                    "Day": TODAY,
                    "VS": game['away'] if team == 'home' else game['home'],
                    "Game Time (CST)": game['datetime_obj'].strftime('%H:%M'),
                    "Strikeouts": "TBD",
                    "O/U Odds": get_odds(pitcher_name, market_type='K'),
                    "HRs Allowed": "TBD",
                    "Notes": "Probable starter"
                })
    return jsonify(pitchers)

@app.route('/test-odds-api', methods=['GET'])
def test_odds_api():
    test_name = request.args.get('player', 'Aaron Judge')
    market_type = request.args.get('market', 'HR')
    odds = get_odds(test_name, market_type)
    return jsonify({"Player": test_name, "Market": market_type, "Odds": odds})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
