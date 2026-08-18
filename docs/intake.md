# Intake — the two messages before any search

Nothing is searched, written, or sent until intake is done. Intake is exactly **two messages**, and
their shape is fixed because a person needs to be able to skim them and correct you fast.

- **Message 1 — what you need from them.** Only sent if their opening request left something open.
- **Message 2 — what you decided on your own.** Always sent, right before you start searching.

If their opening request answered all six questions and their data holds no contradictions, skip
message 1 entirely and send message 2.

---

## Message 1 — the questions

Open with **one line** saying what the list is. Then a **numbered list**. Nothing else above it.

> Six things I need before I start looking. Answer whichever you have a view on — I'll assume the
> rest from your data and show you exactly what I assumed before anything goes out.

Ask **only the unanswered ones**, but keep the original numbering so the person can answer by number
and you can match the reply without ambiguity.

### 0. What work counts

Which roles, titles, and kinds of work should count as a match — and anything that should never be
sent to them. Ask for the shape of the job, not a job title they saw once.

### 1. How far outside the obvious fit should you reach

A role asking for more experience than they have is a *stretch*. Some people want only clean
matches; some want anything with a real chance; some want the long shots too, knowing most will not
answer.

Offer three concrete settings rather than an abstract question:

| Setting | Means |
|---|---|
| **Tight** | Only roles whose stated requirements they already meet. |
| **Balanced** *(default)* | Clean matches, plus roles asking a couple of years more, marked as stretches. |
| **Wide** | Anything where a real argument exists, including senior titles. Expect a lower reply rate. |

Whatever they pick, **every stretch role is still labelled as one when presented.** The setting
changes what gets sourced, never what gets disclosed to them.

### 2. Where

Not just a city. Ask for the boundary:

- a commute radius around a place ("within about an hour of Tel Aviv"),
- anywhere in the country,
- specific other countries,
- or anywhere, subject to work authorisation.

**Work authorisation is the trap here.** A remote role advertised for one country usually still
requires the right to work there. Ask which countries they can legally work in, and treat that as a
hard filter — not a preference. If they say "remote, anywhere", they mean the desk, not the payroll.

### 3. On-site, hybrid, or remote

Four answers: on-site, hybrid, fully remote, or no preference. If they have a hybrid limit ("at most
two office days"), capture the number.

### 4. Do they want to approve each application, or should you send them

**This one carries a warning, and the warning is not decoration.** Present both, and present the risk
before the convenience:

> **Review first (default).** You see every CV and the posting it goes to before anything is sent.
> Slower, and nothing goes out that you have not read.
>
> **Send without review.** Faster and it scales. But an application cannot be recalled. If a CV
> misreads something in your data, that mistake arrives at a real company under your name, becomes
> their permanent record of you, and you find out only if they mention it. You would also be
> committing to roles before seeing them.
>
> There is a middle setting most people actually want: **send without review, but show me the batch
> first** — you approve the list of roles, and the CVs go out unseen.

Default to **review first**. Only switch on an unambiguous, explicit instruction — "yes, send them
without showing me" — and never on silence, a shrug, or a general "go ahead". Record the exact words
they used in `profile.md`.

If they choose review-first, also ask which they want per role: the full CV, or a one-line summary
plus a link to the posting. Both are supported; the second is what most people prefer past the first
batch.

### 5. Anything else

An open box. Phrase it as *"anything you'd want a person doing this for you to know that I haven't
asked about"* — constraints, a company they will not work for, a notice period, a salary floor,
something in their history they want handled a particular way.

Anything they name here that touches how facts are presented goes into
[Handling instructions](profile-compilation.md#handling-instructions).

---

## Also in message 1 — contradictions in their data

If compiling their raw data surfaced anything ambiguous or mutually exclusive, it goes in **this same
message**, below the questions, as a table. They are already answering things; this is the cheapest
moment to resolve it.

> A few things in what you sent don't line up. I haven't guessed at any of them:

| # | What I found | Where it came from | What I need |
|---|---|---|---|
| A | Two different end dates for the same role — 2023 and 2024 | `cv_2024.pdf` vs `linkedin_export.csv` | Which is right |
| B | Listed as both "Senior" and "Mid-level" for the same period | `notes.txt` vs `old_resume.docx` | Which title was actually held |

Never resolve a factual contradiction by picking the more impressive side. Never resolve it by
picking the more recent file, either — recency is not accuracy. **Ask.** Until it is answered, the
fact is unusable and neither version goes on a CV.

---

## Also in message 1 — email access

Put this at the **end of message 1**, under its own heading. It needs an action from them and it
takes a few minutes, so asking early means it is ready when you need it.

You need their mailbox for three things, and it is worth saying so plainly:

1. **Sourcing** — job alerts they already receive are the best-matched postings they will get.
2. **Sending** — several employers accept applications only by email.
3. **Tracking** — a reply, a rejection, or an interview invitation arrives there and nowhere else.

### How to ask for it

Never ask for a password. Ask for an **app password** — a revocable, single-purpose credential that
does not unlock the account itself, cannot change the password, and can be destroyed in one click
without touching anything else.

> To read job alerts and send applications from your address, I need an app password — a
> single-purpose key that only works for mail. It is not your account password, it cannot be used to
> sign in as you, and you can revoke it at any time without changing anything else.
>
> **Gmail:** you need 2-Step Verification on first, then create one at
> `myaccount.google.com/apppasswords`. You get a 16-character string.
> **Outlook / others:** the same feature exists, usually under Security → App passwords.
>
> Send it here and I will write it straight into your own `.env` file, which is never committed and
> never shown. If you would rather not, paste it into `people/<you>/.env` yourself:
>
> ```
> MAIL_ADDRESS=you@example.com
> MAIL_APP_PASSWORD=xxxxxxxxxxxxxxxx
> ```
>
> If you would rather not connect mail at all, that is fine — I will hand you each application to
> send yourself, and you will need to tell me about any replies.

Then confirm it works, and confirm it **out loud** so they know the connection is live:

```bash
python3 scripts/mailbox.py --person hanna list -n 5
```

**Once that credential exists, it is never printed, echoed back, put in a summary, written into any
file other than that `.env`, or included in an error message.** If a command would print it, redact
it before showing the output.

---

## Message 2 — the assumptions table

Sent once the answers are in, immediately before you start sourcing. Same shape: one line of
explanation, then the table.

> Here's everything I'm assuming that you didn't tell me. Correct any line and I'll re-run with it —
> otherwise I'll start looking now.

| # | Assumption | Why | Where it came from |
|---|---|---|---|
| 1 | Targeting backend and full-stack roles | Every role in her history is server-side | `source_data/raw/cv_2024.pdf` |
| 2 | About 4 years of experience | First dated role starts 2022 | `profile.md` |
| 3 | Applying in English | Her CV and her public profile are both in English | `raw/linkedin_export.csv` |
| 4 | Salary not raised unless the employer asks | She named no figure | intake, question 5 unanswered |
| 5 | Full-time, permanent | Nothing in her data suggests contract work | default |

Rules for this table:

- **Every assumption that shapes what gets searched or written appears here.** If you assumed it and
  it matters, it is on the table. An assumption you did not surface is one they cannot correct.
- **Cite where each came from** — a file in `raw/`, a line in `profile.md`, an intake answer, or the
  word `default`. "Inferred" without a source is not good enough.
- **Never put a fact on this table.** Facts they stated are not assumptions; mixing the two teaches
  them to skim it.
- Keep it to what genuinely matters. Twenty rows of trivia hides the one row that is wrong.

After this message, start sourcing. Do not wait for approval of the assumptions table — it is a
correction surface, not a gate. If a correction arrives mid-batch, apply it and say what changed.

---

## Recording the answers

Everything from intake lands in `source_data/profile.md`, under `## Search parameters`, in the
person's own words where they were explicit. It is read at the start of every later batch, so a
second run never re-asks what was already settled.
