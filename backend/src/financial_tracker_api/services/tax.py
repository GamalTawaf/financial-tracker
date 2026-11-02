"""Ontario HST taxability rules (practical CRA approximation)."""

from __future__ import annotations

from financial_tracker_api.config import get_settings

# Keyword lists — not tax advice; based on CRA Basic Groceries / Snack Foods guidance.
ZERO_RATED_KEYWORDS: tuple[str, ...] = (
    "bread",
    "milk",
    "egg",
    "eggs",
    "butter",
    "cheese",
    "yogurt",
    "apple",
    "banana",
    "orange",
    "lettuce",
    "carrot",
    "broccoli",
    "onion",
    "potato",
    "tomato",
    "chicken",
    "beef",
    "pork",
    "fish",
    "cereal",
    "coffee bean",
    "flour",
    "rice",
    "pasta",
    "unsalted",
)

TAXABLE_KEYWORDS: tuple[str, ...] = (
    "chips",
    "crisps",
    "candy",
    "chocolate",
    "soda",
    "cola",
    "pop",
    "soft drink",
    "granola bar",
    "trail mix",
    "salted",
    "cookie",
    "popcorn",
    "shirt",
    "pants",
    "jeans",
    "shoe",
    "jacket",
    "gasoline",
    "petrol",
    "fuel",
    "detergent",
    "soap",
    "paper towel",
)


def classify_tax_status(item_name: str, category: str) -> str:
    """Return taxable | zero_rated | unknown for an item."""
    lowered = item_name.lower()
    if category in {"clothes", "gas", "household", "snacks"}:
        return "taxable"
    if any(keyword in lowered for keyword in TAXABLE_KEYWORDS):
        return "taxable"
    if any(keyword in lowered for keyword in ZERO_RATED_KEYWORDS):
        return "zero_rated"
    if category in {"fruit", "vegetable", "dairy", "meat", "bakery", "grocery"}:
        return "zero_rated"
    return "unknown"


def compute_tax_cents(line_total_cents: int, tax_status: str) -> int:
    """Compute HST cents for a line based on tax status."""
    if tax_status != "taxable":
        return 0
    rate = get_settings().hst_rate
    return int(round(line_total_cents * rate))
