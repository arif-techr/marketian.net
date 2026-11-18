---
name: marketian-docs-and-commits
description: Use when writing or updating Marketian docs (STATUS.md, Project Planning/02-status.md, 03-decisions.md, READMEs, .env.example comments) or commit messages, at the end of any piece of work.
---

# Marketian docs and commit messages

The owner reads these, often on another PC weeks later. Write plain English: short sentences, the
real names of files and commands, no jargon that isn't explained, no marketing words.

## Which file says what
| File | Holds | Update when |
|---|---|---|
| `STATUS.md` | Where we left off: what's live, how to continue on another PC, what's being built, "Before the next deploy", "Open (needs you)" | Every session that changes the state |
| `Project Planning/02-status.md` | Site table (status, test counts), deployment facts, open issues, **change log (newest first)** | Every commit worth noting, every deploy |
| `Project Planning/03-decisions.md` | **Decision** (date), then why. Newest first | A choice that a future change could undo |
| `Project Planning/0X-*-plan.md` | Task tables with ✅/⬜ and a "Done when" column | A task finishes |
| `README.md` | How the server fits together and how to set it up | Architecture or setup steps change |
| `sites/<site>/README.md` | How to run and test that site | Its setup changes |
| `.env.example` | Every setting, with a comment saying where its value comes from | A setting is added |

Rules: dates are absolute (`2026-11-18`, never "yesterday"). Say "not deployed" / "not committed"
when true. Give exact test counts. Things the user must do go under "Open (needs you)" or
"Before the next deploy", with the exact commands.

## Commit messages
Format used in this repo:
```
<Area>: <what changed, in plain words>          (≤ 72 chars, no period)

<Why: the problem, as the user would see it.>
<What: the change, one short paragraph per part.>
<Anything not done or not deployed, and what's needed first.>

Tests: <site> <count>, <site> <count>.

Co-Authored-By: <attribution line from the system reminder>
```
Area is the site or topic: `Accounts`, `Links`, `Marketian SMS`, `Tracking`, `Status`, `Deploy`.
Examples from the log: "One Marketian account everywhere: admin pages too; database rule",
"Accounts: visitors can sign up again; admin needs a verified email".

- One topic per commit. Docs updates go in the same commit as the code they describe.
- Commit only when the user asks or the task clearly includes it. Push and deploy only with a yes.
- Never commit `.env`, `.venv`, `db.sqlite3*`, `media/`, `backups/`, keys.
