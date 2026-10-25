# Contributing to TraceNest

Thank you for your interest in contributing to **TraceNest**! We welcome contributions that align with our core principles of correctness, privacy, and deterministic analysis.

---

## Development Setup

### Prerequisites

- Python 3.12 or newer
- Git 2.30 or newer

### Local Installation

Clone the repository and set up editable installation with dev dependencies:

```bash
git clone https://github.com/tracenest/tracenest.git
cd tracenest

# Install development dependencies
pip install -e ".[dev]"
```

---

## Code Quality Standards

Before submitting a pull request, ensure your code passes all linting, formatting, type checking, and automated tests.

### Running Tests

```bash
pytest
```

To run with coverage reporting:

```bash
pytest --cov=tracenest --cov-report=term-missing
```

### Running Linter and Formatter

We use [Ruff](https://github.com/astral-sh/ruff) for linting and formatting:

```bash
ruff check .
ruff format --check .
```

To automatically apply formatting and fixes:

```bash
ruff format .
ruff check --fix .
```

### Type Checking

We use [Mypy](https://mypy-lang.org/) for static type verification:

```bash
mypy src
```

---

## Pull Request Guidelines

1. **Branch Naming:** Use clear branch names such as `feat/secret-rule-enhancement` or `fix/windows-path-traversal`.
2. **Testing Required:** All new features or bug fixes must include corresponding unit and/or integration tests.
3. **Deterministic First:** Do not introduce reliance on remote AI APIs for core functionality.
4. **No Premature Dependencies:** Keep runtime dependencies strictly minimal.
5. **Documentation:** Update README and docs when introducing new configuration options or CLI commands.
