"""Local policy checks; these do not establish external website compatibility."""

import pytest
from fastapi import HTTPException
from adex_tools.creation.diagram import validate_diagram
from adex_tools.runners.browser_policy import admitted_hosts


@pytest.mark.parametrize("arrow", ["-->", "->>", "-->>", "->", "<--", "<->"])
def test_diagram_arrows_are_tokens_not_html_filters(arrow):
    assert validate_diagram(f"flowchart LR\nA{arrow}B")["valid"]


@pytest.mark.parametrize(
    "payload", ["<script>alert(1)</script>", "<!--x-->", "<<--script-->>", "A[<img src=x>]"]
)
def test_diagram_rejects_angle_syntax_that_is_not_an_arrow(payload):
    with pytest.raises(HTTPException):
        validate_diagram("flowchart LR\n" + payload)


@pytest.mark.parametrize(
    "host", ["a" * 64 + ".com", "-a.com", "a-.com", "a..com", "a.1x", "a." * 200 + "com"]
)
def test_host_labels_and_total_length_are_validated(host, monkeypatch):
    monkeypatch.setenv("ADEX_BROWSER_MODE", "public")
    with pytest.raises(HTTPException):
        admitted_hosts("https://" + host)
