# app/embeddings.py

from sentence_transformers import SentenceTransformer


MODEL_NAME = "all-MiniLM-L6-v2"

model = SentenceTransformer(MODEL_NAME)


def create_embedding(text: str) -> list[float]:
    """
    creates embeddings out of text.
    """

    embedding = model.encode(text)

    return embedding.tolist()


def create_champion_text(
    set_nr:str,
    name: str,
    cost: int,
    traits: list[str],
    ability: str
) -> str:
    """
    creates text for champion§.
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
    content: str
) -> str:
    """
    creates text for patch note.
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
    creates text for patch note.
    """

    return (
        f"The Item {name} has the following description: {description}. "
        f"It has the following stats: {stats}. "
        f"Its composition is {composition}. "
    )