"""Core logic for the Workout Plan Generator.

Everything that is not UI lives here so it can be unit-tested without
Streamlit:

* input validation
* prompt design (system prompt + user prompt)
* the Groq API call, wrapped in try/except with friendly error messages
* response validation (empty / malformed / constraint violations)
* stretch-goal helpers (exercise swap, export)
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Final

from groq import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    Groq,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
)

# ---------------------------------------------------------------------------
# Allowed input values (single source of truth for the UI *and* validation)
# ---------------------------------------------------------------------------

GOALS: Final[list[str]] = [
    "Build muscle",
    "Lose fat",
    "General fitness",
    "Improve endurance",
]
EXPERIENCE_LEVELS: Final[list[str]] = ["Beginner", "Intermediate", "Advanced"]
EQUIPMENT_OPTIONS: Final[list[str]] = ["No equipment", "Home dumbbells", "Full gym"]
SESSION_LENGTHS: Final[list[int]] = [20, 30, 45, 60, 75, 90]

MIN_DAYS: Final[int] = 1
MAX_DAYS: Final[int] = 7
MAX_LIMITATIONS_CHARS: Final[int] = 500

# Groq retired llama-3.3-70b-versatile in Aug 2026; gpt-oss-120b is the
# recommended replacement. Override with the GROQ_MODEL env var if needed.
DEFAULT_MODEL: Final[str] = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
FALLBACK_MODELS: Final[list[str]] = ["openai/gpt-oss-20b", "qwen/qwen3.6-27b"]

DISCLAIMER: Final[str] = (
    "> ⚠️ **Disclaimer:** This plan is general fitness information, not medical "
    "advice. Because you mentioned an injury or limitation, please check with a "
    "doctor or physiotherapist before starting, and stop any exercise that causes "
    "pain."
)

# Keywords that must NOT appear when the user lacks that equipment.
# Used by the guardrail that double-checks the model obeyed the prompt.
_GYM_ONLY_KEYWORDS: Final[list[str]] = [
    "barbell", "cable", "machine", "smith", "leg press", "lat pulldown",
    "pulldown", "pec deck", "hack squat", "leg extension", "leg curl machine",
    "ez bar", "ez-bar", "trap bar", "kettlebell", "sled", "rowing machine",
    "treadmill", "elliptical", "stationary bike", "assault bike",
]
_DUMBBELL_KEYWORDS: Final[list[str]] = ["dumbbell", " db "]


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class PlanGenerationError(Exception):
    """Raised with a message that is safe to show directly to the end user."""

    def __init__(self, user_message: str) -> None:
        super().__init__(user_message)
        self.user_message = user_message


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WorkoutRequest:
    """The structured inputs a personal trainer would ask for."""

    goal: str
    experience: str
    days_per_week: int
    equipment: tuple[str, ...]
    limitations: str = ""
    session_minutes: int = 45

    @property
    def has_limitations(self) -> bool:
        return bool(self.limitations.strip())


@dataclass
class PlanResult:
    """What the UI receives after a successful generation."""

    plan_markdown: str
    model: str
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_inputs(
    goal: str | None,
    experience: str | None,
    days_per_week: int | float | str | None,
    equipment: list[str] | tuple[str, ...] | None,
    limitations: str | None = "",
    session_minutes: int | None = 45,
) -> list[str]:
    """Return a list of friendly error messages (empty list == inputs are valid)."""
    errors: list[str] = []

    if not goal or goal not in GOALS:
        errors.append("Please choose a fitness goal.")
    if not experience or experience not in EXPERIENCE_LEVELS:
        errors.append("Please choose your experience level.")

    try:
        days = int(days_per_week)  # type: ignore[arg-type]
        if isinstance(days_per_week, float) and not days_per_week.is_integer():
            raise ValueError
    except (TypeError, ValueError):
        errors.append("Days per week must be a whole number between 1 and 7.")
    else:
        if days < MIN_DAYS:
            errors.append(
                "You selected 0 days — pick at least 1 training day so we can build a plan."
            )
        elif days > MAX_DAYS:
            errors.append("There are only 7 days in a week — please pick 1 to 7 days.")

    if not equipment:
        errors.append(
            "Please select your equipment access (choose 'No equipment' if you have none)."
        )
    else:
        unknown = [e for e in equipment if e not in EQUIPMENT_OPTIONS]
        if unknown:
            errors.append(f"Unknown equipment option(s): {', '.join(unknown)}.")

    if limitations and len(limitations) > MAX_LIMITATIONS_CHARS:
        errors.append(
            f"Please keep injuries/limitations under {MAX_LIMITATIONS_CHARS} characters."
        )

    if session_minutes is not None and session_minutes not in SESSION_LENGTHS:
        errors.append("Please choose a session length from the list.")

    return errors


def normalize_equipment(equipment: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    """'No equipment' combined with real equipment is contradictory — drop it."""
    items = [e for e in EQUIPMENT_OPTIONS if e in equipment]  # stable order
    if len(items) > 1 and "No equipment" in items:
        items.remove("No equipment")
    return tuple(items)


# ---------------------------------------------------------------------------
# Prompt design
# ---------------------------------------------------------------------------

SYSTEM_PROMPT: Final[str] = """\
You are an experienced, certified strength & conditioning coach who writes \
practical weekly workout plans that a real person can follow without a trainer \
standing next to them.

## Hard rules (never break these)
1. EQUIPMENT: Only prescribe exercises that can be done with the equipment listed \
under "Allowed equipment". If an exercise needs anything else, replace it with an \
alternative that uses only allowed equipment. Do not assume a pull-up bar, bench, \
bands, kettlebells or cardio machines unless they are explicitly allowed.
2. DAYS: Write EXACTLY the number of training days requested — no more, no fewer. \
Every other day of the week is a rest / active-recovery day.
3. INJURIES & LIMITATIONS: Treat every stated limitation as a hard constraint. \
Never include a movement that loads or aggravates the affected area. Prefer safe \
substitutions and say briefly why in the Notes column.
4. SCOPE: You are not a doctor. Do not diagnose, do not promise medical or \
rehabilitation outcomes, do not give nutrition prescriptions, supplements or \
calorie targets. Keep the advice to exercise programming.
5. LEVEL & TIME: Match exercise complexity, volume and intensity to the experience \
level, and make each session fit inside the stated session length (including \
warm-up and cool-down).

## Output format (follow exactly, Markdown only, no preamble)
### Weekly Overview
A Markdown table with columns: | Day | Focus | — one row for each of the 7 days \
(Monday..Sunday). Mark rest days as "Rest / active recovery".

Then, for EACH training day N (1..days requested), in order:
## Day N — <Weekday>: <Focus>
**Warm-up (X min):** one line.
| Exercise | Sets | Reps / Time | Rest | Notes |
|---|---|---|---|---|
(4–8 exercise rows; Sets is a number; Reps can be a range like 8–12 or a time like 30s)
**Cool-down (X min):** one line.

After the training days:
### Progression
2–4 bullet points on how to progress week to week.
### Constraint Check
Bullet list confirming: equipment used, number of training days, and how each \
limitation was respected (or "No limitations provided").

Do not wrap the answer in a code block. Do not add any text before "### Weekly Overview".
"""


def _equipment_description(equipment: tuple[str, ...]) -> tuple[str, str]:
    """Return (allowed, forbidden) equipment text for the prompt."""
    if "Full gym" in equipment:
        return (
            "Full commercial gym (barbells, dumbbells, cables, machines, benches, "
            "pull-up bar, cardio machines) plus bodyweight.",
            "Nothing is forbidden.",
        )
    if "Home dumbbells" in equipment:
        return (
            "A pair of adjustable/home dumbbells, bodyweight, the floor, a wall and a "
            "sturdy chair.",
            "Barbells, cable machines, any gym machines, benches, pull-up bars, "
            "kettlebells, resistance bands and cardio machines.",
        )
    return (
        "Bodyweight only — the floor, a wall and a sturdy chair or step.",
        "Dumbbells, barbells, kettlebells, bands, cables, machines, benches, "
        "pull-up bars and cardio machines.",
    )


_GOAL_GUIDANCE: Final[dict[str, str]] = {
    "Build muscle": "Hypertrophy focus: mostly 6–15 reps, 60–120 s rest, enough weekly "
    "volume per muscle group, train each muscle ~2x/week when days allow.",
    "Lose fat": "Fat-loss focus: preserve muscle with compound strength work, add "
    "circuits/supersets or intervals to raise energy expenditure, shorter rests.",
    "General fitness": "Balanced focus: full-body strength, some conditioning, mobility; "
    "sustainable and enjoyable.",
    "Improve endurance": "Endurance focus: higher reps, timed sets, circuits and "
    "cardio intervals; build aerobic base progressively.",
}

_LEVEL_GUIDANCE: Final[dict[str, str]] = {
    "Beginner": "Simple, low-skill movements, 2–3 sets, conservative loads, explain form "
    "cues briefly in Notes. No advanced techniques.",
    "Intermediate": "Moderate volume (3–4 sets), some exercise variety, progressive "
    "overload, optional supersets.",
    "Advanced": "Higher volume and intensity (3–5 sets), splits, advanced techniques "
    "(tempo, drop sets, supersets) where they fit the goal.",
}


def build_user_prompt(request: WorkoutRequest, variation: int = 0) -> str:
    """Turn the structured inputs into a clear, constraint-first brief."""
    allowed, forbidden = _equipment_description(request.equipment)
    limitations = (
        request.limitations.strip() if request.has_limitations else "None provided."
    )
    rest_days = 7 - request.days_per_week

    lines = [
        "Write a one-week workout plan for this client.",
        "",
        "## Client profile",
        f"- Goal: {request.goal}",
        f"- Experience level: {request.experience}",
        f"- Training days per week: {request.days_per_week} "
        f"(so {rest_days} rest day{'s' if rest_days != 1 else ''})",
        f"- Session length: about {request.session_minutes} minutes including warm-up "
        "and cool-down",
        f"- Allowed equipment: {allowed}",
        f"- Forbidden equipment (client does NOT have it): {forbidden}",
        f"- Injuries / limitations: {limitations}",
        "",
        "## Programming guidance",
        f"- {_GOAL_GUIDANCE[request.goal]}",
        f"- {_LEVEL_GUIDANCE[request.experience]}",
        f"- Write exactly {request.days_per_week} '## Day N' sections "
        f"(Day 1 to Day {request.days_per_week}) and spread them sensibly across "
        "the week with recovery between hard sessions.",
    ]
    if request.has_limitations:
        lines.append(
            "- The client reported a limitation: avoid every movement that stresses "
            "that area, choose safer alternatives, and mention the substitution in Notes."
        )
    if variation > 0:
        lines.append(
            f"- Variation #{variation}: produce a noticeably different plan from a "
            "standard template (different exercise selection and/or split) while "
            "still obeying every rule."
        )
    lines += ["", "Follow the output format from the system prompt exactly."]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Response validation / guardrails
# ---------------------------------------------------------------------------

_DAY_HEADING_RE: Final = re.compile(r"^##\s*Day\s*(\d+)\b", re.IGNORECASE | re.MULTILINE)


def clean_response(text: str) -> str:
    """Strip whitespace, accidental ``` fences and any reasoning tags."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = text.strip()
    fence = re.match(r"^```(?:markdown|md)?\s*\n(.*)\n```$", text, flags=re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    return text


def count_training_days(plan: str) -> int:
    return len(set(_DAY_HEADING_RE.findall(plan)))


def is_malformed(plan: str) -> bool:
    """A plan is unusable if it has no Day sections or no exercise tables."""
    return count_training_days(plan) == 0 or "|" not in plan


def find_constraint_violations(plan: str, request: WorkoutRequest) -> list[str]:
    """Cheap keyword guardrail: did the model ignore the equipment / day count?"""
    problems: list[str] = []
    # Only look at exercise table rows, not the "Constraint Check" prose,
    # which legitimately says things like "no barbells were used".
    rows = "\n".join(
        line.lower() for line in plan.splitlines() if line.lstrip().startswith("|")
    )
    rows = f" {rows} "

    if "Full gym" not in request.equipment:
        hits = sorted({k for k in _GYM_ONLY_KEYWORDS if k in rows})
        if hits:
            problems.append(f"uses equipment the client doesn't have: {', '.join(hits)}")
        if "Home dumbbells" not in request.equipment:
            if any(k in rows for k in _DUMBBELL_KEYWORDS):
                problems.append("uses dumbbells but the client has no equipment")

    days = count_training_days(plan)
    if days != request.days_per_week:
        problems.append(
            f"has {days} training days instead of {request.days_per_week}"
        )
    return problems


def ensure_disclaimer(plan: str, request: WorkoutRequest) -> str:
    """Guarantee the disclaimer is present whenever a limitation was given."""
    if request.has_limitations and "disclaimer" not in plan.lower():
        return f"{DISCLAIMER}\n\n{plan}"
    return plan


# ---------------------------------------------------------------------------
# Groq API
# ---------------------------------------------------------------------------


def _friendly_api_error(exc: Exception) -> str:
    """Map SDK exceptions to messages a non-technical user can act on."""
    if isinstance(exc, AuthenticationError):
        return "Your Groq API key was rejected. Please check the key and try again."
    if isinstance(exc, PermissionDeniedError):
        return "This Groq API key doesn't have access to that model. Try another model."
    if isinstance(exc, RateLimitError):
        return "Groq's rate limit was reached. Please wait a minute and try again."
    if isinstance(exc, APITimeoutError):
        return "The request to Groq timed out. Please try again."
    if isinstance(exc, APIConnectionError):
        return "Couldn't reach Groq — please check your internet connection and retry."
    if isinstance(exc, NotFoundError):
        return (
            "The selected model isn't available on Groq any more. Pick another model in "
            "the sidebar."
        )
    if isinstance(exc, BadRequestError):
        return "Groq couldn't process this request. Try a different model or shorter input."
    if isinstance(exc, APIStatusError):
        return f"Groq returned an error (HTTP {exc.status_code}). Please try again shortly."
    return "Something went wrong while generating the plan. Please try again."


def _chat(
    client: Groq,
    model: str,
    messages: list[dict[str, str]],
    temperature: float,
) -> str:
    completion = client.chat.completions.create(
        model=model,
        messages=messages,  # type: ignore[arg-type]
        temperature=temperature,
        max_completion_tokens=4096,
    )
    if not completion.choices:
        return ""
    return completion.choices[0].message.content or ""


def generate_workout_plan(
    goal: str,
    experience: str,
    days_per_week: int,
    equipment: list[str],
    limitations: str = "",
    session_minutes: int = 45,
    *,
    api_key: str | None = None,
    model: str = DEFAULT_MODEL,
    variation: int = 0,
    client: Groq | None = None,
) -> PlanResult:
    """Build the prompt from structured inputs, call Groq and return a usable plan.

    Raises:
        PlanGenerationError: with a user-friendly message for invalid input, API
        failures and empty/malformed responses. The UI shows ``user_message``.
    """
    errors = validate_inputs(
        goal, experience, days_per_week, equipment, limitations, session_minutes
    )
    if errors:
        raise PlanGenerationError(" ".join(errors))

    request = WorkoutRequest(
        goal=goal,
        experience=experience,
        days_per_week=int(days_per_week),
        equipment=normalize_equipment(equipment),
        limitations=(limitations or "").strip(),
        session_minutes=session_minutes,
    )

    key = (api_key or os.getenv("GROQ_API_KEY") or "").strip()
    if client is None and not key:
        raise PlanGenerationError(
            "No Groq API key found. Add GROQ_API_KEY to your .env / Streamlit secrets, "
            "or paste it in the sidebar."
        )

    messages: list[dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_prompt(request, variation)},
    ]
    temperature = 0.5 if variation == 0 else 0.9

    try:
        client = client or Groq(api_key=key, timeout=60.0, max_retries=2)
        raw = _chat(client, model, messages, temperature)
        plan = clean_response(raw)

        if not plan:
            raise PlanGenerationError(
                "The AI returned an empty response. Please click Generate again."
            )
        if is_malformed(plan):
            raise PlanGenerationError(
                "The AI's answer wasn't in a usable day-by-day format. Please click "
                "Generate again (or try another model)."
            )

        # Guardrail: if the model ignored a constraint, ask it to fix the plan once.
        warnings: list[str] = []
        violations = find_constraint_violations(plan, request)
        if violations:
            repair = messages + [
                {"role": "assistant", "content": plan},
                {
                    "role": "user",
                    "content": "Your plan breaks the rules: "
                    + "; ".join(violations)
                    + ". Rewrite the full plan so it follows every rule and the exact "
                    "output format.",
                },
            ]
            fixed = clean_response(_chat(client, model, repair, 0.3))
            if fixed and not is_malformed(fixed):
                plan = fixed
                violations = find_constraint_violations(plan, request)
            if violations:
                warnings.append(
                    "Heads-up: the plan may still not fully match your inputs ("
                    + "; ".join(violations)
                    + "). Consider regenerating."
                )

        plan = ensure_disclaimer(plan, request)
        return PlanResult(plan_markdown=plan, model=model, warnings=warnings)

    except PlanGenerationError:
        raise
    except Exception as exc:  # noqa: BLE001 — every failure must become a friendly message
        raise PlanGenerationError(_friendly_api_error(exc)) from exc


# ---------------------------------------------------------------------------
# Stretch goal: swap one exercise
# ---------------------------------------------------------------------------

_SEPARATOR_RE: Final = re.compile(r"^\|\s*:?-{2,}")


def list_exercises(plan: str) -> list[tuple[str, str]]:
    """Return (day heading, exercise row) pairs found in the plan's tables."""
    exercises: list[tuple[str, str]] = []
    current_day = ""
    for line in plan.splitlines():
        stripped = line.strip()
        if _DAY_HEADING_RE.match(stripped):
            current_day = stripped.lstrip("# ").strip()
            continue
        if not current_day or not stripped.startswith("|"):
            continue
        if _SEPARATOR_RE.match(stripped):
            continue
        first_cell = stripped.strip("|").split("|")[0].strip()
        if not first_cell or first_cell.lower() == "exercise":
            continue
        exercises.append((current_day, stripped))
    return exercises


def exercise_name(row: str) -> str:
    return row.strip().strip("|").split("|")[0].strip()


def swap_exercise(
    plan: str,
    day: str,
    row: str,
    request: WorkoutRequest,
    reason: str = "",
    *,
    api_key: str | None = None,
    model: str = DEFAULT_MODEL,
    client: Groq | None = None,
) -> str:
    """Ask the LLM for ONE replacement table row and splice it into the plan."""
    if row not in plan:
        raise PlanGenerationError("That exercise is no longer in the plan.")
    key = (api_key or os.getenv("GROQ_API_KEY") or "").strip()
    if client is None and not key:
        raise PlanGenerationError("No Groq API key found.")

    columns = row.strip().strip("|").count("|") + 1
    allowed, forbidden = _equipment_description(request.equipment)
    prompt = (
        f"In the workout plan below, replace the exercise '{exercise_name(row)}' on "
        f"'{day}' with a different exercise that trains a similar muscle group/purpose.\n"
        f"Allowed equipment: {allowed}\nForbidden equipment: {forbidden}\n"
        f"Injuries/limitations: {request.limitations or 'None'}\n"
        f"Experience: {request.experience}. Goal: {request.goal}.\n"
        f"User's reason for swapping: {reason.strip() or 'wants variety'}\n"
        "Do not pick an exercise already in that day.\n"
        f"Reply with ONLY one Markdown table row with exactly {columns} cells, in the "
        "same column order as this row, and nothing else:\n"
        f"{row}\n\n--- PLAN ---\n{plan}"
    )
    try:
        client = client or Groq(api_key=key, timeout=60.0, max_retries=2)
        raw = clean_response(
            _chat(client, model, [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ], 0.7)
        )
    except Exception as exc:  # noqa: BLE001
        raise PlanGenerationError(_friendly_api_error(exc)) from exc

    new_row = next(
        (ln.strip() for ln in raw.splitlines()
         if ln.strip().startswith("|") and not _SEPARATOR_RE.match(ln.strip())),
        "",
    )
    if not new_row or new_row.strip("|").count("|") + 1 != columns:
        raise PlanGenerationError(
            "Couldn't get a clean replacement exercise. Please try the swap again."
        )
    if not new_row.endswith("|"):
        new_row += " |"
    return plan.replace(row, new_row, 1)


# ---------------------------------------------------------------------------
# Stretch goal: export
# ---------------------------------------------------------------------------


def to_plain_text(plan: str) -> str:
    """Rough Markdown → readable .txt conversion."""
    out: list[str] = []
    for line in plan.splitlines():
        s = line.strip()
        if _SEPARATOR_RE.match(s):
            continue
        if s.startswith("|"):
            s = "  " + "  |  ".join(c.strip() for c in s.strip("|").split("|"))
        s = re.sub(r"^#+\s*", "", s)
        s = s.replace("**", "").lstrip("> ")
        out.append(s)
    return "\n".join(out).strip() + "\n"
