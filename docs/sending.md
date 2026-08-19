# Sending — the employer's own channel, and the walls in front of it

Nothing is sent unless intake question 4 authorised it. Approving a CV is not authorising a send —
that is rule 6 in [SKILL.md](../SKILL.md), and it is the rule people are most surprised by, which is
exactly why it is written down.

Every application goes through the **employer's own official path**. Finding that path is its own step,
and the obvious URL is frequently the wrong one.

---

## Finding the real apply path

Recon each posting before touching a form. The patterns that recur:

- **A careers URL that redirects behind a bot shield** and never renders. The ATS embed underneath it
  usually works — `job-boards.greenhouse.io/embed/job_app?for=<slug>&token=<id>`.
- **A contact form at the top of the job page with no file input at all.** A CV cannot be attached to
  it. The real form is often an embed further down the page.
- **A domain that does not resolve**, whose posting ends by telling applicants to email a named
  person. That instruction *is* the official path. Use it.
- **No form at all** — some companies only ask for a CV and a short note, by email.
- **Comeet** boards: the standalone apply form is
  `comeet.co/jobs/<companyUid>/<positionUid>/apply?token=<token>`, and all three identifiers come out
  of a JS blob in the careers page HTML. The form cannot be submitted by a driven browser, but each
  position publishes an email address that reaches the same pipeline.

Greenhouse exposes its required fields without authentication, which is the cheapest way to know in
advance whether a form will block:

```bash
curl -s "https://boards-api.greenhouse.io/v1/boards/<token>/jobs/<id>?questions=true"
```

There is no `boards-api.eu.greenhouse.io`. The US host serves EU-hosted jobs.

---

## Form mechanics that cost hours

Each of these was paid for once. Read them before driving a form, not after.

**Greenhouse**

- Submission is gated behind an **emailed 8-character code**. Click submit, read the code from the
  inbox, fill `#security-input-0` through `#security-input-7`, submit again. A jump to ~13 console
  errors is the normal signature of that gate, not a failure. A stale code is cheap — clicking Submit
  again mails a fresh one.
- React forms carry `id` attributes but **empty `name` attributes**. Target by `id`. Multi-selects have
  literal brackets in the id. Dropdowns are react-select, not `<select>`.
- **react-select keeps its chosen option in component state**, rendered as a `[class*="single-value"]`
  sibling. `el.value` is *always* the typed search text — so a required-field check that reads
  `el.value` reports a fully-answered form as empty. Read the single-value node.
- The **phone-country control is a combobox**, not a `<select>`. Click it, type the country one key at
  a time, then `Enter`. Confirm from the accessibility snapshot, not the DOM: the visible value and the
  underlying state can disagree.

**Comeet**

- Accepts `.pdf`, `.doc`, `.docx`, `.rtf` **only** — no `.txt`, no paste-text fallback.
- Angular dropdowns can have the **question itself as the element id**, e.g.
  `id="How did you hear about us?"`.
- The resume input is `opacity: 0`, so a driven click fails as "not visible". Click
  `label.clickableLink[for='cv']` instead.
- **Refuses driven submissions outright.** A valid, fully-filled form returns *"session verification
  failed due to a human check error"*. That is reCAPTCHA scoring the browser, not a bad field.
  Refilling changes nothing. **Do not attempt a third variation.**

**Lever**

- The **location autocomplete can offer zero suggestions**, and `Escape` on an empty dropdown wipes
  what was typed. The field takes free text — write it directly, do not drive the combobox.
- Lever **parses the uploaded CV and back-fills fields from it**, sometimes wrongly. Re-read the whole
  form after upload and clear its guesses.
- Sometimes shows an hCaptcha checkbox after submit. One human click; never touched by an agent.

**Ashby**

- Can reject a completed submit as *"flagged as possible spam"*, and its own advice is to submit again.
  A re-click on a still-filled page is the fix — which is an argument for parking rather than refilling.

**Everything else**

- **A file upload needs an open file chooser.** Click the attach button first; a hidden
  `<input type=file>` cannot be targeted directly.
- **monday.com forms use downshift comboboxes.** A direct click on the option can hang. Open the
  control, `ArrowDown` to the option, `Enter`.
- **Read a hand-rolled careers form's own JavaScript before filling it.** WordPress forms commonly post
  to `wp-admin/admin-ajax.php` in two steps — an upload call returning a URL, then a submit call taking
  it as a field — with a reCAPTCHA token appended by a handler nothing else reveals. Five minutes in
  the bundle beats an hour of guessing at an error code.
- **Some job boards serve a bot interstitial on first contact.** *"Verifying your browser before
  proceeding"* on navigation one; navigate again and it passes.
- **Every form runs invisible reCAPTCHA.** An automated fill can be scored down silently. **No
  submission counts until a confirmation page is on screen** — for Greenhouse, a URL ending
  `/confirmation` titled "Thank you for applying"; for a monday.com form, the form replacing itself
  with "Thank you!".

**The uploaded filename is what the recruiter sees.** Stage every upload as `<Person_Name>_CV.pdf`
inside its per-role directory. A file called `..._CV_Acme.pdf` tells Acme it is one of a batch.

---

## Email sends

`scripts/mailbox.py` sends from the person's own address. Two things it learned the hard way:

- **A send that hangs is a blocked port, not a slow server.** Cloud hosts commonly block outbound
  25 and 465 (Hetzner does); the socket sits in `SYN-SENT` forever. Port 587 with STARTTLS is
  usually open — set `SMTP_PORT=587` in the person's `.env`, and `mailbox.py` switches to STARTTLS
  on that port by itself.
- **`make_msgid()` with no domain argument stamps the machine's hostname** into the Message-ID
  header of every mail. Headers are part of the application; a hostname that says automation is a
  fingerprint. `mailbox.py` stamps the sender's own mail domain instead.

---

## Walls

Three recur, and the difference matters, because two have workarounds and one does not.

### 1. A human-verification challenge — no workaround, by design

A visible hCaptcha, a Cloudflare Turnstile widget, or an invisible reCAPTCHA token the form's own
JavaScript demands.

**These are not solved and not bypassed.** Solving one is claiming to be a person, to a system that
asked precisely because it wants a person. This is rule 4 in [SKILL.md](../SKILL.md) — a line, not a
capability gap.

Two things worth knowing:

- **It can fail silently.** A filled, valid form that returns an error is being scored, not misfilled.
  **Two attempts, then stop.** Never a third variation.
- **It can escalate on the submit click.** A widget that sat dormant through the whole fill can turn
  into an image puzzle at the end. The answer is not a stealth plugin or a patched
  `navigator.webdriver`. It is the park pattern below.

### 2. A mandatory account — reroute

Some aggregators hide the apply button behind registration. **No third-party account is ever created in
someone's name** — it means choosing and storing a password as them and signing them up to whatever the
marketing checkbox says.

The workaround is nearly always available and better: find the employer's own channel — their ATS
board, their careers page, a published recruiting address — and go direct.

### 3. A network or WAF block — diagnose before recording

A host answering `403` or a vendor-specific code may be blocking the *address*, or it may be blocking
the *shape of the request*. These look identical and are not.

**Run the comparison before writing anything down.** Retry the same request from a different network
the person controls — their own machine. If it succeeds, the block was the address, and routing through
their machine is legitimate: it is their hardware and their application.

If it fails from there too — a DataDome challenge body, `geo.captcha-delivery.com`, *"Please enable JS
and disable any ad blocker"* — the block is aimed at the automation fingerprint itself. No profile,
address, or header changes it. That is wall 1, and the remedy is their own everyday browser.

---

## The park pattern

When a wall stops a submission, the application does not die. It gets **parked**: filled to completion
in a real browser on the person's own machine, CV attached, every question pre-researched and answered
— and stopped **one click short of Submit**.

They review and click. This keeps the human as the one who submits, which is what the anti-automation
systems are actually asking for, while removing the twenty minutes of typing.

Rules for a park:

- **Never auto-detect success.** A loose body-text match on `thank you|submitted|received your` will
  report a submission that never happened. Success is a confirmation page you can name, or a mail
  message-id, and nothing else.
- **Leave honeypot fields blank** — anything matching
  `/real human|leave this (line|field) blank|summarize this job/i`. Filling one is what marks the
  submission as spam. This is rule 5 in [SKILL.md](../SKILL.md).
- **Hand over any code the employer mails**, do not enter it. Reading a Greenhouse security code out of
  the inbox and giving it to the person is help. Typing it yourself is automating the
  confirm-you-are-human step.
- **Close the parked window the moment they say they have handled it.** A stray window fights them.
- Say exactly what is left to do, in one line. "Open, review, click Submit" is a complete handover.

A parked role is logged with the specific blocker named and the CV ready to send. **A blocked role is
never quietly recorded as sent.**

---

## Recording a send

One row per application in `applications.csv`, written **after** the proof exists — not after the
click. The proof is a confirmation page or a message-id from the mail server.

**Archive what was sent, the moment it is recorded.** Copy the exact artifacts that went out — the
rendered PDF, the `cv.html` that produced it, the email body or form answers, and the
`job-description.md` capture — into `people/<person>/sent_archive/<date>-<role-dir>/`, with a short
`sent.md` naming the channel, recipient, subject and proof id. `created_data/` is a workshop; its
files get edited, re-rendered and reused. The archive is the record of what the employer actually
received, and nothing in it is ever edited after the fact.

The two columns worth sorting by:

- **`added_technologies`** — the study list. What to close before that company's interview.
- **`response`** — kept current from the mailbox, not from memory.

Every claim in this pipeline is verified from the authoritative source. Your own log is not evidence
about the world; the employer's confirmation is. See [verification.md](verification.md).
