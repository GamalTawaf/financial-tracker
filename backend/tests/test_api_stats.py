"""Category stats endpoint."""

from helpers import SIMPLE_OCR, auth_header, register, upload_receipt


def test_category_stats_rollups_and_date_filter(client) -> None:
    token = register(client, "stats@example.com")
    headers = auth_header(token)
    upload_receipt(client, token, ocr_text=SIMPLE_OCR)
    # Second receipt with another dairy line hits existing category bucket.
    upload_receipt(
        client,
        token,
        ocr_text="Loblaws\n2026-10-20\nMilk 1.00\nSubtotal 1.00\nTotal 1.00\n",
    )

    all_stats = client.get("/api/stats/by-category", headers=headers)
    assert all_stats.status_code == 200
    body = all_stats.json()
    assert body["categories"]
    assert sum(row["item_count"] for row in body["categories"]) >= 4

    in_range = client.get(
        "/api/stats/by-category",
        headers=headers,
        params={"from": "2026-10-01", "to": "2026-10-31"},
    )
    assert in_range.status_code == 200
    assert in_range.json()["categories"]

    out_of_range = client.get(
        "/api/stats/by-category",
        headers=headers,
        params={"from": "2020-01-01", "to": "2020-12-31"},
    )
    assert out_of_range.status_code == 200
    assert out_of_range.json()["categories"] == []


def test_stats_require_auth(client) -> None:
    assert client.get("/api/stats/by-category").status_code == 401
