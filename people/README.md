# people/

Every person tracked by this pipeline gets one directory here. **Everything in this directory is
gitignored** — this README is the only file that is committed. Nobody's CV, credentials, or
application history is ever pushed anywhere.

Create one with:

```bash
python3 scripts/new_person.py "Hanna Levi"
python3 scripts/new_person.py --list
```

That gives you:

```
people/hanna/
├── .person               # their full name, so a collision can be detected
├── .env                  # their mail app password. Never printed, never committed.
├── .preflight            # terms that must never appear in an outward artifact
├── applications.csv      # every role ever presented, and what happened to it
├── source_data/
│   ├── raw/              # what they gave you, untouched
│   └── profile.md        # the compiled fact base — the ONLY source a CV may draw from
└── created_data/
    └── <company>-<role-slug>/
        ├── job-description.md
        ├── cv.html
        ├── <Person_Name>_CV.pdf
        └── cover-letter.html      # only when the employer asks
```

## Naming

**First name, lowercased** — `people/hanna`.

If that directory is already held by a *different* Hanna, the new person becomes `hanna_cohen`
**and the existing one is migrated to `hanna_levi` at the same time**, so a bare first name never
stays ambiguous. `new_person.py` performs both moves and prints what it did.

## The two directories, and why the split matters

`source_data/raw/` is **evidence**. Whatever arrived, exactly as it arrived — a CV file, a LinkedIn
export, a voice-note transcript, three lines pasted into chat. Never edited, never cleaned, never
deleted.

`source_data/profile.md` is **testimony**. One compiled document, every fact carrying its source.
It is the only thing a CV may draw facts from.

When the two disagree, the raw files win and the profile gets fixed. See
[docs/profile-compilation.md](../docs/profile-compilation.md).
