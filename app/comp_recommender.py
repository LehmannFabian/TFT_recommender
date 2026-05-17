from app.database import get_recommended_comps


def clean_tft_name(value: str) -> str:
    """
    Convert Riot API ids like TFT14_Annie into readable names.
    """

    if not value:
        return ""

    name = value.split("_")[-1]

    return name.replace("Characters/", "").replace("_", " ")


def format_unit(unit: dict) -> str:
    champion = clean_tft_name(unit.get("champion", ""))
    star_level = unit.get("star_level")
    items = [
        clean_tft_name(item)
        for item in unit.get("items", [])
    ]

    unit_text = champion

    if star_level:
        unit_text += f" {star_level}*"

    if items:
        unit_text += f" ({', '.join(items)})"

    return unit_text


def format_trait(trait: dict) -> str:
    name = clean_tft_name(trait.get("name", ""))
    tier = trait.get("tier_current", 0)
    units = trait.get("num_units", 0)

    if tier:
        return f"{name} {units}"

    return name


def format_comp_recommendation(comp: dict, rank: int) -> str:
    units = [
        format_unit(unit)
        for unit in comp["units"]
    ]

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

    traits = [
        format_trait(trait)
        for trait in active_traits[:6]
    ]

    return (
        f"{rank}. Avg placement {comp['avg_placement']} | "
        f"Top 4 {comp['top4_rate']}% | "
        f"{comp['games']} games | "
        f"{comp['wins']} wins\n"
        f"   Units: {', '.join(units)}\n"
        f"   Traits: {', '.join(traits) if traits else 'No active traits'}"
    )


def build_comp_recommendations(limit=10, min_games=3) -> str:
    comps = get_recommended_comps(
        limit=limit,
        min_games=min_games,
    )

    if not comps:
        return (
            "No comp recommendations available yet. "
            "Load match games first, or lower the minimum games threshold."
        )

    lines = [
        "Recommended comps from stored high-elo match boards:",
        "",
    ]

    for index, comp in enumerate(comps, start=1):
        lines.append(format_comp_recommendation(comp, index))
        lines.append("")

    return "\n".join(lines).strip()
