# Step-by-Step Guide (for first-timers)

This guide takes you from a fresh computer to a **submitted assignment**. Do the parts in order, and tick each box ✅ as you finish it.

| Part | What you'll do | Time |
|---|---|---|
| A | Install the tools (Python, Git, VS Code) | 15 min |
| B | Create the accounts and the Groq API key | 10 min |
| C | Get the project code onto your computer | 5 min |
| D | Set up the Python environment and install packages | 5 min |
| E | Add your API key safely | 3 min |
| F | Run the app | 2 min |
| G | Test it against the rubric | 15 min |
| H | Iterate on the prompt (the real learning goal) | 20+ min |
| I | Push your work to GitHub | 10 min |
| J | (Optional) Deploy online with Streamlit Community Cloud | 10 min |
| K | Submit on codebasics | 2 min |

> **What's a terminal?** It's the text window where you type commands.
> **Windows:** press `Win`, type **PowerShell** and open it. **macOS:** press `Cmd + Space`, type **Terminal** and press Enter.
> In VS Code you can also open one with **Terminal → New Terminal**.
> In the commands below, type only the text in the grey boxes, and press **Enter** after each line.

---

## Part A: Install the tools

### A1. Python (3.10 or newer)
1. Go to <https://www.python.org/downloads/> and download the latest Python 3.
2. **Windows:** run the installer and **tick "Add python.exe to PATH"** at the bottom of the first screen before clicking *Install Now*. This step is important.
   **macOS:** run the `.pkg` installer.
3. Check that it worked. Open a **new** terminal and run:
   ```bash
   python --version
   ```
   You should see something like `Python 3.12.x`. (On macOS, if `python` isn't found, use `python3` everywhere in this guide.)

### A2. Git
1. Download it from <https://git-scm.com/downloads> and install it with the default options.
2. Check that it worked:
   ```bash
   git --version
   ```
3. Tell Git who you are. Use the same email as your GitHub account:
   ```bash
   git config --global user.name "Your Name"
   git config --global user.email "you@example.com"
   ```

### A3. VS Code (recommended editor)
1. Download it from <https://code.visualstudio.com/> and install it.
2. Open VS Code, go to **Extensions** (the square icon on the left), search for **Python** (published by Microsoft) and click **Install**.

✅ **Checkpoint:** `python --version` and `git --version` both print a version.

---

## Part B: Accounts and API key

### B1. GitHub account
Sign up at <https://github.com/signup> if you don't have an account yet. Remember your **username**.

### B2. Groq API key
1. Go to <https://console.groq.com> and sign in (Google or GitHub login is fine).
2. Open **API Keys** at <https://console.groq.com/keys> and click **Create API Key**. Name it `workout-app`.
3. **Copy the key now.** It starts with `gsk_`. You won't be able to see it again. Paste it somewhere temporary, such as Notepad.

> 🔒 Treat this key like a password. **Never** paste it into code that you push to GitHub. Part E shows the safe way to store it.

✅ **Checkpoint:** you have a key that starts with `gsk_`.

---

## Part C: Get the project code

Choose **one** option.

**Option 1: Clone the finished solution (fastest)**
```bash
cd Desktop
git clone https://github.com/sheetalmk004/workout-plan-generator.git
cd workout-plan-generator
```

**Option 2: Build it yourself**
1. Create a folder called `workout-plan-generator` on your Desktop.
2. In VS Code, choose **File → Open Folder…** and select that folder.
3. Create these files and copy their contents from the solution repo: `app.py`, `planner.py`, `requirements.txt`, `.gitignore`, `.env.example`. If you want the tests too, also create `tests/test_planner.py`, `tests/conftest.py` and `requirements-dev.txt`.

Then open the folder in VS Code (**File → Open Folder…**) and open a terminal inside it (**Terminal → New Terminal**).

✅ **Checkpoint:** running `ls` (macOS) or `dir` (Windows) shows `app.py` and `planner.py`.

---

## Part D: Python environment and packages

A **virtual environment** ("venv") keeps this project's packages separate from everything else on your computer.

1. Create it (only needed once):
   ```bash
   python -m venv .venv
   ```
2. Activate it. You need to do this **every time** you open a new terminal.
   - **Windows (PowerShell):**
     ```powershell
     .venv\Scripts\Activate.ps1
     ```
     If you get an error about *running scripts is disabled*, run this once and then try again:
     `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`
   - **macOS / Linux:**
     ```bash
     source .venv/bin/activate
     ```
   Your prompt now starts with `(.venv)`.
3. Install the packages:
   ```bash
   pip install -r requirements-dev.txt
   ```
   This installs `streamlit`, `groq`, `python-dotenv` and `pytest`.

✅ **Checkpoint:** `streamlit --version` prints a version.

---

## Part E: Add your API key safely

1. Make a copy of the example file:
   - **macOS/Linux:** `cp .env.example .env`
   - **Windows:** `copy .env.example .env`
2. Open `.env` in VS Code and replace the placeholder with your real key:
   ```
   GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxx
   ```
3. Save the file.

The `.gitignore` file already lists `.env`, so **Git will never upload it**. You can check this in Part I: `.env` must **not** appear in `git status`.

> Alternative: skip `.env` and paste the key into the **sidebar** of the running app each time.

---

## Part F: Run the app

```bash
streamlit run app.py
```

Your browser opens at <http://localhost:8501>. (If it doesn't, open that address yourself.)

1. In the sidebar, check that it says **"API key loaded ✔"**.
2. Fill in the form. For example: *Lose fat · Beginner · 3 days · No equipment · 30 min · "bad knees"*.
3. Click **✨ Generate Plan**. After a few seconds you'll see:
   - a **Weekly Overview** table covering all 7 days,
   - **Day 1 … Day 3**, each with a warm-up, an exercise table (Exercise / Sets / Reps / Rest / Notes) and a cool-down,
   - **Progression** tips and a **Constraint Check**,
   - a **⚠️ Disclaimer**, because you entered an injury.
4. Try the extras: **🔄 Regenerate**, **⬇️ Download (.md / .txt)** and **🔁 Swap one exercise**.

To stop the app, click in the terminal and press `Ctrl + C`.

✅ **Checkpoint:** you can see a full plan in the browser.

---

## Part G: Test it against the rubric

### G1. Automated tests (no API key needed)
```bash
pytest -q
```
Expected result: `32 passed`.

### G2. Manual "try to break it" checklist

| Rubric item | What to do | Expected result |
|---|---|---|
| Doesn't crash on empty or invalid input (20%) | Click **Generate** without choosing anything and with the slider on **0** | Yellow friendly warnings and no red traceback |
| Inputs are structured and passed into the prompt (25%) | Generate twice, changing only the equipment | The exercises change to match the equipment |
| Prompt respects constraints (30%) | Try *No equipment + "no overhead pressing"* | No dumbbells, barbells or overhead presses, the right number of days, and a disclaimer |
| Error handling (15%) | In the sidebar, paste `gsk_wrong` as the key and generate | "Your Groq API key was rejected…" |
| | Turn off Wi-Fi and generate | "Couldn't reach Groq — please check your internet…" |
| | Click Generate many times quickly | Possibly "rate limit was reached…" (friendly) |
| Code quality (10%) | Open `planner.py` | Type hints, small functions and docstrings |

---

## Part H: Iterate on the prompt (the real learning goal)

1. Open [`docs/PROMPT_DESIGN.md`](PROMPT_DESIGN.md) and run the 8 test inputs in the **test matrix**.
2. For each one, check whether the model followed **every** constraint (equipment, number of days, injury, format).
3. When it slips, edit `SYSTEM_PROMPT` or `build_user_prompt()` in `planner.py`. You might add a stronger rule, an example, or a name to the forbidden list. Save the file, and Streamlit reloads automatically (click **Rerun** if it asks).
4. Write what you changed in the **Iteration log** table in `PROMPT_DESIGN.md`. Reviewers like to see this.

---

## Part I: Push your work to GitHub

### I1. Create an empty repository on GitHub
1. Go to <https://github.com/new>.
2. **Repository name:** `workout-plan-generator`
3. Choose **Public**. This is required, because the graders must be able to open it.
4. **Don't** tick *Add a README*, *.gitignore* or *license*. The project already has them.
5. Click **Create repository** and keep the page open.

### I2. Commit and push from your computer
Run these in the project folder. Replace `YOUR-USERNAME` with your GitHub username.
```bash
git init
git add .
git status
```
👀 Look at the list before you continue: **`.env` must NOT be in it.** If it is, stop and check that `.gitignore` exists.
```bash
git commit -m "Workout Plan Generator: Streamlit + Groq assignment"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/workout-plan-generator.git
git push -u origin main
```

**When Git asks you to sign in:**
- **Windows/macOS with Git Credential Manager:** a browser window opens. Click **Authorize**.
- **If it asks for a username and password:** GitHub no longer accepts your account password here. Create a **Personal Access Token** instead: go to <https://github.com/settings/tokens>, choose **Generate new token (classic)**, tick the **repo** scope, then copy the token and paste it as the *password*.

> If you used *Option 1* in Part C (cloning the solution), the folder already has a Git history that points at someone else's repo. Run `git remote set-url origin https://github.com/YOUR-USERNAME/workout-plan-generator.git` instead of `git init` and `git remote add`, then run `git push -u origin main`.

### I3. Check the repo
Refresh your repo page on GitHub. You should see `app.py`, `planner.py`, `README.md` and the other files, and **no `.env`**. Open the page in a private or incognito window to confirm it's **public**.

### I4. Push later changes
```bash
git add .
git commit -m "Improve prompt: stricter equipment rule"
git push
```

✅ **Checkpoint:** the repo is public, and the README shows on its front page.

---

## Part J (optional): Deploy so anyone can click and test

1. Go to <https://share.streamlit.io> and sign in with GitHub.
2. Click **Create app**, choose your repo, branch `main` and main file `app.py`.
3. Open **Advanced settings → Secrets** and paste:
   ```toml
   GROQ_API_KEY = "gsk_your_real_key"
   ```
4. Click **Deploy**. When it's ready, add the live URL to the top of your README.

---

## Part K: Submit

1. Copy your repo URL, for example `https://github.com/YOUR-USERNAME/workout-plan-generator`.
2. On codebasics.io, open **Session 1 – Kickoff and Fundamentals** and click **Submit**.
3. Paste the GitHub link and submit it.

🎉 You're done!

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `python` is not recognised (Windows) | Reinstall Python and tick **Add to PATH**, then open a new terminal |
| `streamlit` is not recognised | The venv isn't active. Run the activate command from Part D2 again |
| "No API key yet" in the sidebar | `.env` isn't in the project folder or has a typo. It must say `GROQ_API_KEY=gsk_...` with no spaces or quotes |
| "The selected model isn't available" | Pick another model in the sidebar dropdown. Groq retires models from time to time |
| "Rate limit was reached" | The free tier has per-minute limits. Wait about 60 seconds |
| `git push` was rejected (`fetch first`) | You created the repo **with** a README. Run `git pull origin main --allow-unrelated-histories` and then `git push` |
| `.env` was pushed by mistake | Delete the key at console.groq.com/keys **right away**, create a new one, run `git rm --cached .env`, then commit and push again |

---

## How the code works (2-minute tour)

```
app.py (UI)                        planner.py (logic)
─────────────                      ──────────────────
form inputs ──► validate_inputs() ─► friendly warnings if invalid
Generate   ──► generate_workout_plan(goal, experience, days, equipment, limitations, minutes)
                 ├─ build_user_prompt() + SYSTEM_PROMPT
                 ├─ try: Groq chat.completions.create(...)
                 ├─ clean_response() / is_malformed()      → fallback message
                 ├─ find_constraint_violations() → 1 repair call → warning if still wrong
                 ├─ ensure_disclaimer()
                 └─ except: _friendly_api_error()          → "key rejected", "rate limit", …
st.session_state.plan ◄── PlanResult   (persists across reruns)
Regenerate / Download / Swap exercise all work from session_state
```
