"""Render docs/img/demo.gif. Every line shown is real: the two vault pages are the demo vault's, the `→` lines are
the router's recall output on it, and the answers are what `claude -p --plugin-dir .` (Claude Code with this repo's
plugin, a clean HOME, no other instructions) replied on 2026-10-11. Requires Pillow; macOS fonts.

    python3 docs/img/make_demo_gif.py docs/img/demo.gif
"""
import sys
from PIL import Image, ImageDraw, ImageFont

OUT = sys.argv[1]
W, H = 960, 540
BG, FG, DIM, ACC, OK, WARN, CARD = "#0f1115", "#e6e6e6", "#8a8f98", "#7aa2f7", "#9ece6a", "#e0af68", "#171a21"
MONO = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 17)
MONO_B = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 17, index=1)
CJK = ImageFont.truetype("/System/Library/Fonts/Hiragino Sans GB.ttc", 17)
TITLE = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 22, index=1)
SMALL = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 13)
LH = 26
X0 = 40


def is_cjk(ch):
    return ord(ch) > 0x2E80


def draw_text(d, x, y, text, fill=FG, bold=False):
    for ch in text:
        f = CJK if is_cjk(ch) else (MONO_B if bold else MONO)
        d.text((x, y), ch, font=f, fill=fill)
        x += d.textlength(ch, font=f)
    return x


def wrap(text, width_chars=78):
    out, line = [], ""
    for word in text.split(" "):
        if len(line) + len(word) + 1 > width_chars:
            out.append(line)
            line = word
        else:
            line = (line + " " + word).strip()
    return out + [line]


def frame(title, day_color, lines, footer=True):
    """lines: [(text, color, bold)]"""
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, 54], fill=CARD)
    d.text((X0, 15), title, font=TITLE, fill=day_color)
    y = 80
    for text, color, bold in lines:
        draw_text(d, X0, y, text, color, bold)
        y += LH
    if footer:
        d.text((X0, H - 28), "Real output: Claude Code + KRouter plugin on a demo vault (github.com/398894496-arch/KRouter)",
               font=SMALL, fill=DIM)
    return im


frames, durations = [], []


def add(im, ms):
    frames.append(im)
    durations.append(ms)


mon = [("vault: 02 经验与方法/Release/Release process (Monday).md", DIM, False), ("", FG, False),
       ("# Release process (Monday)", FG, True), ("", FG, False),
       ("Ship from any branch: tag the commit by hand and upload the build.", FG, False)]
add(frame("Monday · we decide A", ACC, mon), 2600)

wed = [("vault: 02 经验与方法/Release/Release process.md", DIM, False), ("", FG, False),
       ("# Release process", FG, True), ("", FG, False),
       ("Ship only from a tag on main; CI builds and publishes the release.", OK, False),
       ("Corrected on Wednesday, after a hotfix from a feature branch skipped", FG, False),
       ("the tests. This replaces “Release process (Monday)”.", FG, False), ("", FG, False),
       ("Release process (Monday).md   status: superseded", WARN, False)]
add(frame("Wednesday · we change it to B", WARN, wed), 3400)

q1 = "How do we ship a release?"
a1 = ("You ship only from a tag on `main`, and CI builds and publishes the release (this was a correction made on "
      "2026-10-07). Source: `02 经验与方法/Release/Release process.md` in your vault.")
for i in range(0, len(q1) + 1, 3):
    add(frame("Thursday · any agent asks", OK, [("> " + q1[:i] + "▌", FG, True)]), 70)
base = [("> " + q1, FG, True), ("", FG, False), ("  krouter_ask(\"How do we ship a release?\")", DIM, False),
        ("  → 02 经验与方法/Release/Release process.md  tier=rule status=active", DIM, False), ("", FG, False)]
add(frame("Thursday · any agent asks", OK, base), 1400)
add(frame("Thursday · any agent asks", OK, base + [(ln, FG, False) for ln in wrap(a1, 70)]), 4200)

q2 = "What is our Kubernetes autoscaling policy?"
a2 = ("Your KRouter vault has no page on a Kubernetes autoscaling policy, so I can't tell you what it is without "
      "guessing. If it's written down somewhere else, like a repo, a doc or a link, point me to it and I'll look.")
for i in range(0, len(q2) + 1, 3):
    add(frame("And when the vault does not know", ACC, [("> " + q2[:i] + "▌", FG, True)]), 70)
base2 = [("> " + q2, FG, True), ("", FG, False), ("  krouter_ask(\"What is our Kubernetes autoscaling policy?\")", DIM, False),
         ("  → recall: none (no page covers enough of the question; do not guess)", WARN, False), ("", FG, False)]
add(frame("And when the vault does not know", ACC, base2), 1400)
add(frame("And when the vault does not know", ACC, base2 + [(ln, FG, False) for ln in wrap(a2, 70)]), 4500)

pal = [f.convert("P", palette=Image.ADAPTIVE, colors=32) for f in frames]
pal[0].save(OUT, save_all=True, append_images=pal[1:], duration=durations, loop=0, optimize=True, disposal=1)
print(len(frames), "frames")
