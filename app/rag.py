import os

from dotenv import load_dotenv

from app.comp_recommender import clean_tft_name, format_trait, format_unit
from app.retriever import retrieve_context

from google import genai

load_dotenv()

DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"


def build_context(docs: list[dict]) -> str:
    """
    Convert retrieved documents into a single context string.
    """

    context_parts = []

    for doc in docs:
        if doc["source_type"] == "champion":
            context_parts.append(
                f"[Champion]\n"
                f"Name: {doc['name']}\n"
                f"Cost: {doc['cost']}\n"
                f"Traits: {', '.join(doc['traits'])}\n"
                f"Ability: {doc['ability']}\n"
                f"Content: {doc.get('content', '')}"
            )

        elif doc["source_type"] == "item":
            context_parts.append(
                f"[Item]\n"
                f"Name: {doc['name']}\n"
                f"Description: {doc['description']}\n"
                f"Stats: {doc['stats']}\n"
                f"Composition: {doc['composition']}"
            )

        elif doc["source_type"] == "patch_note":
            context_parts.append(
                f"[Patch Note]\n"
                f"Patch: {doc['patch_version']}\n"
                f"Title: {doc['title']}\n"
                f"Content: {doc['content']}\n"
                f"URL: {doc['url']}"
            )

        elif doc["source_type"] == "comp":
            units = [
                format_unit(unit)
                for unit in doc["units"]
            ]
            traits = [
                format_trait(trait)
                for trait in doc["traits"]
                if trait.get("tier_current", 0) > 0
            ]
            items = [
                clean_tft_name(item)
                for item in doc["items"]
            ]

            context_parts.append(
                f"[Comp Recommendation]\n"
                f"Games: {doc['games']}\n"
                f"Requested Terms Matched: {doc.get('matched_terms', 0)}\n"
                f"Average Placement: {doc['avg_placement']}\n"
                f"Top 4 Rate: {doc['top4_rate']}%\n"
                f"Top 4 Count: {doc['top4s']}\n"
                f"Wins: {doc['wins']}\n"
                f"Representative Level: {doc['level']}\n"
                f"Units: {', '.join(units)}\n"
                f"Traits: {', '.join(traits)}\n"
                f"Items Seen: {', '.join(items)}\n"
                f"Best Placement Seen: {doc['best_placement']}"
            )

    return "\n\n---\n\n".join(context_parts)

def build_prompt(question: str, context: str) -> str:
    """
    Build the final prompt for the language model.
    """

    return f"""
You are a helpful Teamfight Tactics assistant.

Answer questions about champions, items, and team comps using only the provided context.
For comp recommendations, prefer comps with strong average placement, top-4 rate, wins, and enough games.
If the answer is not contained in the context, say that you do not have enough information.

Context:
{context}

Question:
{question}

Answer:
""".strip()


def build_fallback_answer(question: str, docs: list[dict], reason: str | None = None) -> str:
    if not docs:
        return (
            "I do not have enough information in the current database to answer that. "
            "Try loading current champion, item, or match data first."
        )

    lines = []

    if reason:
        lines.append(f"Gemini is unavailable: {reason}")
        lines.append("")
        lines.append("Retrieved context:")

    for doc in docs:
        if doc["source_type"] == "champion":
            traits = ", ".join(doc.get("traits") or []) or "No traits stored"
            ability = doc.get("ability") or "No ability text stored"
            lines.append(
                f"- Champion: {doc['name']} | Cost: {doc['cost']} | "
                f"Traits: {traits} | Ability: {ability}"
            )

        elif doc["source_type"] == "item":
            description = doc.get("description") or "No description stored"
            lines.append(f"- Item: {doc['name']} | {description}")

        elif doc["source_type"] == "comp":
            units = ", ".join(
                format_unit(unit)
                for unit in doc["units"]
            )
            traits = ", ".join(
                format_trait(trait)
                for trait in doc["traits"]
                if trait.get("tier_current", 0) > 0
            )
            lines.append(
                f"- Comp: avg placement {doc['avg_placement']}, "
                f"top 4 rate {doc['top4_rate']}%, games {doc['games']}. "
                f"Units: {units}. Traits: {traits or 'No active traits'}."
            )

    return "\n".join(lines)


def call_gemini(prompt: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured. Add it to your .env file."
        )

    model_name = os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
    client = genai.Client(api_key=api_key)
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
        )
    except Exception as exc:
        error_text = str(exc)

        if "RESOURCE_EXHAUSTED" in error_text or "429" in error_text:
            raise RuntimeError(
                "Gemini quota exceeded for this API key/model. "
                "Check Google AI Studio billing/quota or set GEMINI_MODEL to another available Gemini model."
            ) from exc

        raise RuntimeError(f"Gemini request failed: {exc}") from exc

    text = getattr(response, "text", None)

    if not text:
        raise RuntimeError("Gemini returned an empty response.")

    return text.strip()


def generate_answer(question: str) -> str:
    """
    Retrieve relevant documents and generate a final answer with Gemini.
    """

    docs = retrieve_context(question, limit=5)

    if not docs:
        return build_fallback_answer(question, docs)

    context = build_context(docs)

    prompt = build_prompt(question, context)

    try:
        return call_gemini(prompt)
    except RuntimeError as exc:
        return build_fallback_answer(question, docs, reason=str(exc))
