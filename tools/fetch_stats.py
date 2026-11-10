"""Fetch GitHub stats into cache/ (stats.json for the card, calendar.json for the board). Needs GITHUB_TOKEN.
Lines of code are cached per repo by head commit, so an unchanged repo is never walked twice."""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "cache"
LOGIN = os.environ.get("GH_LOGIN", "Abdulraqib20")
TOKEN = os.environ.get("GITHUB_TOKEN")
BULK = 5000  # a commit touching more lines than this is a data dump or lockfile, not authored code

session = requests.Session()


def gql(document: str, **variables) -> dict:
    for attempt in range(4):
        resp = session.post(
            "https://api.github.com/graphql",
            json={"query": document, "variables": variables},
            headers={"Authorization": f"bearer {TOKEN}"},
            timeout=60,
        )
        if resp.status_code in (403, 429, 502) and attempt < 3:
            wait = int(resp.headers.get("Retry-After", 30))
            print(f"  {resp.status_code}, retrying in {wait}s", file=sys.stderr)
            time.sleep(wait)
            continue
        resp.raise_for_status()
        body = resp.json()
        if "errors" in body:
            raise SystemExit(f"GraphQL error: {json.dumps(body['errors'], indent=2)}")
        return body["data"]
    raise SystemExit("gave up after repeated rate limits")


REPOS = """
query($login:String!, $after:String) {
  user(login:$login) {
    id createdAt
    followers { totalCount }
    repositoriesContributedTo(first:1, contributionTypes:[COMMIT, PULL_REQUEST, REPOSITORY]) { totalCount }
    repositories(ownerAffiliations:OWNER, isFork:false, first:100, after:$after) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes { nameWithOwner stargazerCount defaultBranchRef { target { ... on Commit { oid } } } }
    }
  }
}"""

YEAR = """
query($login:String!, $from:DateTime!, $to:DateTime!) {
  user(login:$login) {
    contributionsCollection(from:$from, to:$to) { totalCommitContributions restrictedContributionsCount }
  }
}"""

HISTORY = """
query($owner:String!, $name:String!, $author:ID!, $after:String) {
  repository(owner:$owner, name:$name) {
    defaultBranchRef { target { ... on Commit {
      history(first:100, after:$after, author:{id:$author}) {
        pageInfo { hasNextPage endCursor }
        nodes { additions deletions }
      }
    } } }
  }
}"""

CALENDAR = """
query($login:String!) {
  user(login:$login) {
    contributionsCollection { contributionCalendar {
      totalContributions
      weeks { contributionDays { date weekday contributionCount contributionLevel } }
    } }
  }
}"""

LEVELS = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2, "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}


def iso(d: datetime) -> str:
    return d.isoformat().replace("+00:00", "Z")


def fetch_user() -> tuple[dict, list[dict]]:
    repos, after, user = [], None, None
    while True:
        data = gql(REPOS, login=LOGIN, after=after)["user"]
        user = user or data
        repos += data["repositories"]["nodes"]
        page = data["repositories"]["pageInfo"]
        if not page["hasNextPage"]:
            return user, repos
        after = page["endCursor"]


def count_commits(created_at: str) -> int:
    """contributionsCollection spans at most a year, so walk one year at a time."""
    cursor = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    now, total = datetime.now(timezone.utc), 0
    while cursor < now:
        end = min(cursor.replace(year=cursor.year + 1, day=min(cursor.day, 28)), now)
        c = gql(YEAR, login=LOGIN, **{"from": iso(cursor), "to": iso(end)})["user"]["contributionsCollection"]
        total += c["totalCommitContributions"] + c["restrictedContributionsCount"]
        cursor = end
    return total


def count_loc(repos: list[dict], author: str) -> tuple[int, int]:
    path = CACHE / "loc.json"
    cache = json.loads(path.read_text()) if path.exists() else {}
    added = deleted = 0
    for repo in repos:
        head = ((repo.get("defaultBranchRef") or {}).get("target") or {}).get("oid")
        if not head:
            continue
        name = repo["nameWithOwner"]
        if cache.get(name, {}).get("oid") != head or cache[name].get("bulk") != BULK:
            owner, short = name.split("/", 1)
            a = d = 0
            after = None
            while True:
                hist = gql(HISTORY, owner=owner, name=short, author=author, after=after)
                hist = hist["repository"]["defaultBranchRef"]["target"]["history"]
                authored = [n for n in hist["nodes"] if n["additions"] + n["deletions"] <= BULK]
                a += sum(n["additions"] for n in authored)
                d += sum(n["deletions"] for n in authored)
                if not hist["pageInfo"]["hasNextPage"]:
                    break
                after = hist["pageInfo"]["endCursor"]
            cache[name] = {"oid": head, "bulk": BULK, "added": a, "deleted": d}
            print(f"  walked {name}: +{a:,} -{d:,}")
        added += cache[name]["added"]
        deleted += cache[name]["deleted"]
    path.write_text(json.dumps(cache, indent=1, sort_keys=True) + "\n")
    return added, deleted


def fetch_calendar() -> dict:
    cal = gql(CALENDAR, login=LOGIN)["user"]["contributionsCollection"]["contributionCalendar"]
    weeks = []
    for week in cal["weeks"]:
        slots: list[dict | None] = [None] * 7  # index = weekday, 0 is Sunday
        for day in week["contributionDays"]:
            slots[day["weekday"]] = {"date": day["date"], "count": day["contributionCount"],
                                     "level": LEVELS[day["contributionLevel"]]}
        weeks.append(slots)
    return {"total": cal["totalContributions"], "weeks": weeks}


def main() -> None:
    if not TOKEN:
        raise SystemExit("GITHUB_TOKEN is not set")
    CACHE.mkdir(exist_ok=True)
    user, repos = fetch_user()
    added, deleted = count_loc(repos, user["id"])
    stats = {
        "repos": user["repositories"]["totalCount"],
        "contributed": user["repositoriesContributedTo"]["totalCount"],
        "stars": sum(r["stargazerCount"] for r in repos),
        "commits": count_commits(user["createdAt"]),
        "followers": user["followers"]["totalCount"],
        "loc": added - deleted,
        "added": added,
        "deleted": deleted,
        "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    (CACHE / "stats.json").write_text(json.dumps(stats, indent=2) + "\n")
    print(json.dumps(stats, indent=2))
    calendar = fetch_calendar()
    (CACHE / "calendar.json").write_text(json.dumps(calendar) + "\n")
    print(f"calendar: {len(calendar['weeks'])} weeks, {calendar['total']} contributions")


if __name__ == "__main__":
    main()
