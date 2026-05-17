import os
from pathlib import Path
from typing import Any

from app.database import create_tables, insert_champion, clear_champions, insert_items,clear_items
from app.dragon_api import fetch_champions, extract_champion_data,fetch_items,extract_item_data
from app.comp_recommender import (
    build_comp_recommendations,
    clean_tft_name,
    format_trait,
    format_unit,
)
from app.database import get_recommended_comps
from app.rag import generate_answer
from app.riot_api import collect_high_elo_players, collect_matches_from_players

from fastapi import Body, Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field


BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"

app = FastAPI(title="TFT Recommender API")
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


class AskRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=1000)


class AskResponse(BaseModel):
    question: str
    answer: str


class LoadMatchesRequest(BaseModel):
    max_players_per_rank: int = Field(25, ge=1, le=100)
    matches_per_player: int = Field(10, ge=1, le=50)


def admin_enabled() -> bool:
    return bool(os.getenv("ADMIN_TOKEN"))


def require_admin(x_admin_token: str | None = Header(default=None)):
    expected_token = os.getenv("ADMIN_TOKEN")

    if not expected_token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin endpoints are disabled for this deployment.",
        )

    if x_admin_token != expected_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid admin token.",
        )


def bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed_value = int(value)
    except (TypeError, ValueError):
        return default

    return max(minimum, min(parsed_value, maximum))


def serialize_comp(comp: dict, rank: int) -> dict:
    active_traits = [
        trait
        for trait in comp["traits"]
        if trait.get("tier_current", 0) > 0
    ]

    active_traits = sorted(
        active_traits,
        key=lambda trait: (
            trait.get("tier_current", 0),
            trait.get("num_units", 0),
        ),
        reverse=True,
    )

    return {
        "rank": rank,
        "comp_key": comp["comp_key"],
        "games": comp["games"],
        "avg_placement": comp["avg_placement"],
        "top4s": comp["top4s"],
        "top4_rate": comp["top4_rate"],
        "wins": comp["wins"],
        "level": comp["level"],
        "best_placement": comp["best_placement"],
        "matched_terms": comp["matched_terms"],
        "units": [
            {
                "name": clean_tft_name(unit.get("champion", "")),
                "star_level": unit.get("star_level"),
                "items": [
                    clean_tft_name(item)
                    for item in unit.get("items", [])
                ],
                "label": format_unit(unit),
            }
            for unit in comp["units"]
        ],
        "traits": [
            {
                "name": clean_tft_name(trait.get("name", "")),
                "tier_current": trait.get("tier_current", 0),
                "num_units": trait.get("num_units", 0),
                "label": format_trait(trait),
            }
            for trait in active_traits[:8]
        ],
    }


@app.get("/")
def index():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


@app.get("/api/config")
def config():
    return {
        "admin_enabled": admin_enabled(),
        "demo_mode": not admin_enabled(),
    }


@app.post("/api/ask", response_model=AskResponse)
def ask(request: AskRequest):
    try:
        answer = generate_answer(request.question)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "question": request.question,
        "answer": answer,
    }


@app.get("/api/comps")
def comps(
    limit: int = Query(10, ge=1, le=50),
    min_games: int = Query(3, ge=1, le=100),
):
    try:
        recommendations = get_recommended_comps(
            limit=limit,
            min_games=min_games,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "items": [
            serialize_comp(comp, index)
            for index, comp in enumerate(recommendations, start=1)
        ]
    }


@app.post("/api/load/champions")
def load_champions(_: None = Depends(require_admin)):
    try:
        clear_champions()
        load_champions_into_database()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"status": "ok"}


@app.post("/api/load/items")
def load_items(_: None = Depends(require_admin)):
    try:
        clear_items()
        load_items_into_database()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"status": "ok"}


@app.post("/api/load/matches")
def load_matches(
    request: Any = Body(default=None),
    _: None = Depends(require_admin),
):
    if not isinstance(request, dict):
        request = {}

    max_players_per_rank = bounded_int(
        request.get("max_players_per_rank"),
        default=1,
        minimum=1,
        maximum=100,
    )
    matches_per_player = bounded_int(
        request.get("matches_per_player"),
        default=1,
        minimum=1,
        maximum=50,
    )

    try:
        players = collect_high_elo_players(
            max_players_per_rank=max_players_per_rank
        )
        import_stats = collect_matches_from_players(
            players,
            matches_per_player=matches_per_player,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"status": "ok", **import_stats}





def load_champions_into_database():
    """
    Fetch champion data, create embeddings, and store everything in PostgreSQL.
    """

    from app.embeddings import create_champion_text, create_embedding

    raw_data = fetch_champions()
    champions = extract_champion_data(raw_data)

    for champion in champions:
        content = create_champion_text(
            set_nr=champion["set_nr"],
            name=champion["name"],
            cost=champion["cost"],
            traits=champion["traits"],
            ability=champion["ability"]
        )

        embedding = create_embedding(content)

        insert_champion(
            set_nr=champion["set_nr"],
            name=champion["name"],
            cost=champion["cost"],
            traits=champion["traits"],
            ability=champion["ability"],
            content=content,
            embedding=embedding
        )

    print(f"Stored {len(champions)} champions.")


def load_items_into_database():
    """
    Fetch item data, create embeddings, and store everything in PostgreSQL.
    """

    from app.embeddings import create_embedding, create_item_text

    raw_data = fetch_items()
    items = extract_item_data(raw_data)

    for item in items:
        content = create_item_text(
            name=item["name"],
            description=item["desc"],
            stats=item["stats"],
            composition=item["composition"]
        )

        embedding = create_embedding(content)

        insert_items(
            name=item["name"],
            description=item["desc"],
            stats=item["stats"],
            composition=item["composition"],
            embedding=embedding
        )

    print(f"Stored {len(items)} items.")



def ask_question():
    """
    Ask a TFT question and print the generated RAG prompt.
    """

    question = input("Ask a TFT question: ")

    answer = generate_answer(question)

    print("\n--- RAG OUTPUT ---\n")
    print(answer)


def read_positive_int(prompt: str, default: int) -> int:
    value = input(prompt).strip()

    if not value:
        return default

    try:
        parsed_value = int(value)
    except ValueError:
        print(f"Invalid number, using {default}.")
        return default

    if parsed_value <= 0:
        print(f"Number must be positive, using {default}.")
        return default

    return parsed_value


def recommend_comps():
    """
    Print comp recommendations from stored match boards.
    """

    limit = read_positive_int("How many comps? [10]: ", 10)
    min_games = read_positive_int("Minimum games per comp? [3]: ", 3)

    recommendations = build_comp_recommendations(
        limit=limit,
        min_games=min_games,
    )

    print("\n--- COMP RECOMMENDATIONS ---\n")
    print(recommendations)




if __name__ == "__main__":
    main()
