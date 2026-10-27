/*
 * est_compat - es_tools (est_*) commands for EventScripts on today's Counter-Strike: Source.
 *
 * es_tools (est4css) shipped with most EventScripts addons; its 2013 binary no longer works. This
 * SourceMod plugin brings back the most used commands, with the same syntax, so that addons of that era
 * find them. The est_effect visual effects are not part of this plugin.
 *
 * <players>: a userid, or a filter #a (all), #t, #ct, #alive, #dead, #bot, #human, which can be combined
 * (#t#alive). Commands that return a value write it to a server variable (as EventScripts does).
 *
 * Requires Metamod:Source and SourceMod 1.12 (SDK Tools, SDK Hooks and CS Tools extensions).
 *
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
#include <sourcemod>
#include <sdktools>
#include <sdkhooks>
#include <cstrike>

#pragma semicolon 1
#pragma newdecls required

public Plugin myinfo =
{
    name = "est_compat",
    author = "CSS-EventScripts-Remastered",
    description = "es_tools (est_*) commands for EventScripts",
    version = "1.0",
    url = ""
};

public void OnPluginStart()
{
    RegServerCmd("est_setgravity", Cmd_SetGravity, "est_setgravity <players> <gravity> (1.0 = normal)");
    RegServerCmd("est_setplayercolor", Cmd_SetPlayerColor, "est_setplayercolor <players> <r> <g> <b> <a> [weapons 0/1]");
    RegServerCmd("est_burn", Cmd_Burn, "est_burn <players> [duration in seconds]");
    RegServerCmd("est_extinguish", Cmd_Extinguish, "est_extinguish <players>");
    RegServerCmd("est_healthadd", Cmd_HealthAdd, "est_healthadd <players> <health>");
    RegServerCmd("est_sethealth", Cmd_SetHealth, "est_sethealth <players> <health>");
    RegServerCmd("est_setarmor", Cmd_SetArmor, "est_setarmor <players> <armor>");
    RegServerCmd("est_setspeed", Cmd_SetSpeed, "est_setspeed <players> <multiplier>");
    RegServerCmd("est_god", Cmd_God, "est_god <players> <0/1>");
    RegServerCmd("est_noclip", Cmd_Noclip, "est_noclip <players> <0/1>");
    RegServerCmd("est_freeze", Cmd_Freeze, "est_freeze <players> <0/1>");
    RegServerCmd("est_damage", Cmd_Damage, "est_damage <attacker> <victims> <damage>");
    RegServerCmd("est_spawn", Cmd_Spawn, "est_spawn <players> [force 0/1]");
    RegServerCmd("est_getwallbetween", Cmd_GetWallBetween, "est_getwallbetween <variable> <x1> <y1> <z1> <x2> <y2> <z2>");
    RegServerCmd("est_rounddecimal", Cmd_RoundDecimal, "est_rounddecimal <variable> <value> <decimals>");
}

/* ── Player selection ────────────────────────────────────────────── */

static int Targets(const char[] spec, int[] out)
{
    int count = 0;
    if (spec[0] != '#') {
        int client = GetClientOfUserId(StringToInt(spec));
        if (client > 0 && IsClientInGame(client))
            out[count++] = client;
        return count;
    }
    bool t = StrContains(spec, "#t", false) != -1 && StrContains(spec, "#ct", false) == -1;
    bool ct = StrContains(spec, "#ct", false) != -1;
    bool alive = StrContains(spec, "#alive", false) != -1;
    bool dead = StrContains(spec, "#dead", false) != -1;
    bool bot = StrContains(spec, "#bot", false) != -1;
    bool human = StrContains(spec, "#human", false) != -1;
    for (int client = 1; client <= MaxClients; client++) {
        if (!IsClientInGame(client))
            continue;
        int team = GetClientTeam(client);
        if ((t && team != 2) || (ct && team != 3))
            continue;
        if ((alive && !IsPlayerAlive(client)) || (dead && IsPlayerAlive(client)))
            continue;
        if ((bot && !IsFakeClient(client)) || (human && IsFakeClient(client)))
            continue;
        out[count++] = client;
    }
    return count;
}

static int ArgTargets(int arg, int[] out)
{
    char spec[64];
    GetCmdArg(arg, spec, sizeof(spec));
    return Targets(spec, out);
}

static float ArgFloat(int arg)
{
    char buffer[32];
    GetCmdArg(arg, buffer, sizeof(buffer));
    return StringToFloat(buffer);
}

static int ArgInt(int arg)
{
    char buffer[32];
    GetCmdArg(arg, buffer, sizeof(buffer));
    return StringToInt(buffer);
}

/* EventScripts server variable (a ConVar): created if needed, as es_set does */
static void SetServerVar(const char[] name, const char[] value)
{
    ConVar cvar = FindConVar(name);
    if (cvar == null)
        cvar = CreateConVar(name, "", "EventScripts variable (est_compat)", FCVAR_DONTRECORD);
    cvar.SetString(value);
}

static bool Usage(int needed)
{
    if (GetCmdArgs() >= needed)
        return false;
    char name[64];
    GetCmdArg(0, name, sizeof(name));
    PrintToServer("[est_compat] wrong syntax for %s (see: help %s)", name, name);
    return true;
}

/* ── Commands ────────────────────────────────────────────────────── */

public Action Cmd_SetGravity(int args)
{
    if (Usage(2)) return Plugin_Handled;
    int targets[MAXPLAYERS];
    int n = ArgTargets(1, targets);
    float gravity = ArgFloat(2);
    for (int i = 0; i < n; i++)
        SetEntityGravity(targets[i], gravity);
    return Plugin_Handled;
}

public Action Cmd_SetPlayerColor(int args)
{
    if (Usage(5)) return Plugin_Handled;
    int targets[MAXPLAYERS];
    int n = ArgTargets(1, targets);
    int r = ArgInt(2), g = ArgInt(3), b = ArgInt(4), a = ArgInt(5);
    bool weapons = args >= 6 && ArgInt(6) != 0;
    for (int i = 0; i < n; i++) {
        SetEntityRenderMode(targets[i], a < 255 ? RENDER_TRANSCOLOR : RENDER_NORMAL);
        SetEntityRenderColor(targets[i], r, g, b, a);
        if (!weapons)
            continue;
        int size = GetEntPropArraySize(targets[i], Prop_Send, "m_hMyWeapons");
        for (int slot = 0; slot < size; slot++) {
            int weapon = GetEntPropEnt(targets[i], Prop_Send, "m_hMyWeapons", slot);
            if (weapon > MaxClients && IsValidEntity(weapon)) {
                SetEntityRenderMode(weapon, a < 255 ? RENDER_TRANSCOLOR : RENDER_NORMAL);
                SetEntityRenderColor(weapon, r, g, b, a);
            }
        }
    }
    return Plugin_Handled;
}

public Action Cmd_Burn(int args)
{
    if (Usage(1)) return Plugin_Handled;
    int targets[MAXPLAYERS];
    int n = ArgTargets(1, targets);
    float duration = args >= 2 ? ArgFloat(2) : 10.0;
    for (int i = 0; i < n; i++)
        if (IsPlayerAlive(targets[i]))
            IgniteEntity(targets[i], duration);
    return Plugin_Handled;
}

public Action Cmd_Extinguish(int args)
{
    if (Usage(1)) return Plugin_Handled;
    int targets[MAXPLAYERS];
    int n = ArgTargets(1, targets);
    for (int i = 0; i < n; i++)
        ExtinguishEntity(targets[i]);
    return Plugin_Handled;
}

public Action Cmd_HealthAdd(int args)
{
    if (Usage(2)) return Plugin_Handled;
    int targets[MAXPLAYERS];
    int n = ArgTargets(1, targets);
    int amount = ArgInt(2);
    for (int i = 0; i < n; i++)
        if (IsPlayerAlive(targets[i]))
            SetEntityHealth(targets[i], GetClientHealth(targets[i]) + amount);
    return Plugin_Handled;
}

public Action Cmd_SetHealth(int args)
{
    if (Usage(2)) return Plugin_Handled;
    int targets[MAXPLAYERS];
    int n = ArgTargets(1, targets);
    int health = ArgInt(2);
    for (int i = 0; i < n; i++)
        if (IsPlayerAlive(targets[i]))
            SetEntityHealth(targets[i], health);
    return Plugin_Handled;
}

public Action Cmd_SetArmor(int args)
{
    if (Usage(2)) return Plugin_Handled;
    int targets[MAXPLAYERS];
    int n = ArgTargets(1, targets);
    int armor = ArgInt(2);
    for (int i = 0; i < n; i++)
        SetEntProp(targets[i], Prop_Send, "m_ArmorValue", armor);
    return Plugin_Handled;
}

public Action Cmd_SetSpeed(int args)
{
    if (Usage(2)) return Plugin_Handled;
    int targets[MAXPLAYERS];
    int n = ArgTargets(1, targets);
    float speed = ArgFloat(2);
    for (int i = 0; i < n; i++)
        SetEntPropFloat(targets[i], Prop_Data, "m_flLaggedMovementValue", speed);
    return Plugin_Handled;
}

public Action Cmd_God(int args)
{
    if (Usage(2)) return Plugin_Handled;
    int targets[MAXPLAYERS];
    int n = ArgTargets(1, targets);
    int on = ArgInt(2);
    for (int i = 0; i < n; i++)
        SetEntProp(targets[i], Prop_Data, "m_takedamage", on ? 0 : 2, 1);
    return Plugin_Handled;
}

public Action Cmd_Noclip(int args)
{
    if (Usage(2)) return Plugin_Handled;
    int targets[MAXPLAYERS];
    int n = ArgTargets(1, targets);
    int on = ArgInt(2);
    for (int i = 0; i < n; i++)
        SetEntityMoveType(targets[i], on ? MOVETYPE_NOCLIP : MOVETYPE_WALK);
    return Plugin_Handled;
}

public Action Cmd_Freeze(int args)
{
    if (Usage(2)) return Plugin_Handled;
    int targets[MAXPLAYERS];
    int n = ArgTargets(1, targets);
    int on = ArgInt(2);
    for (int i = 0; i < n; i++)
        SetEntityMoveType(targets[i], on ? MOVETYPE_NONE : MOVETYPE_WALK);
    return Plugin_Handled;
}

public Action Cmd_Damage(int args)
{
    if (Usage(3)) return Plugin_Handled;
    int attacker = GetClientOfUserId(ArgInt(1));
    int targets[MAXPLAYERS];
    int n = ArgTargets(2, targets);
    float damage = ArgFloat(3);
    for (int i = 0; i < n; i++)
        if (IsPlayerAlive(targets[i]))
            SDKHooks_TakeDamage(targets[i], attacker > 0 ? attacker : 0, attacker > 0 ? attacker : 0, damage, DMG_GENERIC);
    return Plugin_Handled;
}

public Action Cmd_Spawn(int args)
{
    if (Usage(1)) return Plugin_Handled;
    int targets[MAXPLAYERS];
    int n = ArgTargets(1, targets);
    bool force = args >= 2 && ArgInt(2) != 0;
    for (int i = 0; i < n; i++)
        if (GetClientTeam(targets[i]) >= 2 && (force || !IsPlayerAlive(targets[i])))
            CS_RespawnPlayer(targets[i]);
    return Plugin_Handled;
}

public bool TraceWorldOnly(int entity, int mask)
{
    return entity == 0;
}

public Action Cmd_GetWallBetween(int args)
{
    if (Usage(7)) return Plugin_Handled;
    char varname[64];
    GetCmdArg(1, varname, sizeof(varname));
    float a[3], b[3];
    for (int i = 0; i < 3; i++) {
        a[i] = ArgFloat(2 + i);
        b[i] = ArgFloat(5 + i);
    }
    TR_TraceRayFilter(a, b, MASK_SOLID_BRUSHONLY, RayType_EndPoint, TraceWorldOnly);
    SetServerVar(varname, TR_DidHit() ? "1" : "0");
    return Plugin_Handled;
}

public Action Cmd_RoundDecimal(int args)
{
    if (Usage(3)) return Plugin_Handled;
    char varname[64], text[64];
    GetCmdArg(1, varname, sizeof(varname));
    float value = ArgFloat(2);
    int decimals = ArgInt(3);
    if (decimals <= 0)
        IntToString(RoundToNearest(value), text, sizeof(text));
    else
    {
        char format[16];
        FormatEx(format, sizeof(format), "%%.%df", decimals);
        FormatEx(text, sizeof(text), format, value);
    }
    SetServerVar(varname, text);
    return Plugin_Handled;
}
