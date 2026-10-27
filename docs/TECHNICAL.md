# Technical details

How EventScripts 2.1.1.379 (April 2013) was made to run on the current Counter-Strike: Source, bug by bug: symptom, root
cause, how it was found, and the fix. Useful if a future engine update breaks something again.

## Starting point

- **The engine.** Counter-Strike: Source moved to the TF2 engine branch in 2025 (`ServerVersion 11003710`). The dedicated
  server still has a 32-bit binary (`srcds_linux`, the default) next to the new 64-bit one; the 32-bit libraries are
  built against glibc 2.29.
- **EventScripts.** The last build, `es2-ob-linux-bld379.zip` (21 April 2013), comes from the Wayback Machine copy of
  `build.eventscripts.com` ([original/](../original)). The core, `mattie_eventscripts.so`, is a 32-bit library built
  with GCC 4.1.2, without PIC, not stripped and with debug information, which made the analysis possible. Its source code
  was never published, so it is used unmodified.
- **What still matched.** Every engine interface EventScripts asks for still exists under the same version
  (`VEngineServer021`, `GAMEEVENTSMANAGER002`, `ISERVERPLUGINCALLBACKS002`, `VEngineCvar004`, `VFileSystem022`…), all its
  imported symbols are still exported by `libtier0_srv.so` and `libvstdlib_srv.so`, and the `CCommand` layout is
  unchanged (`argv` at offset `0x408` both in the engine and in ES). So ES loads; the problems appear at run time.

## The loader: es_shim.so

`addons/mattie_eventscripts.vdf` loads `addons/es_shim` instead of `addons/mattie_eventscripts`. The shim
([source](../src/es_shim/es_shim.c)) exports only `CreateInterface` and `Py_InitModule4`. On the first `CreateInterface`
call from the engine it:

1. promotes itself to the global symbol scope (`dlopen(self, RTLD_GLOBAL | RTLD_NOLOAD)`, reference released at once),
   so that symbols it exports take precedence for libraries loaded afterwards;
2. creates the lower-case folder links (bug 4);
3. loads `mattie_eventscripts.so`, whose dependency `libpython2.5.so.1.0` is loaded with it;
4. rewrites some of ES's relocations (bugs 5 and 6);
5. forwards `CreateInterface` to ES. The engine then talks to ES directly.

When ES initializes Python, its call to `Py_InitModule4` resolves to the shim (global scope first), which wraps the ES
functions (bugs 2 and 3) before calling the real `Py_InitModule4` of libpython. When the engine unloads the shim, the
shim's destructor unloads ES (bug 7).

The shim is built in the `manylinux2014_i686` image and needs only glibc 2.3.3. It is compiled with `-mstackrealign`
because some of its functions are called with a misaligned stack.

## 1. Hang on every map start (es_checkversion)

- **Symptom.** `WatchDog! Server took too long to process (probably infinite loop)`, then the server exits, right after
  `SV_ActivateServer`.
- **Cause.** A gdb backtrace of the main thread showed it blocked in `connect()` called from Python's `socket` module:
  `corelib/es_checkversion` posts the server version, IP and port to `api.eventscripts.com` on every map start with
  `urllib2.urlopen`, without a timeout. The domain still resolves, but nothing answers.
- **Fix.** `es_xload corelib/es_checkversion` is commented out in `corelib/es_corelib.txt`. It also stops sending the
  server address to a domain that may change hands.

## 2. Crash when Python calls into the engine (stack alignment)

- **Symptom.** SIGSEGV in Steam code (`SetMasterServerKeyValue`, the `FCVAR_NOTIFY` callback of a ConVar), on a
  `movaps` instruction, as soon as a Python addon did `es.ServerVar("sv_gravity").set(800)` (the Python test suite did).
- **Cause.** `movaps` needs a 16-byte aligned stack, and the stack was 8 bytes off. Measuring `esp % 16` at function
  entries with gdb: the engine calls ES with an aligned stack, and ES (GCC 4.1.2) keeps the alignment, but the embedded
  libpython 2.5 and psyco code drift by 4 bytes at every nested call. Code from 2007 never needed more; today's engine
  and Steam libraries are built assuming the System V i386 ABI's 16-byte alignment.
- **Fix.** ES exposes its 197 Python functions (module `es_C`) only through `Py_InitModule4`. The shim intercepts that
  call and replaces each function pointer of the method table with a trampoline:

  ```
  push ebp ; mov ebp, esp ; and esp, -16           realign
  push [ebp+20] ; push [ebp+16] ; push [ebp+12] ; push [ebp+8]
  mov eax, <ES function> ; call eax                 the stack is aligned at the call
  mov dword [g_pPyReturn], 0                        see bug 3
  leave ; ret
  ```

## 3. Python heap corruption (nested es.* calls) — a bug from 2013

- **Symptom.** Loading the WCS addon crashed the server in `PyObject_Malloc`, deterministically, while Python was
  compiling an unrelated file. Disabling psyco, SourceMod or glibc's caches did not change anything.
- **How it was found.** Dumping the corrupted allocator pool showed a free-list pointer read 2 bytes too early, the mark
  of an object decremented (`Py_DECREF`) twice after being freed. Bisecting WCS pointed at an addon loaded with `es.load`
  from inside the import of another one, but the crash moved around. The shim was then built with an "electric fence"
  (`-DES_SHIM_EFENCE`): it exports `PyObject_Malloc/Free/Realloc`, which libpython then calls instead of its own
  allocator; after `SIGUSR2`, objects of the corrupted size class get their own page, made inaccessible when freed.
  The next run crashed on the faulty `Py_DECREF` itself: a `POP_TOP` right after `es.load(...)` returned, on a freed
  string `"-928.000000 -776.000000 176.000000"`, a spawn point origin read by `es.entitygetvalue` during that load.
- **Cause.** Disassembling `espy_load` (and every other `espy_*` function) gives:

  ```c
  g_pPyReturn = NULL;
  do_es_xload(command);                 /* the ES command may set g_pPyReturn to a new object */
  if (g_pPyReturn) return g_pPyReturn;  /* handed over without Py_INCREF: the command created it */
  Py_INCREF(Py_None); return Py_None;
  ```

  `g_pPyReturn` is never reset after the return. When `es.load` loads an addon whose `load()` calls
  `es.entitygetvalue`, the inner call leaves its result in `g_pPyReturn`, and `es.load` returns it a second time,
  although it already belongs to the inner caller. Python then releases it one time too many. The bug was already in
  2013; the memory layout of that time simply hid it.
- **Fix.** The trampolines write `NULL` to `g_pPyReturn` after every call (the return value is already in `eax`).

## 4. Folders with upper-case letters

- **Symptom.** `ERROR: Could not load keygroup: addons/eventscripts/corelib/interfaces/AuthorizationService/es_AuthorizationService_db.txt!`
  at startup, then `cannot find key: _constants`: the authorization service and interface constants were missing.
- **Cause.** The current engine filesystem looks folders up in lower case; only the final file name is matched
  case-insensitively. `exec zzTestDir/a.cfg` fails while `exec zztestdir2/Upper.cfg` works. Any folder with an
  upper-case letter is unreachable through the engine (keygroups, `exec`), while Python, which uses the real paths,
  still finds it.
- **Fix.** When it loads, the shim walks `addons/eventscripts` and `cfg` (`nftw`, without following links) and creates a
  lower-case symbolic link next to every folder whose name has upper-case letters (`authorizationservice ->
  AuthorizationService`). Scripts and Python keep the original paths.

## 5. Paths with "//"

- **Symptom.** `es_keygroupsave mygroup` without a path: `ERROR: Could not save keygroup file: cfg//es_mygroup_db.txt!`.
- **Cause.** ES builds paths with formats such as `%s/%s/es_%s_db.txt`; with no sub-folder the result contains `//`,
  which the current filesystem refuses (`cfg/sub/es_x_db.txt` works).
- **Fix.** ES is not position independent: each call to `sprintf`, `snprintf` and `vsnprintf` is an `R_386_PC32`
  relocation written into its code at load time. The shim walks ES's dynamic relocation table and rewrites those 283
  call sites to its own wrappers, which collapse `//` in the result when the format string belongs to ES and describes a
  path. Nothing else in the process is affected.

## 6. UTF-8 text split inside characters

- **Symptom.** `es_tell` showed `16000 $ ajout � �s` instead of `16000 $ ajoutés`.
- **Cause.** The engine's command tokenizer (`CUtlBuffer::ParseToken`, also linked into ES through tier1) ends a word on
  `c <= ' '` with a signed `char`: every byte above 0x7F counts as a separator. The UTF-8 `é` (`C3 A9`) became the words
  `ajout`, `\xC3`, `\xA9s`, which ES joined with spaces. The engine's own `echo` behaves the same; the raw text (`ArgS`)
  is intact.
- **Fix.** The shim implements the same algorithm (quotes, break characters `{}()':`, `//` comments, the `ArgS` offset
  rules) on unsigned bytes. The 302 calls to `CCommand::Tokenize` inside ES are redirected to it, and the two entry
  points through which the engine hands commands to ES are wrapped by rewriting their vtable slot (`R_386_32`
  relocations): `ConCommand::Dispatch` (console and script commands) and `CEventScriptsPlugin::ClientCommand` (player
  commands and chat). Both re-tokenize the command from its raw text before calling ES. On ASCII input the result is
  identical to the engine's (checked on quotes, unterminated quotes, break characters, comments).

## 7. Unloading

- **Symptom.** `plugin_unload` left EventScripts in memory.
- **Fix.** The reference taken to promote the shim is released at once, so the engine can really unload it, and the
  shim's destructor calls `dlclose` on ES, as when the engine loaded ES directly: its static ConVar/ConCommand
  destructors run while the engine is alive.

## 8. corelib `while`

- **Symptom.** `Can't alias "_whilecmd" as it's already a ConCommand or ConVar`, and `while` loops did nothing.
- **Cause.** corelib used `_whilecmd` both as a server variable and as an alias; the current engine refuses an alias with
  the name of a ConVar.
- **Fix.** The alias is renamed `_whilecmd_alias` in `corelib/es_corelib.txt`.

## 9. es_install (ESAM)

`es_install` downloads addons from `addons.eventscripts.com` and runs them. The domain is dead and may change hands, so
in `_libs/python/esamlib.py` every request now raises `IOError("ESAM (addons.eventscripts.com) is offline...")`.
`corelib/es_install` itself stays loaded, because it also autoloads addons that were installed with it in the past.

## Not bugs

Observed during the tests, unrelated to this port:

- `quit` prints Steam assertions (`Attempt to call interface with invalid hSteamUser`): a stock server without any
  plugin does the same.
- `dlopen failed trying to load: ~/.steam/sdk32/steamclient.so` on servers not installed through SteamCMD: stock srcds.
- `DataTable warning: Out-of-range value ... m_flEndRadius` comes from addons sending visual effects with values above
  the engine limits (radius 4096, width 128, amplitude 64); the engine clamps them.
- `getplayerlocation, invalid userid` comes from scripts reading `event_var(attacker)` on damage without an attacker.
