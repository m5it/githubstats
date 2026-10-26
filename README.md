# GitHub Repository Preview

A small Python tool that fetches a preview of a GitHub repository from the
GitHub API, saves the response to a local JSON file every time it runs, and
keeps a daily log of repository values.

## Usage

1. Export your GitHub personal access token in your shell:

   ```bash
   export GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
   ```

2. Run the script:

   ```bash
   # Single repository preview + daily log
   python3 github_repo_preview.py owner/repo

   # All public repositories for a user
   python3 github_repo_preview.py username

   # All repositories for the authenticated user (public + private)
   python3 github_repo_preview.py me

   # Include owner-only traffic data (views/clones for the last 14 days)
   python3 github_repo_preview.py me --with-traffic

   # List and preview all saved daily logs
   python3 github_repo_preview.py --list-logs
   ```

## Output

- A concise repository preview is printed to the terminal.
- The full API response is saved under `github_data/` as
  `github_data/<owner>_<repo>_<timestamp>.json`.
- A daily log is saved under `logs/` as `logs/<owner>_<repo>_YYYY-MM-DD.json`.
  - The log contains the repository object and tracked values.
  - If you run the script again on the same day, the log is only overwritten
    when the tracked values change.

## Traffic data

Views and clones are only visible to the repository owner or users with push
access. For other repositories, the script still shows stars/forks but marks
traffic as not accessible.

## Requirements

- Python 3
- `requests`

Install the dependency with:

```bash
pip install requests
```
