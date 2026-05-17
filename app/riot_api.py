import os
import time

import requests
from dotenv import load_dotenv

from app.database import (
    get_connection,
    create_tables,
    insert_match,
    insert_board,
)


load_dotenv()

API_KEY = os.getenv("RIOT_API_KEY")

PLATFORM_ROUTE = "euw1"
REGIONAL_ROUTE = "europe"
TFT_RANKED_QUEUE = "RANKED_TFT"

HEADERS = {
    "X-Riot-Token": API_KEY
}


def riot_get(url, params=None):
    if not API_KEY:
        raise RuntimeError("RIOT_API_KEY is not configured.")

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

    return riot_get(url, params={"queue": TFT_RANKED_QUEUE})["entries"]


def get_grandmaster_players():
    url = (
        f"https://{PLATFORM_ROUTE}.api.riotgames.com/"
        f"tft/league/v1/grandmaster"
    )

    return riot_get(url, params={"queue": TFT_RANKED_QUEUE})["entries"]


def get_master_players():
    url = (
        f"https://{PLATFORM_ROUTE}.api.riotgames.com/"
        f"tft/league/v1/master"
    )

    return riot_get(url, params={"queue": TFT_RANKED_QUEUE})["entries"]


def get_summoner_by_id(encrypted_summoner_id):
    url = (
        f"https://{PLATFORM_ROUTE}.api.riotgames.com/"
        f"tft/summoner/v1/summoners/{encrypted_summoner_id}"
    )

    return riot_get(url)


def get_match_ids_by_puuid(puuid, count=10):
    url = (
        f"https://{REGIONAL_ROUTE}.api.riotgames.com/"
        f"tft/match/v1/matches/by-puuid/{puuid}/ids"
    )

    return riot_get(url, params={"count": count})


def get_match(match_id):
    url = (
        f"https://{REGIONAL_ROUTE}.api.riotgames.com/"
        f"tft/match/v1/matches/{match_id}"
    )

    return riot_get(url)


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
            puuid = entry.get("puuid")

            if not puuid:
                encrypted_summoner_id = entry.get("summonerId")

                if not encrypted_summoner_id:
                    raise RuntimeError(
                        "Riot league entry did not include puuid or summonerId."
                    )

                summoner = get_summoner_by_id(encrypted_summoner_id)
                puuid = summoner["puuid"]
                time.sleep(1.3)

            players.append({
                "rank": rank_name,
                "puuid": puuid,
                "league_points": entry.get("leaguePoints", 0),
                "wins": entry.get("wins", 0),
                "losses": entry.get("losses", 0),
            })

        time.sleep(1.3)

    return players


def extract_boards_from_match(match_data):
    match_id = match_data["metadata"]["match_id"]
    boards = []

    for participant in match_data["info"]["participants"]:
        units = []
        items = []

        for unit in participant.get("units", []):
            champion = unit.get("character_id")

            if not champion:
                continue

            # Remove summons/fake units
            if "Summon" in champion:
                continue

            unit_items = [
                item for item in unit.get("itemNames", [])
                if item != "TFT_Item_EmptyBag"
            ]

            units.append({
                "champion": champion,
                "star_level": unit.get("tier"),
                "rarity": unit.get("rarity"),
                "items": unit_items,
            })

            items.extend(unit_items)

        traits = [
            trait for trait in participant.get("traits", [])
            if trait.get("tier_current", 0) > 0
        ]

        comp_key = "|".join(sorted(
            unit["champion"] for unit in units
        ))

        boards.append({
            "match_id": match_id,
            "puuid": participant["puuid"],
            "placement": participant["placement"],
            "level": participant["level"],
            "win": participant["win"],
            "units": units,
            "traits": traits,
            "items": items,
            "comp_key": comp_key,
        })

    return boards


def collect_matches_from_players(players, matches_per_player=10):
    conn = get_connection()
    cur = conn.cursor()
    stats = {
        "players": len(players),
        "downloaded_matches": 0,
        "stored_matches": 0,
        "duplicate_matches": 0,
        "stored_boards": 0,
        "duplicate_boards": 0,
    }

    try:
        for player in players:
            puuid = player["puuid"]

            print(
                f"Fetching match IDs for {player['rank']} "
                f"with {player['league_points']} LP..."
            )

            match_ids = get_match_ids_by_puuid(
                puuid=puuid,
                count=matches_per_player
            )

            time.sleep(1.3)

            for match_id in match_ids:
                print(f"Downloading match: {match_id}")

                match_data = get_match(match_id)
                stats["downloaded_matches"] += 1

                if insert_match(cur, match_data):
                    stats["stored_matches"] += 1
                else:
                    stats["duplicate_matches"] += 1

                boards = extract_boards_from_match(match_data)

                for board in boards:
                    if insert_board(cur, board):
                        stats["stored_boards"] += 1
                    else:
                        stats["duplicate_boards"] += 1

                conn.commit()

                print(f"Stored {match_id} with {len(boards)} boards.")

                time.sleep(1.3)

        return stats

    finally:
        cur.close()
        conn.close()
