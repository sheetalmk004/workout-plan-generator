# Prompt Design Notes

The assignment says the real exercise is **prompt design**: getting the model to respect constraints, return structured output and stay in scope. This file explains the choices made and gives a test matrix for iterating.

## 1. Why the inputs aren't just pasted into a sentence

A naive prompt such as *"Make a workout plan for a beginner who wants to lose fat, 3 days, no equipment, bad knees"* tends to fail in predictable ways:

| Typical failure | Fix in this project |
|---|---|
| The model "helpfully" adds dumbbells, a pull-up bar or a bench | The prompt lists both **allowed** and **forbidden** equipment by name, and Rule 1 says *"Do not assume a pull-up bar, bench, bands…"* |
| It writes 4 or 5 days when 3 were asked for | The day count is stated twice ("Training days per week: 3 (so 4 rest days)" and "Write exactly 3 '## Day N' sections"), and code counts the `## Day N` headings afterwards |
| Injuries are acknowledged and then ignored (jump squats for "bad knees") | Rule 3 makes limitations a hard constraint. Each substitution must be explained in the *Notes* column, and the closing **Constraint Check** section makes the model state how each limitation was handled |
| A wall of text that's hard to follow | A strict **output contract**: Weekly Overview table, then `## Day N — Weekday: Focus`, then a warm-up line, an exercise table and a cool-down line, then Progression and Constraint Check |
| Medical claims ("this will fix your knee") or diet and supplement advice | Rule 4 sets the scope (*"You are not a doctor…"*), and a **disclaimer is added in code** whenever a limitation is entered |
| A generic template that ignores the goal and level | The prompt adds goal-specific guidance (rep ranges, rest, conditioning) and level-specific guidance (sets, complexity) |

## 2. The prompt layers

1. **System prompt** (`SYSTEM_PROMPT` in `planner.py`). This holds the coach persona, five numbered **hard rules** and the exact **output format**. Numbered rules with capitalised keywords are easier for the model to follow and easier for us to reference in the repair message.
2. **User prompt** (`build_user_prompt`). This is the client profile as a bulleted brief. It is built constraint-first: allowed and forbidden equipment, the limitation, then programming guidance and the exact day count.
3. **Variation nudge**. *Regenerate* adds "Variation #N: produce a noticeably different plan…" and raises the temperature from 0.5 to 0.9.

## 3. Guardrails in code (trust, but verify)

LLMs sometimes ignore instructions, so `generate_workout_plan` checks the answer after it comes back:

- `clean_response` removes `<think>` blocks and code fences that wrap the whole answer.
- `is_malformed` treats a reply with no `## Day N` heading or no table as unusable and shows a friendly fallback.
- `find_constraint_violations` scans only the **exercise table rows** for forbidden equipment keywords (barbell, cable, machine, dumbbell for no-equipment users, and so on) and checks the day count. It skips the Constraint Check prose, so "no barbells used" isn't a false alarm.
- If it finds a violation, the model gets **one repair turn** that names the exact problems. If a problem is still there afterwards, the user sees a warning instead of a silently wrong plan.
- `ensure_disclaimer` adds a disclaimer whenever a limitation was entered and the model left one out.

## 4. Test matrix for iterating

Run these input sets in the app and check each column. Record what you see and adjust `SYSTEM_PROMPT` or `build_user_prompt` where the model slips. (The assignment's tip is to *"iterate on your system prompt a few times with different inputs"*.)

| # | Goal | Level | Days | Equipment | Limitation | What to check |
|---|---|---|---|---|---|---|
| 1 | Lose fat | Beginner | 3 | No equipment | bad knees | No jumping or deep lunges. Wall sits and glute bridges are fine. Disclaimer present. Exactly 3 days |
| 2 | Build muscle | Advanced | 6 | Full gym | – | A sensible split (PPL or upper/lower). 3–5 sets. 6 days and 1 rest day |
| 3 | Build muscle | Intermediate | 4 | Home dumbbells | no overhead pressing | No overhead press, push press or handstand. Uses dumbbells only, with no barbell or bench |
| 4 | Improve endurance | Beginner | 1 | No equipment | – | Exactly 1 day. A full-body circuit. Fits in the session length |
| 5 | General fitness | Advanced | 7 | Full gym | lower-back pain | 7 days with deloads or active recovery. No heavy deadlifts or good mornings. Disclaimer present |
| 6 | Lose fat | Intermediate | 5 | No equipment + Home dumbbells | – | "No equipment" is dropped and the plan uses dumbbells |
| 7 | (any) | (any) | **0** | (none) | – | Friendly validation messages and **no API call** |
| 8 | (valid) | | | | | Paste an invalid API key and confirm the friendly "key was rejected" message |

### Iteration log (fill in as you test)

| Date | Input # | Model | What went wrong | Prompt change made |
|---|---|---|---|---|
| | | | | |
