"""Category keyword classification and learned rules."""

from helpers import auth_header, register, upload_receipt
from sqlmodel import Session, select

from financial_tracker_api.models import CategoryRule
from financial_tracker_api.services.categories import (
    classify_category,
    normalize_item_key,
)


def test_costco_produce_and_staples_categorized() -> None:
    cases = {
        "BLUEBERRIES": "fruit",
        "LIMES 3 LB": "fruit",
        "BANANAS": "fruit",
        "CILANTRO": "vegetable",
        "MINI CUKES": "vegetable",
        "BAKER POTATO": "vegetable",
        "AA SPAGHETTI": "grocery",
        "KÉFIR 2L": "dairy",
        "SOFT CR CHSE": "dairy",
        "GARLIC CHEES": "dairy",
        "2% LIBERTÉ": "dairy",
        "HOMO MILK": "dairy",
        "KS FR EGGS": "dairy",
        "**KS FACIAL*": "household",
    }
    for name, expected in cases.items():
        slug, needs_review = classify_category(name)
        assert slug == expected, f"{name}: got {slug}"
        assert needs_review is False


def test_normalize_item_key_strips_pack_size() -> None:
    assert normalize_item_key("LIMES 3 LB.") == normalize_item_key("LIMES")
    assert normalize_item_key("KÉFIR 2L") == "kefir"


def test_classify_prefers_section_and_learned() -> None:
    assert classify_category("Anything", "vegetable") == ("vegetable", False)
    assert classify_category("Mystery SKU", learned_category="snacks") == ("snacks", False)


def test_remember_and_lookup_empty_keys(client) -> None:
    from financial_tracker_api.services.categories import (
        lookup_learned_category,
        remember_category,
    )

    engine = client.app.state.test_engine
    with Session(engine) as session:
        remember_category(session, user_id=1, item_name="***", category="fruit")
        remember_category(session, user_id=1, item_name="OK ITEM", category="")
        session.commit()
        assert lookup_learned_category(session, 1, "***") is None
        assert lookup_learned_category(session, 1, "OK ITEM") is None
        assert lookup_learned_category(session, 1, "") is None


def test_remember_updates_existing_rule(client) -> None:
    from financial_tracker_api.services.categories import (
        lookup_learned_category,
        remember_category,
    )

    token = register(client, "updaterule@example.com")
    engine = client.app.state.test_engine
    with Session(engine) as session:
        from financial_tracker_api.models import User

        user = session.exec(select(User).where(User.email == "updaterule@example.com")).first()
        assert user and user.id
        remember_category(session, user.id, "ROCCO ROMA", "meat")
        session.commit()
        remember_category(session, user.id, "ROCCO ROMA", "grocery")
        session.commit()
        assert lookup_learned_category(session, user.id, "ROCCO ROMA") == "grocery"


def test_patch_category_is_remembered_on_next_upload(client) -> None:
    token = register(client, "learncats@example.com")
    headers = auth_header(token)
    first = upload_receipt(
        client,
        token,
        ocr_text="Mystery Mart\nROCCO ROMA 5.99\nSubtotal 5.99\nTotal 5.99\n",
    ).json()
    item = next(i for i in first["line_items"] if "ROCCO" in i["name"].upper())
    assert item["category"] == "other"

    patched = client.patch(
        f"/api/receipts/line-items/{item['id']}",
        headers=headers,
        json={"category": "grocery"},
    )
    assert patched.status_code == 200
    assert patched.json()["category"] == "grocery"

    engine = client.app.state.test_engine
    with Session(engine) as session:
        rules = session.exec(select(CategoryRule)).all()
        assert len(rules) == 1
        assert rules[0].category == "grocery"

    second = upload_receipt(
        client,
        token,
        ocr_text="Mystery Mart\nROCCO ROMA 5.99\nSubtotal 5.99\nTotal 5.99\n",
        filename="receipt2.png",
    ).json()
    learned = next(i for i in second["line_items"] if "ROCCO" in i["name"].upper())
    assert learned["category"] == "grocery"
