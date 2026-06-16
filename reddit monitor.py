#!/usr/bin/env python3
"""
Reddit keyword monitor for r/worldcup2026tickets.

Polls the subreddit's public JSON feed, checks new posts against a set of
keyword rules, and sends a push notification via ntfy.sh for any new match.
Designed to be run on a schedule (e.g. every 5 min via GitHub Actions).

State (which post IDs have already been seen) is stored in seen_posts.json
in the same directory, so re-runs don't re-alert on the same post.
"""

import json
import os
import sys
import urllib.error
import urllib.request

SUBREDDIT = "worldcup2026tickets"  # <-- double check this is the exact subreddit name
NTFY_TOPIC = "jack-wc26-fbf0f7c3"  # change this to anything you like, just keep it unique
SEEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seen_posts.json")
USER_AGENT = "reddit-keyword-monitor/1.0 (personal use script)"

# Each rule is a list of terms that must ALL appear (case-insensitive) in the
# post title or body for it to count as a match. Add/edit rules freely.
KEYWORD_RULES = [
    ["seattle"],
    ["egypt", "iran"],
    ["bosnia", "qatar"],
]


def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE) as f:
            return set(json.load(f))
    return set()


def save_seen(seen_ids):
    with open(SEEN_FILE, "w") as f:
        json.dump(sorted(seen_ids), f)


def fetch_new_posts(limit=50):
    url = f"https://www.reddit.com/r/{SUBREDDIT}/new.json?limit={limit}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.load(resp)
    return [child["data"] for child in data["data"]["children"]]


def matches_keywords(post):
    text = f"{post.get('title', '')} {post.get('selftext', '')}".lower()
    return any(all(term in text for term in rule) for rule in KEYWORD_RULES)


def send_ntfy_alert(post):
    title = post.get("title", "(no title)")
    permalink = "https://reddit.com" + post.get("permalink", "")
    message = f"{title}\n{permalink}"
    req = urllib.request.Request(
        f"https://ntfy.sh/{NTFY_TOPIC}",
        data=message.encode("utf-8"),
        headers={
            "Title": "World Cup 2026 ticket post match",
            "Click": permalink,
            "Priority": "high",
        },
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=10)
    except urllib.error.URLError as e:
        print(f"Failed to send ntfy alert: {e}", file=sys.stderr)


def main():
    seen = load_seen()
    first_run = len(seen) == 0

    try:
        posts = fetch_new_posts()
    except Exception as e:
        # Don't fail the whole run on a transient Reddit hiccup
        print(f"Error fetching posts: {e}", file=sys.stderr)
        sys.exit(0)

    new_matches = 0
    for post in posts:
        post_id = post.get("id")
        if post_id in seen:
            continue
        seen.add(post_id)
        if matches_keywords(post) and not first_run:
            send_ntfy_alert(post)
            new_matches += 1

    if first_run:
        print(f"First run: recorded {len(seen)} existing posts as seen, no alerts sent.")
    else:
        print(f"Checked {len(posts)} posts, {new_matches} new match(es), {len(seen)} total seen.")

    save_seen(seen)


if __name__ == "__main__":
    main()
