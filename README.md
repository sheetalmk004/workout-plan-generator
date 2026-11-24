# 🏋️ Workout Plan Generator

A single-page **Streamlit** app that asks the questions a personal trainer would ask, then uses an LLM through the **Groq API** to write a personalised, day-by-day weekly workout plan that respects your equipment, schedule and injuries.

> Submission for **AI Engineering Cohort – Assignment 1 (codebasics.io)**.
> 👉 New to all of this? Follow the **[Step-by-step guide](docs/STEP_BY_STEP_GUIDE.md)**. It assumes you've never done any of it before.

---

## ✨ Features

| Requirement | How it's met |
|---|---|
| Structured inputs | Dropdowns for **goal** and **experience**, a **days/week slider**, an **equipment multiselect**, a **session-length** slider and an optional **injuries/limitations** text box |
| Generate Plan button | Sends the inputs to Groq and renders a **Weekly Overview** table, then **Day 1…Day N** sections with *Exercise / Sets / Reps / Rest / Notes* tables |
| Typed Python function | `generate_workout_plan(goal: str, experience: str, days_per_week: int, equipment: list[str], limitations: str = "", ...) -> PlanResult` in [`planner.py`](planner.py). It builds the prompt, calls Groq inside `try/except`, and returns the plan |
| Invalid input handling | 0 days, a missing goal, no equipment and similar problems show friendly warnings, and the API is never called |
| API failure handling | A bad key, rate limit, network error, timeout or retired model each maps to a plain-English message (no tracebacks) |
| Empty / malformed response | Empty replies, `<think>` tags and stray code fences are cleaned. A reply with no `Day N` sections or tables gets a friendly fallback message |
| Prompt design | A rule-based system prompt, a constraint-first user prompt, an output format contract **and** a code guardrail that checks the plan and asks the model to repair it once if it ignored a constraint (see [Prompt design notes](docs/PROMPT_DESIGN.md)) |
| Disclaimer | Added automatically whenever an injury or limitation is entered, even if the model forgets it |

**Stretch goals (all done):** 🔄 Regenerate (a different variation) · 💾 plan saved in `st.session_state` · ⬇️ download as `.md` or `.txt` · 🔁 "Swap this exercise" for one exercise at a time.

---

## 🚀 Quick start

```bash
git clone https://github.com/<your-username>/workout-plan-generator.git
cd workout-plan-generator
python -m venv .venv
# Windows: .venv\Scripts\activate     macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then paste your Groq key into .env
streamlit run app.py
```

Get a free API key at <https://console.groq.com/keys>. You can also paste the key into the app's sidebar instead of using `.env`.

**Model:** defaults to `openai/gpt-oss-120b`. Groq retired `llama-3.3-70b-versatile` in August 2026 and recommends this model as its replacement. You can change models in the sidebar or with the `GROQ_MODEL` environment variable.

## 🧪 Tests

```bash
pip install -r requirements-dev.txt
pytest -q
```

The 32 unit tests use a fake Groq client, so they need no key or network. They cover validation, the contents of the prompt, empty and malformed responses, each kind of API failure, the constraint guardrail, exercise swapping and export.

## 📁 Project structure

```
workout-plan-generator/
├── app.py                  # Streamlit UI (inputs, buttons, results, stretch goals)
├── planner.py              # Logic: validation, prompts, Groq call, guardrails
├── tests/test_planner.py   # Unit tests (no API key needed)
├── docs/
│   ├── STEP_BY_STEP_GUIDE.md   # First-timer walkthrough: setup → run → GitHub → submit
│   └── PROMPT_DESIGN.md        # Prompt design decisions + test matrix
├── requirements.txt
├── requirements-dev.txt
├── .env.example            # Template. Copy it to .env (git-ignored)
└── .streamlit/secrets.toml.example
```

## ⚠️ Disclaimer

This app produces general fitness information, **not medical advice**. Consult a qualified professional before starting a new exercise programme, especially if you have an injury or a medical condition.
