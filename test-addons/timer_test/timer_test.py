# -*- coding: utf-8 -*-
# timer_test - measures the accuracy of the EventScripts timers (gamethread.delayed, es_xdelayed in
# classic script, repeat) and checks the firing order and the cancelling of a named timer.
# Chat: !timers      Server console: timers_test      (the test lasts 7 seconds)
import es
import cmdlib
import gamethread
import repeat
import time

info = es.AddonInfo()
info.name = "timer_test"
info.basename = "timer_test"
info.version = "1.0"

TAG = "#green[timers] #default"
TOLERANCE = 0.1          # seconds (the server runs at 66 ticks per second, 15 ms per tick)
DELAYS = (0.1, 0.5, 1.0, 2.0, 5.0)
run = {}                 # state of the running test


def load():
    cmdlib.registerSayCommand("!timers", say_test, "Measures the accuracy of the ES timers (7 s)")
    cmdlib.registerServerCommand("timers_test", console_test, "Measures the accuracy of the ES timers (7 s)")
    cmdlib.registerServerCommand("timers_mark", mark_cmd, "Used internally by timer_test")
    es.msg("#multi", TAG + "loaded: type #lightgreen!timers")


def unload():
    cmdlib.unregisterSayCommand("!timers")
    cmdlib.unregisterServerCommand("timers_test")
    cmdlib.unregisterServerCommand("timers_mark")
    gamethread.cancelDelayed("timers_cancelled")
    if repeat.find("timers_repeat"):
        repeat.delete("timers_repeat")


def say_test(userid, args):
    start(userid)


def console_test(args):
    start(None)


def out(text):
    es.dbgmsg(0, "[timers] " + text)
    if run.get("userid") and es.exists("userid", run["userid"]):
        es.tell(run["userid"], "#multi", TAG + text)


def start(userid):
    if run.get("active"):
        if userid:
            es.tell(userid, "#multi", TAG + "a test is already running")
        return
    run.clear()
    run.update(active=True, userid=userid, start=time.time(), marks=[], ticks=[], cancelled_fired=False)
    out("test started, results in 7 seconds")
    for d in DELAYS:
        gamethread.delayed(d, mark, ("gamethread.delayed %.1f s" % d, d))
    # Timer of the classic script engine, measured by the timers_mark command
    es.server.queuecmd("es_xdelayed 3 timers_mark 3")
    # repeat: 5 runs, 1 second apart
    if repeat.find("timers_repeat"):
        repeat.delete("timers_repeat")
    repeat.create("timers_repeat", tick)
    repeat.start("timers_repeat", 1, 5)
    # Named timer cancelled right away: it must never fire
    gamethread.delayedname(1.5, "timers_cancelled", cancelled)
    gamethread.cancelDelayed("timers_cancelled")
    gamethread.delayed(7, report)


def mark(name, expected):
    run["marks"].append((name, expected, time.time() - run["start"]))


def mark_cmd(args):
    if run.get("active") and args:
        mark("es_xdelayed %s s (script)" % args[0], float(args[0]))


def tick():
    run["ticks"].append(time.time() - run["start"])


def cancelled():
    run["cancelled_fired"] = True


def report():
    ok = ko = 0
    for name, expected, elapsed in run["marks"]:
        drift = elapsed - expected
        good = abs(drift) <= TOLERANCE
        if good:
            ok += 1
        else:
            ko += 1
        out("%s: measured %.3f s, drift %+d ms %s" % (name, elapsed, int(drift * 1000), good and "OK" or "FAILED"))

    fired = [m[0] for m in run["marks"]]
    expected_order = [m[0] for m in sorted(run["marks"], key=lambda m: m[1])]
    good = fired == expected_order and len(run["marks"]) == len(DELAYS) + 1
    ok, ko = ok + good, ko + (not good)
    out("firing order (%d timers) %s" % (len(run["marks"]), good and "OK" or "FAILED"))

    ticks = run["ticks"]
    gaps = [b - a for a, b in zip([0.0] + ticks[:-1], ticks)]
    good = len(ticks) == 5 and max([abs(g - 1.0) for g in gaps] or [9]) <= TOLERANCE
    ok, ko = ok + good, ko + (not good)
    out("repeat: %d/5 runs, intervals %s %s" % (
        len(ticks), ", ".join(["%.3f" % g for g in gaps]), good and "OK" or "FAILED"))

    good = not run["cancelled_fired"]
    ok, ko = ok + good, ko + (not good)
    out("cancelled timer never fired %s" % (good and "OK" or "FAILED"))

    out("result: %d passed, %d failed" % (ok, ko))
    if repeat.find("timers_repeat"):
        repeat.delete("timers_repeat")
    run["active"] = False
