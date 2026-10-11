# LinkedIn Easy Apply

This channel exists only for a person who has explicitly authorised LinkedIn Easy Apply and
submission in writing. Record that authority in their `profile.md` before attaching to Chrome.

## Shape of the pipeline

The browser is the person's existing Chrome session on their own machine. The controller connects
through Microsoft's Playwright browser bridge, then performs one observed action at a time:

1. Snapshot and screenshot the current page.
2. Read the role, company, location, requirements, and application state.
3. Check the exact role against `applications.csv`.
4. Decide one action from the verified profile and standing form-answer rules.
5. Act through the element reference returned by the latest snapshot.
6. Snapshot and screenshot again before the next action.

There is no unattended loop. The controller does not scrape results, message people, copy browser
storage, or keep a second login profile.

## One-time runner setup

The person's Windows runner needs Node.js, `@playwright/cli`, Google Chrome, and the official
Playwright MCP Bridge extension in the Chrome profile that holds the LinkedIn session.

```powershell
npm install --global @playwright/cli
```

Install the Playwright MCP Bridge from the Chrome Web Store. An administrator may instead put its
published extension id in Chrome's `ExtensionInstallForcelist` policy. Chrome must refresh policy or
restart once before the extension appears. Do not close a person's active Chrome session merely to
speed that up.

## Controller

Run the controller from the machine that can SSH to the Windows runner:

```bash
export LINKEDIN_RUNNER='user@runner'
python3 scripts/linkedin_easy_apply.py doctor
python3 scripts/linkedin_easy_apply.py attach
```

The bridge attaches to the signed-in Chrome profile without copying cookies. Use a dedicated
session name when more than one application operator is active:

```bash
python3 scripts/linkedin_easy_apply.py --session role-123 attach
```

## Screenshot, analyse, act loop

Navigate only to a LinkedIn URL. The controller rejects other hosts.

```bash
python3 scripts/linkedin_easy_apply.py goto 'https://www.linkedin.com/jobs/view/123/'
python3 scripts/linkedin_easy_apply.py snapshot
python3 scripts/linkedin_easy_apply.py screenshot 'C:\path\before.png'
```

The snapshot returns stable element references such as `e17`. Act on a reference only from the
latest snapshot:

```bash
python3 scripts/linkedin_easy_apply.py click e17
python3 scripts/linkedin_easy_apply.py fill e24 'verified answer'
python3 scripts/linkedin_easy_apply.py upload 'C:\CVs\Person_Name_CV.pdf'
python3 scripts/linkedin_easy_apply.py snapshot
```

Do not pass passwords, one-time codes, recovery answers, or other credentials to `fill`. If LinkedIn
requests any of them, park the form for the person.

## Before the final submit

- The posting title, company, and location are visible and saved in `job-description.md`.
- The exact role is absent from the ledger, including earlier `no` or `dropped` decisions.
- The attached filename is the current verified CV.
- Every answer comes from `profile.md`. A binary degree question follows the person's recorded
  instruction. A salary number is never invented.
- No CAPTCHA, identity check, security warning, account lock, or ambiguous state is present.

Take one screenshot of the completed review state. Submit only when the person's recorded send
authority covers it.

## Proof and cleanup

A click is not proof. After submit, capture the named LinkedIn confirmation state and check the
mailbox for an acknowledgement when one exists. Then write and read back the ledger row, verify the
CSV column count, and archive the exact CV, posting, form answers, and proof.

Detach when finished. Detach leaves the person's Chrome session open:

```bash
python3 scripts/linkedin_easy_apply.py detach
```
