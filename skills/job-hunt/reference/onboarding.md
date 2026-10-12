# Onboarding: one person, asked once

Nothing is searched, written, or sent for a person until onboarding is done and they have confirmed
the summary. Onboarding runs in two cases:

- **First run.** `onboard.py status` prints `"first_run": true`. If its `workspace` is `null`, ask
  where the workspace goes (question 0b); otherwise the workspace exists and only has no people
  yet. Then onboard the first person.
- **A new person.** Someone asks you to run a search for a name that is not in `people`.

It also runs partially whenever a `## Settings` line in an existing `profile.md` is empty: ask only
that question, the same way.

---

## How to ask

Ask in **rounds of at most 5 questions**. Each question carries your recommendation. Ask only what
the opening request and their raw material did not already answer, but keep the numbering below so
an answer by number is never ambiguous.

**The CV comes first.** If the opening request carried no CV or other raw material, the first round
asks for it (question 1), together with question 0 if the person is not yet named. Nothing else is
asked until it arrives or they say they have none, because it answers most of what follows. Once it
is in, save it to `raw/`, compile, and fill every field it already holds before the next round.

**Never ask what the material already answers.** After compiling, go through every question below
and fill each answer the raw material settles; questions marked **Skip when** name the usual cases.
Ask only where the material is silent, unclear, or contradicts itself. Preferences (stretch
tolerance, arrangement, send authority, CV mode, salary, batch size) are never in a CV and are
always asked. Every filled answer appears in the closing summary as assumed, with the file it came
from, so the person can still correct it.

**Fixed-choice questions go through the `AskUserQuestion` picker** when your harness has it (Claude
Code does). Put the recommended option first and mark it in its label, e.g. "Tailored per role,
general CV for Easy Apply (recommended)". If the picker fits fewer questions per call than the round holds, split the round
across calls. Open questions (contact details, target roles) go in prose.

**Without the picker, use this format in prose**, one block per question:

```
❓ **Q1** - **<title>**: <question and options>
➡️ <recommended answer>
```

Options carry a marker:

| Marker | Means |
|---|---|
| ✅ | recommended, or fine to pick |
| ⚠️ | powerful; read the warning before picking it |
| ❌ | not advised |

Contradictions found in their raw data go in the same round as the questions, as a table (see
"Contradictions" below). They are already answering things; that is the cheapest moment.

---

## First run only: the workspace

**0b. Where should the workspace live?** Recommend `~/job-hunt`. It holds every person's data,
outside the skill folder, because skill files are replaced on update. Then:

```bash
python3 <skill-dir>/scripts/onboard.py init ~/job-hunt
```

That writes only the workspace path to the user config (`~/.config/job-hunt/config.json`, or
`%APPDATA%\job-hunt\config.json` on Windows). Everything else is per person.

---

## The questions, in order

Each entry says which line of the person's `profile.md` the answer fills. Settings lines are under
`## Settings`; write the answer in plain words, and for send authority quote the person's own words
with the date.

### 0. Who is this for?

Yourself, or someone else? Their full name. Then scaffold them:

```bash
python3 <skill-dir>/scripts/onboard.py person "Hanna Levi"   # prints: created   people/hanna
```

Fills: the folder name and the profile title. If the script prints a `migrated` line, tell the
operator which folder moved.

### 1. Raw material

Any existing CV however old, a LinkedIn data export or the text of their profile, anything else:
certificates, a portfolio, notes in their own words about one thing they built and what changed
because of it. Every file lands in `raw/` untouched, named for what it is and when it arrived.

If they have nothing written down, that is fine: ask for their work history in prose instead
(employer, title, dates, what they built, what changed because of it), one job at a time.

Fills: `raw/`, and then the compiled body of `profile.md` (see [profile.md](profile.md)). Compile
before asking the next round, so later questions can be skipped when the material answers them.

### 2. Contact

Name as it should appear on a CV, email, phone, city (a city, never a street address), and any
public profile or portfolio URL they are happy to have on the CV.

**Take what the raw material already holds and do not ask for it again.** Ask only for fields that
are missing or broken, and check each one before trusting it:

| Field | Broken when |
|---|---|
| Email | not a well-formed address, or a domain that does not resolve |
| Phone | no country code, wrong digit count for the country |
| URL (GitHub, portfolio) | it does not load (404, dead domain, redirect to a home page), or the page is someone else's |
| LinkedIn URL | not of the form `linkedin.com/in/<slug>` (LinkedIn walls logged-out visitors, so a login redirect alone proves nothing) |
| Location | a street address (keep the city only) |

Name the broken field and why in the round ("the GitHub link in your CV returns 404: what is the
right one?"). Fields taken from the CV go in the summary as assumed, with the file they came from.

Fills: `## Contact` (Name, Email, Phone, Location, Public profile / portfolio).

### 3. Target roles and seniority

The shape of the work that counts, and anything that should never be sent to them. Ask how far past
the obvious fit to reach:

- ✅ **Balanced** (recommended): clean matches, plus roles asking a couple of years more, marked as
  stretches.
- ✅ **Tight**: only roles whose stated requirements they already meet.
- ⚠️ **Wide**: anything with a real argument, including senior titles. Expect a lower reply rate.

**Skip when** (the work only, never the stretch tolerance): the CV shows one clear track, such as
every role being backend work at mid level. Propose that as the target in the summary instead.

Fills: `## Search parameters`, lines 0 (what work counts) and 1 (stretch tolerance). Every stretch
is still labelled as one in reports, whatever the setting.

### 4. Location and arrangement

The boundary, not just a city: a commute radius, the whole country, named countries, or anywhere.
On-site, hybrid (with the office-day limit as a number), remote, or no preference. Open to
relocation?

The city comes from the contact details (question 2); ask only for the boundary and arrangement.

Fills: `## Search parameters`, line 2 (location, boundary, relocation) and line 3 (on-site,
hybrid, remote).

### 5. Exclusions

Their current employer, companies they already applied to on their own, companies they will not
work for.

**Skip part:** a role the CV shows as current ("2022 to present") puts that employer on the list
without asking; ask only for the others.

Fills: Settings `Exclusions:`. Roles at those companies are never sourced.

### 6. Send authority

- ⚠️ **Full autonomy** (recommended): the agent sends without asking. Recorded in writing in
  profile.md. An application cannot be recalled: a misread fact arrives at a real company under
  their name. Only pick this on their explicit words, never on silence or a general "go ahead".
- ✅ **Approve each batch**: they see the list of roles, approve it, and the approved ones go out.
- **Drafts only**: everything is prepared and handed over; email applications become Gmail drafts;
  they press send.

Fills: Settings `Send authority:`, with their exact words and the date, e.g.
`Full autonomy. "yes, send them without showing me" (2026-10-11)`.

**If they pick full autonomy, warn them about permissions next, in the same round:**

> ⚠️ Full autonomy also turns on Claude Code's **bypass permissions** mode: from the next start, the
> agent runs commands, edits files, and drives the browser with no permission prompt. Claude Code
> takes this mode only from its user settings (`~/.claude/settings.json`), so it applies to **every
> Claude Code session on this computer, in every folder**, not only the job hunt. A mistake, or an
> instruction hidden in a job posting, then meets no prompt. Undo it any time with
> `onboard.py permissions restore`. Turn it on?

Only on an explicit yes:

```bash
python3 <skill-dir>/scripts/onboard.py permissions bypass    # prints: defaultMode bypassPermissions   <path>
```

It keeps every other setting and backs the file up once to `settings.json.job-hunt.bak`. It takes
effect on the next start of Claude Code, which then shows its own warning; that one is theirs to
accept, so the script never pre-accepts it. Claude Code refuses this mode when run as root. If
`onboard.py permissions status` already shows `bypassPermissions` (an earlier person turned it on),
say so and skip the question. A no changes nothing else: full autonomy over sending still stands,
with permission prompts along the way.

Fills: Settings `Tool permissions:`, `Bypass` with their words and the date, or `Prompts`.

### 7. CV mode

- ✅ **Tailored per role, with one general CV for LinkedIn Easy Apply** (recommended).
- **Tailored per role for everything.**
- **One general CV for everything.**

Fills: Settings `CV mode:`. The general CV lives in `roles/general-cv/` and renders to
`cvs/general-cv.pdf`.

### 8. Fixed answers

Forms ask these constantly, and a guess is never acceptable:

- **Degree yes/no wording.** How to answer "Do you have a bachelor's degree?" given their real
  education. Recommend the literal truth; if studies are in progress, the exact wording they accept.
  **Skip when** the CV settles it: a completed bachelor's or higher means `Yes`, no higher
  education at all means `No`. Ask only for studies in progress or unfinished, or a diploma,
  certificate, or bootcamp whose equivalence is a judgement call.
  Fills: Settings `Degree yes/no answer:`.
- **Salary.** A figure (with currency, gross or net, monthly or yearly), or "never fill". With
  "never fill", a form that forces a number is deferred. Fills: Settings `Salary fields:`.
- **Work authorisation.** Which countries they may legally work in, and whether they need
  sponsorship. A hard filter: a remote role advertised for one country usually still needs the
  right to work there. **Skip when** the CV states citizenship or a work permit. Where they live
  and have worked is not proof, so ask otherwise. Fills: Settings `Work authorisation:`.

### 9. Channels

- ✅ **Gmail connector check.** If the claude.ai Gmail connector is available (tools such as
  `search_threads`, `get_thread`, `create_draft`), run one search on their inbox to confirm it is
  live. It reads, searches, and drafts, with no password. Fills: Settings `Gmail connector:`.
- ⚠️ **Automatic email sending** (recommended for full autonomy): needs a Gmail app password. Hint
  shown: Google Account > Security > 2-Step Verification > App passwords
  (myaccount.google.com/apppasswords). Stored only in the person's `.env`. It is not their account
  password: it only works for mail and can be revoked in one click. Write it into
  `<ws>/people/<p>/.env` as `MAIL_ADDRESS=` and `MAIL_APP_PASSWORD=` (or let them paste it there),
  never echo it, then confirm it works out loud:
  `python3 <skill-dir>/scripts/mailbox.py --person <p> list -n 5`.
  Fills: Settings `Automatic email sending:` (yes or no, never the password).
- **LinkedIn Easy Apply module** (optional): a local Chrome extension plus the Playwright CLI,
  driving their own logged-in session. Needs their explicit written authority for both the channel
  and submission. See [linkedin-easy-apply.md](linkedin-easy-apply.md).
  Fills: Settings `LinkedIn Easy Apply:`, with their words and the date.

### 10. Batch size and cadence

How many roles per batch, and how often: on request only, or a recorded rhythm such as "8 roles
every Monday". Recommend 8 to 10 per batch; ten well-matched roles beat fifty scraped ones.

Fills: Settings `Batch size and cadence:`.

---

## Say this once

Before the summary, state this once, verbatim:

> applications.csv is everything decided. deferred.csv holds the roles the agent found and wanted to
> send but could not, usually because a form needed something only you can answer (salary, legal
> status, a CAPTCHA). Answer those and the agent sends them.

---

## Contradictions

If compiling their raw data surfaced anything ambiguous or mutually exclusive, put it in the round
that is going out anyway, as a table:

| # | What I found | Where it came from | What I need |
|---|---|---|---|
| A | Two end dates for the same role, 2023 and 2024 | `cv_2024.pdf` vs `linkedin_export.csv` | Which is right |
| B | Both "Senior" and "Mid-level" for the same period | `notes.txt` vs `old_resume.docx` | Which title was held |

Never resolve a contradiction by picking the more impressive side, or the more recent file. Until
it is answered, the fact sits in `## Open questions` and neither version goes on a CV.

---

## The summary to confirm

Onboarding ends with one table covering every Settings line, contact, targets, and every assumption
that shapes the search. Mark each row as stated by them or assumed by you, and say where an
assumption came from (a file in `raw/`, a line of `profile.md`, or "default").

| Item | Value | Source |
|---|---|---|
| Send authority | Approve each batch | stated, Q6 |
| Degree yes/no answer | Yes | assumed: B.Sc. completed 2019 in `raw/cv_2024.pdf` |
| CV mode | Tailored per role, general CV for Easy Apply | stated, Q7 |
| Target | Backend and full-stack, mid-level | assumed: every role in `raw/cv_2024.pdf` is server-side |
| Language of applications | English | assumed: CV and public profile are in English |
| Salary | Never fill | stated, Q8 |
| Batch | 8 roles, on request | default |

Ask them to confirm or correct. Apply corrections to `profile.md`, then start the first batch.
Never put a stated fact under "assumed", and keep the table to what genuinely matters: twenty rows
of trivia hide the one that is wrong.

## Credentials

Once a credential exists it is never printed, echoed back, put in a summary, written into any file
other than that person's `.env`, or included in an error message. If a command would print it,
redact the output before showing it. Never ask for an account password; ask for an app password.
