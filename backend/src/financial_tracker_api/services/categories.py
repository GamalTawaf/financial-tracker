"""Category keyword classification and per-user learned rules."""

from __future__ import annotations

import re
import unicodedata

from sqlmodel import Session, select

from financial_tracker_api.models import CategoryRule

CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "fruit": (
        "apple",
        "banana",
        "orange",
        "grape",
        "berry",
        "berries",
        "blueberr",
        "strawberr",
        "raspberr",
        "mango",
        "pear",
        "fruit",
        "lime",
        "lemon",
        "melon",
        "avocado",
        "peach",
        "plum",
        "cherry",
        "cherries",
        "kiwi",
        "pineapple",
    ),
    "vegetable": (
        "lettuce",
        "carrot",
        "broccoli",
        "onion",
        "potato",
        "tomato",
        "veg",
        "spinach",
        "pepper",
        "mint",
        "cilantro",
        "parsley",
        "basil",
        "garlic",
        "cuke",
        "cucumber",
        "celery",
        "cabbage",
        "kale",
        "zucchini",
        "squash",
        "corn",
        "mushroom",
        "asparagus",
        "radish",
        "beet",
    ),
    "snacks": ("chips", "crisps", "candy", "chocolate", "cookie", "granola", "popcorn", "snack"),
    "dairy": (
        "milk",
        "cheese",
        "chees",
        "chse",
        "yogurt",
        "yoghurt",
        "butter",
        "cream",
        "egg",
        "kefir",
        "liberte",
        "lactose",
    ),
    "meat": ("chicken", "beef", "pork", "fish", "turkey", "bacon", "sausage", "meat"),
    "bakery": ("bread", "bagel", "bun", "loaf", "croissant", "muffin", "flour"),
    "beverages": ("juice", "soda", "cola", "water", "coffee", "tea", "beer", "wine"),
    "grocery": (
        "grocery",
        "flour",
        "coconut",
        "baking",
        "powder",
        "nuts",
        "pasta",
        "spaghetti",
        "penne",
        "macaroni",
        "rice",
        "bean",
        "lentil",
        "oatmeal",
        "cereal",
        "oil",
        "vinegar",
        "sauce",
        "soup",
        "broth",
    ),
    "clothes": ("shirt", "pants", "jeans", "sock", "shoe", "jacket", "hoodie", "clothes"),
    "gas": ("gasoline", "petrol", "fuel", "gas station"),
    "household": (
        "soap",
        "detergent",
        "paper towel",
        "tissue",
        "facial",
        "cleaner",
        "trash bag",
        "toilet",
        "shampoo",
        "toothpaste",
        "napkin",
    ),
}

SEED_CATEGORIES: list[tuple[str, str]] = [
    ("fruit", "Fruit"),
    ("vegetable", "Vegetable"),
    ("snacks", "Snacks"),
    ("dairy", "Dairy"),
    ("meat", "Meat"),
    ("bakery", "Bakery"),
    ("beverages", "Beverages"),
    ("grocery", "Grocery"),
    ("clothes", "Clothes"),
    ("gas", "Gas"),
    ("household", "Household"),
    ("other", "Other"),
]


def _fold(text: str) -> str:
    """Lowercase and strip accents so KÉFIR / LIBERTÉ still match keywords."""
    normalized = unicodedata.normalize("NFKD", text.casefold())
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def normalize_item_key(name: str) -> str:
    """Stable key for learned rules: fold accents, drop pack size noise."""
    folded = _fold(name)
    folded = re.sub(r"[*]+", " ", folded)
    # Drop trailing pack / weight markers: ``3 lb``, ``2l``, ``12ct``.
    folded = re.sub(
        r"\b\d+(?:[.,]\d+)?\s*(?:lb|lbs|kg|g|oz|ct|pk|pack|l)\b",
        " ",
        folded,
    )
    folded = re.sub(r"[^a-z0-9%]+", " ", folded)
    return re.sub(r"\s+", " ", folded).strip()


def lookup_learned_category(session: Session, user_id: int, item_name: str) -> str | None:
    """Return a user-taught category for this item name, if any."""
    key = normalize_item_key(item_name)
    if not key:
        return None
    rule = session.exec(
        select(CategoryRule).where(
            CategoryRule.user_id == user_id,
            CategoryRule.name_key == key,
        )
    ).first()
    return rule.category if rule else None


def remember_category(session: Session, user_id: int, item_name: str, category: str) -> None:
    """Upsert a learned item→category rule for future uploads."""
    key = normalize_item_key(item_name)
    if not key or not category:
        return
    rule = session.exec(
        select(CategoryRule).where(
            CategoryRule.user_id == user_id,
            CategoryRule.name_key == key,
        )
    ).first()
    if rule is None:
        session.add(CategoryRule(user_id=user_id, name_key=key, category=category))
    else:
        rule.category = category
        from financial_tracker_api.models import utcnow

        rule.updated_at = utcnow()
        session.add(rule)


def classify_category(
    item_name: str,
    section_category: str | None = None,
    *,
    learned_category: str | None = None,
) -> tuple[str, bool]:
    """Return (category_slug, needs_review) for an item name.

    Order: section header → user-taught rule → keywords → other.
    """
    if section_category:
        return section_category, False
    if learned_category:
        return learned_category, False
    lowered = _fold(item_name)
    # Cheese / dairy abbreviations beat produce words (e.g. ``GARLIC CHEES``).
    dairy_strong = ("cheese", "chees", "chse", "kefir", "yogurt", "yoghurt", "milk", "liberte")
    if any(token in lowered for token in dairy_strong):
        return "dairy", False
    for slug, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return slug, False
    return "other", True
