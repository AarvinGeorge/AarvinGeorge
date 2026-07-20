#!/usr/bin/env python3
"""Sync the Featured Builds section of README.md with the user's live pinned repos.

v2: self-hosted cards. Instead of hotlinking github-readme-stats (rate-limited,
renders broken images), this script fetches pinned repo metadata via GitHub
GraphQL and generates local SVG cards in the radical theme, committed to
assets/cards/. The README block between <!-- PINNED:START --> and
<!-- PINNED:END --> references those local SVGs, so rendering never depends on
an external image service.

Runs in GitHub Actions with the default GITHUB_TOKEN. Exits non-zero only on
hard errors; the workflow commits only if files changed.
"""
import html
import json
import os
import re
import sys
import urllib.request

USERNAME = "AarvinGeorge"
ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
README = os.path.join(ROOT, "README.md")
CARDS_DIR = os.path.join(ROOT, "assets", "cards")
START = "<!-- PINNED:START -->"
END = "<!-- PINNED:END -->"

# radical theme (matches the stats cards)
BG = "#141321"
TITLE = "#fe428e"
TEXT = "#a9fef7"
ACCENT = "#f8d847"

LANG_COLORS = {
    "Python": "#3572A5", "TypeScript": "#3178c6", "JavaScript": "#f1e05a",
    "Jupyter Notebook": "#DA5B0B", "HTML": "#e34c26", "CSS": "#563d7c",
    "Java": "#b07219", "Shell": "#89e051", "Dockerfile": "#384d54",
    "Go": "#00ADD8", "Rust": "#dea584", "C++": "#f34b7d",
}

QUERY = """
query {
  user(login: "%s") {
    pinnedItems(first: 6, types: REPOSITORY) {
      nodes {
        ... on Repository {
          name url description stargazerCount
          primaryLanguage { name color }
        }
      }
    }
  }
}
""" % USERNAME


def fetch_pinned(token: str):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if "errors" in data:
        raise RuntimeError(f"GraphQL errors: {data['errors']}")
    return data["data"]["user"]["pinnedItems"]["nodes"]


def wrap(text: str, width: int = 54, max_lines: int = 2):
    words = (text or "").split()
    lines, cur = [], ""
    for w in words:
        if len(cur) + len(w) + 1 <= width:
            cur = f"{cur} {w}".strip()
        else:
            lines.append(cur)
            cur = w
            if len(lines) == max_lines:
                break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    if len(lines) == max_lines and len(" ".join(words)) > sum(len(l) for l in lines) + max_lines:
        lines[-1] = lines[-1][: width - 1].rstrip() + "…"
    return lines


def card_svg(repo: dict) -> str:
    name = repo["name"]
    desc_lines = wrap(repo.get("description") or "")
    stars = repo.get("stargazerCount") or 0
    lang = (repo.get("primaryLanguage") or {}) or {}
    lang_name = lang.get("name") or ""
    lang_color = lang.get("color") or LANG_COLORS.get(lang_name, "#8b8b8b")

    desc_svg = ""
    for i, line in enumerate(desc_lines):
        desc_svg += (
            f'<text x="20" y="{58 + i * 17}" font-size="12" fill="{TEXT}" '
            f'font-family="Segoe UI, Ubuntu, sans-serif">{html.escape(line)}</text>'
        )

    footer, fx = "", 20
    if lang_name:
        footer += f'<circle cx="{fx + 5}" cy="109" r="5" fill="{lang_color}"/>'
        footer += (
            f'<text x="{fx + 16}" y="113" font-size="12" fill="{TEXT}" '
            f'font-family="Segoe UI, Ubuntu, sans-serif">{html.escape(lang_name)}</text>'
        )
        fx += 16 + 8 * len(lang_name) + 24
    footer += (
        f'<path transform="translate({fx},101) scale(0.85)" fill="{ACCENT}" '
        'd="M8 .25a.75.75 0 0 1 .673.418l1.882 3.815 4.21.612a.75.75 0 0 1 .416 1.279l-3.046 2.97.719 4.192a.75.75 0 0 1-1.088.791L8 12.347l-3.766 1.98a.75.75 0 0 1-1.088-.79l.72-4.194L.818 6.374a.75.75 0 0 1 .416-1.28l4.21-.611L7.327.668A.75.75 0 0 1 8 .25Z"/>'
        f'<text x="{fx + 18}" y="113" font-size="12" fill="{TEXT}" '
        f'font-family="Segoe UI, Ubuntu, sans-serif">{stars}</text>'
    )

    return f'''<svg width="400" height="130" viewBox="0 0 400 130" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{html.escape(name)}">
<rect x="0.5" y="0.5" width="399" height="129" rx="10" fill="{BG}"/>
<path transform="translate(20,20) scale(1.1)" fill="{TITLE}" d="M2 2.5A2.5 2.5 0 0 1 4.5 0h8.75a.75.75 0 0 1 .75.75v12.5a.75.75 0 0 1-.75.75h-2.5a.75.75 0 0 1 0-1.5h1.75v-2h-8a1 1 0 0 0-.714 1.7.75.75 0 1 1-1.072 1.05A2.495 2.495 0 0 1 2 11.5Zm10.5-1h-8a1 1 0 0 0-1 1v6.708A2.486 2.486 0 0 1 4.5 9h8ZM5 12.25a.25.25 0 0 1 .25-.25h3.5a.25.25 0 0 1 .25.25v3.25a.25.25 0 0 1-.4.2l-1.45-1.087a.249.249 0 0 0-.3 0L5.4 15.7a.25.25 0 0 1-.4-.2Z"/>
<text x="45" y="33" font-size="{16 if len(name) <= 30 else (14 if len(name) <= 36 else 12)}" font-weight="600" fill="{TITLE}" font-family="Segoe UI, Ubuntu, sans-serif">{html.escape(name)}</text>
{desc_svg}
{footer}
</svg>'''


def build_block(pinned: list) -> str:
    lines = [START]
    for i in range(0, len(pinned), 2):
        pair = pinned[i:i + 2]
        row = ['<p align="center">']
        for p in pair:
            row.append(
                f'  <a href="{p["url"]}"><img src="assets/cards/{p["name"]}.svg" '
                f'width="400" alt="{html.escape(p["name"])}"/></a>'
            )
        row.append("</p>")
        lines.append("\n".join(row))
    lines.append(END)
    return "\n".join(lines)


def write_outputs(pinned: list) -> None:
    os.makedirs(CARDS_DIR, exist_ok=True)
    # Remove stale cards so unpinned repos disappear
    for f in os.listdir(CARDS_DIR):
        if f.endswith(".svg") and f[:-4] not in {p["name"] for p in pinned}:
            os.remove(os.path.join(CARDS_DIR, f))
    for p in pinned:
        with open(os.path.join(CARDS_DIR, f'{p["name"]}.svg'), "w", encoding="utf-8") as f:
            f.write(card_svg(p))

    with open(README, encoding="utf-8") as f:
        content = f.read()
    if START not in content or END not in content:
        raise RuntimeError("PINNED markers not found in README.md")
    new_content = re.sub(
        re.escape(START) + r".*?" + re.escape(END), build_block(pinned), content, flags=re.DOTALL
    )
    if new_content != content:
        with open(README, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"README + {len(pinned)} card(s) updated.")
    else:
        print("README already up to date; cards refreshed.")


def main() -> int:
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print("::error::GITHUB_TOKEN not set")
        return 1
    pinned = fetch_pinned(token)
    if not pinned:
        print("No pinned repositories found; leaving README unchanged.")
        return 0
    write_outputs(pinned)
    return 0


if __name__ == "__main__":
    sys.exit(main())
