"""The nightly learner learns a trigger only with proof: the sentence it says answers the query must be on the page.

A neighbour page (same subject, does not answer) has no such sentence, so a model that picks it anyway is refused.
A bare path, the learner's old answer format, no longer counts. Secret pages are never shown to the model.
"""

from __future__ import annotations

import reconsolidate as rc

PAGE = "Every new screen meets WCAG 2.2 AA. Buttons need a visible focus ring and a contrast ratio of at least 4.5:1."


def test_a_quote_on_the_page_is_learned():
    cands = {"Engineering/Accessibility.md": PAGE}
    pick = {"page": "Engineering/Accessibility.md", "quote": "Buttons need a visible focus ring and a contrast ratio of at least 4.5:1."}
    assert rc.grounded(pick, cands) == "Engineering/Accessibility.md"


def test_no_quote_a_made_up_quote_or_a_bare_path_is_refused():
    cands = {"Engineering/Accessibility.md": PAGE}
    assert rc.grounded("Engineering/Accessibility.md", cands) == ""
    assert rc.grounded({"page": "Engineering/Accessibility.md"}, cands) == ""
    made_up = {"page": "Engineering/Accessibility.md", "quote": "New screens are tested with VoiceOver."}
    assert rc.grounded(made_up, cands) == ""
    other = {"page": "Engineering/Other.md", "quote": "Every new screen meets WCAG 2.2 AA."}
    assert rc.grounded(other, cands) == ""  # 只能从给出的候选里选


def test_secret_pages_are_never_candidates(tmp_path):
    (tmp_path / "钥匙.md").write_text("---\ntitle: 钥匙\n---\nAPI key 放在这里。\n", encoding="utf-8")
    (tmp_path / "Rules.md").write_text("---\ntitle: Rules\nsecret: true\n---\nDo the thing.\n", encoding="utf-8")
    (tmp_path / "Open.md").write_text("---\ntitle: Open\n---\nShip from main.\n", encoding="utf-8")
    assert rc.page_text(tmp_path, "钥匙.md") is None and rc.page_text(tmp_path, "Rules.md") is None
    assert rc.page_text(tmp_path, "Open.md") == "Ship from main."
