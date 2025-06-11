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

# MLB Stats API: Leaderboard fetch function
def get_stat_leaders(stat_type, player_pool='qualified', limit=10):
    stat_map = {
        'strikeouts': 'strikeouts',
        'homeRunsAllowed': 'homeRunsAllowed'
    }
    stat_type_corrected = stat_map.get(stat_type, stat_type)
    url = f"https://statsapi.mlb.com/api/v1/stats/leaders?leaderCategories={stat_type_corrected}&season=2024&playerPool={player_pool}&limit={limit}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        if not data.get('leagueLeaders'):
            print(f"No leader data returned for {stat_type}")
            return []
        leaders = data['leagueLeaders'][0].get('leaders', [])
        results = []
        for player in leaders:
            try:
                name = player.get('person', {}).get('fullName', 'Unknown')
                team = player.get('team', {}).get('name', 'Unknown')
                stat_val = player.get('value', 0)
                results.append({"Name": name, "Team": team, "Stat": stat_val, "Day": TODAY, "VS": "TBD", "O/U Odds": "-", "Notes": f"Recent {stat_type} TBD"})
            except Exception as inner_e:
                print(f"Skipping one player due to format issue: {inner_e}")
        return results
    except requests.exceptions.RequestException as e:
        print(f"Error fetching {stat_type} data: {e}")
        return []

# The Odds API
ODDS_API_KEY = '803756147f1055030d8f479b0000351c'
ODDS_API_URL = 'https://api.the-odds-api.com/v4/sports/baseball_mlb/odds/'

def get_odds_data():
    params = {
        'apiKey': ODDS_API_KEY,
        'regions': 'us',
        'markets': 'totals',
        'oddsFormat': 'decimal'
    }
    try:
        response = requests.get(ODDS_API_URL, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching odds data: {e}")
        return []

def merge_odds_with_players(players, odds_data):
    for player in players:
        name = player['Name']
        for game in odds_data:
            for bookmaker in game.get('bookmakers', []):
                for market in bookmaker.get('markets', []):
                    if market['key'] == 'totals':
                        for outcome in market.get('outcomes', []):
                            if 'over' in outcome['name'].lower():
                                player['O/U Odds'] = outcome['price']
                                player['VS'] = game.get('away_team') if game.get('home_team') == player['Team'] else game.get('home_team')
                                player['Notes'] = f"Game Total: {outcome['point']} (Updated: {TODAY})"
    return players

@app.route('/mlb-stats', methods=['GET'])
def mlb_stats():
    category = request.args.get('category', 'sluggers')
    stat_key_map = {
        'sluggers': 'homeRuns',
        'strikeouts': 'strikeouts',
        'obp': 'onBasePercentage',
        'hr_allowed': 'homeRunsAllowed'
    }
    stat_type = stat_key_map.get(category)
    if not stat_type:
        return jsonify({"error": "Invalid category"}), 400

    players = get_stat_leaders(stat_type)
    odds = get_odds_data()
    enriched = merge_odds_with_players(players, odds)

    # Save snapshot
    filename = f"{category}_{TODAY}.csv"
    filepath = os.path.join(DATA_DIR, filename)
    keys = enriched[0].keys() if enriched else []
    if keys:
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(enriched)
        print(f"Saved {filename} to {filepath}")

    return jsonify(enriched)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
