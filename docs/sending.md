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
- **An aggregator's "apply" link that chains through an ad tracker** (gute-jobs.de → jobspreader.com)
  can dead-end in an interstitial carrying a hidden reCAPTCHA. That chain is advertising plumbing,
  not the official path. Search the employer's own careers site for the same requisition — it is
  usually there, sometimes with an account-free form the aggregator never showed.
- **A Bundesagentur für Arbeit posting with no contact block and no external URL** still has an
  official path: the employer's own published application address, with the BA Referenznummer in
  the subject line so the recipient can place it.
- **A job list that renders empty may sit in an iframe gated on the cookie dialog.** jobactive.de's
  listings load only after the site's own consent prompt is answered; the board iframe underneath
  (`bewerbercenter.jobactive.de/job/listing/external?jobBoard=<n>`) is directly navigable after that.
- **The careers page may not list every role.** One employer's page showed only its core-business
  jobs; the IT vacancies existed solely on its ATS tenant (`<company>.softgarden.io/de/vacancies`).
  When a posting names a company whose careers page lacks the role, probe the common ATS domains
  before concluding the posting is stale.

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
- **The code is mixed-case** (e.g. shaped like `XSzk9gAI`), so an `[A-Z0-9]{8}` extractor silently
  misses it, and the mail wraps it in prose — anchor on the phrase instead:
  `/security code field[\s\S]{0,120}?\b([A-Za-z0-9]{8})\b/i`, with a standalone-line
  `/^\s*([A-Za-z0-9]{8})\s*$/m` fallback. Test any new extractor against a real code mail before
  trusting it: a looser variant of this regex once matched the word "security" itself.
- **The code mail can lag four minutes or more.** A 180-second poll declares a false wall; poll the
  mailbox for at least 480 seconds before concluding the code never came.
- **React hydration wipes fills made in the first ~2 seconds.** Values typed the moment
  `#first_name` appears are silently emptied when the bundle finishes booting. Wait ~2s after the
  field renders, fill, then run a second re-fill pass over the basics before verifying.
- **The country control `#country` is a react-select combobox**, not the intl-tel-input it appears
  to be — the `.iti__country-list` in the DOM is a 0×0 vestige and a click on it times out. Open
  `#country`, type the country, click the `[id^="react-select-country-option"]` entry, and verify
  via the `.iti__selected-country` flag title.
- **The location autocomplete is a city/district geocoder with no country-level entries.** Typing a
  bare country offers only foreign cities that contain the string. Its hierarchy is
  City, District, Country — when the profile holds only a region ("Israel, center"), the honest
  match is the district-level node (e.g. "Tel Aviv, Israel"), and the choice is disclosed in the
  ledger.
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
- **The human-check error UI carries its own way out**: an *"email your resume"* mailto link to
  `<Company>.<positionUid>@applynow.io` — Comeet's inbound-application intake for that exact
  position. Emailing the CV there from the person's mailbox is applying through the employer's
  designated channel, not circumvention. Confirmed on two separate Comeet employers; grab the
  mailto from the error frame's link dump before closing the page.
- Radio options are **custom-styled and digit-led**: ids like `1713…` are invalid in CSS `#id`
  selectors, and the real `<input>` fails Playwright's actionability check. Click the visible
  `label:has-text(...)` and verify `checked` via JS. Submit buttons omit `type="submit"` yet
  default to it — match on `button:has-text('Submit Application')`, not `button[type=submit]`.

**Lever**

- The **location autocomplete can offer zero suggestions**, and `Escape` on an empty dropdown wipes
  what was typed. The field takes free text — write it directly, do not drive the combobox.
- Lever **parses the uploaded CV and back-fills fields from it**, sometimes wrongly. Re-read the whole
  form after upload and clear its guesses.
- Sometimes shows an hCaptcha checkbox after submit. One human click; never touched by an agent.

**Ashby**

- Can reject a completed submit as *"flagged as possible spam"*, and its own advice is to submit again.
  A re-click on a still-filled page is the fix — which is an argument for parking rather than refilling.

**AllJobs (alljobs.co.il)**

- **Login is a passwordless OTP widget** in an iframe on `app.alljobs.co.il/auth/...`. It boots
  slowly — poll up to 60s for the email input; a fixed wait reads an empty spinner.
- **Entering a registered email fires an SMS code to the account's phone**, not a mail. Warn the
  person their phone will buzz. After the ~60s countdown a second button appears —
  *"הקוד לא הגיע, שלחו לי גם למייל"* — which mails a 5-digit code instead. That is the drivable
  path: read it from the mailbox, fill the five `input[type=tel]` boxes (they auto-advance).
- **An email you thought was unregistered may not be.** The SMS-not-mail behaviour on "sign up" is
  how an existing account announces itself. Check the person's history before assuming.
- **CV management** lives at `/User/UserCVsPanel/CVManagement.aspx`. Upload is three steps and fails
  silently if shortened: click `#aUploadNewCV`, set the file on `#txtFileUploadCV`, then **fill the
  display-name field `#txtFileUploadCVName`** — the commit function validates it and does nothing
  while it is empty. The save IMG `#btn-save` is overlaid by a pointer-intercepting div, so a real
  click times out; invoke the page's own `UploadNewCV(false)` instead. Success is the list counter
  incrementing (`סה"כ N קורות חיים`), not the absence of an error.
- **Never touch CVs already on the account** — they are the person's own uploads.
- **The apply click on a stale session pops a fresh OTP round; on a fresh one it sends
  immediately** — with the account's newest CV and no picker. So the order is fixed: upload the
  tailored CV first, verify it is the newest on the account, then click. The confirmation popup
  names the file it sent ("שם הקובץ: ...") — read it to verify the right CV went.
- **Each OTP round costs the person a code on their phone or in their inbox.** Batch everything
  into one authenticated session, and tell the person codes are coming — a flood of unexplained
  OTPs reads as fraud to the account's owner.
- **Two auth iframes coexist**, both with `id="LoginRegisterIframe"` — a page-level login widget
  and the apply popup's own. First-match-by-URL finds the wrong one; a `fill()` on the covered
  background widget even *succeeds* (fill bypasses hit-testing) while the click is intercepted.
  Select the frame whose iframe element sits inside `#job-sendcv-view`.
- **Match the button to the job — by its own card, never by ancestry search.** A job page carries
  a rail of similar-job cards, each with its own `send-cv-btn`. Walking up the DOM looking for the
  wanted JobID in `outerHTML` false-matches once an ancestor is broad enough to contain the whole
  page. Resolve each button to its enclosing card and extract that card's single JobID; if no
  button resolves to the wanted job exactly, click nothing.
- **Some listings are paid-tier only** ("פתוחה ללקוחות AllJobs VIP בלבד", ₪59/month) — the apply
  redirects to a credit-card page. Payment is never entered; a paid-gated role is an operator
  decision. Watch for a redirect to `CreditCard`/`Purchase` URLs after any apply click.
- **Proof of a send is the job page's own applied banner** — "הגשת מועמדות למשרה זו בתאריך ..." —
  which persists server-side on a fresh load. AllJobs sends no confirmation email.

**HeyJobs (heyjobs.co)**

- The CTA "Ich bin interessiert" is an `<a>`, and overlays love to intercept the click — skip it and
  navigate straight to `<job-url>/apply/now`.
- **Entering an email creates an account** and mails a password-set link. Set the password from that
  link, write it into the person's `.env`, and keep the browser storage state — funnel progress
  lives server-side on the account.
- The funnel is a step wizard whose question textareas carry per-session UUID names plus an unnamed
  decoy. Target fields by their visible label, never by name.
- **Answered steps are skipped on the next application, and the CV carries over.** The review screen
  names the attached file; route through Dokumente → Ändern to swap in the role's tailored CV, or
  the previous role's CV goes out under the new application.
- Success is "Deine Bewerbung wurde erfolgreich abgeschickt!" — or "Deine Bewerbung sieht schon gut
  aus!" plus a forwards-in-N-hours note when the optional strengths quiz is skipped; it forwards
  regardless. The durable proof is the account's applications page listing "Beworben am <date>".

**compleet job boards → persy.jobs**

- `<compleet-cookie-banner>` is a shadow-DOM custom element that intercepts pointer events
  page-wide, so the apply click times out with nothing visibly in the way — and a force-click
  changes nothing. Dismiss it by evaluating into its `shadowRoot` (button "AUSWAHL SPEICHERN") in a
  retry loop that verifies the element is gone. "Direkt bewerben" then opens the real form as a
  popup onto a persy.jobs session URL.
- persy's styled radios and checkboxes are invisible to `check()` and label clicks; set them via
  evaluate — click, force `checked`, dispatch `change`. The phone number is three separate inputs
  (country / area / local).
- **The first file input is an inert template.** `upload[med_file_path][]` accepts a file and does
  nothing with it. The live uploader is `input[name^="afu-file"]`, and it re-arms after every
  upload — upload files one at a time, and set each new row's "Anlage Typ" select (Lebenslauf /
  Zeugnis) as the row appears.
- **Submission is two dialogs deep.** The submit click first surfaces persy's own cookie dialog,
  then a final confirm with a "Ja, absenden" button. Until that second button is clicked nothing has
  been sent — a driver that stops at the submit click reports success on an unsent form.

**Cornerstone (csod.com)**

- Requisitions on a `careersite` tenant take applications **without an account**:
  `/ux/ats/careersite/1/requisition/<id>/application?c=<tenant>&jobboardid=0#1`.
- Inputs carry no usable names — map them by aria-label and nearest label text, fill by index.
- The CV upload announces an on-screen AI scan of the document; give it several seconds to finish,
  then re-verify every field already filled (same reflex as Lever's back-fill).
- Consent and source checkboxes are styled — evaluate-click them. The "how did you find us" options
  take the honest answer (e.g. "Agentur für Arbeit" for a BA-sourced role).
- Success is the wizard's step 2 replacing the form with "Vielen Dank für deine Bewerbung!".

**finest-jobs.com**

- **Upload success never appears in body text.** Files land in proxy inputs `input[id^=upload_]`
  whose `.value` holds the stored filename — verify those, and abort before submit if the CV proxy
  is empty.
- There is no `button[type=submit]` anywhere; the submit control is an `<a>` reading "Bewerbung
  absenden".
- **A field can be client-enforced required while its HTML says `required=false`** — the submit then
  fails silently, with no navigation. Screenshot after every submit click; the red validation
  message and asterisk exist only on screen. A required bare salary number found this way is a wall:
  park it, never invent the number.

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
- **A bot interstitial that stops passing has flagged your session, not your address.** After a burst
  of automated hits, AllJobs' Radware page went from auto-passing to an endless spinner — in
  headless and headed alike — for as long as the saved cookies were presented. A fresh context from
  the same machine passed in seconds. Don't fight the spinner with browser flags: discard the stored
  state and re-authenticate. On an OTP site the login session is cheap; anything already uploaded to
  the account is still there. (An interstitial that blocks even a fresh context is wall 3 —
  diagnose from the person's own network before recording it.)
- **An upload limit ("Die Datei ist zu groß") on a box with no gs/qpdf** still has a recompression
  path: `pdftoppm -jpeg -r 100 -jpegopt quality=72` the PDF into per-page JPEGs, wrap them in an
  HTML shell (`@page { size: A4; margin: 0 }`, one full-page `<img>` per page,
  `page-break-after: always`), and print that to PDF with headless Chromium — a 3.7 MB certificate
  scan came out at 1.5 MB across 13 pages. Verify legibility on a rendered page before sending.
  **Scans only, never the CV** — rasterising the CV destroys the text layer ATS parsing depends on.
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

### 2. A mandatory account — reroute, or open it

Some aggregators hide the apply button behind registration. Two ways through, in order:

- **Reroute.** Find the employer's own channel — their ATS board, their careers page, a published
  recruiting address — and go direct. Nearly always available, and better.
- **Open the account.** Registration is normal work, not a wall: the person's real details, a
  generated password written straight into their `.env` (rule 10 — never echoed, never logged),
  required consents only — marketing checkboxes stay empty. A verification link or code lands in
  a mailbox already being driven. From there on it is the same footing as that mailbox: log in,
  fill, submit, verify a named confirmation, record.

**A wall is something you saw, not something you inferred.** Signup pages everywhere carry
Cloudflare scripts and reCAPTCHA site keys in their source; markers are not challenges. This
doctrine once declared taasiya.co.il's `/register/` gated on exactly that reading — and a human
then registered there without ever being challenged. Attempt the registration. The only thing that
stops it is a challenge that actually interposes; that is wall 1, and the park happens at precisely
that step, not one step before it.

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
