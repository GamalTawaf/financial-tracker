"""Category keyword classification."""

from __future__ import annotations

CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "fruit": ("apple", "banana", "orange", "grape", "berry", "mango", "pear", "fruit"),
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
    ),
    "snacks": ("chips", "crisps", "candy", "chocolate", "cookie", "granola", "popcorn", "snack"),
    "dairy": ("milk", "cheese", "yogurt", "butter", "cream", "egg"),
    "meat": ("chicken", "beef", "pork", "fish", "turkey", "bacon", "sausage", "meat"),
    "bakery": ("bread", "bagel", "bun", "loaf", "croissant", "muffin", "flour"),
    "beverages": ("juice", "soda", "cola", "water", "coffee", "tea", "beer", "wine"),
    "grocery": ("grocery", "flour", "coconut", "baking", "powder", "nuts"),
    "clothes": ("shirt", "pants", "jeans", "sock", "shoe", "jacket", "hoodie", "clothes"),
    "gas": ("gasoline", "petrol", "fuel", "gas station"),
    "household": ("soap", "detergent", "paper towel", "tissue", "cleaner", "trash bag"),
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


def classify_category(item_name: str, section_category: str | None = None) -> tuple[str, bool]:
    """Return (category_slug, needs_review) for an item name.

    Prefer a receipt section header (Adonis ``GROCERY`` / ``VEGETABLE``) when present.
    """
    if section_category:
        return section_category, False
    lowered = item_name.lower()
    for slug, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return slug, False
    return "other", True
