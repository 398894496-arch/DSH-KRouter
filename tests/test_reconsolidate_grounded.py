"""The nightly learner learns a trigger only with a quote that passes three checks.

The sentence the model says answers the query must be on the candidate page, be a sentence (at least QUOTE_TOKENS
words, not a fragment like "stored in") and share a content word with the query (an unrelated sentence from the page
does not count). A bare path, the learner's old answer format, no longer counts. This stops made-up, fragmentary and
unrelated quotes; whether a neighbour page truly answers is still the model's call, asked for in the prompt. Secret
pages and inputs pages (`03 资料与证据`) are never shown to the model as candidates.
"""

from __future__ import annotations

import reconsolidate as rc

PAGE = "Every new screen meets WCAG 2.2 AA. Buttons need a visible focus ring and a contrast ratio of at least 4.5:1."
SECRETS = "API keys and tokens are stored in the team vault, never in the repository. Rotate them every quarter."
Q_BUTTONS = "What contrast ratio do buttons need?"
Q_SSH = "Where do we keep the SSH keys for production servers?"


def test_a_quote_on_the_page_that_answers_is_learned():
    cands = {"Engineering/Accessibility.md": PAGE}
    pick = {"page": "Engineering/Accessibility.md", "quote": "Buttons need a visible focus ring and a contrast ratio of at least 4.5:1."}
    assert rc.grounded(pick, cands, Q_BUTTONS) == "Engineering/Accessibility.md"


def test_no_quote_a_made_up_quote_a_bare_path_or_another_page_is_refused():
    cands = {"Engineering/Accessibility.md": PAGE}
    assert rc.grounded("Engineering/Accessibility.md", cands, Q_BUTTONS) == ""
    assert rc.grounded({"page": "Engineering/Accessibility.md"}, cands, Q_BUTTONS) == ""
    made_up = {"page": "Engineering/Accessibility.md", "quote": "Buttons are tested with VoiceOver."}
    assert rc.grounded(made_up, cands, Q_BUTTONS) == ""
    other = {"page": "Engineering/Other.md", "quote": "Buttons need a visible focus ring."}
    assert rc.grounded(other, cands, Q_BUTTONS) == ""  # 只能从给出的候选里选


def test_a_fragment_or_an_unrelated_sentence_from_the_page_is_refused():
    """An outside review's two attacks on the first version: a 9-character fragment, and a true but unrelated line."""
    cands = {"Engineering/Where secrets live.md": SECRETS}
    for quote in ("stored in", "Rotate them every quarter."):
        assert rc.grounded({"page": "Engineering/Where secrets live.md", "quote": quote}, cands, Q_SSH) == ""


def test_secret_pages_are_never_candidates(tmp_path):
    (tmp_path / "钥匙.md").write_text("---\ntitle: 钥匙\n---\nAPI key 放在这里。\n", encoding="utf-8")
    (tmp_path / "Rules.md").write_text("---\ntitle: Rules\nsecret: true\n---\nDo the thing.\n", encoding="utf-8")
    (tmp_path / "Open.md").write_text("---\ntitle: Open\n---\nShip from main.\n", encoding="utf-8")
    assert rc.page_text(tmp_path, "钥匙.md") is None and rc.page_text(tmp_path, "Rules.md") is None
    assert rc.page_text(tmp_path, "Open.md") == "Ship from main."


def test_inputs_pages_are_not_candidates():
    assert "03 资料与证据/剪藏/某网页.md".startswith(rc.UNTRUSTED)
    assert not "02 经验与方法/发版.md".startswith(rc.UNTRUSTED)
