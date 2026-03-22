# Repository Guidelines

## Project Structure & Module Organization
`tools/extract/` contains the Python extraction pipeline that syncs Linux tags, scans docs and source, and builds the index. `tests/` holds `unittest` coverage for the extractor, document parsing, and generated sample data. `data/generated/` is committed output consumed by the site; `data/cache/`, `data/raw/`, and `data/state/` are local working directories and should not be committed. `site/` contains the Astro frontend, with pages under `site/src/pages/`, shared code in `site/src/lib/`, layouts in `site/src/layouts/`, and the staging script in `site/scripts/stage-data.mjs`.

## Build, Test, and Development Commands
Run commands from the repository root unless noted.

- `npm run sample`: build the small sample dataset and refresh `data/generated/`.
- `npm run build`: stage generated data into the site and produce the static build in `site/dist/`.
- `npm run dev`: start the Astro dev server with staged local data.
- `npm run check`: run Python unit tests plus `astro check`.
- `npm run extract:sync`: fetch and cache Linux release tags.
- `npm run extract:all`: run the full extraction pipeline across tags.

If `site/node_modules/` is missing, install frontend dependencies with `npm ci --prefix site`.

## Coding Style & Naming Conventions
Python uses 4-space indentation, type hints, and `snake_case` names for functions, files, and variables. Keep extractor modules focused and prefer small, pure helpers over inline branching. Astro, TypeScript, and CSS files use 2-space indentation and descriptive DOM ids/classes. Preserve the repository’s data naming scheme: generated parameter files are kebab-safe sysctl names such as `data/generated/params/vm.swappiness.json`.

## Testing Guidelines
Use `python3 -m unittest discover -s tests` for backend changes and `npm --prefix site run check` for frontend/type checks. Add tests beside the affected behavior in `tests/test_*.py`. When changing extraction logic, regenerate sample data with `npm run sample` and verify `data/generated/catalog.json` and `data/generated/versions.json` still match the expected sample set.

## Commit & Pull Request Guidelines
History is minimal, but the existing style uses short, imperative subjects (`Initial commit`). Follow that pattern and keep summaries concise. In pull requests, include:

- a brief description of behavior changes,
- the commands you ran to verify them,
- screenshots for `site/` UI changes,
- a note when committed `data/generated/` files were refreshed.
