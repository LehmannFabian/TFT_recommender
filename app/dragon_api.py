# app/dragon_api.py

import requests
import re


DDRAGON_BASE_URL = (
    "https://ddragon.leagueoflegends.com/cdn"
)


def get_latest_version() -> str:
    """
    Fetch the latest Data Dragon version.
    """

    url = (
        "https://ddragon.leagueoflegends.com/api/versions.json"
    )

    response = requests.get(url)

    response.raise_for_status()

    versions = response.json()

    return versions[0]


def fetch_champions(version: str = None) -> dict:
    """
    Fetch TFT champion data from Riot Data Dragon.
    """

    if version is None:
        version = get_latest_version()

    url = (
        f"{DDRAGON_BASE_URL}/"
        f"{version}/data/en_US/tft-champion.json"
    )

    response = requests.get(url)

    response.raise_for_status()

    return response.json()


def fetch_traits(version: str = None) -> dict:
    """
    Fetch TFT trait data.
    """

    if version is None:
        version = get_latest_version()

    url = (
        f"{DDRAGON_BASE_URL}/"
        f"{version}/data/en_US/tft-trait.json"
    )

    response = requests.get(url)

    response.raise_for_status()

    return response.json()


def fetch_items(version: str = None) -> dict:
    """
    Fetch TFT item data.
    """

    if version is None:
        version = get_latest_version()

    url = "https://raw.communitydragon.org/latest/cdragon/tft/en_us.json"


    response = requests.get(url)

    response.raise_for_status()

    return response.json()

def extract_item_data(raw_data:dict) -> list:
    """
    Extract TFT item data from raw JSON response.
    """

    items = raw_data["items"]
    real_items = []


    for item in items:
        api_name = item.get("apiName", "")

        if not api_name.startswith("TFT_Item_"):
            continue
        item_data = {
            "name": item.get("name",),
            "desc":item.get("desc"),
            "stats":item.get("effects"),
            "composition": item.get("composition")
        }

        real_items.append(item_data)
    return real_items





def extract_champion_data(raw_data: dict) -> list[dict]:
    """
    Extract relevant champion information
    from Riot's raw JSON response.
    """


    champions = []

    for key, champion in raw_data["data"].items():
        champion_data = {
            "set_nr": key.split("/")[4],
            "name": champion.get("name", "").strip(),
            "cost": champion.get("cost"),
            "traits": champion.get("traits", []),
            "ability": (
                champion.get("ability", {})
                .get("desc", "")
            )
        }

        champions.append(champion_data)

    return champions

