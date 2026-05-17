# app/retriever.py

import re

from app.database import get_connection, get_recommended_comps
from app.embeddings import create_embedding
from app.query_router import RetrievalPlan, route_query


DEFAULT_MIN_COMP_GAMES = 3
MAX_SEMANTIC_DISTANCE = 0.72


COMP_QUERY_WORDS = {
    "comp",
    "comps",
    "composition",
    "compositions",
    "team",
    "teams",
    "board",
    "boards",
    "recommend",
    "recommendation",
    "recommendations",
    "play",
    "playing",
    "build",
    "carry",
}

ITEM_QUERY_WORDS = {
    "item",
    "items",
    "slammed",
    "slam",
    "equip",
    "bis",
}

COMP_SEARCH_STOP_WORDS = COMP_QUERY_WORDS | {
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
    "item",
    "items",
    "champion",
    "champions",
    "does",
    "trait",
    "traits",
}

TEXT_SEARCH_STOP_WORDS = COMP_SEARCH_STOP_WORDS | {
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
    "against",
    "versus",
    "vs",
    "champ",
    "unit",
    "units",
}


def unique_by_id(results: list[dict]) -> list[dict]:
    seen = set()
    unique_results = []

    for result in results:
        entity_name = result.get("name")
        key = (
            result["source_type"],
            entity_name.lower() if entity_name else result["id"],
        )

        if key in seen:
            continue

        seen.add(key)
        unique_results.append(result)

    return unique_results


def unique_comps(comps: list[dict]) -> list[dict]:
    seen = set()
    unique_results = []

    for comp in comps:
        comp_key = comp["comp_key"]

        if comp_key in seen:
            continue

        seen.add(comp_key)
        unique_results.append(comp)

    return unique_results


def is_comp_query(query: str) -> bool:
    words = query.lower().replace("?", " ").replace(",", " ").split()

    return any(word in COMP_QUERY_WORDS for word in words)


def is_item_query(query: str) -> bool:
    words = query.lower().replace("?", " ").replace(",", " ").split()

    return any(word in ITEM_QUERY_WORDS for word in words)


def extract_comp_search_terms(query: str) -> list[str]:
    cleaned_query = re.sub(r"[^a-z0-9]+", " ", query.lower())

    terms = []

    for word in cleaned_query.split():
        if len(word) < 3:
            continue

        if word in COMP_SEARCH_STOP_WORDS:
            continue

        terms.append(word)

    return terms


def extract_text_search_terms(query: str) -> list[str]:
    terms = []

    for word in re.sub(r"[^a-z0-9]+", " ", query.lower()).split():
        if len(word) < 3:
            continue

        if word in TEXT_SEARCH_STOP_WORDS:
            continue

        if word not in terms:
            terms.append(word)

    return terms


def build_entity_query(query: str, names: list[str]) -> str:
    if not names:
        return query

    return " ".join([query, *names])


def create_query_embedding(query: str) -> list[float]:

    return create_embedding(query)


def retrieve_champions(
    query: str,
    limit: int = 5,
    names: list[str] | None = None,
    search_terms: list[str] | None = None,
) -> list[dict]:
    """
    Retrieve relevant champions using exact text matches plus vector search.
    """

    names = names or []
    query_embedding = create_query_embedding(build_entity_query(query, names))
    search_terms = search_terms or extract_text_search_terms(query)
    search_terms = [*names, *search_terms]
    search_patterns = [
        f"%{term}%"
        for term in search_terms
    ]

    conn = get_connection()
    cur = conn.cursor()
    results = []

    if search_patterns:
        exact_conditions = []
        exact_params = []

        for pattern in search_patterns:
            exact_conditions.append("""
                CASE
                    WHEN name ILIKE %s
                      OR ability ILIKE %s
                      OR content ILIKE %s
                      OR traits::text ILIKE %s
                    THEN 1
                    ELSE 0
                END
            """)
            exact_params.extend([pattern, pattern, pattern, pattern])

        cur.execute(f"""
            SELECT
                id,
                name,
                cost,
                traits,
                ability,
                content,
                ({' + '.join(exact_conditions)}) AS text_score
            FROM champions
            WHERE ({' + '.join(exact_conditions)}) > 0
            ORDER BY text_score DESC, cost DESC, name ASC
            LIMIT %s;
        """, exact_params + exact_params + [limit])

        for row in cur.fetchall():
            results.append({
                "source_type": "champion",
                "id": row[0],
                "name": row[1],
                "cost": row[2],
                "traits": row[3],
                "ability": row[4],
                "content": row[5],
                "distance": -100 - row[6],
            })

    cur.execute("""
        SELECT
            id,
            name,
            cost,
            traits,
            ability,
            content,
            embedding <=> %s::vector AS distance
        FROM champions
        ORDER BY distance
        LIMIT %s;
    """, (
        query_embedding,
        limit
    ))

    for row in cur.fetchall():
        if row[6] is None or row[6] > MAX_SEMANTIC_DISTANCE:
            continue

        results.append({
            "source_type": "champion",
            "id": row[0],
            "name": row[1],
            "cost": row[2],
            "traits": row[3],
            "ability": row[4],
            "content": row[5],
            "distance": row[6]
        })

    cur.close()
    conn.close()

    return unique_by_id(results)[:limit]


def retrieve_patch_notes(query: str, limit: int = 5) -> list[dict]:
    """
    Retrieve the most semantically similar patch notes for a user query.
    """

    query_embedding = create_query_embedding(query)

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            id,
            patch_version,
            title,
            content,
            url,
            embedding <=> %s::vector AS distance
        FROM patch_notes
        ORDER BY distance
        LIMIT %s;
    """, (
        query_embedding,
        limit
    ))

    rows = cur.fetchall()

    cur.close()
    conn.close()

    results = []

    for row in rows:
        results.append({
            "source_type": "patch_note",
            "id": row[0],
            "patch_version": row[1],
            "title": row[2],
            "content": row[3],
            "url": row[4],
            "distance": row[5]
        })

    return results

def retrieve_items(
    query: str,
    limit: int = 5,
    names: list[str] | None = None,
    search_terms: list[str] | None = None,
) -> list[dict]:
    """
    Retrieve relevant items using exact text matches plus vector search.
    """

    names = names or []
    query_embedding = create_query_embedding(build_entity_query(query, names))
    search_terms = search_terms or extract_text_search_terms(query)
    search_terms = [*names, *search_terms]
    search_patterns = [
        f"%{term}%"
        for term in search_terms
    ]

    conn = get_connection()
    cur = conn.cursor()
    results = []

    if search_patterns:
        exact_conditions = []
        exact_params = []

        for pattern in search_patterns:
            exact_conditions.append("""
                CASE
                    WHEN name ILIKE %s
                      OR description ILIKE %s
                      OR composition::text ILIKE %s
                    THEN 1
                    ELSE 0
                END
            """)
            exact_params.extend([pattern, pattern, pattern])

        cur.execute(f"""
            SELECT
                id,
                name,
                description,
                stats,
                composition,
                ({' + '.join(exact_conditions)}) AS text_score
            FROM items
            WHERE name IS NOT NULL
              AND name NOT ILIKE 'tft_item_name_%%'
              AND ({' + '.join(exact_conditions)}) > 0
            ORDER BY text_score DESC, name ASC
            LIMIT %s;
        """, exact_params + exact_params + [limit])

        for row in cur.fetchall():
            results.append({
                "source_type": "item",
                "id": row[0],
                "name": row[1],
                "description": row[2],
                "stats": row[3],
                "composition": row[4],
                "distance": -100 - row[5]
            })

    cur.execute("""
        SELECT
            id,
            name,
            description,
            stats,
            composition,
            embedding <=> %s::vector AS distance
        FROM items
        WHERE name IS NOT NULL
          AND name NOT ILIKE 'tft_item_name_%%'
        ORDER BY distance
        LIMIT %s;
    """, (
        query_embedding,
        limit
    ))

    for row in cur.fetchall():
        if row[5] is None or row[5] > MAX_SEMANTIC_DISTANCE:
            continue

        results.append({
            "source_type": "item",
            "id": row[0],
            "name": row[1],
            "description": row[2],
            "stats": row[3],
            "composition": row[4],
            "distance": row[5]
        })

    cur.close()
    conn.close()

    return unique_by_id(results)[:limit]


def retrieve_comps(
    query: str,
    limit: int = 5,
    force: bool = False,
    allow_fallback: bool = True,
    search_terms: list[str] | None = None,
    min_games: int = DEFAULT_MIN_COMP_GAMES,
) -> list[dict]:
    """
    Retrieve top comp stats for comp recommendation questions.
    """

    if not force and not is_comp_query(query):
        return []

    if search_terms is None:
        search_terms = extract_comp_search_terms(query)

    comps = []

    min_games_options = [
        value
        for value in (min_games, 2, 1)
        if value <= min_games
    ]

    for min_games_option in min_games_options:
        comps = get_recommended_comps(
            limit=limit,
            min_games=min_games_option,
            search_terms=search_terms,
        )

        if comps:
            break

    if allow_fallback and search_terms and len(comps) < limit:
        seen_comp_keys = {
            comp["comp_key"]
            for comp in comps
        }
        fallback_comps = []

        for min_games_option in min_games_options:
            fallback_comps = get_recommended_comps(
                limit=limit,
                min_games=min_games_option,
            )

            if fallback_comps:
                break

        for comp in fallback_comps:
            if comp["comp_key"] in seen_comp_keys:
                continue

            comps.append(comp)
            seen_comp_keys.add(comp["comp_key"])

            if len(comps) >= limit:
                break

    return unique_comps(comps)[:limit]



def build_comp_terms(plan: RetrievalPlan) -> list[str]:
    terms = []

    for name in [*plan.champion_names, *plan.item_names]:
        terms.extend(extract_comp_search_terms(name))

    terms.extend(plan.search_terms)

    unique_terms = []

    for term in terms:
        if term not in unique_terms:
            unique_terms.append(term)

    return unique_terms


def retrieve_context(query: str, limit: int = 5) -> list[dict]:
    """
    Retrieve relevant context from multiple tables.
    """

    plan = route_query(query)
    comp_results = []
    champion_results = []
    item_results = []
    patch_results = []

    if "comps" in plan.sources:
        comp_results = retrieve_comps(
            query,
            limit=limit,
            force=True,
            allow_fallback=plan.intent == "comp_recommendation",
            search_terms=build_comp_terms(plan),
            min_games=plan.min_games,
        )

    if "champions" in plan.sources:
        champion_results = retrieve_champions(
            query,
            limit=limit,
            names=plan.champion_names,
            search_terms=plan.search_terms,
        )

    if "items" in plan.sources:
        item_results = retrieve_items(
            query,
            limit=limit,
            names=plan.item_names,
            search_terms=plan.search_terms,
        )

    if "patch_notes" in plan.sources:
        patch_results = retrieve_patch_notes(query, limit=limit)

    has_exact_champion = any(
        item["distance"] <= -100
        for item in champion_results
    )

    if has_exact_champion and plan.intent == "champion_info":
        item_results = [
            item
            for item in item_results
            if item["distance"] <= -100
        ]

    results = []

    for item in comp_results:
        item["source_type"] = "comp"
        item["distance"] = -50 - item.get("matched_terms", 0)
        results.append(item)

    for item in champion_results:
        item["source_type"] = "champion"
        results.append(item)

    for item in patch_results:
        item["source_type"] = "patch_note"
        results.append(item)

    for item in item_results:
        item["source_type"] = "item"
        results.append(item)

    source_priority_by_intent = {
        "champion_info": {
            "champion": 0,
            "item": 1,
            "comp": 2,
            "patch_note": 3,
        },
        "item_info": {
            "item": 0,
            "champion": 1,
            "comp": 2,
            "patch_note": 3,
        },
        "comp_recommendation": {
            "comp": 0,
            "champion": 1,
            "item": 2,
            "patch_note": 3,
        },
        "item_recommendation": {
            "comp": 0,
            "champion": 1,
            "item": 2,
            "patch_note": 3,
        },
        "general": {
            "champion": 0,
            "item": 1,
            "patch_note": 2,
            "comp": 3,
        },
    }
    source_priority = source_priority_by_intent[plan.intent]

    return sorted(
        results,
        key=lambda x: (
            source_priority.get(x["source_type"], 99),
            x["distance"],
        )
    )[:limit]
