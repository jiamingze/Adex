from adex_tools.search import normalize_results


def test_result_links_and_evidence():
    result = normalize_results(
        {"results": [{"title": "News", "url": "https://example.com/news", "content": "snippet"}]}, "now"
    )
    assert result["provider"] == "tavily"
    assert result["items"][0]["evidence_level"] == "SEARCH_SNIPPET"


def test_unsafe_links_and_duplicates():
    rows = [
        {"url": url}
        for url in [
            "javascript:alert(1)",
            "https://user:secret@example.com",
            "https://example.com",
            "https://example.com",
        ]
    ]
    assert len(normalize_results({"results": rows}, "now")["items"]) == 1
