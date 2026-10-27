# Writing addons for EventScripts 2.1.1 (Remastered)

This guide is for people who want to write, or bring back, EventScripts addons on this version. The scripting language
and the Python API are those of EventScripts 2.1.1.379 (2013): everything written for it should work, within the
behaviours described below. The original documentation is archived by the Wayback Machine:

- [EventScripts encyclopedia (classic script commands)](https://web.archive.org/web/2014/http://www.eventscripts.com/pages/Main_Page)
- [EventScripts Python documentation](https://web.archive.org/web/2013/http://python.eventscripts.com/)
- [EventScripts forums](https://web.archive.org/web/2013/http://forums.eventscripts.com/)

Every API mentioned here was exercised by the [test addons](../test-addons) on the current engine. They are short and
meant to be read: they are the quickest way to see working code.

## Contents

- [Addon layout and loading](#addon-layout-and-loading)
- [A classic script addon](#a-classic-script-addon)
- [A Python addon](#a-python-addon)
- [Game events](#game-events)
- [Verified APIs](#verified-apis)
- [Behaviours to know](#behaviours-to-know)
- [Python 2.5 constraints](#python-25-constraints)
- [es_tools commands (est_compat)](#es_tools-commands-est_compat)
- [Debugging](#debugging)

## Addon layout and loading

An addon is a folder in `cstrike/addons/eventscripts/`:

```
addons/eventscripts/myaddon/
├── es_myaddon.txt        classic script addon (blocks and events)
└── myaddon.py            Python addon (functions and events)
```

An addon can be classic script, Python, or both. EventScripts creates `__init__.py` in the folder by itself. Prefer
**lower-case folder names** (see [Behaviours to know](#behaviours-to-know)).

| Command | Effect |
|---|---|
| `es_load myaddon` | loads `addons/eventscripts/myaddon` (runs `load`) |
| `es_unload myaddon` | unloads it (runs `unload`) |
| `es_reload myaddon` | unload + load, after editing the files |
| `es_load folder/sub` | loads a sub-addon (`addons/eventscripts/folder/sub/`) |
| `es_scriptpacklist` | lists the loaded addons |

Addons to load at every start go in `cstrike/cfg/autoexec.cfg`, one `es_load` per line.

## A classic script addon

`addons/eventscripts/hello/es_hello.txt`:

```
block load
{
  es_xset hello_uid 0
  es_xset hello_name 0
  es_xregsaycmd !hello hello/hello "Says hello"
}

block unload
{
  es_xunregsaycmd !hello
}

block hello
{
  es_xgetcmduserid hello_uid
  es_getplayername hello_name server_var(hello_uid)
  es_tell server_var(hello_uid) #multi #greenHello #lightgreen server_var(hello_name)
}

event player_death
{
  es_msg #multi #lightgreen event_var(es_attackername) #defaultkilled #lightgreen event_var(es_username)
}
```

Variables are server variables (ConVars): create them with `es_xset name value` before using them. `es_` commands expand
`server_var(...)` and `event_var(...)`; `es_x` commands do not (see [Variable expansion](#behaviours-to-know)).

## A Python addon

`addons/eventscripts/hellopy/hellopy.py`:

```python
# -*- coding: utf-8 -*-
import es
import cmdlib
import playerlib

info = es.AddonInfo()
info.name = "hellopy"
info.basename = "hellopy"
info.version = "1.0"


def load():
    cmdlib.registerSayCommand("!health", cmd_health, "Shows your health")


def unload():
    cmdlib.unregisterSayCommand("!health")


def cmd_health(userid, args):
    player = playerlib.getPlayer(userid)
    es.tell(userid, "#multi", "#greenHealth: #lightgreen%s" % player.get("health"))


def player_spawn(ev):                     # every function named like a game event receives it
    es.tell(ev["userid"], "Welcome back, %s" % ev["es_username"])
```

Every public function of the module is also a block, callable from classic script with `es_doblock hellopy/cmd_name`.
Functions whose name starts with `_` are private.

## Game events

In Python, a function named like the event receives an event object: `ev["userid"]`, `ev["attacker"]`… (it has no
`get()` method). In classic script, `event player_death { ... }` and `event_var(attacker)`.

EventScripts adds variables to player events, for example `es_userteam`, `es_username`, `es_steamid`, and for the
attacker `es_attackerteam`, `es_attackername`, `es_attackersteamid`. EventScripts also fires `es_map_start`.

All Counter-Strike: Source events are received (`player_spawn`, `player_hurt`, `player_death`, `round_start`,
`round_end`, `bomb_planted`, `bomb_defused`, `item_pickup`, `player_say`…), except the "noisy" ones until they are
requested (see below). Custom events are declared in a `.res` file loaded with `es_loadevents declare <file>`.

## Verified APIs

Exercised by the test addons and EventScripts' own test suites on the current engine:

| Area | Functions |
|---|---|
| Players | `es.getUseridList`, `es.getuserid`, `es.getplayername`, `es.getplayersteamid`, `es.getplayerteam`, `es.isbot`, `es.getplayerhandle`, `es.getindexfromhandle`, `es.getplayerlocation`, `es.setpos`, `es.createplayerlist` (kills, deaths, health, armor, weapon, position, ping…) |
| Network props | `es.getplayerprop` / `es.setplayerprop` (`CBasePlayer.m_iHealth`, `CCSPlayer.m_iAccount`, `CCSPlayer.m_ArmorValue`, `CBasePlayer.pl.deadflag`, `CBaseEntity.m_vecOrigin`…), `es.getindexprop` (`CTeam.m_iScore`…) |
| Entities | `es.createentitylist`, `es.getEntityIndexes`, `es.entitygetvalue`, `es.fire`, `es_xgive` (weapons and items), `es_entcreate` |
| Messages | `es.tell`, `es.msg`, `es.centertell`, `es_toptext`, `usermsg.hudhint`, `usermsg.keyhint`, `usermsg.centermsg`, `usermsg.fade`, `usermsg.shake`, `usermsg.motd`, `es_usermsg` |
| Sounds | `es.playsound`, `es_emitsound` |
| Commands | `cmdlib.registerSayCommand` / `registerClientCommand` / `registerServerCommand`, `es_regsaycmd`, `es_regcmd`, `es.getargv`, `es.getargc`, `es_sexec`, `es_cexec`, `es.server.queuecmd`, `es.server.cmd` |
| Variables | `es.ServerVar`, `es.set`, `es.getString`, `es.getInt`, `es_xset`, `es_math`, `es_mathparse` |
| Timers | `gamethread.delayed`, `gamethread.delayedname`, `gamethread.cancelDelayed`, `repeat`, `es_delayed`, `es_xsoon` |
| Data | keygroups (`es_keygroupcreate`, `es_keysetvalue`, `es_keygroupsave` / `load`, `es_keygroupcopy`, `keygroupsort`, `es_foreachkey`), `keyvalues`, `sqlite3` (SQLite 3.6.23), `configobj`, `path` |
| Libraries | `playerlib` (`get`/`set`: health, armor, cash, speed, color, weapons…), `popuplib` (`easymenu`, `easylist`, popups), `keymenu`, `cfglib`, `langlib`, `vecmath`, `services` (authorization), eXtensible Admin (`es_load xa`, load an auth provider first: `es_load examples/auth/basic_auth`) |

## Behaviours to know

These are behaviours of EventScripts and of the engine, unchanged since 2013 unless stated; most of them surprised us
while writing the test addons.

| Behaviour | What to do |
|---|---|
| **Events are processed at the end of the frame.** The values carried by the event are exact, but a prop read inside the handler gives the end-of-frame state: a second hit in the same frame is already applied, the frag of a kill is already counted. | Trust the event values; compare a prop with another source read at the same moment, not with the event. |
| **The `player_hurt` of a fatal hit arrives after the death was processed** (Counter-Strike: Source): frags and money are already updated, armor is reset. | Do not use the fatal `player_hurt` as a "before" snapshot. |
| **"Noisy" events** (`weapon_fire`, footsteps, jumps, reloads…) are ignored until requested. | `es.doblock("corelib/noisy_on")` in `load`, `es.doblock("corelib/noisy_off")` in `unload` (reference counted). |
| **Variable expansion in classic script** happens only in `es_` commands (not `es_x`) and after the `es` prefix, and only at the start of a word: `uniqueid myvar event_var(userid)` receives the raw text. | Write `es uniqueid myvar event_var(userid)`; put a space before `server_var(...)` (`Health: server_var(x)`, not `Health:server_var(x)`). |
| **`{ } ( ) ' :` split words in classic script** (engine tokenizer). An apostrophe in a message becomes a separate word. | Quote strings, avoid apostrophes in `es_tell`/`es_msg` texts. |
| `es_dbgmsg` and `echo` print their words joined with spaces. | Cosmetic. |
| **KeyValues numbers read back from disk become floats with 6 decimals** (`1.75` → `1.750000`). | Compare numerically, or store as text you control. |
| **An alias cannot have the name of a server variable** (current engine). | Use distinct names (this broke corelib `while`, fixed in this release). |
| **Folders with upper-case letters**: the engine looks folders up in lower case; the loader creates lower-case links next to existing folders when the server starts. | Use lower-case names for new addons; folders created while the server runs get their link at the next start. |
| Files are read as bytes; players expect **UTF-8**. | Save scripts as UTF-8. Python files with non-ASCII characters need `# -*- coding: utf-8 -*-` on the first line. |
| `popuplib` does not send menus to bots. | Test menus with a real player. |
| `es_install` is disabled (ESAM is gone). | Install addons by copying their folder. |

## Python 2.5 constraints

EventScripts embeds Python 2.5.1 (with psyco). Code written for Python 2.6+ often fails:

- no `with` statement (unless `from __future__ import with_statement`), no `str.format`, no `json` module,
  no `tuple.index()`, no `except X as e` (write `except X, e`), no `print()` as a function;
- conditional expressions (`a if c else b`), generators, `set`, `sorted`, decorators and `sqlite3` are available;
- psyco is active (`psyco.full()` is called by the ES libraries): `sys.getrefcount` returns meaningless values;
- `print` output goes to the server console; prefer `es.dbgmsg(0, text)`.

To check syntax before loading: `python2.7 -m py_compile file.py` catches most errors (2.7 accepts a little more than 2.5).

## es_tools commands (est_compat)

With Metamod:Source, SourceMod 1.12 and [`optional/est_compat`](../optional/est_compat) installed, these commands are
available from classic script, Python (`es.server.queuecmd`) and the console. `<players>` is a userid or a filter `#a`,
`#t`, `#ct`, `#alive`, `#dead`, `#bot`, `#human` (combinable: `#t#alive`).

| Command | Effect |
|---|---|
| `est_setgravity <players> <gravity>` | gravity multiplier (1.0 = normal) |
| `est_setplayercolor <players> <r> <g> <b> <a> [weapons 0/1]` | color and transparency (alpha < 255 = transparent), optionally of the weapons |
| `est_burn <players> [seconds]` / `est_extinguish <players>` | set on fire / put out |
| `est_healthadd <players> <hp>` / `est_sethealth <players> <hp>` | add / set health |
| `est_setarmor <players> <armor>` | set armor |
| `est_setspeed <players> <multiplier>` | movement speed (1.0 = normal) |
| `est_god <players> <0/1>`, `est_noclip <players> <0/1>`, `est_freeze <players> <0/1>` | god mode, noclip, freeze |
| `est_damage <attacker> <victims> <damage>` | damage credited to the attacker (armor absorbs it as in the game) |
| `est_spawn <players> [force 0/1]` | respawn (dead players, or everyone with force) |
| `est_getwallbetween <var> <x1> <y1> <z1> <x2> <y2> <z2>` | `var` = 1 if the world blocks the line between the two points |
| `est_rounddecimal <var> <value> <decimals>` | `var` = value rounded |

## Debugging

- Python exceptions are printed in the server console after `*** EventScripts caught an exception`, with the traceback.
- `eventscripts_debug 1` (or higher) prints what EventScripts executes; `es_xdbgmsg 0 text` prints from scripts.
- EventScripts' own test suites: copy `addons/eventscripts/unittest/unittest.cfg` to `cfg/` and run
  `exec unittest.cfg` (84 tests, plus the Python tests of `pyunittest`).
- [`verify_data`](../test-addons/verify_data) is a model of an addon that checks its own data while the game runs.
- For crashes in native code, run `srcds_linux` under `gdb`. For memory corruption of Python objects, the loader can be
  built with `-DES_SHIM_EFENCE` ([`src/es_shim/build.sh -DES_SHIM_EFENCE`](../src/es_shim/build.sh)): after `SIGUSR2` is
  sent to the server, Python objects of a chosen size get their own page and freed objects become inaccessible, so a
  use-after-free crashes immediately in the call stack of the culprit. This is how the nested return value bug was found
  ([TECHNICAL.md](TECHNICAL.md)).
