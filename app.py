import requests
import json
import datetime
import os
from flask import Flask, jsonify, request

app = Flask(__name__)

ODDS_API_KEY = "803756147f1055030d8f479b0000351c"
TODAY = datetime.datetime.now().strftime('%Y-%m-%d')

# Convert UTC time to CST (no daylight saving)
def convert_to_cst(utc_time_str):
    utc_time = datetime.datetime.fromisoformat(utc_time_str.replace('Z', '+00:00'))
    cst_time = utc_time - datetime.timedelta(hours=6)
    return cst_time.replace(tzinfo=None)

# Fetch MLB games
@app.route("/fetch-mlb-stats", methods=["GET"])
def fetch_mlb_stats():
    stat_category = request.args.get("category", "sluggers")
    if stat_category not in ["sluggers", "strikeouts", "obp", "hr_allowed"]:
        return jsonify({"error": "Invalid stat category"}), 400

    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={TODAY}&hydrate=probablePitcher"
    response = requests.get(url)
    if response.status_code != 200:
        return jsonify({"error": "Failed to fetch MLB games"}), 500

    games_data = response.json().get('dates', [])[0].get('games', [])
    players = []
    for game in games_data:
        game_time = convert_to_cst(game['gameDate'])
        teams = game['teams']
        home = teams['home']['team']['name']
        away = teams['away']['team']['name']
        probable_pitchers = teams['home'].get('probablePitcher', {}).get('fullName', '') + " vs " + teams['away'].get('probablePitcher', {}).get('fullName', '')

        players.append({
            "Name": probable_pitchers,
            "Team": home,
            "Day": TODAY,
            "VS": away,
            "Game Time (CST)": game_time.strftime('%H:%M'),
            "O/U Odds": get_odds(probable_pitchers.split(' vs ')[0], market_type="K"),
            "Notes": "Probable pitchers"
        })

    return jsonify(players)

# Fetch odds for a player from the odds API
def get_odds(player_name, market_type='HR'):
    market_key = {
        'HR': 'batter_home_runs',
        'OBP': 'batter_total_bases',
        'K': 'pitcher_strikeouts'
    }.get(market_type, 'batter_home_runs')

    events_url = "https://api.the-odds-api.com/v4/sports/baseball_mlb/odds"
    events_params = {
        "regions": "us",
        "markets": market_key,
        "apiKey": ODDS_API_KEY
    }

    response = requests.get(events_url, params=events_params)
    if response.status_code != 200:
        return "-"

    odds_data = response.json()
    for game in odds_data:
        for bookmaker in game.get("bookmakers", []):
            for market in bookmaker.get("markets", []):
                for outcome in market.get("outcomes", []):
                    if player_name.lower() in outcome.get("name", "").lower():
                        return f"O{outcome.get('line', '?')} {outcome.get('price', '')}"

    return "-"

@app.route("/test-odds-api", methods=["GET"])
def test_odds_api():
    player_name = request.args.get("player", "Aaron Judge")
    market = request.args.get("market", "HR")
    odds = get_odds(player_name, market)
    return jsonify({"Player": player_name, "Market": market, "Odds": odds})

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)
