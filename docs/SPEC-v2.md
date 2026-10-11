# SPEC: auto-job-hunt-skill v2 (the `job-hunt` skill)

Status: draft for approval, 2026-10-11. Source: grill-me rounds 1 and 2 with the operator.

## 1. What it is

A single, self-contained Claude Code skill named `job-hunt` that runs a job search for one or more
people: onboard them, compile their verified facts, source matching roles, write the CV, apply
through each employer's real channel, and keep an honest ledger.

The skill folder is the whole product. Everything an agent needs (rules, folder map, commands,
onboarding) is inside it. Any agent, started anywhere, that has the skill loaded gets full context.
No `CLAUDE.md` management is required of the user.

## 2. Repository and delivery

- Repo: `friendly-agentic-cv-apply` rebuilt in place as v2, tagged `v2.0.0`, then renamed on GitHub
  to `auto-job-hunt-skill` (GitHub keeps a redirect from the old URL).
- Delivery methods, same files:
  - Plugin: `/plugin marketplace add Ryuketsukami/auto-job-hunt-skill`, then install `job-hunt`.
  - Clone: the repo contains the skill at `skills/job-hunt/`; a one-line `CLAUDE.md` only points to
    it. It is never a second copy of the rules.
- Cross-platform: Windows, macOS, Linux. Every script is Python; `python3` is the only hard
  requirement. CV rendering uses an installed Chrome, Chromium or Edge in headless mode, found on PATH or
  in the usual install locations (plan amendment: replaces both the bash renderer and the earlier
  Playwright Chromium idea, so there is no browser download).

## 3. Workspace (user data)

- Plugin files are replaced on update, so data never lives in the plugin.
- Onboarding asks where the workspace goes; recommended `~/job-hunt/`. Saved in
  `~/.config/job-hunt/config.json` (only the workspace path; everything else is per person).
- First run is detected by the absence of that config or of any person folder.

```
<workspace>/
  people/<name>/
    profile.md          settings + verified facts (per person)
    raw/                what they handed over, untouched
    applications.csv    every role decided: sent, interview, offer, rejected, no-response, dropped
    deferred.csv        roles the agent could not send and that wait on the person
    cvs/                final PDFs only: <batch>-<company>-<role>.pdf
    roles/<batch>-<company>-<role>/   posting, cv.html, form answers, proof screenshots
```

## 4. The two CSVs

- CSV, not xlsx: CSV is the more universal format (Excel, Google Sheets, Numbers, any agent), so
  agents and humans both use CSV. No xlsx copies.
- Written as UTF-8 with BOM so Excel shows the status icons correctly.
- Only `scripts/ledger.py` writes them. Never by hand. Every write re-validates the column count.
- Order: oldest batch on top, new rows appended at the bottom. `batch` is an integer per person that
  `ledger.py` increments when a new batch starts.
- Same 14 columns in both files (deferred adds `needs`):
  `batch, date, company, role, location, arrangement, url, channel, cv_file, status, status_date,
  stretch, reason_or_notes, proof` (+ `needs` in deferred.csv)
- A deferred role that later gets sent moves into `applications.csv` under the current batch, with
  `deferred from batch N` in `reason_or_notes`.
- Dropped roles stay in `applications.csv` so they are never sourced again.

### Status values: word plus icon, always together

| status | meaning |
|---|---|
| `✅ sent` | applied, waiting |
| `💬 interview` | any positive reply or interview |
| `🏆 offer` | offer received |
| `❌ rejected` | employer said no |
| `⏳ no-response` | 30+ days of silence (ledger.py ages these) |
| `⛔ dropped` | considered, never sent; reason given |
| `⚠️ deferred` | in deferred.csv only; waiting on the person |

The skill directive tells every agent to write the status as icon plus word, from this table only.
Mailbox checks upgrade rows to interview or rejected when a reply arrives.

## 5. Onboarding (per person, grill-me style)

Asked in rounds of at most 5 questions, each with a recommendation. Uses Claude Code's
`AskUserQuestion` picker for fixed-choice questions; falls back to prose in this format:

```
❓ **Q1** - **<title>**: <question and options>
➡️ <recommended answer>
```

Options are marked ✅ (recommended / fine), ⚠️ (powerful, read the warning), ❌ (not advised).

Order:
0. Who is this for? (yourself, or someone else; their name). Workspace location on first run only.
1. Contact: name, email, phone, city.
2. Raw material: CV upload, LinkedIn text, anything else.
3. Target roles and seniority.
4. Location, remote or hybrid, relocation.
5. Exclusions: current employer, companies already applied to.
6. Send authority:
   - ⚠️ Full autonomy (recommended): the agent sends without asking. Recorded in writing in profile.md.
   - ✅ Approve each batch.
   - Drafts only.
7. CV mode:
   - ✅ Tailored per role, with one general CV for LinkedIn Easy Apply (recommended).
   - Tailored per role for everything.
   - One general CV for everything.
8. Fixed answers: degree yes/no wording, salary (a figure, or never fill), work authorisation.
9. Channels:
   - Gmail connector check (read, search, draft; no password).
   - ⚠️ Automatic email sending (recommended for full autonomy): needs a Gmail app password. Hint
     shown: Google Account > Security > 2-Step Verification > App passwords
     (myaccount.google.com/apppasswords). Stored only in the person's `.env`.
   - LinkedIn Easy Apply module (optional; local Chrome extension + Playwright CLI).
10. Batch size and cadence.

Onboarding also states, once: "applications.csv is everything decided. deferred.csv holds the roles
the agent found and wanted to send but could not, usually because a form needed something only you
can answer (salary, legal status, a CAPTCHA). Answer those and the agent sends them."

It ends with a summary table for the person to confirm.

## 6. Pipeline (unchanged in spirit, consolidated)

1. Resolve person, read applications.csv first.
2. Compile profile.md from raw material (facts fixed, framing free).
3. Source; dedupe against the ledger; drop knockouts (mandatory degree when absent, far-out years,
   missing core stack, clearance) with a reason row.
4. Write the CV per the CV mode; render to one page.
5. Gate: `preflight.py` exits 0 (voice rules, banned terms, no em dashes, linked contacts, no agent
   fingerprint) and the render is one page.
6. Send through the employer's channel per send authority; defer anything the profile cannot answer.
7. Proof: employer confirmation on screen or receipt; screenshot; ledger row; read back.

The ten rules that never bend carry over verbatim in substance.

## 7. Gmail

- Default: the claude.ai Gmail connector (Anthropic side, no password): receipts, verification
  codes, reply tracking, and email applications created as drafts.
- Opt-in: app password in the person's `.env` enables `mailbox.py` to send automatically.
- Measured basis: 55 of 174 historical sends (32%) went by email.

## 8. Consolidation and dead code

- Fold in generic mechanics only from the private `cvs` and `job-applications` repos (ATS quirks,
  wall handling, per-CV algorithm). No personal data, ever; a scrub check runs before every commit.
- Regional material moves to `skills/job-hunt/reference/regions/israel.md` (Drushim, AllJobs, Hebrew postings).
- Dead = unreferenced by any doc or script, superseded rule wording, one-off batch scripts,
  duplicated rules between AGENTS.md and SKILL.md. A deletion list is shown before removal.

## 9. Migration (local only)

`skills/job-hunt/scripts/migrate.py` converts the operator's existing people to the v2 layout and CSV schema,
preserving batch numbers. Runs on this machine; data stays gitignored, never pushed.

## 10. Build and release

- Built with the superpowers workflow (plan, implement in small verified steps, tests).
- Tests: ledger ordering and column checks, status vocabulary, onboarding first-run detection,
  preflight rules, migration round-trip, Easy Apply controller.
- Push to GitHub only after the operator approves this spec and reviews the final diff.

## Open items

None. Every branch of the interview is settled.
