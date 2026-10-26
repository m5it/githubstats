# GitHub Repository Preview

A small Python tool that fetches a preview of a GitHub repository from the
GitHub API and saves the response to a local JSON file every time it runs.

## Usage

1. Export your GitHub personal access token in your shell:

   ```bash
   export GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
   ```

2. Run the script with the repository in `owner/repo` format:

   ```bash
   python3 github_repo_preview.py owner/repo
   ```

   Example:

   ```bash
   python3 github_repo_preview.py torvalds/linux
   ```

## Output

- A concise repository preview is printed to the terminal.
- The full API response is saved under `github_data/` as
  `github_data/<owner>_<repo>_<timestamp>.json`.

## Requirements

- Python 3
- `requests`

Install the dependency with:

```bash
pip install requests
```
