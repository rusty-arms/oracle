# CLAUDE.md: oracle

## What this repo is

`oracle` is the Rusty Arms oracle rig: it replays scripted inputs in Dolphin, running the owner's own disc, and records RAM traces and screenshots. See [README.md](README.md) and core's `docs/oracle-rig.md`.

It holds **no code from the original game, no game data, no addresses in the game and no captures**, and it never will. Project policy, decisions and status live in `core`: `docs/clean-room.md`, `docs/decisions/`, `PROGRESS.md`.

## Clean-room rules (short form)

- **Never** access, search for, fetch, clone or read: the 2019 source leak or anything built on it; the community asset compiler; archive copies of the source or prototype discs; the community HD texture pack; decompiler output of the retail executable.
- **Never** read anything in the lab (`~/Develop/rusty-arms/ma-lab`) unless this session started inside it as an observer.
- If forbidden material appears anyway: stop, don't summarise or quote it, tell the owner, and log an incident in core's `docs/provenance-log.md`.
- **Never commit** retail game data, disc images, savestates, input recordings, traces, screenshots or captures of the game, real watch lists, anything from the lab, or blocklist terms. Examples and test fixtures are made up, or use generic GameCube facts from public hardware documentation.
- In committed files, describe forbidden material generically. Never name the owner; write "the owner".

## Session discipline

1. Start by reading core's `PROGRESS.md` and this repo's `git log -10`.
2. One task per session.
3. Make small commits, one per step.
4. Record where you stopped in core's `PROGRESS.md` before ending the session.

## Approval and guard rails

- The rig is a verifier. Changes to `oracle/`, `tests/` and `.github/` need the owner's explicit approval in the chat. CODEOWNERS enforces this on GitHub as well.
- **Never weaken** the rig or its tests to make a comparison pass, and never edit a golden trace.
- **Never weaken or edit** `scripts/check_no_retail.py`, `scripts/check_links.py`, `.githooks/` or `.github/workflows/guard.yml`. They are copies of core's: change them in core first, then copy them here unchanged.
- Do not route around a blocked tool call. A block is the answer; report it.
- Keep `oracle/` standard library only and compatible with Python 3.8, because it runs inside Dolphin's embedded interpreter.

## Checks

```sh
python3 -m unittest discover -s tests
python3 scripts/check_no_retail.py --all
python3 scripts/check_links.py
yamllint -s .
```
