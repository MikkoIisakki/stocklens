---
name: code-quality-tools
description: Static analysis, linting, formatting, type checking, security scanning, and complexity tools used in the pulse project. All gates enforced in CI. For engineer and devops use.
---

# Code Quality Tools

All tools run in CI. A PR cannot merge if any gate fails.

---

## Tool Stack

| Tool | Purpose | Config file | CI gate |
|---|---|---|---|
| `ruff` | Linting + formatting (replaces flake8, isort, pyupgrade) | `pyproject.toml` | ✓ fail on any violation |
| `mypy` | Static type checking | `pyproject.toml` | ✓ fail on type errors |
| `bandit` | Security vulnerability scanning | `pyproject.toml` | ✓ fail on HIGH/CRITICAL |
| `radon` | Cyclomatic complexity | `pyproject.toml` | ✓ fail if CC > 10 |
| `pytest-cov` | Test coverage | `pyproject.toml` | ✓ fail below 80% |
| `gitleaks` | Secret scanning in git history | `.gitleaks.toml` | ✓ fail on any secret |
| `trivy` | Docker image CVE scanning | inline in GHA | ✓ fail on CRITICAL/HIGH |
| `pip-audit` | Python dependency vulnerability check | inline in GHA | ✓ fail on known CVEs |
| `pip-licenses` | Dependency license compatibility check | inline in GHA | ✓ fail on GPL/AGPL/SSPL |

---

## `pyproject.toml` Configuration

```toml
[tool.ruff]
target-version = "py312"
line-length = 100
select = [
    "E",    # pycodestyle errors
    "W",    # pycodestyle warnings
    "F",    # pyflakes
    "I",    # isort
    "N",    # pep8-naming
    "UP",   # pyupgrade
    "B",    # flake8-bugbear
    "C4",   # flake8-comprehensions
    "SIM",  # flake8-simplify
    "RUF",  # ruff-specific rules
]
ignore = [
    "E501",  # line length handled by formatter
]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"

[tool.ruff.isort]
known-first-party = ["app"]

[tool.mypy]
python_version = "3.12"
strict = true
ignore_missing_imports = false
disallow_untyped_defs = true
disallow_any_generics = true
warn_return_any = true
warn_unused_ignores = true
plugins = ["pydantic.mypy"]

[tool.bandit]
skips = ["B101"]   # allow assert in tests
severity = "HIGH"
confidence = "HIGH"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "--cov=app --cov-report=term-missing --cov-fail-under=80"

[tool.coverage.run]
omit = ["tests/*", "*/migrations/*", "*/__init__.py"]

[tool.radon]
cc_min = "C"   # flag complexity class C (CC > 10) and above
```

---

## Running Tools Locally

```bash
# Format + lint
ruff format backend/
ruff check backend/ --fix

# Type check
mypy backend/app

# Security scan
bandit -r backend/app -ll   # only HIGH and above

# Complexity check
radon cc backend/app -n C   # show functions with CC > 10

# All tests with coverage
pytest tests/ -q

# Dependency vulnerabilities
pip-audit -r backend/requirements.txt

# Dependency license check
pip-licenses --order=license --fail-on="GNU General Public License v2 (GPLv2);GNU General Public License v3 (GPLv3);GNU Affero General Public License v3 (AGPLv3);Server Side Public License"

# Secret scan (requires gitleaks installed)
gitleaks detect --source .
```

---

## Cyclomatic Complexity Rules

Cyclomatic complexity (CC) measures the number of linearly independent paths through code.

| CC | Rating | Action |
|---|---|---|
| 1–5 | A — Simple | ✓ Acceptable |
| 6–10 | B — Moderate | ✓ Acceptable, consider simplifying |
| 11–15 | C — Complex | ✗ CI fails — must refactor before merge |
| 16–20 | D — Very complex | ✗ CI fails |
| 21+ | F — Untestable | ✗ CI fails |

**Common causes of high CC and their fixes**:

```python
# Bad — CC=8, nested conditions
def score_action(score, rsi, volume, trend):
    if score > 60:
        if rsi < 70:
            if volume > 2:
                return "strong_buy"
            else:
                return "buy"
        else:
            return "buy"
    elif score > 25:
        ...

# Good — extract early returns and lookup table
SCORE_THRESHOLDS = [(60, "strong_buy"), (25, "buy"), (-25, "hold"), (-60, "sell")]

def score_to_action(score: float) -> str:
    for threshold, action in SCORE_THRESHOLDS:
        if score >= threshold:
            return action
    return "strong_sell"
```

---

## Type Checking Standards

All code must pass `mypy --strict`. No `# type: ignore` without a documented reason.

```python
# Bad — untyped
def compute_score(signals):
    total = 0
    for s in signals:
        total += s["value"]
    return total

# Good — fully typed
def compute_score(signals: list[Signal]) -> float:
    return sum(s.value or 0.0 for s in signals if s.signal_type != "unavailable")
```

Pydantic models count as typed — no additional annotations needed on model fields.

For `asyncpg` records (which are dynamically typed), type the return of repository functions explicitly:

```python
async def get_asset(conn: asyncpg.Connection, symbol: str) -> Asset | None:
    row: asyncpg.Record | None = await conn.fetchrow(...)
    return Asset(**dict(row)) if row else None
```

---

## Security Scanning

`bandit` flags common Python security issues. Know the common ones:

| Bandit ID | Issue | Our stance |
|---|---|---|
| B101 | `assert` used (skipped in tests) | Allowed in tests only |
| B105/106 | Hardcoded password | Always fix — move to env |
| B201 | Flask debug mode on | Not applicable |
| B301 | Pickle usage | Fix — use JSON |
| B310 | URL with user-supplied scheme | Fix — validate scheme |
| B608 | SQL injection via string formatting | Fix — always use `$1` params |

SQL injection is the most critical for this project — asyncpg parameterized queries prevent it by default. Never use f-strings to build SQL:

```python
# CRITICAL vulnerability — never do this
await conn.execute(f"SELECT * FROM asset WHERE symbol = '{symbol}'")

# Correct — parameterized
await conn.execute("SELECT * FROM asset WHERE symbol = $1", symbol)
```

---

## CI Quality Gate Workflow

```yaml
# .github/workflows/ci.yml — quality gates section
- name: Format check
  run: ruff format backend/ --check

- name: Lint
  run: ruff check backend/

- name: Type check
  run: mypy backend/app

- name: Security scan
  run: bandit -r backend/app -ll --exit-zero-on-skips

- name: Complexity check
  run: radon cc backend/app -n C --show-complexity

- name: Tests + coverage
  run: pytest tests/ -q
  env:
    DATABASE_URL: postgresql://stocks:test@localhost:5432/stocks_test

- name: Dependency audit
  run: pip-audit -r backend/requirements.txt

- name: License audit
  run: |
    pip install pip-licenses
    pip-licenses --order=license --fail-on="GNU General Public License v2 (GPLv2);GNU General Public License v3 (GPLv3);GNU Affero General Public License v3 (AGPLv3);Server Side Public License"

- name: Secret scan
  uses: gitleaks/gitleaks-action@v2
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

All gates must pass. No `--exit-zero` suppression to hide failures.

---

## Pre-commit Hooks (local)

Install pre-commit to catch issues before they reach CI:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.4.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.9.0
    hooks:
      - id: mypy
        additional_dependencies: [pydantic, asyncpg-stubs]

  - repo: https://github.com/PyCQA/bandit
    rev: 1.7.8
    hooks:
      - id: bandit
        args: [-ll, -r, backend/app]

  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.2
    hooks:
      - id: gitleaks
```

```bash
# Install
pip install pre-commit
pre-commit install

# Run manually on all files
pre-commit run --all-files
```
