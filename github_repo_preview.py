#!/usr/bin/env python3
"""Retrieve and cache GitHub repository preview information with daily logs."""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests


GITHUB_API_URL = "https://api.github.com/repos/{owner}/{repo}"
GITHUB_USER_REPOS_URL = "https://api.github.com/users/{username}/repos"
GITHUB_TRAFFIC_VIEWS_URL = "https://api.github.com/repos/{owner}/{repo}/traffic/views"
GITHUB_TRAFFIC_CLONES_URL = "https://api.github.com/repos/{owner}/{repo}/traffic/clones"
DATA_DIR = Path("github_data")
LOGS_DIR = Path("logs")


def get_token() -> str:
    """Read the GitHub token from a bash/environment variable."""
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError(
            "GITHUB_TOKEN environment variable is not set. "
            "Export it in your shell before running this script, e.g.:\n"
            "export GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx"
        )
    return token


def api_headers(token: str) -> dict:
    """Return common GitHub API request headers."""
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def fetch_repo_info(owner: str, repo: str, token: str) -> dict:
    """Fetch repository information from the GitHub API."""
    url = GITHUB_API_URL.format(owner=owner, repo=repo)
    response = requests.get(url, headers=api_headers(token), timeout=30)
    response.raise_for_status()
    return response.json()


def fetch_traffic(owner: str, repo: str, token: str, endpoint: str) -> dict | None:
    """
    Fetch repository traffic data (views or clones) from the GitHub API.

    Returns None if the traffic endpoint is not accessible (e.g. the
    authenticated user is not the repository owner or lacks push access).
    """
    if endpoint == "views":
        url = GITHUB_TRAFFIC_VIEWS_URL.format(owner=owner, repo=repo)
    elif endpoint == "clones":
        url = GITHUB_TRAFFIC_CLONES_URL.format(owner=owner, repo=repo)
    else:
        raise ValueError("endpoint must be 'views' or 'clones'")

    response = requests.get(url, headers=api_headers(token), timeout=30)

    if response.status_code == 403:
        return None

    response.raise_for_status()
    return response.json()


def fetch_user_repos(username: str, token: str) -> list[dict]:
    """Fetch all public repositories for a GitHub user, handling pagination."""
    repos = []
    page = 1
    per_page = 100

    while True:
        url = GITHUB_USER_REPOS_URL.format(username=username)
        params = {"page": page, "per_page": per_page}

        response = requests.get(url, headers=api_headers(token), params=params, timeout=30)
        response.raise_for_status()
        page_repos = response.json()

        if not page_repos:
            break

        repos.extend(page_repos)
        page += 1

    return repos


def fetch_authenticated_user_repos(token: str) -> list[dict]:
    """Fetch all repositories for the authenticated user, including private ones."""
    repos = []
    page = 1
    per_page = 100

    while True:
        url = "https://api.github.com/user/repos"
        params = {"page": page, "per_page": per_page}

        response = requests.get(url, headers=api_headers(token), params=params, timeout=30)
        response.raise_for_status()
        page_repos = response.json()

        if not page_repos:
            break

        repos.extend(page_repos)
        page += 1

    return repos


def fetch_repo_with_traffic(owner: str, repo: str, token: str) -> dict:
    """
    Fetch repository info and, if accessible, traffic views/clones.

    Traffic data is only available to repository owners or users with push
    access. If the token does not have access, the traffic fields are set to
    None and a notice is included.
    """
    data = fetch_repo_info(owner, repo, token)

    views = fetch_traffic(owner, repo, token, "views")
    clones = fetch_traffic(owner, repo, token, "clones")

    data["_traffic"] = {
        "views_accessible": views is not None,
        "views": views,
        "clones_accessible": clones is not None,
        "clones": clones,
    }

    return data


def save_repo_info(owner: str, repo: str, data: dict) -> Path:
    """Save repository data to a timestamped JSON file."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"{owner}_{repo}_{timestamp}.json"
    filepath = DATA_DIR / filename

    record = {
        "owner": owner,
        "repo": repo,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }

    with filepath.open("w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)

    return filepath


def save_user_repos(username: str, repos: list[dict], with_traffic: bool = False) -> Path:
    """Save a list of a user's repositories to a timestamped JSON file."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"{username}_repos_{timestamp}.json"
    filepath = DATA_DIR / filename

    record = {
        "username": username,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "count": len(repos),
        "with_traffic": with_traffic,
        "repos": repos,
    }

    with filepath.open("w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)

    return filepath


# ---------------------------------------------------------------------------
# Daily logging helpers
# ---------------------------------------------------------------------------


def log_path(owner: str, repo: str, date: str | None = None) -> Path:
    """Return the daily log file path for a repository."""
    if date is None:
        date = datetime.now(timezone.utc).date().isoformat()
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    return LOGS_DIR / f"{owner}_{repo}_{date}.json"


def log_values(data: dict) -> dict:
    """Extract the values we track over time from a repository response."""
    traffic = data.get("_traffic", {})
    values = {
        "stars": data.get("stargazers_count"),
        "forks": data.get("forks_count"),
        "open_issues": data.get("open_issues_count"),
        "watchers": data.get("watchers_count"),
        "subscribers": data.get("subscribers_count"),
    }

    if traffic.get("views_accessible"):
        views = traffic.get("views", {})
        values["views_count"] = views.get("count")
        values["views_uniques"] = views.get("uniques")
    else:
        values["views_count"] = None
        values["views_uniques"] = None

    if traffic.get("clones_accessible"):
        clones = traffic.get("clones", {})
        values["clones_count"] = clones.get("count")
        values["clones_uniques"] = clones.get("uniques")
    else:
        values["clones_count"] = None
        values["clones_uniques"] = None

    return values


def build_log_record(owner: str, repo: str, data: dict) -> dict:
    """Build a daily log record for a repository."""
    return {
        "owner": owner,
        "repo": repo,
        "date": datetime.now(timezone.utc).date().isoformat(),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "values": log_values(data),
        "data": data,
    }


def values_changed(old_record: dict, new_record: dict) -> bool:
    """Compare tracked values between two log records."""
    old_values = old_record.get("values", {})
    new_values = new_record.get("values", {})
    return old_values != new_values


def save_daily_log(owner: str, repo: str, data: dict) -> tuple[Path, str]:
    """
    Save or update the daily log for a repository.

    Returns the log file path and a status string:
    - "created" if a new log was written
    - "updated" if the values changed and the log was overwritten
    - "unchanged" if the values are the same as the existing log
    """
    path = log_path(owner, repo)
    new_record = build_log_record(owner, repo, data)

    if path.exists():
        old_record = json.loads(path.read_text(encoding="utf-8"))
        if not values_changed(old_record, new_record):
            return path, "unchanged"

    with path.open("w", encoding="utf-8") as f:
        json.dump(new_record, f, indent=2)

    if path.exists() and "old_record" in dir():
        return path, "updated"
    return path, "created"


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------


def print_preview(data: dict) -> None:
    """Print a concise preview of the repository."""
    traffic = data.get("_traffic", {})

    print("Repository Preview")
    print("=" * 40)
    print(f"Name:        {data.get('full_name')}")
    print(f"Description: {data.get('description')}")
    print(f"URL:         {data.get('html_url')}")
    print(f"Stars:       {data.get('stargazers_count')}")
    print(f"Forks:       {data.get('forks_count')}")
    print(f"Open issues: {data.get('open_issues_count')}")
    print(f"Language:    {data.get('language')}")
    print(f"Created:     {data.get('created_at')}")
    print(f"Updated:     {data.get('updated_at')}")

    if traffic:
        print()
        print("Traffic (owner-only data)")
        print("-" * 40)

        if traffic.get("views_accessible"):
            views = traffic.get("views", {})
            print(f"Views (14d):     count={views.get('count')}, uniques={views.get('uniques')}")
        else:
            print("Views:           not accessible (token must have repo owner/push access)")

        if traffic.get("clones_accessible"):
            clones = traffic.get("clones", {})
            print(f"Clones (14d):    count={clones.get('count')}, uniques={clones.get('uniques')}")
        else:
            print("Clones:          not accessible (token must have repo owner/push access)")


def print_user_preview(username: str, repos: list[dict], include_traffic: bool = False, token: str | None = None) -> None:
    """Print a concise preview of all repositories for a user."""
    private_count = sum(1 for r in repos if r.get("private"))

    print(f"\nRepositories for user: {username}")
    print("=" * 60)
    print(f"Total repositories: {len(repos)} (public: {len(repos) - private_count}, private: {private_count})")
    print()

    for repo in sorted(repos, key=lambda r: r.get("name", "")):
        owner, name = repo.get("full_name", "/").split("/", 1)
        print(f"- {repo.get('full_name')} {'(private)' if repo.get('private') else ''}")
        print(f"  Description: {repo.get('description')}")
        print(f"  URL:         {repo.get('html_url')}")
        print(f"  Stars:       {repo.get('stargazers_count')}")
        print(f"  Forks:       {repo.get('forks_count')}")
        print(f"  Language:    {repo.get('language')}")

        if include_traffic and token:
            try:
                data = fetch_repo_with_traffic(owner, name, token)
                traffic = data.get("_traffic", {})
                if traffic.get("views_accessible"):
                    views = traffic.get("views", {})
                    print(f"  Views (14d): count={views.get('count')}, uniques={views.get('uniques')}")
                if traffic.get("clones_accessible"):
                    clones = traffic.get("clones", {})
                    print(f"  Clones (14d): count={clones.get('count')}, uniques={clones.get('uniques')}")
            except requests.exceptions.RequestException:
                print("  Traffic:     not available")

        print()


def list_log_files() -> list[Path]:
    """Return all repository daily log files sorted by name."""
    if not LOGS_DIR.exists():
        return []
    return sorted(LOGS_DIR.glob("*.json"))


def print_logs_preview() -> None:
    """Read all saved daily logs and print a preview for each one."""
    log_files = list_log_files()

    if not log_files:
        print("No daily log files found in 'logs/'.")
        return

    print(f"Found {len(log_files)} daily log file(s)")
    print("=" * 60)

    for path in log_files:
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            print(f"\nCould not read {path}: {exc}")
            continue

        data = record.get("data", {})
        date = record.get("date", "unknown")
        fetched_at = record.get("fetched_at", "unknown")

        print(f"\nLog file: {path.name}")
        print(f"Date:     {date}")
        print(f"Saved at: {fetched_at}")
        print_preview(data)


# ---------------------------------------------------------------------------
# Command-line parsing and main entry point
# ---------------------------------------------------------------------------


def print_help() -> None:
    """Print usage instructions and available options."""
    print("github_repo_preview.py - Fetch GitHub repository info and keep daily logs")
    print()
    print("Usage:")
    print("  python github_repo_preview.py <owner/repo>")
    print("  python github_repo_preview.py <username>")
    print("  python github_repo_preview.py me")
    print("  python github_repo_preview.py me --with-traffic")
    print("  python github_repo_preview.py --list-logs")
    print("  python github_repo_preview.py --help | -h")
    print()
    print("Examples:")
    print("  python github_repo_preview.py torvalds/linux")
    print("  python github_repo_preview.py m5it")
    print("  export GITHUB_TOKEN=ghp_xxx && python github_repo_preview.py me --with-traffic")
    print()
    print("Options:")
    print("  --with-traffic   Include owner-only traffic data (views/clones, 14 days)")
    print("  --list-logs      Read and preview all saved daily log files")
    print("  --help, -h       Show this help message")
    print()
    print("Environment:")
    print("  GITHUB_TOKEN     GitHub personal access token (required for API access)")
    print()
    print("Output:")
    print("  github_data/     Raw API responses with timestamps")
    print("  logs/            Daily per-repository JSON logs (updated only when values change)")


def parse_args(argv: list[str]) -> tuple[str | None, bool, bool, bool]:
    """
    Parse command-line arguments.

    Returns a tuple of (target, is_username, with_traffic, list_logs).
    - owner/repo format   -> specific repo
    - username only       -> all public repos for that user
    - me                  -> all repos for the authenticated user
    - --with-traffic      -> include views/clones for each repo (owner-only)
    - --list-logs         -> list and preview all saved daily logs
    """
    if len(argv) == 2 and argv[1] in ("--help", "-h"):
        print_help()
        sys.exit(0)

    if len(argv) < 2 or len(argv) > 3:
        print_help()
        sys.exit(1)

    if "--list-logs" in argv:
        return None, False, False, True

    target = argv[1]
    with_traffic = "--with-traffic" in argv

    if "/" in target:
        return target, False, with_traffic, False
    return target, True, with_traffic, False


def main() -> None:
    target, is_username, with_traffic, list_logs = parse_args(sys.argv)

    if list_logs:
        print_logs_preview()
        return

    token = get_token()

    if is_username:
        username = target

        if username == "me":
            print("Fetching all repositories for the authenticated user...")
            repos = fetch_authenticated_user_repos(token)
            username = "authenticated_user"
        else:
            print(f"Fetching all public repositories for {username}...")
            repos = fetch_user_repos(username, token)

        filepath = save_user_repos(username, repos, with_traffic=with_traffic)

        print(f"Saved list of {len(repos)} repositories to: {filepath}")

        for repo_info in sorted(repos, key=lambda r: r.get("name", "")):
            owner, name = repo_info.get("full_name", "/").split("/", 1)
            try:
                if with_traffic:
                    data = fetch_repo_with_traffic(owner, name, token)
                else:
                    data = repo_info.copy()
                    data["_traffic"] = {"views_accessible": False, "views": None, "clones_accessible": False, "clones": None}

                log_file, status = save_daily_log(owner, name, data)
                print(f"  Daily log for {owner}/{name}: {status} ({log_file.name})")
            except requests.exceptions.RequestException as exc:
                print(f"  Could not create log for {owner}/{name}: {exc}")

        print_user_preview(username, repos, include_traffic=with_traffic, token=token)
    else:
        owner, repo = target.split("/", 1)
        print(f"Fetching repository info for {owner}/{repo}...")

        data = fetch_repo_with_traffic(owner, repo, token)
        filepath = save_repo_info(owner, repo, data)
        log_file, status = save_daily_log(owner, repo, data)

        print(f"Data saved to: {filepath}")
        print(f"Daily log: {log_file.name} ({status})")
        print()
        print_preview(data)


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.RequestException as exc:
        print(f"Network error: {exc}", file=sys.stderr)
        sys.exit(1)
