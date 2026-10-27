# Changelog

## 1.0.0 — 2026-10-28

First release: EventScripts 2.1.1.379 running on Counter-Strike: Source as of 2025 (`ServerVersion 11003710`).
Details of every fix: [docs/TECHNICAL.md](docs/TECHNICAL.md).

### Added

- `addons/es_shim.so`, a loader started instead of `mattie_eventscripts.so`, which loads EventScripts and fixes it for
  the current engine (source: `src/es_shim/es_shim.c`, built on glibc 2.17).
- `optional/est_compat`: SourceMod plugin bringing back 15 es_tools commands (`est_setgravity`, `est_setplayercolor`,
  `est_burn`, `est_extinguish`, `est_healthadd`, `est_sethealth`, `est_setarmor`, `est_setspeed`, `est_god`,
  `est_noclip`, `est_freeze`, `est_damage`, `est_spawn`, `est_getwallbetween`, `est_rounddecimal`).
- `test-addons/`: seven test addons (`test_chat`, `test_menu`, `test_stats`, `verify_data`, `leaderboard`, `timer_test`,
  `sql_rank`), not installed by default.
- Electric fence diagnostic build of the loader (`-DES_SHIM_EFENCE`).
- Developer guide ([docs/DEVELOPERS.md](docs/DEVELOPERS.md)).

### Fixed

- Server hung and killed by the watchdog on every map start (`es_checkversion` calling a dead server without timeout).
- Crash when Python addons call ES functions that call the engine (16-byte stack alignment).
- Python heap corruption when an `es.*` function runs inside another one (`g_pPyReturn` never reset, present since 2013).
- Keygroups and files in folders with upper-case letters not found by the engine.
- `es_keygroupsave`/`es_keygroupload` without a path (`cfg//` paths refused).
- UTF-8 characters split by the command tokenizer (signed `char`).
- corelib `while` loops (alias with the name of a server variable).
- `plugin_unload` not unloading EventScripts.

### Security

- `es_checkversion` no longer sends the server address to `api.eventscripts.com`.
- `es_install` no longer downloads and runs code from `addons.eventscripts.com` (dead domain).

## 2.1.1.379 — 2013-04-21

The original build by Mattie, kept unchanged in [original/](original): "New Orange Box build released for 379 to support
recent breaking changes to CS:S".
