# CSS EventScripts Remastered

**EventScripts 2.1.1, running again on today's Counter-Strike: Source.**

If you ran a Counter-Strike: Source server between 2005 and 2013, you probably used
[EventScripts](https://web.archive.org/web/20131229192728/http://mattie.info/cs/), Mattie's scripting plugin: classic
`es_` scripts, Python addons, GunGame, WCS, eXtensible Admin, popups, keygroups… Its last build (2.1.1.379, April 2013)
stopped working long ago: Valve kept updating the engine, the EventScripts websites went offline, and the core binary was
never open sourced.

This repository brings that last build back to life on the current CS:S (the 2025 engine branch, `ServerVersion 11003710`)
without modifying the original binary: a small loader (`es_shim.so`) fixes, from the outside, everything that breaks on
the modern engine, and three script files of the original package are patched. Everything is documented, the sources of
both the original release and the fixes are included, and the result is a drop-in `cstrike/` folder.

> [!NOTE]
> The WCS (Warcraft Source) addon is not part of this repository. It runs on this version and will be published separately.

## Status

Tested on a clean dedicated server installed the classic way (repository `cstrike/` folder copied over a stock server, started
with `./srcds_run`) on Ubuntu 22.04, and on a Debian 13 server:

| Test | Result |
|---|---|
| EventScripts' own test suites (`unittest.cfg`, `es_unittest`, `pyunittest`) | 84/84 script tests, 10/10 Python tests |
| [`verify_data`](test-addons/verify_data) — engine data, network props and events cross-checked during real games with bots | 484/484 (and 623/623 with WCS loaded) |
| Keygroups saved and reloaded from disk (accents, `[U:1:…]` SteamIDs, decimals) | 9/9 |
| Timers: `gamethread.delayed` ±9 ms, `es_xdelayed` ±44 ms, `repeat`, firing order, cancelling | 9/9 |
| SQLite 3.6 from Python (integrity, UTF-8, rollback, persistence, database = memory counters) | 4/4 and 15/15 |
| UTF-8 text in commands and chat (`"ajoutés à vous"`) | intact |
| Popups, keymenus, `playerlib`, `usermsg`, `es_give`, props, events, map changes, `plugin_unload` | working |
| Endurance (bots, map changes, addons reloaded in a loop) | no crash |

## Requirements

- A **Linux** Counter-Strike: Source dedicated server, up to date (Steam app 232330).
- The **32-bit** server binary, which is what `./srcds_run` starts by default (`srcds_linux`). EventScripts only exists
  in 32 bits: the 64-bit binary (`srcds_linux64`) cannot load it.
- Nothing else: EventScripts ships its own Python 2.5. The loader only needs glibc 2.3.3, and CS:S itself needs 2.29,
  so any distribution able to run the game will do.
- Optional: [Metamod:Source 1.12](https://www.sourcemm.net/downloads.php?branch=stable) and
  [SourceMod 1.12](https://www.sourcemod.net/downloads.php?branch=stable), only for the `est_*` commands of
  [`optional/est_compat`](optional/est_compat). EventScripts itself does not need them.

Windows servers are not supported (see [Limitations](#limitations)).

## Installation

1. Download the repository (**Code → Download ZIP**, or `git clone`).
2. Copy the `cstrike/` folder of the repository over the `cstrike/` folder of your server (merge the folders; nothing of
   the game is overwritten).
3. Restart the server.

That's it. Check in the server console:

```
plugin_print
```

It must list `Mattie's EventScripts, http://www.eventscripts.com, Version:2.1.1.379`. At startup, the console also shows
the loader at work:

```
[es_shim] relocations redirected: printf 283, Tokenize 302, Dispatch 1, ClientCommand 1
[EventScripts] Loading Mattie's EventScripts Beta 2.1.1.379...
[es_shim] module es_C: 197 functions wrapped
[EventScripts] Loaded successfully.
```

### Loading addons

EventScripts addons go in `cstrike/addons/eventscripts/<name>/` and are loaded with `es_load <name>`. To load them at
every start, add the lines to `cstrike/cfg/autoexec.cfg` (create it if needed):

```
es_load popup
es_load keymenu
es_load myaddon
```

`es_unload <name>` and `es_reload <name>` work as before. `es_install` is disabled: its addon site is gone (see
[Limitations](#limitations)); install addons by copying their folder.

## Try it: test addons

[`test-addons/`](test-addons) contains seven small addons written for this version, in classic script and in Python. They
are **not installed by default**: copy the ones you want into `cstrike/addons/eventscripts/` and load them. Details and
commands: [test-addons/README.md](test-addons/README.md).

| Addon | Type | In-game commands | What it shows |
|---|---|---|---|
| `test_chat` | classic script | `!testhelp` `!hello` `!hp` `!money` `!ak` `!countdown` | chat commands, colors, props, `es_give`, `es_delayed` |
| `test_menu` | Python | `!menu` `!info` `!motd` | popuplib menu, playerlib, usermsg (HUD, shake, fade, MOTD), gamethread |
| `test_stats` | Python | `!stats` | events, kill streaks, sounds, HUD messages |
| `verify_data` | Python | `!verify` `!tests` | continuous data checks (engine = props = events = game rules) |
| `leaderboard` | classic script | `!top` `!me` | keygroups saved to disk, sorting, disk round trip test |
| `timer_test` | Python | `!timers` | timer accuracy |
| `sql_rank` | Python | `!rank` `!toprank` | persistent stats in SQLite |

## Optional: es_tools commands (est_compat)

Most EventScripts addons of that era also needed **es_tools** (`est_*` commands), whose binary is dead.
[`optional/est_compat`](optional/est_compat) is a SourceMod plugin that brings back the most used ones with the same syntax:
`est_setgravity`, `est_setplayercolor`, `est_burn`, `est_extinguish`, `est_healthadd`, `est_sethealth`, `est_setarmor`,
`est_setspeed`, `est_god`, `est_noclip`, `est_freeze`, `est_damage`, `est_spawn`, `est_getwallbetween`, `est_rounddecimal`.
Install Metamod:Source and SourceMod 1.12, then copy `optional/est_compat/cstrike/` over your server's `cstrike/` folder.

## What was fixed

The core binary (`mattie_eventscripts.so`) is used as released in 2013; `es_shim.so` is loaded in its place by
`addons/mattie_eventscripts.vdf`, loads it and fixes the following from the outside. Full details, root causes and how
each bug was found: [docs/TECHNICAL.md](docs/TECHNICAL.md).

| Problem on the current engine | Fix |
|---|---|
| The server hung, then was killed by the watchdog, on every map start: `es_checkversion` called the dead `api.eventscripts.com` without a timeout (it also sent the server IP to a domain that can change hands) | Version check disabled in `corelib/es_corelib.txt` |
| Crash (SIGSEGV, `movaps`) as soon as Python called an ES function that calls the engine (e.g. `es.ServerVar('sv_gravity').set(800)`): Python 2.5 and psyco do not keep the 16-byte stack alignment the modern engine relies on | Every `es.*` function is called through a trampoline that realigns the stack |
| Python heap corruption, then a crash somewhere else, when an `es.*` function ran inside another one (`es.load` of an addon whose `load()` calls `es.entitygetvalue`). A bug present since 2013: the shared return value `g_pPyReturn` was never reset | The trampolines reset `g_pPyReturn` after every call |
| Keygroups and files in folders with upper-case letters were not found (`corelib/interfaces/AuthorizationService`, interface constants missing): the engine now looks folders up in lower case | The loader creates lower-case links next to such folders |
| `es_keygroupsave`/`es_keygroupload` without a path failed: paths like `cfg//es_x_db.txt` are refused | `//` collapsed in the paths ES builds (283 call sites) |
| UTF-8 text split in the middle of characters (`ajoutés` → `ajout � �s`): the engine tokenizer uses a signed `char` | Commands re-tokenized from their raw text with unsigned bytes |
| corelib `while` broken: its alias had the name of a server variable, which the engine now refuses | Alias renamed in `corelib/es_corelib.txt` |
| `plugin_unload` did not really unload EventScripts | ES unloaded together with the loader |
| `es_install` would download and run whatever `addons.eventscripts.com` serves (dead domain, can change hands) | Every ESAM request refused in `_libs/python/esamlib.py` |

The script changes against the original package are in [`original/changes-vs-bld379.patch`](original/changes-vs-bld379.patch);
the loader source is [`src/es_shim/es_shim.c`](src/es_shim/es_shim.c).

## Limitations

- **Linux only.** The loader is a Linux library; the Windows build of EventScripts (kept in [`original/`](original)) would
  need an equivalent Windows DLL, which does not exist.
- **32-bit server only** (`srcds_linux`, the default). EventScripts was never built for 64 bits.
- **No es_tools visual effects** (`est_effect`): only the commands listed above are provided by `est_compat`.
- **`es_install` and the update check are disabled**: their servers have been offline since 2013.
- **A future Valve update may break something**, as for any server plugin. The fixes target the engine as of 2025
  (`ServerVersion 11003710`).
- **Old scripts saved in ANSI/Windows-1252**: accents go through EventScripts unchanged but display wrongly for players
  (the game expects UTF-8). Save scripts as UTF-8.
- **`quit` prints Steam assertions** (`invalid hSteamUser`): the stock server does the same without any plugin.
- Behaviours of EventScripts itself, unchanged since 2013, that addon authors should know (events handled at the end of
  the frame, "noisy" events, variable expansion rules…) are described in [docs/DEVELOPERS.md](docs/DEVELOPERS.md).

## For developers

[docs/DEVELOPERS.md](docs/DEVELOPERS.md) covers writing addons for this version: addon layout, classic script and Python
examples, the APIs that were verified, the behaviours to know (several surprised even long-time scripters), Python 2.5
constraints, debugging, and the `est_*` commands.

## Repository content

```
cstrike/                     drop-in folder: EventScripts 2.1.1.379 + es_shim.so + the 3 patched scripts
optional/est_compat/         SourceMod plugin with the es_tools commands (compiled + source)
test-addons/                 seven test addons, not installed by default
src/es_shim/                 source and build script of the loader
original/                    the original 2013 builds (Linux and Windows) and the patch against them
docs/                        developer guide and technical details
```

### Building from source

The two binaries are prebuilt; to rebuild them (Docker required):

- `src/es_shim/build.sh` builds `cstrike/addons/es_shim.so` in the `manylinux2014_i686` image (glibc 2.17);
- `est_compat.smx` is built with the SourceMod 1.12 compiler: `spcomp64 est_compat.sp`.

The [GitHub Actions workflow](.github/workflows/build.yml) builds both on every push.

## Credits

- **Mattie Casper** — creator and author of EventScripts (2005–2013), and of most of its libraries.
- **The EventScripts development team and community**, credited in the package: freddukes (Steven Hartin), GODJonez,
  Hunter, Errant and the eXtensible Admin team, SumGuy14 (SoccerDude), XE_ManUp, Satoon101, SuperDave, Venjax, Chun,
  Don, Wonder, cagemonkey, MyFly, Einlanzers, Carlsagan43, HitThePipe, Rio, [OMEGA] - K2, and the ES 2.0 beta testers.
- **Python 2.5** by the Python Software Foundation (Guido van Rossum and contributors), **psyco** by Armin Rigo, both
  shipped with EventScripts.
- **AlliedModders** for Metamod:Source and SourceMod, used by `est_compat`.
- **The Internet Archive**, whose Wayback Machine kept the last EventScripts builds after every official site went down.
- This remaster: CSS EventScripts Remastered contributors.

## License

EventScripts and the libraries written for it are distributed by Mattie Casper under the **MIT License**
([`cstrike/addons/eventscripts/license.txt`](cstrike/addons/eventscripts/license.txt)); the bundled Python 2.5 keeps its own
license. The new code of this repository (the loader, the test addons and the documentation) is released under the MIT
License as well ([LICENSE](LICENSE)). The SourceMod plugin `est_compat` is released under the GNU GPL v3, like SourceMod
plugins ([optional/est_compat/LICENSE](optional/est_compat/LICENSE)).

This project is not affiliated with Valve, Mattie Casper or the former EventScripts team.
