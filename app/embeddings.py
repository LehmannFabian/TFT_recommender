import os

from dotenv import load_dotenv
from google import genai
from google.genai import types


load_dotenv()

DEFAULT_EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIMENSIONS = 384


def create_embedding(text: str) -> list[float]:
    """
    Create a 384-dimensional embedding using Gemini.
    """

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured. Add it to your .env file."
        )

    client = genai.Client(api_key=api_key)
    response = client.models.embed_content(
        model=os.getenv("GEMINI_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL),
        contents=text,
        config=types.EmbedContentConfig(
            output_dimensionality=EMBEDDING_DIMENSIONS,
        ),
    )

    return response.embeddings[0].values


def create_champion_text(
    set_nr: str,
    name: str,
    cost: int,
    traits: list[str],
    ability: str,
) -> str:
    """
    Create searchable text for a champion.
    """

    traits_text = ", ".join(traits)

    return (
        f"{name} is a {cost}-cost TFT champion in set {set_nr}. "
        f"Traits: {traits_text}. "
        f"Ability: {ability}"
    )


def create_patch_note_text(
    patch_version: str,
    title: str,
    content: str,
) -> str:
    """
    Create searchable text for a patch note.
    """

    return (
        f"TFT Patch {patch_version}. "
        f"Title: {title}. "
        f"Content: {content}"
    )


def create_item_text(
    name: str,
    description: str,
    stats: str,
    composition: str,
) -> str:
    """
    Create searchable text for an item.
    """

    return (
        f"The item {name} has the following description: {description}. "
        f"It has the following stats: {stats}. "
        f"Its composition is {composition}. "
    )
