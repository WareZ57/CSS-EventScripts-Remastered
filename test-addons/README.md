# Test addons

Seven small addons written for this version of EventScripts, to try it on your server and to read as examples. They are
not installed by default.

## Installing

1. Copy the folders you want (or all of them) into `cstrike/addons/eventscripts/` on your server.
2. Load them from the server console, or add the lines to `cstrike/cfg/autoexec.cfg` to load them at every start:

```
es_load popup
es_load keymenu
es_load test_chat
es_load test_menu
es_load test_stats
es_load verify_data
es_load leaderboard
es_load timer_test
es_load sql_rank
```

`popup` and `keymenu` are part of EventScripts: they provide the `popup` and `keymenu` commands to classic scripts (the
test addons use the Python libraries directly and work without them). Remove a test addon with `es_unload <name>` and by
deleting its folder.

To have opponents: `bot_join_after_player 0; bot_quota 6` in the server console (`bot_kick` to remove them).

## The addons

| Addon | Type | Chat commands | Server console | What it tests |
|---|---|---|---|---|
| [`test_chat`](test_chat) | classic script | `!testhelp` `!hello` `!hp` `!money` `!ak` `!countdown` | | chat commands, colors, props, `es_give`, `es_delayed`, kill messages |
| [`test_menu`](test_menu) | Python | `!menu` `!info` `!motd` | | popuplib menu (heal, armor, Desert Eagle, low gravity, speed, color, screen effects), playerlib, usermsg, gamethread |
| [`test_stats`](test_stats) | Python | `!stats` | | events, kills/deaths/headshots, kill streaks (DOUBLE KILL…), sounds, HUD |
| [`verify_data`](verify_data) | Python | `!verify` `!tests` | `verify_report` `verify_reset` | while the game runs: the engine player info, the network props and the events must agree, and frags, deaths and team scores must follow the game rules |
| [`leaderboard`](leaderboard) | classic script | `!top` `!me` | `leaderboard_test` `leaderboard_reset` | kill leaderboard in a keygroup saved at every round end; the test saves, wipes, reloads and compares |
| [`timer_test`](timer_test) | Python | `!timers` | `timers_test` | accuracy of `gamethread.delayed`, `es_xdelayed` and `repeat`, firing order, cancelled timer (results after 7 seconds) |
| [`sql_rank`](sql_rank) | Python | `!rank` `!toprank` | `sql_test` `sql_check` | persistent stats in SQLite, checked at every round end against an in-memory counter; integrity test |

Expected results on a working server: `verify_report` and `sql_check` with 0 failed checks after a few rounds,
`leaderboard_test` 9 passed, `timers_test` 9 passed, `sql_test` 4 passed. A failure is printed in the console with its
details, prefixed with `FAILED`.

The classic script addons avoid apostrophes in their messages: in classic script an apostrophe is a word separator.
