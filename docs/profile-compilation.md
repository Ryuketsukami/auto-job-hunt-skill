# Profile compilation — raw data becomes a fact base

Two directories, and the difference between them is the whole point.

- **`source_data/raw/`** — what the person gave you, exactly as they gave it. Never edited, never
  cleaned, never deleted. A CV file, a LinkedIn export, a voice-note transcript, a link, three lines
  pasted into chat. If it arrived, it lands here with a filename that says what it is and when.
- **`source_data/profile.md`** — what you compiled out of it. One document. **The only thing a CV may
  draw facts from.**

The raw files are evidence. The profile is testimony. When they disagree, the raw files win and the
profile gets fixed.

## The recompilation rule

> **Whenever new raw data arrives for a person, `profile.md` is recompiled in the same turn.**

Not later, not at the next batch. A profile that lags its raw directory is how a CV ends up
contradicting the person who sent it — and they will notice, at the worst moment, in an interview.

Recompiling means re-reading **all** of `raw/`, not appending the new file to the bottom. New data
frequently corrects old data: a newer CV supersedes an older title, an export fills in a date that
was a guess. Appending preserves the error; recompiling resolves it.

When recompiling changes a fact that has already gone out on a sent CV, say so plainly and name the
companies that received the old version. Do not quietly correct it.

## What `profile.md` contains

Use `templates/person/source_data/profile.md` as the skeleton. Sections:

```markdown
# <Name> — compiled profile
Last compiled: <date> from <n> files in raw/

## Contact
## Search parameters          <- the intake answers
## Summary of who they are
## Experience                 <- reverse-chronological, one block per role
## Projects
## Education
## Certifications
## Skills
## Languages
## Handling instructions      <- see below
## Open questions             <- unresolved contradictions; facts here are UNUSABLE
```

Rules for the body:

- **Every fact carries its source.** `Acme, Full Stack Developer, 2024–present [cv_2024.pdf]`.
  A fact with no source is not a fact yet; it goes in `## Open questions` until it has one.
- **Dates in one format**, so tenure can be computed without guessing.
- **Numbers stay exact.** "2,140 automated tests" is evidence. "Comprehensive test coverage" is
  nothing. Never round a specific into a generic — that conversion is irreversible and it destroys
  the most credible thing on the CV.
- **Never write an inference as a fact.** If their last role ended in 2024 and the next began in
  2025, the gap is a gap. It is not "a sabbatical" unless they said so.
- **No hedging language.** The profile is internal. Write what is true, flatly.

## Handling instructions

People will tell you to leave something out, or to present something generously. Both are legitimate
and both are recorded here — under a heading of their own, in their own words, with the date.

```markdown
## Handling instructions

- 2026-08-18, her words: "don't put my exact graduation year anywhere"
- 2026-08-18, her words: "you can round the team size up, I was effectively leading five"
```

Then the rule that makes this safe:

> **The instruction lives here and nowhere else. No outward artifact may reveal that anything was
> omitted or presented generously.**

That means, on a CV, a cover letter, a form answer, or an email:

- **No marker.** Never `(omitted)`, `(approx.)`, `(see note)`, `(stretched)`, or a footnote.
- **No hedge that implies management.** "Team of roughly five" invites the question. "Led a team of
  five" or silence about the number — pick one and commit.
- **No structural tell.** A section that conspicuously avoids dates while every other section has
  them announces the omission louder than the omission would have.
- **No mention in your own messages to third parties.** The person knows what they asked for. Nobody
  else needs to.

The check is mechanical. Per-person banned terms go in `.preflight` inside their directory, one per
line, and `scripts/preflight.py` fails the CV if any appears:

```
# people/hanna/.preflight — terms that must never appear in any outward artifact
2019
graduation
```

**A generous framing is still bounded by rule 1: never invent a fact.** "Round five up" is a framing
choice about a real team. "Say I led a team" when they led nobody is a fabrication, and the answer is
no — say so plainly, once, and offer the strongest true version instead.

## Open questions

Anything ambiguous or self-contradictory sits here until the person resolves it. While it sits here,
**neither version may be used.** Not the more impressive one, not the more recent one, not the one
that fits the posting better.

```markdown
## Open questions

- **End date of the Acme role.** `cv_2024.pdf` says 2023; `linkedin_export.csv` says 2024.
  Surfaced 2026-08-18. UNUSABLE until answered.
```

These get surfaced in intake message 1 as the contradictions table. If new ones appear later, raise
them in the next message you send — never sit on one, and never resolve one yourself.

## What raw data is worth asking for

If they offer nothing but a sentence, work with the sentence and ask. In rough order of value:

1. **Any existing CV**, however old. Dates and employers are the expensive facts.
2. **A LinkedIn data export** (Settings → Data Privacy → Get a copy of your data). This is the
   supported way to read their profile — see [sourcing.md](sourcing.md#linkedin).
3. **A public profile or portfolio URL** they are happy to have cited.
4. **What they actually did**, in their own words — the part no CV ever captures. Ask for one
   specific thing they built or fixed and what changed because of it.
5. **Certifications, awards, measurable outcomes.** The rarest and most credible signals.

Ask for these once, together, and then work with whatever arrives. Do not gate the search on a
complete file — an incomplete profile with honest gaps beats a delayed one.
