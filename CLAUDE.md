# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

Hackathon (AI20K, Track A) submission repo for team ComAoGaoTien. Topic A3: AI-assisted lesson production — generate multiple-choice quizzes (PDF) and narrated slide scripts from source material, with two human review gates and per-item source-segment checking (`KHOP_NGUON` / `SAI_NGUON` / `THIEU_NGUON`). The design lives in `spec.md` §4; the working prototype is the "slice" it describes. Most files are Vietnamese-language docs/templates graded by the organizers (see README "Bảy hạng mục bắt buộc").

`AGENTS.md` holds the binding rules for coding agents — read it. Key points: never commit `.env`/keys/raw BTC data; do not edit finished `eval/run-*.csv`, `cost/simulate-*.csv`, `traces/*` (except the `pass` and `ghi_chu` columns); do not change `spec.md` §7 or `eval/metric_spec.yaml` after CP2; never delete failing benchmark cases or edit `expected` to match output; no fabricated interviews/quotes/numbers (mark unsourced numbers *(tự ước tính)*); tools with outward effects only produce drafts awaiting human approval; no code that hard-codes benchmark inputs.

## Commands

Python 3.10+, standard library only (add any extra dependency to `requirements.txt`). On Windows use `python` or `py`; a `.venv/` exists locally (gitignored).

```
python run.py                       # run prototype (codebase/app.py)
python run.py check                 # validate eval/benchmark.csv, eval/metric_spec.yaml, TEAMS.md (warn only)
python run.py eval --try [N]        # smoke-test first N (default 3) cases -> eval/run-try.csv (not counted)
python run.py eval                  # full benchmark -> eval/run-N.csv + traces/run-N.jsonl
python run.py eval --fake           # exercise the runner without calling agent
python run.py score eval/run-N.csv  # % pass after filling the `pass` column (1/0)
python run.py simulate --try [N]    # cost simulation, N sessions (default 10)
python run.py simulate              # >=50 sessions per cost/personas.yaml -> cost/simulate-N.csv + summary
```

Add `--wait 4` to `eval`/`simulate` for rate-limited free tiers. There is no test suite or linter; `check` and `eval` are the verification path. Runs with the fake model are never numbered (`run-mock.csv`, `run-error.csv`, `run-stopped.csv`, `run-try.csv`, `run-fake.csv` are gitignored); numbered `run-N.csv`, `simulate-N.csv`, `traces/run-N.jsonl` MUST be committed.

## Architecture

Everything flows through one contract: `codebase/agent.py::answer(text) -> {"output": str}`. `run.py` is only a dispatcher that spawns subprocesses (`codebase/app.py`, `eval/run_eval.py`, `cost/simulate.py`); `run_app()` can be replaced if the team switches stack, but `answer()` must stay so `eval` and `simulate` keep working.

- **Team-owned (edit):** `codebase/agent.py` (flow), `codebase/ai.py` (`call_model(system, user)` — the ONLY place that calls a model; must return `text`, `model`, `tokens_in`, `tokens_out` with tokens from the API `usage`, not estimated; keep `@model_call`), `codebase/tools.py` (one `@tool` function per tool; docstring = name · input · output · outward effect).
- **Framework (do not edit):** `codebase/tracing.py`, `eval/run_eval.py`, `cost/simulate.py`, `run.py`. `@model_call` / `@tool` decorators record every call (tokens, latency, errors) into per-case traces; this is how `eval` fills token/call-count columns and `simulate` derives cost from measured tokens. Agent loops must cap steps (`MAX_STEPS`) and log stop reason with `note("dừng: …")`.
- `ai.py` runs in **fake mode** unless `.env` sets `MODEL_PROVIDER` (copy `.env.example`; keys: `MODEL_PROVIDER`, `MODEL_NAME`, `API_KEY`). The real-model branch in `call_model` is currently an unimplemented `NotImplementedError` — see `docs/connect-model.md`. `agent.py` and `tools.py` still contain the starter example (`search_example`, empty `SYSTEM`), not yet the A3 flow from `spec.md` §4 (`search_sources`, `get_segment`, `export_quiz_pdf`, `render_slides`, `synthesize_voice`).
- `eval` sends the raw `input` cell of each `eval/benchmark.csv` row to `answer()`; background data goes in `data/` (described in `data/DATA_CARD.md`) and is read through tools.
- Evaluation spec: `eval/benchmark.csv` (needs ≥1/3 cases from real users/data, plus `kho` and `tu_choi` types) and `eval/metric_spec.yaml` (≥3 metrics); `pass` is graded by hand against the metric spec. Cost inputs: `cost/personas.yaml`, `cost/cost-estimate.md`.

## Docs map

`spec.md` (design, §7 "đạt" standard), `canvas.md`, `evidence/` (hypothesis, survey, interviews, summary), `TEAMS.md` (strict format — organizers scan it per person), `docs/ai-usage.md` (AI-use disclosure), `reflection/`, `slides/outline.md`, `validation/log.md`. Deadlines are in the `spec.md` header (CP2 §7 lock 27/11 19:30; CP3 10:00 28/11; CP4 14:30 28/11).
