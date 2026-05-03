# GitHub Publication Checklist

This checklist is for publishing the repository as a standalone project. It is
not a production deployment checklist.

## 1. Pre-Push Checks

Run from the project root:

```powershell
git status --short
.crypto\Scripts\python.exe manage.py check
.crypto\Scripts\python.exe -m ruff check .
.crypto\Scripts\python.exe -m ruff format --check .
.crypto\Scripts\python.exe manage.py test
```

Expected result:

- `git status --short` is clean before push;
- Django system check reports no issues;
- Ruff check passes;
- Ruff format check reports all files already formatted;
- Django test runner passes.

## 2. Files That Must Be Public

These files and directories should be committed and visible:

- `README.md`;
- `requirements.txt`;
- `pyproject.toml`;
- `.env.example`;
- `Dockerfile`;
- `docker-compose.yml`;
- `.dockerignore`;
- `.github/workflows/ci.yml`;
- `docs/`;
- `data/samples/`;
- `docs/assets/screenshots/`;
- `docs/assets/eda/`;
- `tests/`;
- Django apps and `mlcore/` source code.

## 3. Files That Must Stay Private / Ignored

These files and directories must remain local or ignored:

- `.env`;
- `db.sqlite3`;
- `.crypto/`;
- `.venv/`;
- `local_notes/`;
- Docker volumes and container runtime state;
- generated `media/` artifacts:
  - `media/datasets/raw/`;
  - `media/datasets/processed/`;
  - `media/datasets/final/`;
  - `media/models/`;
  - `media/reports/`;
- temporary run/check directories:
  - `tmp_*/`;
  - `tmp_artifacts*/`;
  - `tmp_dataset_repo_check*/`;
- manual local CSV files such as `manual_upload_test.csv`.

Useful checks:

```powershell
git check-ignore -v .env
git check-ignore -v local_notes\project_change_journal.md
git status --short
```

## 4. GitHub Page Review

After pushing, open the repository page and verify:

- README renders correctly;
- screenshots render;
- Mermaid architecture diagram renders;
- documentation links work;
- sample dataset and EDA links work;
- CI workflow appears under GitHub Actions;
- CI starts on the push;
- there are no broken image links.

## 5. No Misleading Claims

Before publishing, verify public docs:

- do not describe the project as a trading bot;
- do not claim profitability;
- do not imply financial advice;
- keep limitations visible;
- clearly label the committed sample dataset as synthetic;
- describe metrics as research signals and pipeline checks, not trading
  performance guarantees.

Run the standard public wording search used in the project verification steps.
Expected result: no matches.

## 6. Optional After Push

Optional repository polish:

- add a concise repository description;
- add topics:
  - `django`;
  - `machine-learning`;
  - `catboost`;
  - `fintech`;
  - `time-series`;
  - `ml-pipeline`;
- verify whether a GitHub Actions badge is useful after the repository URL is
  known;
- pin or highlight the sample dataset and release readiness docs if the GitHub
  project page needs clearer navigation.
