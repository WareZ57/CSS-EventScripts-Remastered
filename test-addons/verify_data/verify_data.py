# -*- coding: utf-8 -*-
# verify_data - continuously checks that EventScripts reports correct data, by comparing three
# independent sources (engine player info through es.createplayerlist, network props through
# es.getplayerprop, event data) and the game rules (frags, deaths, team score).
# ES processes game events at the end of the frame: a prop read inside an event handler gives the
# end-of-frame state (a second hit in the same frame is already applied). The checks take this into
# account: two sources read at the same moment, the chain of events, counters compared at round end.
# Chat: !verify (summary)  !tests (list of the test addons)   Server console: verify_report  verify_reset
import es
import cmdlib
import gamethread

info = es.AddonInfo()
info.name = "verify_data"
info.basename = "verify_data"
info.version = "1.0"

TAG = "#green[verify] #default"

results = {}    # check name -> [passed, failed]
failures = []   # latest failures, with details
life = {}       # userid -> health according to the last event (damage chain)
base = {}       # userid -> (frags, deaths) of the engine at round start
counted = {}    # userid -> [frags, deaths] according to the events since round start
scores = {}     # team number -> score at round start


def check(name, ok, detail=""):
    r = results.setdefault(name, [0, 0])
    if ok:
        r[0] += 1
    else:
        r[1] += 1
        failures.append("%s: %s" % (name, detail))
        del failures[:-30]
        es.dbgmsg(0, "[verify] FAILED %s: %s" % (name, detail))


def plist(uid):
    try:
        return es.createplayerlist(uid)[int(uid)]
    except (KeyError, ValueError):
        return None


def prop(uid, name):
    return es.getplayerprop(uid, name)


def team_scores():
    found = {}
    for index in es.createentitylist("cs_team_manager"):
        found[int(es.getindexprop(index, "CTeam.m_iTeamNum"))] = int(es.getindexprop(index, "CTeam.m_iScore"))
    return found


def load():
    cmdlib.registerSayCommand("!verify", cmd_verify, "Summary of the EventScripts data checks")
    cmdlib.registerSayCommand("!tests", cmd_tests, "List of the test addons")
    cmdlib.registerServerCommand("verify_report", cmd_report, "Details of the EventScripts data checks")
    cmdlib.registerServerCommand("verify_reset", cmd_reset, "Resets the EventScripts data checks")
    scores.update(team_scores())
    snapshot_counters()
    es.msg("#multi", TAG + "loaded: type #lightgreen!verify")


def unload():
    cmdlib.unregisterSayCommand("!verify")
    cmdlib.unregisterSayCommand("!tests")
    cmdlib.unregisterServerCommand("verify_report")
    cmdlib.unregisterServerCommand("verify_reset")


# ── Identity and position: three sources for the same information ────

def player_spawn(ev):
    uid = int(ev["userid"])
    gamethread.delayed(0.1, check_identity, (uid, ev["es_userteam"]))


def check_identity(uid, event_team):
    p = plist(uid)
    if not p or int(p["teamid"]) < 2:
        return
    check("team: event = engine = es.getplayerteam",
          str(event_team) == str(p["teamid"]) == str(es.getplayerteam(uid)),
          "event %s, engine %s, getplayerteam %s" % (event_team, p["teamid"], es.getplayerteam(uid)))
    handle = es.getplayerhandle(uid)
    check("index: engine = handle -> index", int(p["index"]) == es.getindexfromhandle(handle),
          "engine %s, handle %s -> %s" % (p["index"], handle, es.getindexfromhandle(handle)))
    check("handle: engine = es.getplayerhandle", int(p["handle"]) == handle,
          "engine %s, getplayerhandle %s" % (p["handle"], handle))
    check("userid: es.getuserid(name)", es.getuserid(p["name"]) == uid,
          "getuserid(%r) = %s, expected %s" % (p["name"], es.getuserid(p["name"]), uid))
    loc = es.getplayerlocation(uid)
    origin = [float(v) for v in str(prop(uid, "CBaseEntity.m_vecOrigin")).split(",")]
    pl = (float(p["x"]), float(p["y"]), float(p["z"]))
    check("position: engine = getplayerlocation = m_vecOrigin",
          max([abs(a - b) for a, b in zip(loc, pl) + zip(loc, origin)]) < 1.0,
          "getplayerlocation %s, engine %s, m_vecOrigin %s" % (loc, pl, origin))
    # The game also fires player_spawn when a player joins a team while dead
    if not int(p["isdead"]):
        life[uid] = int(p["health"])
        check("health at spawn: engine = prop = 100",
              int(p["health"]) == int(prop(uid, "CBasePlayer.m_iHealth")) == 100,
              "engine %s, prop %s" % (p["health"], prop(uid, "CBasePlayer.m_iHealth")))


# ── Damage: the events and the engine must agree ─────────────────────

def player_hurt(ev):
    uid = int(ev["userid"])
    health, dmg = int(ev["health"]), int(ev["dmg_health"])
    if uid in life:
        # Healing between two hits (regeneration addons...) can only raise the health
        expected = max(life[uid] - dmg, 0)
        check("damage: event health >= previous health - damage", health >= expected,
              "previous %s, damage %s, event %s" % (life[uid], dmg, health))
    life[uid] = health
    # The two ES sources read at the same moment must agree
    p = plist(uid)
    if p:
        check("damage: prop health = engine health", int(prop(uid, "CBasePlayer.m_iHealth")) == int(p["health"]),
              "prop %s, engine %s" % (prop(uid, "CBasePlayer.m_iHealth"), p["health"]))
        check("damage: prop armor = engine armor", int(prop(uid, "CCSPlayer.m_ArmorValue")) == int(p["armor"]),
              "prop %s, engine %s" % (prop(uid, "CCSPlayer.m_ArmorValue"), p["armor"]))


# ── Deaths: frags according to the game rules ────────────────────────

def player_death(ev):
    uid, attacker = int(ev["userid"]), int(ev["attacker"])
    life.pop(uid, None)
    check("death: deadflag = 1", int(prop(uid, "CBasePlayer.pl.deadflag")) == 1,
          "deadflag %s" % prop(uid, "CBasePlayer.pl.deadflag"))
    p = plist(uid)
    if p:
        check("death: engine isdead = 1", int(p["isdead"]) == 1, "isdead %s" % p["isdead"])
    counted.setdefault(uid, [0, 0])[1] += 1
    if attacker == uid:
        counted[uid][0] -= 1                       # suicide: -1 frag
    elif attacker:
        enemy = ev["es_attackerteam"] != ev["es_userteam"]
        counted.setdefault(attacker, [0, 0])[0] += enemy and 1 or -1   # team kill: -1 frag
        a = plist(attacker)
        weapon = ev["weapon"]
        if a and weapon not in ("hegrenade", "world", "") and not int(a["isdead"]):
            check("death: event weapon = weapon in the attacker hands",
                  a["weapon"] == "weapon_" + weapon, "event %s, in hands %s" % (weapon, a["weapon"]))


# CS:S rule: defusing the bomb, or having planted it when it explodes, is worth 3 points (frags)
BOMB_POINTS = 3


def bomb_defused(ev):
    counted.setdefault(int(ev["userid"]), [0, 0])[0] += BOMB_POINTS


def bomb_exploded(ev):
    if int(ev["userid"]):
        counted.setdefault(int(ev["userid"]), [0, 0])[0] += BOMB_POINTS


def snapshot_counters():
    base.clear()
    counted.clear()
    for uid, p in es.createplayerlist().items():
        base[int(uid)] = (int(p["kills"]), int(p["deaths"]))


def check_counters():
    players = es.createplayerlist()
    for uid, (kills, deaths) in base.items():
        if uid not in players:
            continue
        k, d = counted.get(uid, [0, 0])
        now = players[uid]
        check("rule: engine frags = frags counted from the events", int(now["kills"]) == kills + k,
              "%s: start %s + events %+d, engine %s" % (now["name"], kills, k, now["kills"]))
        check("rule: engine deaths = deaths counted from the events", int(now["deaths"]) == deaths + d,
              "%s: start %s + events %+d, engine %s" % (now["name"], deaths, d, now["deaths"]))


# ── Rounds: the winning team score goes up by 1 ──────────────────────

def round_start(ev):
    scores.clear()
    scores.update(team_scores())
    snapshot_counters()


def round_end(ev):
    winner = int(ev["winner"])
    if winner in (2, 3):
        gamethread.delayed(0.2, check_score, (winner, dict(scores)))
    gamethread.delayed(0.2, check_counters)


def check_score(winner, old):
    now = team_scores()
    if winner in old and winner in now:
        check("rule: winning team score +1", now[winner] == old[winner] + 1,
              "team %s: %s -> %s" % (winner, old[winner], now[winner]))


# ── Reports ───────────────────────────────────────────────────────────

TESTS = (
    "#lightgreen!verify #default: continuous checks of the ES data (engine, props, events, rules)",
    "#lightgreen!top !me #default: leaderboard saved to disk (classic script, keygroups)",
    "#lightgreen!timers #default: accuracy of the timers (7 s)",
    "#lightgreen!rank !toprank #default: persistent stats in SQLite",
    "#lightgreen!testhelp #default: first tests (chat, menu, stats)",
)


def cmd_tests(userid, args):
    for line in TESTS:
        es.tell(userid, "#multi", TAG + line)


def totals():
    ok = sum([r[0] for r in results.values()])
    ko = sum([r[1] for r in results.values()])
    return ok, ko


def cmd_verify(userid, args):
    ok, ko = totals()
    color = ko and "#lightgreen" or "#green"
    es.tell(userid, "#multi", "%s%s%d #defaultchecks: %d passed, %d failed, %d kinds of checks"
            % (TAG, color, ok + ko, ok, ko, len(results)))
    for line in failures[-3:]:
        es.tell(userid, "#multi", TAG + line)


def cmd_report(args):
    ok, ko = totals()
    es.dbgmsg(0, "[verify] %d checks: %d passed, %d failed" % (ok + ko, ok, ko))
    names = results.keys()
    names.sort()
    for name in names:
        r = results[name]
        es.dbgmsg(0, "[verify]   %-55s %5d passed %4d failed" % (name, r[0], r[1]))
    for line in failures:
        es.dbgmsg(0, "[verify]   FAILED " + line)


def cmd_reset(args):
    results.clear()
    del failures[:]
    es.dbgmsg(0, "[verify] reset")
