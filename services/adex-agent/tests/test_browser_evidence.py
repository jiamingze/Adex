from adex_agent.browser.evidence import EvidenceNotebook
from adex_agent.browser.workflow import lookup_result


def page(url, text, id="revision"):
    return {
        "url": url,
        "observation_id": id,
        "nodes": [
            {"role": "StaticText", "name": text},
            {"role": "textbox", "name": "secret account", "value": "secret", "protected": True},
        ],
    }


def test_comparison_keeps_sources_and_restores_checkpoint():
    notes = EvidenceNotebook()
    notes.observe(page("https://shop-a.example/item?id=1", "256GB ¥1000"))
    notes.observe(page("https://shop-b.example/item?id=2", "256GB ¥1100"))
    notes.observe(page("https://shop-b.example/item?id=2", "256GB ¥1100"))
    restored = EvidenceNotebook(notes.snapshot())
    assert len(restored.pages) == 2
    assert "secret" not in str(restored.pages)
    result = lookup_result(
        "session",
        page("https://shop-b.example/item?id=2", "256GB ¥1100"),
        "两站价格需核对优惠条件",
        restored.snapshot(),
    )
    assert "shop-a.example" in result["content"] and "shop-b.example" in result["content"]
    assert len(result["artifact"]["research_evidence"]) == 2
    assert not result["artifact"]["receipts"]


def test_notebook_is_bounded_and_skips_login_blocks():
    notes = EvidenceNotebook()
    for i in range(20):
        notes.observe(page(f"https://shop.example/product/{i}", "x" * 9000, str(i)))
    assert len(notes.pages) == 10 and all(len(p["visible_text"]) <= 1600 for p in notes.pages)
    notes.observe(page("https://shop.example/login", "password") | {"login_form": {"fields": []}})
    notes.observe(page("https://shop.example/error", "risk") | {"access_block": {"code": "blocked"}})
    assert len(notes.pages) == 10
