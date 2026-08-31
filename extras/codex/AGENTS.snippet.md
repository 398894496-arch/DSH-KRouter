# Codex / AGENTS snippet

Add this to the Codex handbook the host actually uses. Do not paste someone else's private vault path.

```
Knowledge-dependent tasks: set OBSIDIAN_VAULT, then follow
~/.agents/skills/krouter-obsidian/SKILL.md
and run ~/.agents/skills/krouter-obsidian/scripts/route_knowledge.sh status first.
If the receipt has host_action:, tell the host that line (paste *_API_KEY on
the vault key page, or log in grok / official Codex / claude). Do not print secrets.
Then run route_knowledge.sh for the needed route.
If canonical_match is true, cite canonical_source.
If the receipt lists suggestions, retry one suggested alias once.
At the start of work, run python3 ~/.agents/skills/krouter-obsidian/scripts/ask_product.py ask --query "<user text>". If trigger.ask is set, ask prompt and wait. record does not write active; promote after this task succeeds.
```
