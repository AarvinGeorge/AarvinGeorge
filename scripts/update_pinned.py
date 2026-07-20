#!/usr/bin/env python3
"""Sync the Featured Builds section of README.md with the user's live pinned repos.

Queries GitHub GraphQL for pinned repositories and rewrites the block between
<!-- PINNED:START --> and <!-- PINNED:END --> with styled repo cards
(github-readme-stats pin API, radical theme, matching the profile aesthetic).

Runs in GitHub Actions with the default GITHUB_TOKEN (read access to public
data is sufficient). Exits 0 always; the workflow commits only if the file changed.
"""
import json
import os
import re
import sys
import urllib.request

USERNAME = "AarvinGeorge"
README = os.path.join(os.path.dirname(__file__), "..", "README.md")
START = "<!-- PINNED:START -->"
END = "<!-- PINNED:END -->"
CARD = (
    "[![{name}](https://github-readme-stats.vercel.app/api/pin/"
    "?username={user}&repo={name}&theme=radical&hide_border=true)]({url})"
)

QUERY = """
query {
  user(login: "%s") {
    pinnedItems(first: 6, types: REPOSITORY) {
      nodes { ... on Repository { name url } }
    }
  }
}
""" % USERNAME


def fetch_pinned(token: str):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY}).encode(),
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if "errors" in data:
        raise RuntimeError(f"GraphQL errors: {data['errors']}")
    return data["data"]["user"]["pinnedItems"]["nodes"]


def main() -> int:
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print("::error::GITHUB_TOKEN not set")
        return 1

    pinned = fetch_pinned(token)
    if not pinned:
        # No pins set yet: leave the README untouched rather than emptying the section.
        print("No pinned repositories found; leaving README unchanged.")
        return 0

    cards = "\n".join(CARD.format(user=USERNAME, name=p["name"], url=p["url"]) for p in pinned)
    block = f"{START}\n{cards}\n{END}"

    with open(README, encoding="utf-8") as f:
        content = f.read()

    if START not in content or END not in content:
        print("::error::PINNED markers not found in README.md")
        return 1

    new_content = re.sub(
        re.escape(START) + r".*?" + re.escape(END), block, content, flags=re.DOTALL
    )

    if new_content != content:
        with open(README, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"README updated with {len(pinned)} pinned repo card(s).")
    else:
        print("README already up to date.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
