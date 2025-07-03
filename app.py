from flask import Flask, request, jsonify
import requests
import datetime
import csv
import os

app = Flask(__name__)

TODAY = datetime.datetime.now().strftime('%Y-%m-%d')
DATA_DIR = os.path.expanduser("~/Box/MLB_Stats_Snapshots")
os.makedirs(DATA_DIR, exist_ok=True)

ODDS_API_KEY = '803756147f1055030d8f479b0000351c'

# Convert UTC to CST (no DST)
def convert_to_cst(utc_time_str):
    utc_time = datetime.datetime.fromisoformat(utc_time_str.replace('Z', '+00:00'))
    cst_time = utc_time - datetime.timedelta(hours=6)
    return cst_time.replace(tzinfo=None)

# Fetch all MLB games for today
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

# Fetch player stats
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
    url = f"https://api.the-odds-api.com/v4/sports/baseball_mlb/odds?regions=us&markets=batter_home_runs,pitcher_strikeouts,batter_total_bases&apiKey={ODDS_API_KEY}"
    response = requests.get(url)
    if response.status_code != 200:
        return "-"
    try:
        odds_data = response.json()
        for game in odds_data:
            for bookmaker in game.get('bookmakers', []):
                for market in bookmaker.get('markets', []):
                    if market_type == 'HR' and market['key'] == 'batter_home_runs':
                        for outcome in market.get('outcomes', []):
                            if player_name.lower() in outcome['name'].lower():
                                return f"O{outcome.get('line', '?')} {outcome.get('price', '')}"
                    elif market_type == 'OBP' and market['key'] == 'batter_total_bases':
                        for outcome in market.get('outcomes', []):
                            if player_name.lower() in outcome['name'].lower() and outcome.get('line') == 1:
                                return f"O1.0 {outcome.get('price', '')}"
                    elif market_type == 'K' and market['key'] == 'pitcher_strikeouts':
                        for outcome in market.get('outcomes', []):
                            if player_name.lower() in outcome['name'].lower():
                                return f"O{outcome.get('line', '?')} {outcome.get('price', '')}"
    except:
        return "-"
    return "-"

@app.route('/fetch-mlb-stats', methods=['GET'])
def fetch_mlb_stats():
    category = request.args.get('category')
    if not category:
        return jsonify({"error": "Category query parameter is required."}), 400

    if category == 'sluggers':
        return jsonify([])  # Slugger logic here
    elif category == 'strikeouts':
        return jsonify([])  # Pitcher K logic here
    elif category == 'obp':
        return jsonify([])  # OBP logic here
    elif category == 'hr_allowed':
        return jsonify([])  # HR allowed logic here
    else:
        return jsonify({"error": "Invalid category specified."}), 400

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Route not found. Please check your endpoint URL."}), 404

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
