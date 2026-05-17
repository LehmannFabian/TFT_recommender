import os
import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import execute_values, Json

load_dotenv(override=True)

def get_connection():
    database_url = os.getenv("DATABASE_URL")
    sslmode = os.getenv("DB_SSLMODE", "prefer")

    try:
        if database_url:
            return psycopg2.connect(
                database_url,
                sslmode=sslmode,
                connect_timeout=5,
            )

        return psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        sslmode=sslmode,
        connect_timeout=5
        )
    except UnicodeDecodeError as exc:
        raise RuntimeError(
            "PostgreSQL connection failed and returned a message that could "
            "not be decoded as UTF-8. Check DB_HOST, DB_PORT, DB_NAME, "
            "DB_USER, DB_PASSWORD, and PostgreSQL client/server encoding."
        ) from exc

def create_tables():

    conn = get_connection()
    cur = conn.cursor()

    # pgvector vector extension
    cur.execute("""
        CREATE EXTENSION IF NOT EXISTS vector;
    """)

    # Patch Notes table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS patch_notes (
            id SERIAL PRIMARY KEY,
            patch_version TEXT,
            title TEXT,
            content TEXT,
            url TEXT,
            embedding vector(384)
        );
    """)

    # Champions table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS champions (
            id SERIAL PRIMARY KEY,
            set_nr TEXT,
            name TEXT,
            cost INTEGER,
            traits TEXT[],
            ability TEXT,
            content TEXT,
            embedding vector(384)
        );
    """)
    # Items Table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id SERIAL PRIMARY KEY,
            name TEXT,
            description TEXT,
            stats JSONB,
            composition JSONB,
            embedding vector(384)
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            match_id TEXT PRIMARY KEY,
            set_number INTEGER,
            game_datetime BIGINT,
            game_version TEXT,
            queue_id INTEGER,
            raw_match JSONB
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS boards (
            id SERIAL PRIMARY KEY,
            match_id TEXT REFERENCES matches(match_id),
            puuid TEXT,
            placement INTEGER,
            level INTEGER,
            win BOOLEAN,
            units JSONB,
            traits JSONB,
            items JSONB,
            comp_key TEXT,
            UNIQUE(match_id, puuid)
        );
    """)

    conn.commit()

    cur.close()
    conn.close()

    print("created tables.")



def insert_patch_note(
    patch_version,
    title,
    content,
    url,
    embedding
):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO patch_notes (
            patch_version,
            title,
            content,
            url,
            embedding
        )
        VALUES (%s, %s, %s, %s, %s)
    """, (
        patch_version,
        title,
        content,
        url,
        embedding
    ))

    conn.commit()

    cur.close()
    conn.close()



def insert_items(
    name,
    description,
    stats,
    composition,
    embedding
):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO items (
            name,
            description,
            stats,
            composition,
            embedding
        )
        VALUES (%s, %s, %s, %s, %s)
    """, (
        name,
        description,
        Json(stats),
        Json(composition),
        embedding
    ))

    conn.commit()
    cur.close()
    conn.close()




def insert_champion(
    set_nr,
    name,
    cost,
    traits,
    ability,
    content,
    embedding
):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO champions (
            set_nr,
            name,
            cost,
            traits,
            ability,
            content,
            embedding
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (
        set_nr,
        name,
        cost,
        traits,
        ability,
        content,
        embedding
    ))

    conn.commit()

    cur.close()
    conn.close()



def search_patch_notes(
    query_embedding,
    limit=5
):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
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

    results = cur.fetchall()

    cur.close()
    conn.close()

    return results



def search_champions(
    query_embedding,
    limit=5
):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            set_nr,
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

    results = cur.fetchall()

    cur.close()
    conn.close()

    return results




def get_all_patch_notes():

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM patch_notes;
    """)

    results = cur.fetchall()

    cur.close()
    conn.close()

    return results




def get_all_champions():

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM champions;
    """)

    results = cur.fetchall()

    cur.close()
    conn.close()

    return results

def get_all_items():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM items;
    """)

    results = cur.fetchall()

    cur.close()
    conn.close()

    return results


def clear_champions():
    """
    Remove all champion entries.
    """

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM champions;")

    conn.commit()

    cur.close()
    conn.close()

    print("Champions table cleared.")

def clear_items():
    """
    Remove all champion entries.
    """

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM items;")

    conn.commit()

    cur.close()
    conn.close()

    print("item table cleared.")


def clear_patch_notes():

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM patch_notes;")


    conn.commit()

    cur.close()
    conn.close()

    print("patch notes table cleared.")




def insert_champions(set_nr, name, cost, traits, ability, content, embedding):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO champions (
            set_nr,
            name,
            cost,
            traits,
            ability,
            content,
            embedding
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (
        set_nr,
        name,
        cost,
        traits,
        ability,
        content,
        embedding
    ))

    conn.commit()
    cur.close()
    conn.close()


def insert_match(cur, match_data):
    match_id = match_data["metadata"]["match_id"]
    info = match_data["info"]

    cur.execute("""
        INSERT INTO matches (
            match_id,
            set_number,
            game_datetime,
            game_version,
            queue_id,
            raw_match
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (match_id) DO NOTHING;
    """, (
        match_id,
        info.get("tft_set_number"),
        info.get("game_datetime"),
        info.get("game_version"),
        info.get("queue_id"),
        Json(match_data),
    ))

    return cur.rowcount == 1

def insert_board(cur, board):
    cur.execute("""
        INSERT INTO boards (
            match_id,
            puuid,
            placement,
            level,
            win,
            units,
            traits,
            items,
            comp_key
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (match_id, puuid) DO NOTHING;
    """, (
        board["match_id"],
        board["puuid"],
        board["placement"],
        board["level"],
        board["win"],
        Json(board["units"]),
        Json(board["traits"]),
        Json(board["items"]),
        board["comp_key"],
    ))

    return cur.rowcount == 1

def batch_insert_patch_notes(data):
    conn = get_connection()
    cur = conn.cursor()

    query = """
        INSERT INTO patch_notes (
            patch_version,
            title,
            content,
            url,
            embedding
        )
        VALUES %s
    """

    execute_values(cur, query, data)

    conn.commit()
    cur.close()
    conn.close()

    print(f"{len(data)} saved patch notes.")


def batch_insert_items(data):
    """
    data format:
    [
        (
            name,
            description,
            stats,
            composition,
            embedding
        )
    ]
    """

    conn = get_connection()
    cur = conn.cursor()

    prepared_data = [
        (
            name,
            description,
            Json(stats),
            Json(composition),
            embedding
        )
        for name, description, stats, composition, embedding in data
    ]

    query = """
        INSERT INTO items (
            name,
            description,
            stats,
            composition,
            embedding
        )
        VALUES %s
    """

    execute_values(cur, query, prepared_data)

    conn.commit()
    cur.close()
    conn.close()

    print(f"{len(data)} saved items.")


def get_recommended_comps(limit=10, min_games=3, search_terms=None):
    """
    Return the best repeated comps from stored match boards.

    Ranking is based on average placement first, then top-4 rate and sample size.
    The representative board is the best individual board for that comp.
    """

    conn = get_connection()
    cur = conn.cursor()

    search_terms = search_terms or []
    search_patterns = [
        f"%{term}%"
        for term in search_terms
    ]

    search_filter = ""
    match_score_select = "0 AS matched_terms"
    match_score_params = []
    params = []

    if search_patterns:
        match_score_parts = []

        for pattern in search_patterns:
            match_score_parts.append("""
                CASE
                    WHEN comp_key ILIKE %s
                      OR units::text ILIKE %s
                      OR traits::text ILIKE %s
                      OR items::text ILIKE %s
                    THEN 1
                    ELSE 0
                END
            """)
            match_score_params.extend([
                pattern,
                pattern,
                pattern,
                pattern,
            ])

        match_score_select = (
            f"({' + '.join(match_score_parts)}) AS matched_terms"
        )
        search_filter = "WHERE matched_terms > 0"
        params.extend(match_score_params)

    params.append(min_games)
    params.append(limit)

    cur.execute(f"""
        WITH board_candidates AS (
            SELECT
                comp_key,
                placement,
                level,
                units,
                traits,
                items,
                {match_score_select}
            FROM boards
            WHERE comp_key IS NOT NULL
              AND comp_key <> ''
        ),
        comp_stats AS (
            SELECT
                comp_key,
                COUNT(*) AS games,
                AVG(placement) AS avg_placement,
                COUNT(*) FILTER (WHERE placement <= 4) AS top4s,
                COUNT(*) FILTER (WHERE placement = 1) AS wins,
                MAX(matched_terms) AS matched_terms,
                (
                    COUNT(*) FILTER (WHERE placement <= 4)::numeric
                    / COUNT(*)
                    * 100
                ) AS top4_rate
            FROM board_candidates
            {search_filter}
            GROUP BY comp_key
            HAVING COUNT(*) >= %s
        ),
        representative_boards AS (
            SELECT
                comp_key,
                level,
                units,
                traits,
                items,
                placement,
                matched_terms,
                ROW_NUMBER() OVER (
                    PARTITION BY comp_key
                    ORDER BY matched_terms DESC, placement ASC, level DESC
                ) AS row_number
            FROM board_candidates
            {search_filter}
        )
        SELECT
            comp_stats.comp_key,
            comp_stats.games,
            ROUND(comp_stats.avg_placement::numeric, 2) AS avg_placement,
            comp_stats.top4s,
            ROUND(comp_stats.top4_rate, 1) AS top4_rate,
            comp_stats.wins,
            representative_boards.level,
            representative_boards.units,
            representative_boards.traits,
            representative_boards.items,
            representative_boards.placement AS best_placement,
            comp_stats.matched_terms
        FROM comp_stats
        JOIN representative_boards
          ON representative_boards.comp_key = comp_stats.comp_key
         AND representative_boards.row_number = 1
        ORDER BY
            comp_stats.matched_terms DESC,
            comp_stats.avg_placement ASC,
            comp_stats.top4_rate DESC,
            comp_stats.games DESC
        LIMIT %s;
    """, params)

    rows = cur.fetchall()

    cur.close()
    conn.close()

    return [
        {
            "comp_key": row[0],
            "games": row[1],
            "avg_placement": float(row[2]),
            "top4s": row[3],
            "top4_rate": float(row[4]),
            "wins": row[5],
            "level": row[6],
            "units": row[7],
            "traits": row[8],
            "items": row[9],
            "best_placement": row[10],
            "matched_terms": row[11],
        }
        for row in rows
    ]
