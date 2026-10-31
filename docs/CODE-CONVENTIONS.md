# Code and documentation conventions

How code, comments and documents are written in this repository, so a reader can trust them. These rules describe what the code already does; where a file departs from them, the file is wrong, not the rule.

## Code layout and style

The repository has two deliberate styles. Do not reformat one into the other.

| Area | Style |
| --- | --- |
| `paperclip/factory/`, most of `scripts/` | Dense Python with one-space indentation and several statements on a line separated by `;`. Keep it when editing these files |
| `gateway/`, `chat/`, `moderation/`, `operations/`, `storage/`, `research/`, `tests/` | Conventional four-space Python |

- Prefer the standard library. The third-party packages in use are Pillow (image handling) and `tokenizers` (the gateway's token budget); add another only with a reason recorded in [HISTORY.md](HISTORY.md).
- State lives in clearly named files (see [ARCHITECTURE.md](ARCHITECTURE.md#state-and-retention)); no module writes request content to disk.
- A new network call needs a fixed origin, a timeout and a size bound in code, the way the existing ones do.
- Tests use `unittest`. Every test file begins with a docstring saying what it covers. Anything that talks to the live API sends `X-Request-Purpose: test`.

## Comments and docstrings

A comment is for the reader who will change this code in a year. It explains **why** and **what must stay true**, not what the next line does.

1. **Every module starts with a docstring** that states its responsibility and, when it matters, its boundary ("never stores request content", "read-only", "single use").
2. **Comment what is not obvious from the code:** an invariant another module relies on, a security boundary, an ordering rule (reserve before sending, check before deleting), a value that is a snapshot rather than the source of truth, behaviour that depends on exact error text, and why a limit has the value it has.
3. **Mark the status of code that is not the live path:** retired, legacy, single use, test-only, or not used by production. A reader must never have to guess whether a function is live.
4. **Say what is true now.** No change-log remarks inside code ("unchanged", "now", "no longer", "after the migration"); those belong in [../CHANGELOG.md](../CHANGELOG.md) and [HISTORY.md](HISTORY.md). Use a date only when an owner decision is the reason for a value.
5. **When behaviour changes, change the comment in the same commit.** A comment that contradicts the code is worse than none. Docstrings that name a limit, a path or a count must be re-checked whenever that value moves.
6. **No attribution.** Comments, docstrings and docs never name an AI tool or provider as author, and commits carry no co-author or tool trailers.
7. Keep comments short: one to four lines. If it needs a page, it belongs in a document that the comment links to.

A change that only adds or rewords comments and docstrings can be proved safe:

```sh
python3 scripts/check_comment_only.py            # every changed tracked .py file against HEAD
python3 scripts/check_comment_only.py path.py    # or named files
```

The check compares syntax trees with docstrings removed; it fails if any executable code differs.

## Documents

- **One source of truth per fact.** Link to it instead of copying it. Counts, limits and defaults that change belong where they are generated or enforced ([ARCHITECTURE.md](ARCHITECTURE.md#where-a-fact-is-decided) lists those places); other pages point there.
- **README** is an entry point and map only. **ARCHITECTURE** describes the system as it is now and is updated in the same change as any structural change (a new component, table, endpoint, schedule or integration). **HISTORY** is dated narrative: later entries supersede earlier ones, and nothing in it is rewritten to look current. **CHANGELOG** lists every change for operators and clients.
- **Release notes ship with the work.** Add the CHANGELOG entry in the same change set, then run `python3 scripts/check_changelog.py` before a release; it reports any commit the notes do not cover.
- Write what was measured and what was not. A claim that was not verified says so. Evidence sits in the repository (reports, `results/`), and failed attempts stay visible.
- Private material never enters a document: no keys, hashes, customer text or real third-party contact details.
- Backlog detail for research and data management lives in [../BACKLOG.md](../BACKLOG.md); planning and status for this repository are tracked on its project board, not in a second list.

## Commits

Describe what changed and why, what was verified, and what was deployed and when. The body of a commit is the source for its release note. Do not include tool or co-author trailers.
