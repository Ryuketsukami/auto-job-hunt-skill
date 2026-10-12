<div align="center">

<img src="docs/assets/banner.png" alt="auto-job-hunt-skill: an AI job search agent for Claude Code that tailors a CV to every posting and applies for you" width="100%">

# auto-job-hunt-skill

**An AI job application agent for Claude Code. It interviews you once, finds roles that fit, writes
one tailored ATS-friendly CV per posting, and applies through each employer's official channel,
including LinkedIn Easy Apply. Nothing invented, every send proven, one honest ledger.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Agent Skill](https://img.shields.io/badge/format-Agent%20Skill-7d5bed)](skills/job-hunt/SKILL.md)
[![Claude Code plugin](https://img.shields.io/badge/Claude%20Code-plugin-d97757)](.claude-plugin/plugin.json)
[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-3776ab)](skills/job-hunt/scripts)
[![Windows | macOS | Linux](https://img.shields.io/badge/os-Windows%20%7C%20macOS%20%7C%20Linux-555)](#requirements)

</div>

---

## What it does

`job-hunt` turns Claude Code (or any agent that reads `AGENTS.md` or the Agent Skills format) into a
job search operator for one or more named people. It onboards a person with a short interview,
compiles their history into a verified fact base, finds roles that genuinely match, writes a
different CV for every posting (scored against that posting, with its gap named rather than hidden),
and submits through the employer's own apply path. Nothing is invented: a CV may only draw facts from
the person's compiled profile, and nothing it produces reads as though a machine wrote or sent it.
The full directive, including the rules that never bend, lives in
[`skills/job-hunt/SKILL.md`](skills/job-hunt/SKILL.md); this page does not repeat it.

## Features

- **Tailored CV per job posting.** Mirrors the posting's own terms only where the person really has
  them, proves each one in a bullet, renders a one-page PDF, and blocks anything that fails the
  preflight voice and fingerprint checks.
- **Auto-apply through real channels.** Greenhouse, Lever, Ashby, Workday, Comeet and other ATS
  forms, email applications, and LinkedIn Easy Apply driven in the person's own signed-in browser.
- **Proof, not clicks.** A send counts only when the employer's confirmation is on screen or a
  receipt arrives; the screenshot and the exact CV are archived per role.
- **One ledger, two CSVs.** `applications.csv` and `deferred.csv`, oldest batch on top, statuses as
  icon plus word, so the same role is never sent twice.
- **Grill-style onboarding.** First run asks a few rounds of questions with a recommended answer for
  each, then never asks again.
- **Several people per workspace.** Each person has their own profile, rules, credentials, CVs and
  history.
- **Honest by design.** Never fabricates a fact, never solves a CAPTCHA, never guesses a salary or a
  legal status: those roles wait in `deferred.csv` for the person.

## Install

**Option A: as a Claude Code plugin.**

```
/plugin marketplace add Ryuketsukami/auto-job-hunt-skill
/plugin install job-hunt@auto-job-hunt-skill
```

**Option B: clone the repo.**

```bash
git clone https://github.com/Ryuketsukami/auto-job-hunt-skill.git
```

The skill lives at `skills/job-hunt/` and a one-line `CLAUDE.md` at the repo root points any agent
there. Open the clone with Claude Code (or any agent that reads `CLAUDE.md` or `AGENTS.md`) and ask
it to run a search; it reads the skill before doing anything else.

**As a personal skill**, independent of any one project: copy or symlink `skills/job-hunt` into
`~/.claude/skills/job-hunt`. It then loads for every Claude Code session on the machine.

## First run

Ask for a job search in plain language: "find Hanna some backend roles," "job hunt for Daniel,"
"here's my CV, find me work." The first thing that happens is a grill-style interview, in rounds of
at most five questions, each with a recommended answer. It asks for their CV first if the request
did not include one (an old CV, a LinkedIn export, notes), then only for contact details the CV is
missing or has broken (a dead GitHub link, a phone with no country code), then target roles and seniority, location and arrangement, companies to
exclude, who gets to press send, how CVs should be generated, fixed answers to recurring form
questions (degree wording, salary, work authorisation), which channels to use, and batch size and
cadence. It ends with one summary table marking every item as stated or assumed, for the person to
confirm or correct. Nothing is searched, written, or sent before that confirmation.

Data lives in a workspace outside the skill folder (recommended `~/job-hunt/`, asked once on first
run and recorded in `~/.config/job-hunt/config.json`, or `%APPDATA%\job-hunt\config.json` on
Windows), because skill files get replaced on update.
Each person has their own directory under `<workspace>/people/<name>/`: their profile, their
credentials, their raw material, their generated CVs, and their application history. Nothing under
`people/` is ever committed to this repository; the repository holds only the skill itself.

## Workspace layout

```
<workspace>/people/<name>/
  profile.md          settings + verified facts; the only source a CV may draw facts from
  .env                credentials (mail app password, site passwords); never printed or logged
  .preflight           terms that must never appear in an outward artifact for this person
  raw/                 whatever they handed over, untouched
  applications.csv     every role decided: sent, interview, offer, rejected, no-response, dropped
  deferred.csv         roles found and wanted, but not sent yet because they need the person
  cvs/                 final PDFs only, <batch>-<company>-<role>.pdf
  roles/<batch>-<company>-<role>/   posting, CV source, the PDF, form answers, proof
```

## The two CSVs

Every role a search ever considers ends up in exactly one of two files, both written only by
`scripts/ledger.py`, never by hand.

- **`applications.csv`** holds every role that was decided: sent, or dropped and excluded for good.
- **`deferred.csv`** holds roles the agent found and wanted to send, but could not, usually because
  a form asked for something only the person can answer.

Both use the same status column, always word plus icon:

| Status | Meaning |
|---|---|
| ✅ sent | applied, waiting |
| 💬 interview | any positive reply or interview |
| 🏆 offer | offer received |
| ❌ rejected | employer said no |
| ⏳ no-response | 30+ days of silence |
| ⛔ dropped | considered, never sent; the reason is in the notes |
| ⚠️ deferred | in `deferred.csv` only; the notes say what the person must supply |

A deferred role is not a failure. It usually means a form demanded a salary figure, a legal-status
answer, or hit a live human-verification challenge, none of which the agent will guess at. Answer
what it needs and the next run sends it.

## Gmail

Two independent options, both set during onboarding and neither required:

- **Connector check** (default): if the claude.ai Gmail connector is available, the agent uses it to
  read, search, and draft, with no password involved.
- **Automatic sending** (opt in): needs a Gmail app password, not the account password. Generate one
  at `myaccount.google.com/apppasswords` and it goes only into that person's `.env`, never printed or
  logged, revocable in one click.

## LinkedIn Easy Apply (optional)

A separate module that drives the person's own logged-in Chrome session through LinkedIn's Easy
Apply flow, one observed action at a time. It needs the person's explicit written authority for both
the channel and submission, recorded during onboarding; without it, LinkedIn roles go through the
employer's own channel instead. See
[`skills/job-hunt/reference/linkedin-easy-apply.md`](skills/job-hunt/reference/linkedin-easy-apply.md)
for setup.

## Requirements

- Python 3.8 or newer for every script. On Windows, use `py -3` where these docs say `python3`.
- A Chromium-based browser (Google Chrome, Chromium, or Microsoft Edge) for CV and cover-letter PDF
  rendering.
- Node.js and `@playwright/cli` only if the LinkedIn Easy Apply module is used.

## Migrating from v1

If you were running an earlier per-repo copy of this skill, convert its people into the current
workspace with:

```bash
python3 skills/job-hunt/scripts/migrate.py --from <old-repo-root>
```

It is non-destructive: it reads the old repo's `people/` directories and writes each person into the
currently configured workspace, without touching the old repo.

## Maintainers

The repo is public, so nothing personal may land in a commit. `tools/scrub_check.py` reads terms
from a gitignored `.scrub-names` file at the repo root (one per line, case-insensitive: real names,
employers, anything that must never be pushed) and fails if any staged change contains one. Install
it as a pre-commit hook once per clone:

```bash
ln -s ../../tools/pre-commit .git/hooks/pre-commit
```

Before pushing a branch, check its whole history too:
`python3 tools/scrub_check.py --history origin/main`.

## FAQ

**Can Claude Code apply to jobs for me automatically?**
Yes. With this skill installed, Claude Code sources roles, writes a CV for each, and submits through
the employer's form, by email, or through LinkedIn Easy Apply. How much it sends on its own is your
choice at onboarding: full autonomy, approve each batch, or drafts only. Full autonomy also offers,
with a warning, to turn on Claude Code's bypass permissions mode in your user settings, which removes
permission prompts in every Claude Code session on the machine; `onboard.py permissions restore`
undoes it.

**Does it make things up to match a job description?**
No. Every fact on a CV must exist in the person's compiled profile. Missing requirements stay visible
as gaps, and the score for each CV is recorded in the ledger.

**Will it send the same application twice?**
No. Every role it ever considers is written to `applications.csv` or `deferred.csv`, and both are
checked before anything new is sourced or sent.

**What happens when a form needs something it cannot know, like a salary expectation?**
The role goes to `deferred.csv` with a note saying exactly what is needed. Answer it and the next run
sends it.

**Does it work with LinkedIn?**
LinkedIn Easy Apply is an optional module that drives your own signed-in Chrome one observed step at
a time, only with your written authority. It does not scrape LinkedIn or message anyone.

**Does it work with ChatGPT, Codex, or other agents?**
The skill is plain Markdown plus Python scripts. Claude Code loads it natively as a plugin or skill;
agents that read `AGENTS.md` (such as Codex) are pointed at the same `SKILL.md`.

**Where is my data stored?**
In a local workspace you choose (recommended `~/job-hunt/`), never in this repository and never
uploaded anywhere except to the employers you apply to.

## License

MIT. See [LICENSE](LICENSE).
