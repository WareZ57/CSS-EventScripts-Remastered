# -*- coding: utf-8 -*-
# test_menu - test addon in Python (popuplib, playerlib, usermsg, gamethread)
# Chat commands: !menu  !info  !motd
import es
import cmdlib
import gamethread
import playerlib
import popuplib
import usermsg

info = es.AddonInfo()
info.name = "test_menu"
info.basename = "test_menu"
info.version = "1.0"

TAG = "#green[test_menu] #default"


def tell(userid, text):
    es.tell(userid, "#multi", TAG + text)


def load():
    cmdlib.registerSayCommand("!menu", cmd_menu, "Test: popup menu")
    cmdlib.registerSayCommand("!info", cmd_info, "Test: player information (HUD)")
    cmdlib.registerSayCommand("!motd", cmd_motd, "Test: MOTD window")

    menu = popuplib.easymenu("test_menu_main", None, on_choice)
    menu.settitle("EventScripts test menu")
    menu.addoption("heal", "Heal (100 HP)")
    menu.addoption("armor", "Kevlar + helmet")
    menu.addoption("deagle", "Desert Eagle")
    menu.addoption("gravity", "Low gravity (10 s)")
    menu.addoption("speed", "Speed x1.5 (10 s)")
    menu.addoption("color", "Turn red")
    menu.addoption("effects", "Shake + fade")
    es.msg("#multi", TAG + "loaded: type #lightgreen!menu")


def unload():
    for cmd in ("!menu", "!info", "!motd"):
        cmdlib.unregisterSayCommand(cmd)
    if popuplib.exists("test_menu_main"):
        popuplib.delete("test_menu_main")


def cmd_menu(userid, args):
    popuplib.send("test_menu_main", userid)


def on_choice(userid, choice, popupid):
    if es.getplayerprop(userid, "CBasePlayer.pl.deadflag"):
        tell(userid, "you must be alive")
        return
    p = playerlib.getPlayer(userid)
    if choice == "heal":
        p.set("health", 100)
        tell(userid, "100 HP")
    elif choice == "armor":
        es.server.queuecmd("es_xgive %d item_assaultsuit" % userid)
        tell(userid, "kevlar + helmet")
    elif choice == "deagle":
        es.server.queuecmd("es_xgive %d weapon_deagle" % userid)
        tell(userid, "Desert Eagle given")
    elif choice == "gravity":
        es.fire(userid, "!self", "addoutput", "gravity 0.3")
        tell(userid, "low gravity for 10 seconds")
        gamethread.delayed(10, reset_gravity, userid)
    elif choice == "speed":
        p.set("speed", 1.5)
        tell(userid, "speed x1.5 for 10 seconds")
        gamethread.delayed(10, reset_speed, userid)
    elif choice == "color":
        p.set("color", (255, 0, 0, 255))
        tell(userid, "you are red until your next spawn")
    elif choice == "effects":
        usermsg.shake(userid, 15, 2)
        usermsg.fade(userid, 0, 1, 1, 255, 0, 0, 128)
        tell(userid, "shake + red fade")


def reset_gravity(userid):
    if es.exists("userid", userid):
        es.fire(userid, "!self", "addoutput", "gravity 1")
        tell(userid, "normal gravity")


def reset_speed(userid):
    if es.exists("userid", userid):
        playerlib.getPlayer(userid).set("speed", 1.0)
        tell(userid, "normal speed")


def cmd_info(userid, args):
    p = playerlib.getPlayer(userid)
    x, y, z = es.getplayerlocation(userid)
    text = "%s\n%s\nHealth %s  Armor %s  Money $%s\nPosition %d %d %d" % (
        p.attributes["name"], es.getplayersteamid(userid), p.get("health"), p.get("armor"),
        p.get("cash"), x, y, z)
    usermsg.hudhint(userid, text)
    usermsg.keyhint(userid, "test_menu: keyhint works")
    tell(userid, "information shown at the bottom of the screen")


def cmd_motd(userid, args):
    usermsg.motd(userid, 0, "EventScripts test",
                 "EventScripts 2.1.1.379 is running on this server.\n\n"
                 "Commands: !testhelp !menu !info !stats")
