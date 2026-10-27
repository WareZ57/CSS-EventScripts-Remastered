# -*- coding: utf-8 -*-
# test_stats - test addon in Python (events, counters, kill streaks, sounds, HUD messages)
# Chat command: !stats
import es
import cmdlib
import usermsg

info = es.AddonInfo()
info.name = "test_stats"
info.basename = "test_stats"
info.version = "1.0"

TAG = "#green[test_stats] #default"
STREAKS = {2: "DOUBLE KILL", 3: "TRIPLE KILL", 4: "ULTRA KILL", 5: "RAMPAGE"}

stats = {}    # player key -> [kills, deaths, headshots]
streak = {}   # userid -> kills since the last spawn


def key(userid):
    return es.getplayersteamid(userid) + es.getplayername(userid)


def load():
    cmdlib.registerSayCommand("!stats", cmd_stats, "Test: your stats on this map")
    es.msg("#multi", TAG + "loaded: type #lightgreen!stats")


def unload():
    cmdlib.unregisterSayCommand("!stats")


def es_map_start(ev):
    stats.clear()
    streak.clear()


def round_start(ev):
    es.msg("#multi", TAG + "new round, good luck!")


def player_spawn(ev):
    streak[int(ev["userid"])] = 0


def player_death(ev):
    victim, attacker = int(ev["userid"]), int(ev["attacker"])
    stats.setdefault(key(victim), [0, 0, 0])[1] += 1
    streak[victim] = 0
    if not attacker or attacker == victim:
        return
    s = stats.setdefault(key(attacker), [0, 0, 0])
    s[0] += 1
    if int(ev["headshot"]):
        s[2] += 1
        if not es.isbot(attacker):
            usermsg.centermsg(attacker, "HEADSHOT!")
            es.playsound(attacker, "buttons/bell1.wav", 1.0)
    streak[attacker] = streak.get(attacker, 0) + 1
    name = STREAKS.get(streak[attacker])
    if name:
        es.msg("#multi", "%s#lightgreen%s #default: %s" % (TAG, es.getplayername(attacker), name))


def cmd_stats(userid, args):
    k, d, hs = stats.get(key(userid), [0, 0, 0])
    ratio = d and float(k) / d or float(k)
    es.tell(userid, "#multi", "%sKills #lightgreen%d #defaultDeaths #lightgreen%d #defaultHS #lightgreen%d #defaultRatio #lightgreen%.2f" % (TAG, k, d, hs, ratio))
    usermsg.hudhint(userid, "Kills %d | Deaths %d | Headshots %d | Streak %d" % (k, d, hs, streak.get(userid, 0)))
