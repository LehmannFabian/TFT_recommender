import re
from dataclasses import dataclass, field
from typing import Literal

from app.database import get_connection


Intent = Literal[
    "champion_info",
    "item_info",
    "comp_recommendation",
    "item_recommendation",
    "general",
]

Source = Literal["champions", "items", "comps", "patch_notes"]


COMP_WORDS = {
    "comp",
    "comps",
    "composition",
    "team",
    "board",
    "boards",
    "recommend",
    "recommendation",
    "play",
    "build",
    "carry",
}

ITEM_WORDS = {
    "item",
    "items",
    "bis",
    "slam",
    "slammed",
    "equip",
    "holder",
}

CHAMPION_WORDS = {
    "champion",
    "champions",
    "champ",
    "unit",
    "units",
    "ability",
    "spell",
    "cost",
    "trait",
    "traits",
}


@dataclass
class RetrievalPlan:
    intent: Intent
    sources: list[Source]
    champion_names: list[str] = field(default_factory=list)
    item_names: list[str] = field(default_factory=list)
    trait_names: list[str] = field(default_factory=list)
    search_terms: list[str] = field(default_factory=list)
    min_games: int = 3


def tokenize(query: str) -> list[str]:
    return re.sub(r"[^a-z0-9]+", " ", query.lower()).split()


def find_known_names(query: str, table: str, column: str = "name") -> list[str]:
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            f"""
            SELECT {column}
            FROM (
                SELECT DISTINCT {column}
                FROM {table}
                WHERE {column} IS NOT NULL
                  AND {column} <> ''
                  AND {column} NOT ILIKE 'tft_item_name_%%'
            ) AS known_names
            ORDER BY LENGTH({column}) DESC;
            """
        )
        names = [
            row[0]
            for row in cur.fetchall()
        ]
    finally:
        cur.close()
        conn.close()

    normalized_query = f" {re.sub(r'[^a-z0-9]+', ' ', query.lower())} "
    matches = []

    for name in names:
        normalized_name = re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()

        if not normalized_name:
            continue

        if f" {normalized_name} " in normalized_query:
            matches.append(name)

    return matches


def build_search_terms(
    query: str,
    champion_names: list[str],
    item_names: list[str],
) -> list[str]:
    removed_names = " ".join(champion_names + item_names).lower()
    removed_words = set(tokenize(removed_names))
    stop_words = COMP_WORDS | ITEM_WORDS | CHAMPION_WORDS | {
        "what",
        "which",
        "with",
        "best",
        "good",
        "should",
        "about",
        "into",
        "using",
        "from",
        "have",
        "that",
        "this",
        "and",
        "the",
        "for",
        "you",
        "can",
        "are",
        "does",
        "how",
        "who",
        "why",
        "when",
        "where",
        "tell",
        "explain",
        "give",
        "show",
        "need",
        "want",
    }

    terms = []

    for word in tokenize(query):
        if len(word) < 3:
            continue

        if word in stop_words or word in removed_words:
            continue

        if word not in terms:
            terms.append(word)

    return terms


def route_query(query: str) -> RetrievalPlan:
    words = set(tokenize(query))
    champion_names = find_known_names(query, "champions")
    item_names = find_known_names(query, "items")
    search_terms = build_search_terms(query, champion_names, item_names)

    has_comp_intent = bool(words & COMP_WORDS)
    has_item_intent = bool(words & ITEM_WORDS)
    has_champion_intent = bool(words & CHAMPION_WORDS)

    if has_comp_intent:
        return RetrievalPlan(
            intent="comp_recommendation",
            sources=["comps", "champions", "items"],
            champion_names=champion_names,
            item_names=item_names,
            search_terms=search_terms,
            min_games=3,
        )

    if has_item_intent:
        return RetrievalPlan(
            intent="item_recommendation" if champion_names else "item_info",
            sources=["items", "comps", "champions"],
            champion_names=champion_names,
            item_names=item_names,
            search_terms=search_terms,
            min_games=2,
        )

    if item_names:
        return RetrievalPlan(
            intent="item_info",
            sources=["items"],
            champion_names=champion_names,
            item_names=item_names,
            search_terms=search_terms,
        )

    if champion_names or has_champion_intent:
        return RetrievalPlan(
            intent="champion_info",
            sources=["champions"],
            champion_names=champion_names,
            item_names=item_names,
            search_terms=search_terms,
        )

    return RetrievalPlan(
        intent="general",
        sources=["champions", "items", "patch_notes"],
        champion_names=champion_names,
        item_names=item_names,
        search_terms=search_terms,
    )
