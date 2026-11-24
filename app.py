"""Streamlit UI for the Workout Plan Generator.

Run with:  streamlit run app.py
"""

from __future__ import annotations

import os
from datetime import date

import streamlit as st
from dotenv import load_dotenv

from planner import (
    DEFAULT_MODEL,
    EQUIPMENT_OPTIONS,
    EXPERIENCE_LEVELS,
    FALLBACK_MODELS,
    GOALS,
    MAX_LIMITATIONS_CHARS,
    SESSION_LENGTHS,
    PlanGenerationError,
    WorkoutRequest,
    exercise_name,
    generate_workout_plan,
    list_exercises,
    normalize_equipment,
    swap_exercise,
    to_plain_text,
    validate_inputs,
)

load_dotenv()  # reads GROQ_API_KEY from a local .env file if present

st.set_page_config(page_title="Workout Plan Generator", page_icon="🏋️", layout="wide")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def get_api_key(sidebar_key: str) -> str:
    """Sidebar input > Streamlit secrets > environment variable / .env."""
    if sidebar_key.strip():
        return sidebar_key.strip()
    try:
        secret = st.secrets.get("GROQ_API_KEY", "")
    except Exception:  # no secrets.toml file — that's fine
        secret = ""
    return (secret or os.getenv("GROQ_API_KEY", "")).strip()


def init_state() -> None:
    defaults = {
        "plan": None,          # str | None — last generated plan (persists across reruns)
        "plan_request": None,  # WorkoutRequest used for that plan
        "plan_model": None,
        "warnings": [],
        "variation": 0,
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)


def run_generation(request_inputs: dict, api_key: str, model: str, variation: int) -> bool:
    """Call the planner and store the result in session_state. Returns True on success."""
    with st.spinner("Your coach is writing the plan…"):
        try:
            result = generate_workout_plan(
                **request_inputs, api_key=api_key, model=model, variation=variation
            )
        except PlanGenerationError as err:
            st.error(f"😕 {err.user_message}")
            return False
        except Exception:  # last-resort safety net — never show a traceback
            st.error("😕 Something unexpected went wrong. Please try again.")
            return False

    st.session_state.plan = result.plan_markdown
    st.session_state.plan_model = result.model
    st.session_state.warnings = result.warnings
    st.session_state.variation = variation
    st.session_state.plan_request = WorkoutRequest(
        goal=request_inputs["goal"],
        experience=request_inputs["experience"],
        days_per_week=int(request_inputs["days_per_week"]),
        equipment=normalize_equipment(request_inputs["equipment"]),
        limitations=request_inputs["limitations"].strip(),
        session_minutes=request_inputs["session_minutes"],
    )
    return True


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

init_state()

with st.sidebar:
    st.header("⚙️ Settings")
    sidebar_key = st.text_input(
        "Groq API key",
        type="password",
        help="Optional if GROQ_API_KEY is set in .env or Streamlit secrets. "
        "Get a free key at console.groq.com/keys",
    )
    model_choices = list(dict.fromkeys([DEFAULT_MODEL, *FALLBACK_MODELS]))
    model = st.selectbox("Model", model_choices, index=0)
    api_key = get_api_key(sidebar_key)
    if api_key:
        st.success("API key loaded ✔")
    else:
        st.warning("No API key yet — add one to generate plans.")
    st.caption(
        "This app gives general fitness information only — not medical advice."
    )

st.title("🏋️ Workout Plan Generator")
st.write(
    "Answer a few questions like you would for a personal trainer, and get a "
    "day-by-day weekly plan built around **your** goal, schedule, equipment and limitations."
)

with st.form("inputs"):
    c1, c2 = st.columns(2)
    with c1:
        goal = st.selectbox("🎯 Fitness goal", GOALS, index=None, placeholder="Choose a goal")
        experience = st.selectbox(
            "📈 Experience level", EXPERIENCE_LEVELS, index=None, placeholder="Choose a level"
        )
        days = st.slider("📅 Days available per week", min_value=0, max_value=7, value=3,
                         help="0 is allowed here only so you can see the validation message.")
    with c2:
        equipment = st.multiselect(
            "🏠 Equipment access", EQUIPMENT_OPTIONS, placeholder="Select one or more"
        )
        session_minutes = st.select_slider(
            "⏱️ Time per session (minutes)", options=SESSION_LENGTHS, value=45
        )
        limitations = st.text_area(
            "🩹 Injuries or limitations (optional)",
            placeholder="e.g. bad knees, no overhead pressing, lower-back pain",
            max_chars=MAX_LIMITATIONS_CHARS,
        )
    submitted = st.form_submit_button("✨ Generate Plan", type="primary", use_container_width=True)

inputs = {
    "goal": goal,
    "experience": experience,
    "days_per_week": days,
    "equipment": equipment,
    "limitations": limitations or "",
    "session_minutes": session_minutes,
}

if submitted:
    errors = validate_inputs(**inputs)
    if errors:
        for e in errors:
            st.warning(f"⚠️ {e}")
    elif not api_key:
        st.error("😕 Please add your Groq API key in the sidebar (or in .env) first.")
    else:
        run_generation(inputs, api_key, model, variation=0)

# ---------------------------------------------------------------------------
# Result area (persists across reruns via session_state)
# ---------------------------------------------------------------------------

plan: str | None = st.session_state.plan
if plan:
    st.divider()
    head_l, head_r = st.columns([3, 1])
    with head_l:
        st.subheader("📋 Your weekly plan")
        req: WorkoutRequest = st.session_state.plan_request
        st.caption(
            f"{req.goal} · {req.experience} · {req.days_per_week} day(s)/week · "
            f"{', '.join(req.equipment)} · {req.session_minutes} min · "
            f"model: {st.session_state.plan_model}"
        )
    with head_r:
        if st.button("🔄 Regenerate", use_container_width=True,
                     help="Same inputs, a different variation of the plan"):
            if not api_key:
                st.error("😕 Please add your Groq API key first.")
            else:
                req = st.session_state.plan_request
                ok = run_generation(
                    {
                        "goal": req.goal,
                        "experience": req.experience,
                        "days_per_week": req.days_per_week,
                        "equipment": list(req.equipment),
                        "limitations": req.limitations,
                        "session_minutes": req.session_minutes,
                    },
                    api_key,
                    model,
                    variation=st.session_state.variation + 1,
                )
                if ok:
                    st.rerun()

    for w in st.session_state.warnings:
        st.warning(w)

    with st.container(border=True):
        st.markdown(st.session_state.plan)

    # --- Downloads -----------------------------------------------------------
    stamp = date.today().isoformat()
    d1, d2 = st.columns(2)
    d1.download_button(
        "⬇️ Download as Markdown (.md)",
        data=st.session_state.plan,
        file_name=f"workout-plan-{stamp}.md",
        mime="text/markdown",
        use_container_width=True,
    )
    d2.download_button(
        "⬇️ Download as Text (.txt)",
        data=to_plain_text(st.session_state.plan),
        file_name=f"workout-plan-{stamp}.txt",
        mime="text/plain",
        use_container_width=True,
    )

    # --- Swap one exercise ---------------------------------------------------
    exercises = list_exercises(st.session_state.plan)
    if exercises:
        with st.expander("🔁 Swap one exercise"):
            labels = [f"{day} → {exercise_name(row)}" for day, row in exercises]
            idx = st.selectbox(
                "Exercise to replace", range(len(labels)), format_func=lambda i: labels[i]
            )
            reason = st.text_input(
                "Why? (optional)", placeholder="e.g. hurts my shoulder, too boring, no space"
            )
            if st.button("Swap it"):
                if not api_key:
                    st.error("😕 Please add your Groq API key first.")
                else:
                    day, row = exercises[idx]
                    with st.spinner("Finding a replacement…"):
                        try:
                            st.session_state.plan = swap_exercise(
                                st.session_state.plan,
                                day,
                                row,
                                st.session_state.plan_request,
                                reason,
                                api_key=api_key,
                                model=model,
                            )
                            st.rerun()
                        except PlanGenerationError as err:
                            st.error(f"😕 {err.user_message}")
