# -*- coding: utf-8 -*-
# sql_rank - persistent stats in SQLite (sqlite3 module of the Python 2.5 shipped with ES), checked at
# every round end against a counter kept in memory.
# Chat: !rank  !toprank     Server console: sql_test (SQLite integrity)  sql_check (database = memory)
import es
import cmdlib
import os
import sqlite3

info = es.AddonInfo()
info.name = "sql_rank"
info.basename = "sql_rank"
info.version = "1.0"

TAG = "#green[sql_rank] #default"
db = None
session = {}      # player id -> [kills, deaths, hs] counted in memory since loading
baseline = {}     # player id -> [kills, deaths, hs] in the database when counting started
checks = [0, 0]   # database = memory checks: [passed, failed]
COLUMNS = {"kills": 0, "deaths": 1, "hs": 2}


def path():
    return os.path.join(es.getAddonPath("sql_rank"), "rank.db")


def load():
    global db
    db = sqlite3.connect(path())
    db.text_factory = str
    db.execute("CREATE TABLE IF NOT EXISTS players (id TEXT PRIMARY KEY, name TEXT, "
               "kills INTEGER DEFAULT 0, deaths INTEGER DEFAULT 0, hs INTEGER DEFAULT 0)")
    db.commit()
    cmdlib.registerSayCommand("!rank", cmd_rank, "Your rank (SQLite)")
    cmdlib.registerSayCommand("!toprank", cmd_top, "Top 5 (SQLite)")
    cmdlib.registerServerCommand("sql_test", cmd_test, "SQLite integrity test")
    cmdlib.registerServerCommand("sql_check", cmd_check, "Database = memory checks")
    es.msg("#multi", TAG + "loaded: #lightgreen!rank !toprank")


def unload():
    for c in ("!rank", "!toprank"):
        cmdlib.unregisterSayCommand(c)
    for c in ("sql_test", "sql_check"):
        cmdlib.unregisterServerCommand(c)
    if db:
        db.commit()
        db.close()


def player_id(userid):
    sid = es.getplayersteamid(userid)
    return sid == "BOT" and "BOT_" + es.getplayername(userid) or sid


def row(pid):
    r = db.execute("SELECT kills, deaths, hs FROM players WHERE id = ?", (pid,)).fetchone()
    return r and list(r) or [0, 0, 0]


def add(userid, column):
    pid = player_id(userid)
    name = unicode(es.getplayername(userid), "utf-8", "replace")
    if pid not in session:
        session[pid] = [0, 0, 0]
        baseline[pid] = row(pid)
    db.execute("INSERT OR IGNORE INTO players (id, name) VALUES (?, ?)", (pid, name))
    db.execute("UPDATE players SET name = ?, %s = %s + 1 WHERE id = ?" % (column, column), (name, pid))
    session[pid][COLUMNS[column]] += 1


def player_death(ev):
    victim, attacker = int(ev["userid"]), int(ev["attacker"])
    if victim:
        add(victim, "deaths")
    if attacker and attacker != victim and ev["es_attackerteam"] != ev["es_userteam"]:
        add(attacker, "kills")
        if int(ev["headshot"]):
            add(attacker, "hs")


def round_end(ev):
    db.commit()
    for pid, counts in session.items():
        now = row(pid)
        expected = [b + c for b, c in zip(baseline[pid], counts)]
        if now == expected:
            checks[0] += 1
        else:
            checks[1] += 1
            es.dbgmsg(0, "[sql_rank] FAILED %s: database %s, expected %s" % (pid, now, expected))


def cmd_rank(userid, args):
    pid = player_id(userid)
    kills, deaths, hs = row(pid)
    rank = db.execute("SELECT COUNT(*) + 1 FROM players WHERE kills > ?", (kills,)).fetchone()[0]
    total = db.execute("SELECT COUNT(*) FROM players").fetchone()[0]
    es.tell(userid, "#multi", "%sRank #lightgreen%d/%d #default: %d kills, %d deaths, %d HS"
            % (TAG, rank, max(total, 1), kills, deaths, hs))


def cmd_top(userid, args):
    es.tell(userid, "#multi", TAG + "Top 5 (SQLite database):")
    rows = db.execute("SELECT name, kills, deaths FROM players ORDER BY kills DESC, deaths ASC LIMIT 5").fetchall()
    for i, (name, kills, deaths) in enumerate(rows):
        es.tell(userid, "#multi", "#lightgreen%d - %s #default: %d kills, %d deaths" % (i + 1, name, kills, deaths))
    if not rows:
        es.tell(userid, "#multi", TAG + "the database is empty for now")


def cmd_check(args):
    es.dbgmsg(0, "[sql_rank] database = memory: %d passed, %d failed, %d players tracked" % (checks[0], checks[1], len(session)))


def cmd_test(args):
    """Integrity: rolled back transaction, sum over 1000 rows, UTF-8 text, persistence after reopening."""
    ok = ko = 0
    results = []
    try:
        db.execute("CREATE TEMP TABLE t (n INTEGER, s TEXT)")
        db.executemany("INSERT INTO t VALUES (?, ?)", [(i, u"row %d Zoë" % i) for i in range(1000)])
        results.append(("1000 rows inserted", db.execute("SELECT COUNT(*), SUM(n) FROM t").fetchone() == (1000, 499500)))
        results.append(("UTF-8 text read back unchanged",
                        db.execute("SELECT s FROM t WHERE n = 7").fetchone()[0] == u"row 7 Zoë".encode("utf-8")))
        db.execute("DROP TABLE t")

        db.commit()
        before = db.execute("SELECT COUNT(*) FROM players").fetchone()[0]
        db.execute("INSERT INTO players (id, name) VALUES ('test_rollback', 'x')")
        db.rollback()
        after = db.execute("SELECT COUNT(*) FROM players").fetchone()[0]
        results.append(("rollback cancels the insert", before == after))

        db.execute("INSERT OR REPLACE INTO players (id, name, kills) VALUES ('test_persist', ?, 1234)", (u"Noël Zoë",))
        db.commit()
        other = sqlite3.connect(path())
        other.text_factory = str
        r = other.execute("SELECT name, kills FROM players WHERE id = 'test_persist'").fetchone()
        other.close()
        results.append(("persistence (second connection)", r == (u"Noël Zoë".encode("utf-8"), 1234)))
        db.execute("DELETE FROM players WHERE id = 'test_persist'")
        db.commit()
    except Exception, e:
        results.append(("exception %s" % e, False))
    for name, good in results:
        if good:
            ok += 1
        else:
            ko += 1
        es.dbgmsg(0, "[sql_test] %s %s" % (name, good and "OK" or "FAILED"))
    es.dbgmsg(0, "[sql_test] %d passed, %d failed (sqlite %s)" % (ok, ko, sqlite3.sqlite_version))
