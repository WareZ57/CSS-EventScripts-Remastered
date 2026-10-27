# est_compat

SourceMod plugin that brings back the most used **es_tools** (`est_*`) commands for EventScripts addons, with their
original syntax. es_tools (est4css) shipped with most EventScripts addons of the 2010s; its binary no longer works on
the current Counter-Strike: Source.

## Installing

1. Install [Metamod:Source 1.12](https://www.sourcemm.net/downloads.php?branch=stable) and
   [SourceMod 1.12](https://www.sourcemod.net/downloads.php?branch=stable) (tested with Metamod:Source 1.12.0-git1228 and
   SourceMod 1.12.0.7255).
2. Copy the `cstrike/` folder of this directory over your server's `cstrike/` folder.
3. Restart the server; `sm plugins list` must list `est_compat`.

## Commands

`<players>` is a userid or a filter: `#a` (all), `#t`, `#ct`, `#alive`, `#dead`, `#bot`, `#human`, combinable
(`#t#alive`). Commands that return a value write it to a server variable, usable by EventScripts.

| Command | Effect |
|---|---|
| `est_setgravity <players> <gravity>` | gravity multiplier (1.0 = normal) |
| `est_setplayercolor <players> <r> <g> <b> <a> [weapons 0/1]` | color and transparency, optionally of the weapons too |
| `est_burn <players> [seconds]` | sets on fire (10 seconds by default) |
| `est_extinguish <players>` | puts out |
| `est_healthadd <players> <hp>` | adds health |
| `est_sethealth <players> <hp>` | sets health |
| `est_setarmor <players> <armor>` | sets armor |
| `est_setspeed <players> <multiplier>` | movement speed (1.0 = normal) |
| `est_god <players> <0/1>` | god mode |
| `est_noclip <players> <0/1>` | noclip |
| `est_freeze <players> <0/1>` | freeze |
| `est_damage <attacker> <victims> <damage>` | damage credited to the attacker (armor absorbs part of it, as in the game) |
| `est_spawn <players> [force 0/1]` | respawns dead players (everyone with force) |
| `est_getwallbetween <var> <x1> <y1> <z1> <x2> <y2> <z2>` | `var` = 1 if the world blocks the line between the two points, else 0 |
| `est_rounddecimal <var> <value> <decimals>` | `var` = value rounded to that many decimals |

Not included: the es_tools visual effects (`est_effect`) and the less common commands.

## Building

```sh
spcomp64 cstrike/addons/sourcemod/scripting/est_compat.sp -o est_compat.smx
```

with the SourceMod 1.12 compiler. License: GNU GPL v3 or later ([LICENSE](LICENSE)).
