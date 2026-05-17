# app/retriever.py

import re

from app.database import get_connection, get_recommended_comps
from app.embeddings import create_embedding


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


def create_query_embedding(query: str) -> list[float]:

    return create_embedding(query)


def retrieve_champions(query: str, limit: int = 5) -> list[dict]:
    """
    Retrieve relevant champions using exact text matches plus vector search.
    """

    query_embedding = create_query_embedding(query)
    search_terms = extract_text_search_terms(query)
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

def retrieve_items(query: str, limit: int = 5) -> list[dict]:
    """
    Retrieve relevant items using exact text matches plus vector search.
    """

    query_embedding = create_query_embedding(query)
    search_terms = extract_text_search_terms(query)
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
) -> list[dict]:
    """
    Retrieve top comp stats for comp recommendation questions.
    """

    if not force and not is_comp_query(query):
        return []

    search_terms = extract_comp_search_terms(query)
    comps = []

    for min_games in (DEFAULT_MIN_COMP_GAMES, 2, 1):
        comps = get_recommended_comps(
            limit=limit,
            min_games=min_games,
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

        for min_games in (DEFAULT_MIN_COMP_GAMES, 2, 1):
            fallback_comps = get_recommended_comps(
                limit=limit,
                min_games=min_games,
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

    return comps



def retrieve_context(query: str, limit: int = 5) -> list[dict]:
    """
    Retrieve relevant context from multiple tables.
    """

    comp_query = is_comp_query(query)
    item_query = is_item_query(query)
    comp_results = retrieve_comps(
        query,
        limit=limit,
        force=comp_query or item_query,
        allow_fallback=comp_query,
    )
    champion_results = retrieve_champions(query, limit=limit)
    item_results = retrieve_items(query, limit=limit)
    patch_results = retrieve_patch_notes(query, limit=limit)

    has_exact_champion = any(
        item["distance"] <= -100
        for item in champion_results
    )

    if has_exact_champion and not item_query and not comp_query:
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

    return sorted(
        results,
        key=lambda x: (
            x["distance"],
            x["source_type"],
        )
    )[:limit]
