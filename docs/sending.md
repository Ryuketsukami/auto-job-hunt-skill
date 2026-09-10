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
- **A published email hidden behind Cloudflare's scrape-shield** renders as `[email protected]` with
  the real address in a `data-cfemail` hex attribute. Decode it: XOR each byte with the first byte
  of the hex string. The address is public to every human reader — decoding it is reading the page,
  not harvesting.
- **Comeet** boards: the standalone apply form is
  `comeet.co/jobs/<companyUid>/<positionUid>/apply?token=<token>`, and all three identifiers come out
  of a JS blob in the careers page HTML. A driven submission may pass or be refused by its
  reCAPTCHA scoring (see Form mechanics) — attempt the form first; each position also publishes an
  email address that reaches the same pipeline.
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
- On the wire the gate announces itself as **HTTP 428** on the submit POST. 428 is the code gate
  arming, not an error — do not retry the POST as if it failed; go read the mailbox.
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

- **The apply form's iframe lazy-loads**, on some embeds only after interaction. A fixed wait finds
  no frame at all. Poll for it (15 × 2s worked) and, between attempts, scroll the page and click the
  apply trigger again — the frame appears only once its loader has been provoked.
- **Hidden Angular inputs fail Playwright's actionability check** even when their control is plainly
  on screen. JS-click the `label[for=<id>]` instead, then verify the input's `checked`/`value` via
  JS — the label is the visible control; the input never becomes clickable.
- Accepts `.pdf`, `.doc`, `.docx`, `.rtf` **only** — no `.txt`, no paste-text fallback.
- Angular dropdowns can have the **question itself as the element id**, e.g.
  `id="How did you hear about us?"`.
- The resume input is `opacity: 0`, so a driven click fails as "not visible". Playwright's
  `set_input_files` on the hidden `#cv` input works directly; clicking
  `label.clickableLink[for='cv']` is the fallback.
- The **phone-country selector is a button + search combobox and its default can be wrong**
  (a fresh en-US context got "Germany +49"). Click the button, type the country into the
  revealed `input[placeholder='Search']`, click the option, then verify the button shows the
  right prefix before filling the number.
- **May refuse a driven submission — or accept it.** The invisible reCAPTCHA scores each
  submission: the same rig on the same day was refused on one employer's embed and got a clean
  on-page *"Thank you <name>!"* confirmation on another's first submit. Always attempt the form.
  When it refuses, a valid, fully-filled form returns *"session verification failed due to a human
  check error"* — that is the score, not a bad field. Refilling changes nothing. **Do not attempt
  a third variation.**
- **The human-check error UI carries its own way out**: an *"email your resume"* mailto link to
  `<Company>.<positionUid>@applynow.io` — Comeet's inbound-application intake for that exact
  position. Emailing the CV there from the person's mailbox is applying through the employer's
  designated channel, not circumvention. Confirmed on two separate Comeet employers; grab the
  mailto from the error frame's link dump before closing the page.
- Radio options are **custom-styled and digit-led**: ids like `1713…` are invalid in CSS `#id`
  selectors, and the real `<input>` fails Playwright's actionability check. Click the visible
  `label:has-text(...)` and verify `checked` via JS. Submit buttons omit `type="submit"` yet
  default to it — match on `button:has-text('Submit Application')`, not `button[type=submit]`.

**AllJobs (alljobs.co.il)**

- Job-detail pages bot-wall a guest headless browser but render fully under the person's own
  logged-in session (`storage_state`).
- The plain "הגשת מועמדות" anchor is a one-click `SendCV(jobId)` that sends a **stored** CV
  immediately. The adjacent gear "עדכון קורות החיים לפני שליחה" (`ShowSendCVWithEdit(jobId)`)
  opens a modal with a stored-CV selector, an "הוספת קובץ חדש" mode whose **visible**
  `#txtFileNew` input takes a per-application upload (stored CVs untouched), an optional
  1000-char cover-note textarea (`ShowPreeLetter()`), and its own submit
  (`SubmitForm(JobWithMailForm)`). Success is an on-page dialog: *"קורות החיים הועברו
  בהצלחה!"*.
- Two elements share `ng-click="DisplayCVArea()"` (the mode toggle in each direction), so
  reading the toggle's text via `.first` can grab the hidden twin. Verify the mode by the
  visibility of `#txtFileNew` and the file set on it — never by toggle text.
- A hidden `#inp_UploadCvFile` (a separate "VipBox" component) sits in the page source;
  `set_input_files` on it silently goes nowhere. Target `#txtFileNew` inside the modal.
- **Some listings are VIP-paywalled**: the job's own apply and update-CV controls render as
  plain links to `User/Register/CreditCard.aspx?JobID=<id>` (the paid-package purchase page)
  and no `SendCV(<id>)` handler exists for that id — while other jobs on the same page keep
  normal handlers, proving the account itself is fine. That is a seen wall: log `blocked`.
  Buying the package is the person's decision; payment fields are never entered. If the
  person declines the purchase, retag the row `deferred` (see The park pattern).

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
- **The bot interstitial re-arms after ~7 rapid page loads even on a valid logged-in session** — a
  94-character "Verifying your browser" body carrying an Incident ID — and the cooldown is measured
  in **hours**, not minutes. So probing costs sends: consolidate the day's AllJobs work into **one
  scripted pass** (upload, questions, apply, verification in a single run), never an iterate-and-retry
  loop of page loads.
- **Employer screening questions load async, after the apply modal.** The "המעסיק ביקש" block can
  take tens of seconds to appear — poll ~30s for it before concluding the job has no questions, or
  the application goes out with them unanswered.
- The success dialog's wording varies by flow — match `הועברו בהצלחה|נשלחו בהצלחה|נשלחה בהצלחה`,
  not a single fixed phrase.
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

**Drushim (drushim.co.il)**

- Job URLs are strictly `/job/<numeric-id>/<8-hex>/` — every other shape 404s. The posting (title,
  description, requirements, a JSON-LD JobPosting block) is **server-rendered in the raw HTML** even
  though `__NEXT_DATA__` is near-empty — fetch raw before concluding the SPA hides it. The apply
  button ("הגשה") is the opposite: client-hydrated, zero apply markup in static HTML, so applying
  needs a real browser.
- Applying needs an account. The registration modal's fields carry no usable ids — key them **by
  placeholder** (שם פרטי / שם משפחה / מייל / סיסמה / טלפון). The one required checkbox bundles terms
  and marketing together — there is no separate marketing consent to decline. The city field (ישוב)
  presents as required but the button enables without it.
- A signup 400 *"כתובת האימייל כבר רשומה במערכת"* means the person already has an account —
  **check before assuming they don't** (same lesson as AllJobs). "לכניסה מהירה" is a password login,
  not passwordless. Recovery runs through their mailbox: שכחתי סיסמה → `#reset-request-email` →
  "איפוס" → a mail from `alerts@drushim.co.il` with a `ResetPassword.aspx?token=` link → a single
  `#newPassword` field and "יצירת סיסמה". **Passwords are 8+ characters, letters and digits only** —
  a symbol is refused. A reset kills their old password: tell them, and write the new one straight
  into `.env`.
- The logged-in apply modal (`div.ReactModalPortal`) lists the account's stored CVs as radios, each
  row dated ("נוסף בתאריך"); an `input[type='file']` inside the modal takes a per-application upload
  and auto-selects it. **Same-named files accumulate** — verify the *checked* radio's row carries
  today's upload timestamp, not just the right filename. Stored CVs are the person's own uploads;
  never touch them.
- **Scope the final submit to the modal**: `div.ReactModalPortal button:has-text('הגשה')`. The
  page's own הגשה sits behind the overlay, a generic selector matches it first, and the click times
  out as "intercepts pointer events".
- Proof is threefold: POST 200 to `api/cv/sendsinglecv/?JobCode=<id>`, the on-screen
  *"עבודה טובה! הגשת מועמדות למשרה"*, and the job card flipping to "הגשת ✓".

**Workday (myworkdayjobs.com)**

- The unauthenticated liveness check is the CXS API — the posting's `/job/<slug>` URL fetched via
  `/wday/cxs/<tenant>/<site>/job/<slug>` answers `jobPostingInfo` JSON.
- Everything is addressed by `data-automation-id`. The apply path: `/apply` →
  `a[data-automation-id='applyManually']` → `createAccountLink` →
  `input[data-automation-id='email'/'password'/'verifyPassword']`.
- **The create-account button is covered by an overlay `div[data-automation-id='click_filter']`**
  carrying the action's aria-label. The button beneath never receives a pointer event — click the
  overlay div, not the button.
- **The `beecatcher` input is a honeypot.** Leave it blank (rule 5).
- No email verification: account creation drops straight into the six-step wizard (My Information →
  My Experience → App Questions → Voluntary Disclosures → Review). Persist `storage_state` — wizard
  progress lives on the account and survives a new browser.
- Step-1 defaults follow the tenant's home country, not the job's (an Israel role opened on country
  Germany, phone prefix +49) — fix both. The step can hard-require Street / Postal Code / City;
  a profile that holds only a region cannot fill those. That is an ask-the-person, never an
  invention.

**Niloosoft Hunter minisites (minisite.niloos.ai)**

- Vacancy and apply pages live at `minisite.niloos.ai/vacancy/<24-hex>` and `/apply/<24-hex>`.
  Fields are keyed by placeholder; the CV upload input is `#cvFile`.
- reCAPTCHA v2 is enforced server-side and **the checkbox materializes on the submit click** — a
  widget absent through the whole fill is not absence of a wall. When it appears it is wall 1:
  park, one click short.

**HubSpot-embedded careers forms**

- A careers page (seen on Webflow) can carry its whole apply form as a HubSpot embed. The page
  source holds the config — `hbspt.forms.create({portalId, formId})`, loaded from
  `js-<region>.hsforms.net/forms/embed/v2.js` — but the form renders into an **iframe**: find the
  frame containing `input[name='firstname']`.
- Field names are HubSpot-standard: `firstname`, `lastname`, `email`, custom slugs like
  `which_position_are_you_applying_for_`, `resume` (file), `cover_letter` (textarea). Consent
  splits cleanly: `LEGAL_CONSENT.processing` is the required one;
  `LEGAL_CONSENT.subscription_type_<id>` is marketing — leave it unchecked. Submit is
  `input[type='submit']`.
- The form carries `g-recaptcha-response`, and a driven submission can surface a **visible
  reCAPTCHA image challenge on submit**. Wall 1 — park or defer, never a third attempt.

**Image-button careers modals**

- One hand-rolled Angular careers page (baba-entertainment.com) taught a general trap. Its
  mechanics: positions feed is a public S3 JSON (`.../careers/careers.json`), items `.career-item`,
  apply trigger `img[alt='apply-now']`, modal `app-apply-job-modal`, resume POSTed base64 in the
  body — one file, under 750 KB — success dialog *"Form successfully submitted!"*.
- **The trap: image buttons sharing a class.** `.btn-actions` matched BOTH the close X
  (`.close-btn.btn-actions`) and the submit graphic — a class-based click closes the modal and the
  driver reports success on an unsent form. The real submit was `img[alt='send']` inside
  `.send-btn`. **Match image buttons by their `alt`, never by a shared class.**

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

Three things worth knowing:

- **Know the badge from the challenge.** Invisible reCAPTCHA plants an `api2/anchor` iframe on the
  page — that is the corner badge, present on countless forms that will never challenge anyone. The
  challenge is the `api2/bframe` iframe (or a Turnstile / hCaptcha frame) **when it is visible**. A
  guard that treats the anchor as a wall defers half the internet; watch for a visible bframe
  instead.
- **It can fail silently.** A filled, valid form that returns an error is being scored, not misfilled.
  **Two attempts, then stop.** Never a third variation.
- **It can escalate on the submit click.** A widget that sat dormant through the whole fill can turn
  into an image puzzle at the end — or a checkbox can materialize where none existed. That
  materialized widget **is** a seen wall, as real as one that was there from the start. The answer
  is not a stealth plugin or a patched `navigator.webdriver`. It is the park pattern below.

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

**A page that loads fine can still 403 its own form's API.** Cloudflare's silent JS-detection
(`cdn-cgi/challenge-platform/.../jsd/oneshot` firing on page load) scores the browser, then the WAF
403s only the POST — on WordPress, the Contact Form 7 REST endpoint
(`/wp-json/contact-form-7/v1/.../feedback`). The symptom is a form stuck at `data-status="submitting"`
with an empty `.wpcf7-response-output`; only network logging shows the 403. Confirmed at
laufer.group 2026-09-08 (two attempts; hiding `navigator.webdriver` changed nothing). Two useful
facts: a stalled multipart POST never ran the server-side handler, so nothing half-landed and a
retry is safe; and **check the same page for a published application mailto** — a careers page that
walls its form but prints its recruiting address has handed you the reroute. A short first-person
mail naming the role ID, CV attached, sent from the person's own mailbox, is the employer's own
channel and needs no park.

The same signature on a **job-board middleman** has a cleaner exit. A WP Job Manager board's own
apply form (jobs.secrettelaviv.com, 2026-09-08) 403'd its `admin-ajax.php` upload endpoint behind
Cloudflare while the page rendered fine — on screen just *"HTTP Error."* and a submit stuck on
*"Cannot proceed. Some files are still uploading"*. The board is not the employer: find the
employer's own channel and apply there. A middleman's walled form blocks the middleman, not the
application.

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
never quietly recorded as sent.** And when the wall turns out to be permanent — the person declines a
paid gate, or no channel exists that can ever pass — the row is retagged `deferred`: out of the active
queue, distinct from `no`/`dropped` (the fit was right; the channel was not), revivable if the wall
ever falls.

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
