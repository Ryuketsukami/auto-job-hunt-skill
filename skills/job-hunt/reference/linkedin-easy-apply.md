# LinkedIn Easy Apply

An optional module, for a person whose `profile.md` Settings line `LinkedIn Easy Apply:` records
their explicit written authority for both the channel and submission, with the date (onboarding
section 9). General send authority does not silently extend to LinkedIn. No authority recorded:
LinkedIn roles go through the employer's own channel instead.

Easy Apply uploads the general CV when the CV mode says so (`cvs/general-cv.pdf`), otherwise the
role's own CV.

## Shape of the pipeline

The browser is the person's existing Chrome session. The controller connects through Microsoft's
Playwright browser bridge and performs one observed action at a time:

1. Snapshot and screenshot the current page.
2. Read the role, company, location, requirements, and application state.
3. Check the exact role against the ledger (`ledger.py --person <p> find --url ...`).
4. Decide one action from the verified profile and the Settings answers.
5. Act through the element reference returned by the latest snapshot.
6. Snapshot and screenshot again before the next action.

There is no unattended loop. The controller does not scrape results, message people, send
connection requests, copy browser storage, or keep a second login profile. It never requests,
prints, or stores the LinkedIn password. It stops on an account warning.

## Never touch the person's profile

LinkedIn has **no write API for profile fields**, and nothing in this module edits the person's
LinkedIn profile: headline, experience, skills, education, or settings. Do not change any of it
unless they ask you to, explicitly, for that change. Corrections made inside an application form
(see Education below) apply to that one application only.

## One-time setup

The machine that holds the person's Chrome needs Node.js, `@playwright/cli` **0.1.22 or newer**,
Google Chrome, and the official Playwright MCP Bridge extension in the Chrome profile that holds the
LinkedIn session.

```bash
npm install --global @playwright/cli@latest
```

Install the Playwright MCP Bridge from the Chrome Web Store. An administrator may instead put its
published extension id in Chrome's `ExtensionInstallForcelist` policy. Chrome loads a new extension
only after a full restart. Restart it only with the person's go-ahead: killing Chrome drops their
open tabs to a "Restore pages?" prompt.

**Version pairing.** Bridge 0.4.0 speaks protocol 2. CLI 0.1.9 speaks protocol 1, and the connect
page rejects it with "The client uses an unsupported protocol version" while `attach` hangs with no
error on the controller side. If attach hangs, check the CLI version first.

**Skipping the connect dialog.** On every attach the bridge opens a connect tab that asks the person
to approve. To make attach unattended, the person opens the bridge's status page, copies the token
it shows, and stores it as a user environment variable (on Windows:
`setx PLAYWRIGHT_MCP_EXTENSION_TOKEN "<token>"`). The token is a credential: never print, log, or
commit it.

## Controller

**Local mode (default).** Run on the same machine and desktop session as the person's Chrome:

```bash
python3 <skill-dir>/scripts/linkedin_easy_apply.py doctor
python3 <skill-dir>/scripts/linkedin_easy_apply.py attach
```

**Remote mode.** To drive a Windows machine over SSH, pass `--runner user@host` or set
`LINKEDIN_RUNNER=user@host`. Two traps the controller already handles there, so do not hand-roll
around them:

- **`attach` must run in the person's desktop session.** The CLI opens the connect page by
  launching `chrome.exe`. Launched from SSH, that process lives in Windows session 0 and never
  reaches the Chrome in session 1, so attach hangs forever. The controller registers a one-shot
  interactive scheduled task, runs the CLI hidden through a WScript launcher, and removes the task
  afterwards. Every later command talks to the CLI daemon and works fine from SSH.
- **Never call `npx.cmd`.** It is a batch file, so `cmd.exe` re-parses the arguments and an `&` in a
  search URL silently ends the command. The controller runs `node` on the CLI entry point instead.

Locally on Windows, the controller starts its child processes with no console window.

Use a dedicated session name when more than one operator is active:

```bash
python3 <skill-dir>/scripts/linkedin_easy_apply.py --session role-123 attach
```

## Is the person signed in?

Check before the first Easy Apply action of every session, and again whenever a page looks like a
login screen:

```bash
python3 <skill-dir>/scripts/linkedin_easy_apply.py session    # LINKEDIN_SESSION <state>
```

| State (exit) | Means | Tell the person |
|---|---|---|
| `signed-in` (0) | the attached Chrome is on their feed | nothing; carry on |
| `signed-out` (3) | LinkedIn sent the browser to a login or sign-up page | "Open Chrome, the profile with the Playwright MCP Bridge, sign in to linkedin.com yourself, and tell me when you're in." |
| `challenge` (4) | LinkedIn is showing a security check | "LinkedIn wants to verify it's you. Please finish that check in Chrome." Never touch it. |
| `unreachable` (5) | no attached browser | run `doctor`; say exactly what is missing (Chrome not open, extension not installed, CLI missing), or run `attach` |

Signing in is always the person's own step: never ask for, type, or store the LinkedIn password or a
one-time code. Run `session` again after they say they are in, and only continue on `signed-in`.

**Mid-batch, a missing session never stops the other channels.** Employer forms and email go out as
usual; each Easy Apply role is deferred with
`--needs "sign in to LinkedIn in Chrome, then I send it"`, and the batch report asks once. When they
confirm, re-check and send the deferred roles.

## Screenshot, analyse, act loop

Navigate only to a LinkedIn URL; the controller rejects other hosts.

```bash
python3 <skill-dir>/scripts/linkedin_easy_apply.py goto 'https://www.linkedin.com/jobs/view/123/'
python3 <skill-dir>/scripts/linkedin_easy_apply.py text        # posting body; it is not in the snapshot
python3 <skill-dir>/scripts/linkedin_easy_apply.py snapshot    # element refs, printed inline
python3 <skill-dir>/scripts/linkedin_easy_apply.py screenshot <ws>/people/<p>/roles/<dir>/before.png
python3 <skill-dir>/scripts/linkedin_easy_apply.py tabs
```

The snapshot returns element references such as `e17`. Act on a reference only from the latest
snapshot:

```bash
python3 <skill-dir>/scripts/linkedin_easy_apply.py click e17
python3 <skill-dir>/scripts/linkedin_easy_apply.py fill e24 'verified answer'
python3 <skill-dir>/scripts/linkedin_easy_apply.py select e31 'Germany (+49)'
python3 <skill-dir>/scripts/linkedin_easy_apply.py check e38
python3 <skill-dir>/scripts/linkedin_easy_apply.py uncheck e40
python3 <skill-dir>/scripts/linkedin_easy_apply.py press Enter
python3 <skill-dir>/scripts/linkedin_easy_apply.py upload <ws>/people/<p>/roles/<dir>/Hanna_Levi_CV.pdf
```

`upload` accepts `.pdf`, `.doc`, `.docx`, and `.rtf`.

**Through the extension bridge, `upload` can fail** with `DOM.setFileInputFiles: Not allowed`, and
the CLI session then stays stuck in a file-chooser modal state (every later command refuses to run;
`detach` and `attach` again to clear it). Prefer selecting a resume already stored in the person's
LinkedIn account and check it by hash first. When a fresh file must go in, the working route
(verified on GitHub's uploader, 2026-10-11) is in-page: `fetch` the file from an https URL the page
can read, wrap it in a `File` inside a `DataTransfer`, assign it to the `input[type=file]`, and
dispatch `change`; then verify the upload took on the site itself, not by the input's `files` count,
which the site's handler may reset. A local path is not reachable this way. When no https copy
exists, stream the file in as base64: the controller's command line on Windows tops out near 8,000
characters, so append chunks of about 1,800 characters to `sessionStorage` (page globals do not
survive between `eval` calls), then decode, wrap in a `File`, and attach. Verified 2026-10-12 on a
careers form whose cookie banner also had to be dismissed before the submit click landed.

**On LinkedIn itself, never pick a file input by searching the page.** The open messaging
overlay keeps its own attachment inputs (in shadow DOM), and setting a file on one attaches the CV to
an unsent message draft in whatever conversation is open. The Easy Apply resume input does not exist
until "Upload resume" is clicked. The working route (verified 2026-10-14): temporarily wrap
`HTMLInputElement.prototype.click` so a `type=file` click stores the element instead of opening a
chooser, click "Upload resume" in the dialog, set the `File` on the captured input, dispatch
`input` and `change`, restore the original `click`, then confirm the resume list shows the new file
dated today and checked, and that no attachment sits in the messaging overlay.

Do not pass passwords, one-time codes,
recovery answers, or other credentials to `fill`. If LinkedIn requests any of them, park the form
for the person.

## Easy Apply form mechanics

- **The posting body is not in the accessibility snapshot.** Read it with `text`, save it as
  `job-description.md`, then open the form.
- **Search URL filters:** `f_AL=true` (Easy Apply only), `geoId` plus `location`, and
  `f_TPR=r2592000` (past month). Each results page renders about 7 cards until the list is
  scrolled; scroll the list container before snapshotting.
- **Forms are one page or two to five pages.** One-page forms show Submit straight away. Multi-page
  forms step Contact, Resume, Additional Questions, Review. Scope every button search to the
  dialog: the job carousel behind it has its own "Next" button, and clicking that one does nothing
  to the form.
- **"Follow <company>" is pre-ticked on every form.** Untick it. Following a page is a social action
  nobody authorised.
- **Saved answers prefill.** LinkedIn reuses earlier answers (years with Python, React, and so on)
  and pre-selects the last resume used. Check every prefill against `profile.md`; a prefill is not a
  fact. That includes the **cover letter box: it can arrive holding the letter written for the
  previous company**, addressed to them by name. Replace it or clear it on every form.
- **Education is pulled from the LinkedIn profile, not from `profile.md`.** It can carry wrong
  years, a school of "N/A", or an empty entry whose required School field blocks Next. Correct
  entries to the compiled facts in the form, or use "Delete education" then "Remove from your
  application?". That removes the entry from this one application only, not from the profile.
- **Knockout questions arrive as typed fields.** Years-of-X take a whole number of at most 20
  characters; answer from the numbers in `profile.md`. Degree yes/no follows the Settings line
  `Degree yes/no answer:`. Salary and bonus expectations (unless Settings give a figure),
  contractor or invoicing status, work rights in another country, and anything else the file does
  not hold: discard the draft, `ledger.py --person <p> defer` the role with `--needs` naming the question, and
  ask. Do not guess.
- **The Easy Apply control can be a button or a link.** Both carry the name "Easy Apply to this
  job". Match either role before concluding the posting has no Easy Apply.
- **There is a daily Easy Apply cap.** After a few dozen submissions in one day, clicking Easy Apply
  opens "You reached today's Easy Apply limit" instead of the form. Stop sending for the day, defer
  the remaining fits with `--needs "LinkedIn daily Easy Apply limit reset"`, and resume the next
  day. Heavy browsing on the same day can also stop job descriptions from loading (only loading
  placeholders appear). Pause when that happens rather than reloading.
- **Hash the stored resume before the first send.** The resume radio list shows names and dates
  only. Fetch the stored file from the page and compare its SHA-256 with the verified build.
- **Confirmation has two shapes.** Usually a dialog headed "Your application was sent to
  <Company>!". Sometimes only a "Next best action" dialog appears, while the job page shows
  "Application status: Application submitted". Either one is proof; a click alone is not.
- **The job title can contain "Applied"** ("Applied AI Engineer"). Detect an earlier application by
  the missing Easy Apply button or an "Application submitted" status, never by the word.

## Before the final submit

- The posting title, company, and location are visible and saved in `job-description.md`.
- The exact role is absent from both CSVs.
- The attached file is the current verified CV.
- Every answer comes from `profile.md`. A salary number is never invented.
- No CAPTCHA, identity check, security warning, account lock, or ambiguous state is present.

Take one screenshot of the completed review state into the role directory. Submit only when the
recorded authority covers it.

## Proof and cleanup

A click is not proof. After submit, screenshot the named LinkedIn confirmation state into the role
directory and check the mailbox for an acknowledgement when one exists. Then record it
(`ledger.py --person <p> add ... --status sent --channel linkedin-easy-apply --proof <screenshot>`), read the row
back with `ledger.py --person <p> find`, and run `ledger.py --person <p> validate`.

Treat the first confirmed application on a new setup as the test before running a batch.

Detach when finished. Detach leaves the person's Chrome session open:

```bash
python3 <skill-dir>/scripts/linkedin_easy_apply.py detach
```
