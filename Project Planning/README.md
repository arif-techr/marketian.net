# Project Planning

Planning and status notes for the Marketian sites: what we're building, where each part stands, and what's next. The code lives in the rest of this repo. This folder holds the notes about it.

| File | What it holds | Update it when |
|---|---|---|
| [01-plan.md](01-plan.md) | What we're doing and why, plus the roadmap (Now / Next / Later) | priorities change, or a roadmap item is done |
| [02-status.md](02-status.md) | Current state of every site and of the repo | after any work session, commit, or deploy |
| [03-decisions.md](03-decisions.md) | Architecture and product decisions, with the reason for each | a choice is made that someone could later ask "why?" about |
| [audits/](audits/) | Dated, full audit reports (one file per audit) | an audit is run; never edit an old one, add a new file |

## Rules for keeping it useful
- **Status is dated.** Every status section starts with `As of: YYYY-MM-DD`.
- **Newest first.** In the change log at the bottom of `02-status.md`, add new entries at the top.
- **One fact, one place.** The plan says *what we'll do*, status says *where we are*, decisions say *why*. Link between them instead of copying.
- **Audits are snapshots.** A new audit goes in a new file, `audits/YYYY-MM-DD-audit.md`. Its open items are copied into `02-status.md` → *Open issues*.
