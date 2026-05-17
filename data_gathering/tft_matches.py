import os
import json
import time
from pathlib import Path

import requests
from dotenv import load_dotenv


load_dotenv()

API_KEY = os.getenv("RIOT_API_KEY")

PLATFORM_ROUTE = "euw1"
REGIONAL_ROUTE = "europe"

DATA_DIR = Path("data")
PLAYERS_FILE = DATA_DIR / "high_elo_players.json"
MATCH_IDS_FILE = DATA_DIR / "match_ids.txt"
MATCH_DIR = DATA_DIR / "matches"

DATA_DIR.mkdir(exist_ok=True)
MATCH_DIR.mkdir(exist_ok=True)

HEADERS = {
    "X-Riot-Token": API_KEY
}


def riot_get(url, params=None):
    while True:
        response = requests.get(url, headers=HEADERS, params=params)

        if response.status_code == 200:
            return response.json()

        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 10))
            print(f"Rate limit reached. Waiting {retry_after}s...")
            time.sleep(retry_after)
            continue

        raise RuntimeError(
            f"Riot API error {response.status_code}: {response.text}"
        )


def get_challenger_players():
    url = (
        f"https://{PLATFORM_ROUTE}.api.riotgames.com/"
        f"tft/league/v1/challenger"
    )

    data = riot_get(url)
    return data["entries"]


def get_grandmaster_players():
    url = (
        f"https://{PLATFORM_ROUTE}.api.riotgames.com/"
        f"tft/league/v1/grandmaster"
    )

    data = riot_get(url)
    return data["entries"]


def get_master_players():
    url = (
        f"https://{PLATFORM_ROUTE}.api.riotgames.com/"
        f"tft/league/v1/master"
    )

    data = riot_get(url)
    return data["entries"]




def get_match_ids_by_puuid(puuid, count=10):
    url = (
        f"https://{REGIONAL_ROUTE}.api.riotgames.com/"
        f"tft/match/v1/matches/by-puuid/{puuid}/ids"
    )

    params = {
        "count": count
    }

    return riot_get(url, params=params)


def get_match(match_id):
    url = (
        f"https://{REGIONAL_ROUTE}.api.riotgames.com/"
        f"tft/match/v1/matches/{match_id}"
    )

    return riot_get(url)


def load_existing_match_ids():
    if not MATCH_IDS_FILE.exists():
        return set()

    with open(MATCH_IDS_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())


def save_match_id(match_id):
    with open(MATCH_IDS_FILE, "a", encoding="utf-8") as f:
        f.write(match_id + "\n")


def save_match(match_id, match_data):
    path = MATCH_DIR / f"{match_id}.json"

    with open(path, "w", encoding="utf-8") as f:
        json.dump(match_data, f, ensure_ascii=False, indent=2)


def match_exists(match_id):
    return (MATCH_DIR / f"{match_id}.json").exists()


def save_players(players):
    with open(PLAYERS_FILE, "w", encoding="utf-8") as f:
        json.dump(players, f, ensure_ascii=False, indent=2)





def collect_high_elo_players(max_players_per_rank=50):
    players = []

    ranks = [
        ("CHALLENGER", get_challenger_players),
        ("GRANDMASTER", get_grandmaster_players),
        ("MASTER", get_master_players),
    ]

    for rank_name, fetch_func in ranks:
        print(f"Fetching {rank_name} players...")

        entries = fetch_func()

        sorted_entries = sorted(
            entries,
            key=lambda x: x.get("leaguePoints", 0),
            reverse=True
        )

        for entry in sorted_entries[:max_players_per_rank]:
            players.append({
                "rank": rank_name,
                "puuid": entry["puuid"],
                "league_points": entry.get("leaguePoints", 0),
                "wins": entry.get("wins", 0),
                "losses": entry.get("losses", 0),
            })

        time.sleep(1.3)

    save_players(players)
    return players

def collect_matches_from_players(players, matches_per_player=10):
    existing_match_ids = load_existing_match_ids()

    for player in players:
        puuid = player["puuid"]

        print(
            f"Fetching match IDs for {player['rank']} player "
            f"with {player['league_points']} LP..."
        )

        match_ids = get_match_ids_by_puuid(
            puuid=puuid,
            count=matches_per_player
        )

        time.sleep(1.3)

        for match_id in match_ids:
            if match_id in existing_match_ids or match_exists(match_id):
                print(f"Skipping existing match: {match_id}")
                continue

            print(f"Downloading match: {match_id}")

            match_data = get_match(match_id)

            save_match(match_id, match_data)
            save_match_id(match_id)
            existing_match_ids.add(match_id)

            time.sleep(1.3)


def main():
    players = collect_high_elo_players(
        max_players_per_rank=25
    )

    collect_matches_from_players(
        players,
        matches_per_player=10
    )


if __name__ == "__main__":
    main()