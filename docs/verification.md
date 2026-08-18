# Verification — what counts as proof

One principle underneath all of it:

> **Nothing is taken on trust from the step that produced it.**

A CV that was rendered is not a CV that fits on one page. A form that was filled is not an application
that arrived. A row that was written is not a row that parses. The step that did the work is the worst
possible witness to whether the work succeeded.

Second principle, and it is the one that gets broken:

> **Your own log is not evidence about the world.**

A script that printed `SUBMITTED` proves the script reached that line. It does not prove an employer
received anything. Proof of a send comes from the employer's side — a confirmation page, a message-id
from the mail server, an acknowledgement email. Never from your own output.

---

## The proof table

| Claim | Proof | Command |
|---|---|---|
| CV rendered to one page | Page count reads exactly 1 | `scripts/render_cv.sh <dir>` prints `pages [b'1']` |
| Voice and fingerprint rules hold | Exit code 0 | `python3 scripts/preflight.py <dir>` |
| Handling instructions respected | No banned term found | same run — reads the person's `.preflight` |
| PDF text is actually extractable | The real words come back | `pdftotext <pdf> - \| head -40` |
| CV is on-target | A number, recorded and quoted | self-score in `applications.csv`, repeated in the delivery message |
| Added technologies declared | The cell is filled, or deliberately empty | read the row back |
| Log updated | The row is read back after writing | read the row back |
| CSV intact | Every row parses to the full column count | `python3 -c "import csv,sys;print({len(r) for r in csv.reader(open(sys.argv[1]))})" <csv>` — one value only |
| Application arrived | Confirmation page, or a message-id | screenshot / the SMTP response |
| Employer replied | The message in the mailbox | `scripts/mailbox.py --person <p> search 'FROM "..."'` |

---

## Verifying the render

```bash
scripts/render_cv.sh people/hanna/created_data/acme-backend-engineer
```

It renders `cv.html` with headless Chrome and prints the page count parsed out of the PDF bytes:

```bash
python3 -c "import re,sys;d=open(sys.argv[1],'rb').read();print(re.findall(rb'/Count\s+(\d+)',d))" <pdf>
```

`pdfinfo`, `qpdf`, `mutool`, and `gs` are commonly absent from build hosts, which is why the count is
read from the bytes. `pdftotext` and `pdftoppm` (poppler-utils) are more often present and are worth
using when they are — `pdftotext -f 2 -l 2` on a file you believe is one page is a fast way to catch a
silent overflow.

**A multi-page artifact is never delivered without saying so.** If something renders to two pages and
you hand it over describing it as a table of everything, the person reads page one, counts the rows,
and finds you short. Say the page count out loud.

---

## Verifying voice and fingerprints

```bash
python3 scripts/preflight.py people/hanna/created_data/acme-backend-engineer
```

It fails the CV on any of:

- **Third person** — `he`, `she`, `they`, or the person's own name as the subject of their own bullet.
- **First person** — `I`, `my`, `me`. The CV voice is the implied subject: *"Built the deployment
  pipeline"*.
- **Agent fingerprints** — model or tool names, `generated`, `as an AI`, `based on the provided`,
  meta-commentary about the CV itself, leftover `{{TEMPLATE}}` markers, PDF document properties naming
  a generator.
- **Disclosure of an omission or a stretch** — `(omitted)`, `(approx.)`, `(see note)`, `roughly`
  attached to a number the person asked to be presented a particular way.
- **Any term in that person's `.preflight` file.** One term per line, `#` comments allowed. This is how
  a personal handling instruction becomes a mechanical check instead of a thing you have to remember.

Exit 0 or the CV does not render. It is not optional and it is not advisory.

---

## Verifying a send

Three acceptable proofs, in descending order of strength:

1. **An acknowledgement email from the employer**, in the person's mailbox. Strongest — it proves the
   application reached a system that decided to answer.
2. **A message-id returned by the mail server** for an email application. Proves it left; does not
   prove it was routed to a human.
3. **A confirmation page**, named specifically — a URL ending `/confirmation` titled "Thank you for
   applying", or a form that replaced itself with "Thank you!". Screenshot it.

Not acceptable: a script that logged success, a body-text match on `thank you|submitted|received`, a
`200` status code, or the absence of an error.

---

## Verifying a sub-agent

When drafting is parallelised across roles, verify the returned work against the brief, not against the
sub-agent's summary of it. Read one bullet from the CV it says it wrote. Check the page count yourself.
An agent's report describes what it intended to do.

---

## When verification fails

- **File write** — revert to the prior content, retry once, then stop and say so.
- **Render** — discard and regenerate. Two reflow passes maximum; a third means the content is wrong,
  not the layout.
- **Form submission** — two attempts, then park it. Never a third variation.
- **A fact that will not resolve** — it goes to `## Open questions` in `profile.md` and is unusable
  until the person answers. Not the more impressive version, not the more recent one.

Failing loudly is the whole point. A pipeline that silently downgrades a blocked application into a
sent one is worse than a pipeline that stops.
