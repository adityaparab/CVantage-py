# Contributing

## Setup

1. Install backend dependencies: `cd server && uv sync`
2. Install frontend dependencies: `cd frontend && pnpm install`
3. Install pre-commit hooks at repo root:
  - `pre-commit install`
  - `pre-commit install --hook-type commit-msg`

## Commit Workflow

- Hooks run on commit and block commits on failures.
- Run all hooks manually when needed:
  - `pre-commit run --all-files`

## Commit Messages

Commit messages are validated by commitizen on `commit-msg`.

Allowed format:

- `<type>(<scope>): <subject>`

Allowed types:

- `feat`, `fix`, `chore`, `docs`, `refactor`, `test`

Allowed scopes:

- `server`, `frontend`, `infra`, `docs`, `deps`

Examples:

- `feat(server): add health endpoints (#12)`
- `fix(frontend): handle refresh retry loop (#34)`
