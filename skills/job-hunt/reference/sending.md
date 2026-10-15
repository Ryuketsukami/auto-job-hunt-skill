# Sending: the employer's own channel, and the walls in front of it

Nothing is sent beyond what the person's `Send authority:` line in `profile.md` allows. Approving a
CV is not authorising a send (rule 6): it is the rule people are most surprised by, which is why it
is written down.

**Everything you type into a form or an email is an artifact.** Save the answers to free-text
fields (cover letter, "anything else?", screening answers) and every email body in the role
directory, as `form-answers.txt` or `email.txt`, before `preflight.py` runs. That way the same gate
that checks the CV checks them too, including for a `.env` credential.

Every application goes through the **employer's own official path**. Finding that path is its own
step, and the obvious URL is often the wrong one.

Regional boards (Drushim, AllJobs, Israeli recruiter backends) are in
[regions/israel.md](regions/israel.md). LinkedIn Easy Apply is in
[linkedin-easy-apply.md](linkedin-easy-apply.md).

---

## Gmail

Email matters: 55 of 174 historical sends (32%) went by email, not through a form. And the mailbox
is where receipts, verification codes, and replies arrive.

**Default: the claude.ai Gmail connector.** It runs on Anthropic's side and needs no password. Use
it to search the inbox, read threads, pick up verification codes and receipts, track replies, and
create drafts. Its tools have names such as `search_threads`, `get_thread`, and `create_draft`, and
take Gmail query syntax (`from:greenhouse.io newer_than:2d`). With the connector alone, an email
application becomes a **draft** in the person's account: subject, first-person body, the CV
attached, ready for them to press send. Record it as deferred with
`--needs "send the Gmail draft to <address>"`, and promote it once they confirm it went.

**Opt-in: automatic sending.** With an app password in the person's `.env` (onboarding section 9),
`mailbox.py` sends from their own address over SMTP and reads over IMAP:

```bash
python3 <skill-dir>/scripts/mailbox.py --person hanna list -n 20
python3 <skill-dir>/scripts/mailbox.py --person hanna search 'FROM "no-reply@greenhouse.io"' -n 10
python3 <skill-dir>/scripts/mailbox.py --person hanna read <uid> --chars 4000
python3 <skill-dir>/scripts/mailbox.py --person hanna send --to careers@acme.example \
  --subject "Backend Engineer application" --body-file <ws>/people/hanna/roles/<dir>/email.txt \
  --attach <ws>/people/hanna/roles/<dir>/Hanna_Levi_CV.pdf
```

`send --dry-run` builds the message without sending it. `search` takes IMAP criteria
(`FROM "x"`, `SUBJECT "y"`, `SINCE 01-Aug-2026`, `UNSEEN`), not Gmail syntax. The credential is never
printed, and if you change the script it must stay that way.

Two things `mailbox.py` learned the hard way:

- **A send that hangs is a blocked port, not a slow server.** Cloud hosts commonly block outbound 25
  and 465; the socket sits in `SYN-SENT` forever. Port 587 with STARTTLS is usually open: set
  `SMTP_PORT=587` in the person's `.env`, and `mailbox.py` switches to STARTTLS by itself.
- **`make_msgid()` with no domain stamps the machine's hostname** into every Message-ID. Headers are
  part of the application, and a hostname that says automation is a fingerprint. `mailbox.py`
  stamps the sender's own mail domain instead.

An email application is short, first person, names the role (and its reference ID if the posting
has one), and attaches the role's `<Person_Name>_CV.pdf`. Save the body as `email.txt` in the role
directory. The proof is the message-id, or the message in the Sent folder.

---

## Finding the real apply path

Recon each posting before touching a form. The patterns that recur:

- **A careers URL that redirects behind a bot shield** and never renders. The ATS embed underneath
  it usually works: `job-boards.greenhouse.io/embed/job_app?for=<slug>&token=<id>`.
- **A contact form at the top of the job page with no file input at all.** A CV cannot be attached.
  The real form is often an embed further down the page.
- **A domain that does not resolve**, whose posting ends by telling applicants to email a named
  person. That instruction *is* the official path.
- **No form at all.** Some companies only ask for a CV and a short note, by email.
- **A recruiting address found in a directory or aggregator, not on the employer's own pages.**
  Before mailing a CV there, check the domain receives mail: `dig +short MX <domain>` (or
  `nslookup -type=mx <domain>`). No MX record means the address bounces or was never real.
- **A published email hidden behind Cloudflare's scrape-shield** renders as `[email protected]` with
  the real address in a `data-cfemail` hex attribute. Decode it: XOR each byte with the first byte
  of the hex string. The address is public to every human reader; decoding it is reading the page.
- **Comeet** boards: the standalone apply form is
  `comeet.co/jobs/<companyUid>/<positionUid>/apply?token=<token>`, and all three identifiers come
  out of a JS blob in the careers page HTML. Each position also publishes an email address that
  reaches the same pipeline.
- **An aggregator's "apply" link that chains through an ad tracker** (gute-jobs.de to
  jobspreader.com) can dead-end in an interstitial carrying a hidden reCAPTCHA. That chain is
  advertising plumbing, not the official path. Search the employer's own careers site for the same
  requisition; it is usually there, sometimes with an account-free form.
- **A Bundesagentur für Arbeit posting with no contact block and no external URL** still has an
  official path: the employer's own published application address, with the BA Referenznummer in
  the subject line.
- **A job list that renders empty may sit in an iframe gated on the cookie dialog.** jobactive.de's
  listings load only after the consent prompt is answered; the board iframe
  (`bewerbercenter.jobactive.de/job/listing/external?jobBoard=<n>`) is directly navigable after that.
- **The careers page may not list every role.** Some employers list only core-business jobs there,
  while the IT vacancies exist solely on their ATS tenant (`<company>.softgarden.io/de/vacancies`).
  Probe the common ATS domains before concluding a posting is stale.

Greenhouse exposes its required fields without authentication, which is the cheapest way to know in
advance whether a form will block:

```bash
curl -s "https://boards-api.greenhouse.io/v1/boards/<token>/jobs/<id>?questions=true"
```

There is no `boards-api.eu.greenhouse.io`. The US host serves EU-hosted jobs.

---

## Driving a browser

- **One persistent browser profile per employer** (a Playwright `user_data_dir` or saved
  `storage_state` in `<ws>/people/<p>/.browser/<employer>/`), never one shared profile for
  everything. It holds session cookies: treat it like `.env`. Set the
  context's **locale and timezone to match the person's location**; a German-locale browser in a
  UTC timezone applying from another country is an inconsistency scoring systems notice.
- **Attach an XHR/fetch response listener** from the first navigation, logging method, URL, and
  status of every request. When a submit "does nothing", the answer (a 400, a 403, a 428) is in
  that log, not on the screen.
- **Screenshot after every submit click.** Some validation errors exist only on screen.
- **The uploaded filename is what the recruiter sees.** Upload the role's `<Person_Name>_CV.pdf`
  from the role directory. A file called `..._CV_Acme.pdf` tells Acme it is one of a batch.

---

## Form mechanics that cost hours

Each of these was paid for once. Read them before driving a form, not after.

**Greenhouse**

- **A wrapping `iframe[src*="greenhouse"]`** on a company careers page: navigate straight to the
  iframe's `src` and drive the form there. Reaching into the frame from the parent page costs time
  and breaks on every re-render.
- **Never list `[role="option"]` unfiltered.** The phone-country widget alone floods the DOM with
  about 240 options; scope any option query to the open listbox of the control you just opened.
- Submission is gated behind an **emailed 8-character code**. Click submit, read the code from the
  inbox, fill `#security-input-0` through `#security-input-7` (type into box 0 with a small delay),
  and click the LAST "Submit application". A jump to ~13 console errors is the normal signature of
  that gate. A stale code is cheap: clicking Submit again mails a fresh one.
- On the wire the gate announces itself as **HTTP 428** on the submit POST. 428 is the code gate
  arming, not an error: do not retry the POST; go read the mailbox.
- **The code is mixed-case** (shaped like `XSzk9gAI`), so an `[A-Z0-9]{8}` extractor misses it, and
  the mail wraps it in prose. Anchor on the phrase:
  `/security code field[\s\S]{0,120}?\b([A-Za-z0-9]{8})\b/i`, with a standalone-line fallback
  `/^\s*([A-Za-z0-9]{8})\s*$/m`. Test any new extractor against a real code mail: a looser variant
  once matched the word "security" itself.
- **The code mail can lag four minutes or more.** Poll for at least 480 seconds before concluding it
  never came.
- **React hydration wipes fills made in the first ~2 seconds.** Wait ~2 s after `#first_name`
  renders, fill, then run a second re-fill pass over the basics before verifying.
- **The country control `#country` is a react-select combobox**, not the intl-tel-input it appears
  to be; the `.iti__country-list` in the DOM is a 0x0 vestige. Open `#country`, type the country,
  click the `[id^="react-select-country-option"]` entry, verify via the `.iti__selected-country`
  flag title.
- **The location autocomplete is a city/district geocoder with no country-level entries.** Typing a
  bare country offers only foreign cities containing the string. Type the city, `ArrowDown`, `Enter`.
- Controls have stable ids (`question_NNNN`, `school--0`, `gender`) but **empty `name`
  attributes**. Ids can start with digits or end in `[]`: always select with `[id="..."]`, never
  `#id`. Dropdowns are react-select, not `<select>`.
- **react-select keeps its chosen option in component state**, rendered as a
  `[class*="single-value"]` sibling. `el.value` is always the typed search text, so a check that
  reads it reports a fully answered form as empty. Read the single-value node.
- **React-select option clicks are flaky; the keyboard is reliable**: focus the control,
  `ArrowDown`, read `aria-activedescendant`, `Enter`.
- **Agreement "checkboxes"** (plagiarism or privacy confirmations) can be single-option comboboxes;
  pick their only option ("Yes", "Acknowledge/Confirm").
- **Demographic blocks vary per board**: US EEOC selects, custom required selects, or radio lists.
  All carry a decline option; take it unless `profile.md` says otherwise.
- Validation errors are enumerable via `[id*=error]`, `[role=alert]`: read them instead of guessing.
- Proof: a URL ending `/confirmation` titled "Thank you for applying".

**Comeet**

- **The apply form's iframe lazy-loads**, on some embeds only after interaction. Poll for it
  (15 x 2 s worked) and, between attempts, scroll and click the apply trigger again.
- **Hidden Angular inputs fail Playwright's actionability check** even when the control is plainly
  on screen. JS-click the `label[for=<id>]`, then verify the input's `checked`/`value` via JS.
- Accepts `.pdf`, `.doc`, `.docx`, `.rtf` **only**: no `.txt`, no paste-text fallback.
- Angular dropdowns can have the **question itself as the element id**, e.g.
  `id="How did you hear about us?"`.
- The resume input is `opacity: 0`, so a driven click fails as "not visible". `set_input_files` on
  the hidden `#cv` input works directly; `label.clickableLink[for='cv']` is the fallback.
- The **phone-country selector is a button plus search combobox and its default can be wrong** (a
  fresh en-US context got "Germany +49"). Click the button, type the country into
  `input[placeholder='Search']`, click the option, verify the prefix before filling the number.
- **May refuse a driven submission, or accept it.** The invisible reCAPTCHA scores each submission:
  the same rig on the same day was refused on one employer's embed and got a clean "Thank you
  <name>!" on another's first submit. Always attempt the form. When it refuses, a valid form
  returns "session verification failed due to a human check error": that is the score, not a bad
  field. **Do not attempt a third variation.**
- **The human-check error UI carries its own way out**: an "email your resume" mailto to
  `<Company>.<positionUid>@applynow.io`, Comeet's inbound intake for that exact position. Emailing
  the CV there from the person's mailbox is the employer's designated channel, not circumvention.
  Grab the mailto from the error frame before closing the page.
- Radio options are **custom-styled and digit-led**: ids like `1713...` are invalid in CSS `#id`
  selectors. Click the visible `label:has-text(...)` and verify `checked` via JS. Submit buttons
  omit `type="submit"`: match `button:has-text('Submit Application')`.

**Lever**

- The **location autocomplete can offer zero suggestions**, and `Escape` on an empty dropdown wipes
  what was typed. The field takes free text: write it directly.
- Lever **parses the uploaded CV and back-fills fields from it**, sometimes wrongly. Re-read the
  whole form after upload and clear its guesses.
- Sometimes shows an hCaptcha checkbox after submit. That is a seen wall: park.

**Ashby**

- Can reject a completed submit as "flagged as possible spam", and its own advice is to submit
  again. A re-click on the still-filled page is the fix.
- **Field ids are opaque UUIDs**, but every field has a real `<label for="...">`: dump labels by
  `htmlFor` first, then fill by `[id="..."]`. System fields keep stable ids (`_systemfield_name`,
  `_systemfield_email`, `_systemfield_resume`).
- **Two file inputs**: the first is "Autofill from resume" (a parser). The CV goes on
  `_systemfield_resume` only.
- **Yes/No questions are plain `<button>` pairs**: find the question text, walk up, click the button
  whose exact text is wanted.
- **An "application limits" banner** ("up to N applications within a 60-day period") is
  informational, but a failed submit retried later still counts against N: fix validation errors in
  one session.
- **hCaptcha can interpose as a full image challenge at submit**, not just the checkbox. Park.

**Workday (myworkdayjobs.com)**

- The unauthenticated liveness check is the CXS API: `/wday/cxs/<tenant>/<site>/job/<slug>` answers
  `jobPostingInfo` JSON.
- Everything is addressed by `data-automation-id`. The apply path: `/apply`,
  `a[data-automation-id='applyManually']`, `createAccountLink`, then
  `input[data-automation-id='email'/'password'/'verifyPassword']`.
- **Real buttons sit under an overlay `div[data-automation-id='click_filter']`** carrying the
  action's aria-label. Click the overlay div, not the button.
- **Sign-in and account pages carry honeypots** (a `beecatcher` input, or a labelled robots-only text
  field). Leave them blank (rule 5).
- **Some tenants require email verification**: Create Account bounces back to Sign In with no error,
  and a "Verify your candidate account" email with an `/activate/<token>` link lands in the inbox.
  Open it (`/login/ok` redirect means verified), then sign in. **Other tenants silently reject
  headless account creation** (back to sign-in, no email, login refused). Check the inbox first;
  after three clean attempts with no verification mail, treat it as a wall and hand account
  creation to the person.
- **The wizard draft persists per step, but transient fields reset on every load**: the phone
  number and the source multiselect clear while the rest survives. On each resume, re-enter the
  phone and re-pick the source. Fill a step completely in one session.
- **`fill()` does not commit the phone field**: it shows in the DOM, passes step-1 validation, then
  surfaces as "No Response" on Review and a bare "Page Error" on submit. Real keystrokes (`type`
  plus a `Tab` blur) commit it.
- **Non-Latin countries split Legal Name into local and Latin-script fields with duplicate ids.**
  Selector fills hit only the first. Enumerate with `querySelectorAll` and fill positionally; the
  local-script fields are optional.
- **Prompt widgets are two-level**: "How Did You Hear" opens categories. Click the
  `[data-automation-id='promptOption']` by its `data-automation-label`, then the leaf, and verify
  via the `selectedItem` pills: a stray click selects whatever leaf is first.
- **Simple question dropdowns are not prompts**: after clicking `Select One`, options are plain
  `[role='option']`/`menuItem` nodes. Map buttons to their question text by walking up the DOM.
- **Playwright clicks time out on menu items and footers** (pointer-intercept overlays). Use JS
  `el.click()`.
- **Second applications on the same account**: `/apply/useMyLastApplication` prefills experience and
  the previous CV. Deleting the old attachment is unreliable; the application can go out with two
  CVs. Delete via the attachment row's control and verify the count.
- Extra steps appear per role (an interview-recording consent step, for one). A walker that answers
  mapped questions, declines demographics, checks required consents, and clicks footer-next until
  Review handles them.
- Step-1 defaults follow the tenant's home country, not the job's: fix country and phone prefix. The
  step can hard-require street, postal code, and city; a profile that holds only a region cannot
  fill those. Ask the person; never invent an address.
- Proof: Candidate Home lists the application as Active / "In Review" with a submit date, and a
  "Thanks for applying" receipt email usually arrives.

**Amazon.jobs**

- Old accounts migrate via passport.amazon.jobs: name, an emailed 6-digit code, a new password.
- The application is a 7-section left-nav form that auto-saves per step; selects are native, radios
  need label clicks (`input.click()` does not persist). "Have you previously applied" dates live in
  the dashboard's Archived tab.
- Proof: the thank-you page plus a "Thank you for Applying" receipt email per role.

**HeyJobs (heyjobs.co)**

- The CTA "Ich bin interessiert" is an `<a>` that overlays intercept: navigate straight to
  `<job-url>/apply/now`.
- **Entering an email creates an account** and mails a password-set link. Set the password from it,
  write it into the person's `.env`, keep the storage state: funnel progress lives on the account.
- Question textareas carry per-session UUID names plus an unnamed decoy. Target by visible label.
- **The account's stored CV is reused silently.** A funnel can say "Unterlagen vollständig" without
  an upload step, and whatever Lebenslauf the profile holds forwards to the employer hours later.
  Set the profile CV at `/de-de/profile/documents` BEFORE walking a funnel (its first bare file
  input belongs to Zeugnisse, not the Lebenslauf), or swap it on the review screen via Dokumente,
  Ändern.
- Success is "Deine Bewerbung wurde erfolgreich abgeschickt!", or "Deine Bewerbung sieht schon gut
  aus!" with a forwards-in-N-hours note when the optional quiz is skipped. The durable proof is the
  account's applications page listing "Beworben am <date>".

**compleet job boards to persy.jobs**

- `<compleet-cookie-banner>` is a shadow-DOM element that intercepts pointer events page-wide; a
  force-click changes nothing. Dismiss it by evaluating into its `shadowRoot` (button "AUSWAHL
  SPEICHERN") in a retry loop that verifies it is gone. "Direkt bewerben" then opens the real form as
  a popup onto a persy.jobs session URL.
- persy's styled radios and checkboxes are invisible to `check()`: set them via evaluate (click,
  force `checked`, dispatch `change`). The phone number is three inputs (country, area, local).
- **The first file input is an inert template.** The live uploader is `input[name^="afu-file"]`,
  and it re-arms after every upload: upload one file at a time and set each row's "Anlage Typ".
- **Submission is two dialogs deep**: persy's own cookie dialog, then a final "Ja, absenden". Until
  that second button is clicked nothing has been sent.

**Cornerstone (csod.com)**

- Requisitions on a `careersite` tenant take applications **without an account**:
  `/ux/ats/careersite/1/requisition/<id>/application?c=<tenant>&jobboardid=0#1`.
- Inputs carry no usable names: map them by aria-label and nearest label text, fill by index.
- The CV upload triggers an on-screen scan; wait several seconds, then re-verify every field.
- Consent and source checkboxes are styled: evaluate-click them. "How did you find us" takes the
  honest answer.
- Success is step 2 replacing the form with "Vielen Dank für deine Bewerbung!".

**German ATS portals**

- **rexx (`karriere.<firma>.de`).** Click the consent dialog's visible CTA ("Ja, ich bin
  einverstanden") first: a JS click on the hidden `#cookie-submit-input` sets no session, and the
  final POST dies with "Leider konnten wir Ihre Anfrage nicht bearbeiten" while every field shows
  green. The real submit is often just "Senden"; decoy links at the top ("Mit <portal>-Profil
  bewerben") catch a loose matcher. A `website` text input no human can see is a honeypot.
- **concludis (`<firma>.concludis.de`).** Single page, no account. Every uploaded file must be typed
  via its row's "Dokument-Typ wählen" select (the CV as "Lebenslauf"). Custom radios need JS
  clicks. `KarGehalt` is a bare-number salary input that can be enforced at submit even when the DOM
  says `required=false`.
- **finest-jobs.com.** Upload success never appears in body text: files land in proxy inputs
  `input[id^=upload_]` whose `.value` holds the stored filename; verify those. The submit is an `<a>`
  reading "Bewerbung absenden". A field can be client-enforced required while its HTML says
  `required=false`, and the red mark appears only after the click. The Lebenslauf widget can fail
  server-side forever in a clean headless context; the same role usually exists on the employer's
  own portal, one site-search away.

**HubSpot-embedded careers forms**

- The page source holds the config (`hbspt.forms.create({portalId, formId})`, loaded from
  `js-<region>.hsforms.net/forms/embed/v2.js`), but the form renders into an **iframe**: find the
  frame containing `input[name='firstname']`.
- Fields are HubSpot-standard (`firstname`, `lastname`, `email`, `resume`, `cover_letter`, custom
  slugs). `LEGAL_CONSENT.processing` is the required consent; `LEGAL_CONSENT.subscription_type_<id>`
  is marketing: leave it unchecked.
- A driven submission can surface a visible reCAPTCHA image challenge. Park.

**Image-button careers modals**

- **Image buttons sharing a class are a trap.** On one hand-rolled Angular careers page,
  `.btn-actions` matched both the close X and the submit graphic: a class-based click closed the
  modal and the driver reported success on an unsent form. **Match image buttons by their `alt`**
  (`img[alt='send']`), never by a shared class.

**Everything else**

- **A file upload may need an open file chooser.** Click the attach button first when the hidden
  `<input type=file>` cannot be targeted directly.
- **monday.com forms use downshift comboboxes.** A direct option click can hang: open the control,
  `ArrowDown`, `Enter`. Success is the form replacing itself with "Thank you!".
- **Read a hand-rolled form's own JavaScript before filling it.** WordPress forms commonly post to
  `wp-admin/admin-ajax.php` in two steps (an upload call returning a URL, then a submit call taking
  it), with a reCAPTCHA token appended by a handler nothing else reveals.
- **A bot interstitial on first contact** ("Verifying your browser before proceeding") often passes
  on a second navigation.
- **A bot interstitial that stops passing has flagged your session, not your address.** Discard the
  stored state and re-authenticate in a fresh context rather than fighting it with browser flags.
- **An upload size limit on a host with no gs/qpdf** still has a path for scans: `pdftoppm -jpeg -r
  100 -jpegopt quality=72` into per-page JPEGs, wrap them in an HTML shell (`@page { size: A4;
  margin: 0 }`, one full-page `<img>` per page), and print that to PDF with headless Chromium. Check
  legibility first. **Scans only, never the CV**: rasterising the CV destroys its text layer.
- **Every form may run invisible reCAPTCHA.** No submission counts until a confirmation is on
  screen.

---

## Walls

Three recur, and the difference matters, because two have workarounds and one does not.

### 1. A human-verification challenge: no workaround, by design

A visible hCaptcha, a Cloudflare Turnstile widget, or an invisible reCAPTCHA token the form's own
JavaScript demands. **These are not solved and not bypassed** (rule 4). Solving one is claiming to
be a person, to a system that asked precisely because it wants a person.

- **Know the badge from the challenge.** Invisible reCAPTCHA plants an `api2/anchor` iframe: the
  corner badge, present on countless forms that never challenge anyone. The challenge is the
  `api2/bframe` iframe (or a Turnstile or hCaptcha frame) **when it is visible**.
- **The network decides how hard it is.** hCaptcha serves an active image puzzle to datacenter IPs
  and usually stays passive on a residential connection. A form that walls you from a server may
  pass untouched from the person's own machine; that is a reason to park there, not to fight it.
- **It can fail silently.** A filled, valid form that returns an error is being scored, not
  misfilled. **Two attempts, then stop.** Never a third variation.
- **It can escalate on the submit click.** A dormant widget can turn into an image puzzle at the end,
  or a checkbox can materialize. That **is** a seen wall. The answer is not a stealth plugin or a
  patched `navigator.webdriver`; it is the park pattern.
- **Cloudflare Turnstile in a plain headless browser tends to never complete**: the widget sits at
  an empty bar and "verify you are human" stands after submit. That is the seen wall.

### 2. A mandatory account: reroute, or open it

- **Reroute.** Find the employer's own channel (their ATS board, careers page, a published
  recruiting address) and go direct. Nearly always available, and better.
- **Open the account.** Registration is normal work: the person's real details, a generated password
  written straight into their `.env` (never echoed, never logged), required consents only, marketing
  boxes empty. The verification link or code lands in a mailbox already being read. From there it is
  the same footing as that mailbox.

**A wall is something you saw, not something you inferred.** Signup pages everywhere carry
Cloudflare scripts and reCAPTCHA site keys; markers are not challenges. Attempt the registration.
Only a challenge that actually interposes stops it, and the park happens at precisely that step.

### 3. A network or WAF block: diagnose before recording

A `403` or a vendor-specific code may be blocking the *address*, or the *shape of the request*.
These look identical and are not.

**Run the comparison first.** Retry from a network the person controls, their own machine. If it
succeeds, the block was the address, and routing through their machine is legitimate: it is their
hardware and their application. If it fails there too (a DataDome body, `geo.captcha-delivery.com`,
"Please enable JS and disable any ad blocker"), the block is aimed at automation itself. That is
wall 1, and the remedy is their own everyday browser.

**A page that loads fine can still 403 its own form's API.** Cloudflare's silent JS detection
(`cdn-cgi/challenge-platform/.../jsd/oneshot` on page load) scores the browser, then the WAF 403s
only the POST, on WordPress the Contact Form 7 endpoint (`/wp-json/contact-form-7/v1/.../feedback`).
The symptom is a form stuck at `data-status="submitting"` with an empty `.wpcf7-response-output`;
only the network log shows the 403, and hiding `navigator.webdriver` changes nothing. A stalled
multipart POST never ran the server handler, so nothing half-landed. **Check the page for a
published application mailto**: a short first-person mail naming the role, CV attached, from the
person's own mailbox, is the employer's own channel and needs no park.

A middleman job board with a walled form blocks the middleman, not the application: find the
employer's own channel.

---

## The park pattern

When a wall stops a submission, the application does not die. It gets **parked**: filled to
completion in a real browser on the person's own machine, CV attached, every question answered, and
stopped **one click short of Submit**. They review and click. The human stays the one who submits,
which is what anti-automation systems actually ask for, and the twenty minutes of typing is gone.

A parked window is opened on demand only, never on a timer, and you say in chat that you are
opening one.

- **Never auto-detect success.** A loose body-text match on `thank you|submitted|received your`
  reports submissions that never happened.
- **Leave honeypot fields blank**: anything matching
  `/real human|leave this (line|field) blank|summarize this job/i` (rule 5).
- **In a parked form, hand over any code the employer mails**; do not enter it. Finding the code in
  the inbox and giving it to the person is help.
- **A parked form whose POST keeps returning 400 needs a fresh window.** The stale form state or
  token is poisoned; refilling in place changes nothing. Close it and have the person fill a fresh
  window by hand from the prepared answers.
- **Close the parked window the moment they say it is handled.** A stray window fights them.
- Say exactly what is left, in one line: "Open, review, click Submit."

A parked role is **deferred**, never recorded as sent:

```bash
python3 <skill-dir>/scripts/ledger.py defer --person hanna --company Acme --role "Data Engineer" \
  --url <url> --channel greenhouse --cv-file cvs/<dir>.pdf --needs "click Submit in the parked window"
```

When they confirm and the confirmation is seen, `ledger.py --person <p> promote --url <url> --status sent
--proof <file>` moves it into `applications.csv`. A wall that is permanent (they decline a paid
gate, no channel can ever pass) stays in `deferred.csv` with `--needs` saying so: the fit was right,
the channel was not.

---

## Recording a send

One row per application, written **after** the proof exists, not after the click. The proof is a
named confirmation page (screenshot it into the role directory), an employer receipt, or a mail
message-id.

```bash
python3 <skill-dir>/scripts/ledger.py add --person hanna --company Acme --role "Backend Engineer" \
  --url <url> --status sent --channel greenhouse --location Berlin --arrangement hybrid \
  --cv-file cvs/<dir>.pdf --notes "score 81" --proof roles/<dir>/confirmation.png
python3 <skill-dir>/scripts/ledger.py find --person hanna --url <url>   # read it back
```

**A missing acknowledgement email is not a failure** when the confirmation page was seen. Many
employers and boards send none; the screenshot is the proof.

The role directory is the archive: `job-description.md`, `cv.html`, the PDF, `email.txt` or the
form answers, and the proof screenshot are what the employer received. Do not edit anything in it
after the send. Replies are tracked from the mailbox and recorded with
`ledger.py --person <p> set-status --url <url> --status interview` (or `rejected`, `offer`); `ledger.py --person <p> age`
turns 30+ days of silence into `⏳ no-response`.

Your own log is not evidence about the world; the employer's confirmation is. See
[verification.md](verification.md).

### HiBob (Bob Hiring) careers forms
Seen 2026-10-15: the resume "Add file" control does nothing in automated Chromium (headless or under Xvfb): no file dialog, no upload request, while the form's other Add buttons work. Park the row for the person's own browser. A LinkedIn link to a HiBob role can land on another country's copy of the same ad; check the location and find the right one.
