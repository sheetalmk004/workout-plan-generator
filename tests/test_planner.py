"""Unit tests — no real API calls; Groq is replaced by a tiny fake client."""

from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest
from groq import APIConnectionError, AuthenticationError, RateLimitError

import planner as p

GOOD_PLAN = """### Weekly Overview
| Day | Focus |
|---|---|
| Monday | Full body A |
| Tuesday | Rest / active recovery |
| Wednesday | Full body B |
| Thursday | Rest / active recovery |
| Friday | Full body C |
| Saturday | Rest / active recovery |
| Sunday | Rest / active recovery |

## Day 1 — Monday: Full body A
**Warm-up (5 min):** marching, arm circles.
| Exercise | Sets | Reps / Time | Rest | Notes |
|---|---|---|---|---|
| Push-up | 3 | 8–12 | 60s | Knees down if needed |
| Glute bridge | 3 | 12–15 | 60s | Knee-friendly |
**Cool-down (5 min):** stretch.

## Day 2 — Wednesday: Full body B
| Exercise | Sets | Reps / Time | Rest | Notes |
|---|---|---|---|---|
| Plank | 3 | 30s | 45s | Brace |

## Day 3 — Friday: Full body C
| Exercise | Sets | Reps / Time | Rest | Notes |
|---|---|---|---|---|
| Chair dips | 3 | 10 | 60s | |

### Progression
- Add reps.
### Constraint Check
- Bodyweight only, no barbell used.
"""

VALID = dict(
    goal="General fitness",
    experience="Beginner",
    days_per_week=3,
    equipment=["No equipment"],
    limitations="",
    session_minutes=45,
)


class FakeClient:
    """Mimics client.chat.completions.create(...) returning queued replies."""

    def __init__(self, *replies: object) -> None:
        self.replies = list(replies)
        self.calls: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        if reply is None:
            return SimpleNamespace(choices=[])
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=reply))]
        )


def _http_error(cls: type, status: int) -> Exception:
    req = httpx.Request("POST", "https://api.groq.com")
    return cls("err", response=httpx.Response(status, request=req), body=None)


# ---------------------------------------------------------------- validation


def test_valid_inputs_have_no_errors() -> None:
    assert p.validate_inputs(**VALID) == []


@pytest.mark.parametrize(
    "override, fragment",
    [
        ({"days_per_week": 0}, "0 days"),
        ({"days_per_week": 9}, "only 7 days"),
        ({"days_per_week": "abc"}, "whole number"),
        ({"days_per_week": None}, "whole number"),
        ({"equipment": []}, "equipment"),
        ({"goal": None}, "goal"),
        ({"experience": "Pro"}, "experience"),
        ({"limitations": "x" * 600}, "under"),
    ],
)
def test_invalid_inputs_give_friendly_messages(override: dict, fragment: str) -> None:
    errors = p.validate_inputs(**{**VALID, **override})
    assert errors and fragment in " ".join(errors)


def test_zero_days_never_calls_api() -> None:
    client = FakeClient()
    with pytest.raises(p.PlanGenerationError, match="0 days"):
        p.generate_workout_plan(**{**VALID, "days_per_week": 0}, client=client)
    assert client.calls == []


def test_normalize_equipment_drops_contradiction() -> None:
    assert p.normalize_equipment(["No equipment", "Home dumbbells"]) == ("Home dumbbells",)


# ---------------------------------------------------------------- prompt design


def test_prompt_contains_every_constraint() -> None:
    req = p.WorkoutRequest("Build muscle", "Advanced", 5, ("Home dumbbells",), "bad knees", 60)
    prompt = p.build_user_prompt(req)
    for text in ["Build muscle", "Advanced", "5", "2 rest days", "60 minutes",
                 "dumbbells", "Forbidden equipment", "Barbells", "bad knees",
                 "exactly 5 '## Day N'"]:
        assert text in prompt, text


def test_system_prompt_has_rules_and_format() -> None:
    for text in ["EQUIPMENT", "EXACTLY", "INJURIES", "not a doctor",
                 "## Day N", "| Exercise | Sets |", "Constraint Check"]:
        assert text in p.SYSTEM_PROMPT


# ---------------------------------------------------------------- generation


def test_happy_path_returns_plan() -> None:
    client = FakeClient(GOOD_PLAN)
    result = p.generate_workout_plan(**VALID, client=client)
    assert "## Day 1" in result.plan_markdown
    assert result.warnings == []
    assert client.calls[0]["messages"][0]["role"] == "system"


def test_disclaimer_added_when_limitations_given() -> None:
    result = p.generate_workout_plan(
        **{**VALID, "limitations": "bad knees"}, client=FakeClient(GOOD_PLAN)
    )
    assert "Disclaimer" in result.plan_markdown


def test_code_fence_is_stripped() -> None:
    result = p.generate_workout_plan(**VALID, client=FakeClient(f"```markdown\n{GOOD_PLAN}\n```"))
    assert result.plan_markdown.startswith("### Weekly Overview")


@pytest.mark.parametrize("reply", ["", "   ", None])
def test_empty_response_is_friendly(reply: object) -> None:
    with pytest.raises(p.PlanGenerationError, match="empty"):
        p.generate_workout_plan(**VALID, client=FakeClient(reply))


def test_malformed_response_is_friendly() -> None:
    with pytest.raises(p.PlanGenerationError, match="usable"):
        p.generate_workout_plan(**VALID, client=FakeClient("Just do some squats!"))


@pytest.mark.parametrize(
    "exc, fragment",
    [
        (_http_error(AuthenticationError, 401), "API key"),
        (_http_error(RateLimitError, 429), "rate limit"),
        (APIConnectionError(request=httpx.Request("POST", "https://x")), "internet"),
        (RuntimeError("boom"), "went wrong"),
    ],
)
def test_api_failures_are_friendly(exc: Exception, fragment: str) -> None:
    with pytest.raises(p.PlanGenerationError, match=fragment):
        p.generate_workout_plan(**VALID, client=FakeClient(exc))


def test_missing_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(p.PlanGenerationError, match="API key"):
        p.generate_workout_plan(**VALID)


def test_guardrail_repairs_equipment_violation() -> None:
    bad = GOOD_PLAN.replace("| Push-up |", "| Barbell bench press |")
    client = FakeClient(bad, GOOD_PLAN)
    result = p.generate_workout_plan(**VALID, client=client)
    assert len(client.calls) == 2  # one repair call
    assert "barbell" in client.calls[1]["messages"][-1]["content"]
    assert "Barbell" not in result.plan_markdown
    assert result.warnings == []


def test_guardrail_warns_if_repair_fails() -> None:
    bad = GOOD_PLAN.replace("| Push-up |", "| Barbell bench press |")
    result = p.generate_workout_plan(**VALID, client=FakeClient(bad, bad))
    assert result.warnings and "barbell" in result.warnings[0]


def test_day_count_mismatch_detected() -> None:
    req = p.WorkoutRequest("General fitness", "Beginner", 4, ("No equipment",))
    assert any("3 training days" in v for v in p.find_constraint_violations(GOOD_PLAN, req))


def test_constraint_check_prose_not_flagged() -> None:
    req = p.WorkoutRequest("General fitness", "Beginner", 3, ("No equipment",))
    assert p.find_constraint_violations(GOOD_PLAN, req) == []


# ---------------------------------------------------------------- stretch goals


def test_list_and_swap_exercise() -> None:
    exercises = p.list_exercises(GOOD_PLAN)
    names = [p.exercise_name(r) for _, r in exercises]
    assert names == ["Push-up", "Glute bridge", "Plank", "Chair dips"]

    day, row = exercises[0]
    req = p.WorkoutRequest("General fitness", "Beginner", 3, ("No equipment",))
    new = "| Incline push-up | 3 | 10 | 60s | Hands on chair |"
    updated = p.swap_exercise(GOOD_PLAN, day, row, req, client=FakeClient(new))
    assert "Incline push-up" in updated and "| Push-up |" not in updated


def test_swap_rejects_garbage_reply() -> None:
    day, row = p.list_exercises(GOOD_PLAN)[0]
    req = p.WorkoutRequest("General fitness", "Beginner", 3, ("No equipment",))
    with pytest.raises(p.PlanGenerationError):
        p.swap_exercise(GOOD_PLAN, day, row, req, client=FakeClient("try lunges"))


def test_plain_text_export() -> None:
    txt = p.to_plain_text(GOOD_PLAN)
    assert "##" not in txt and "|---" not in txt and "Push-up" in txt
