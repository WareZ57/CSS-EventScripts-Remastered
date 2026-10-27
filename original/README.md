# Original EventScripts 2.1.1.379

The last EventScripts builds published by Mattie (21 April 2013), unchanged, recovered from the Wayback Machine copy of
`build.eventscripts.com` after every official site (mattie.info, eventscripts.com) went offline.

| File | Source |
|---|---|
| `es2-ob-linux-bld379.zip` | `http://build.eventscripts.com/eventscripts2/2013-04-21/379-804b28a522eb/es2-ob-linux-bld379.zip` ([archive](https://web.archive.org/web/20140810191225/http://build.eventscripts.com/eventscripts2/2013-04-21/379-804b28a522eb/es2-ob-linux-bld379.zip)) |
| `es2-ob-windows-bld379.zip` | `http://build.eventscripts.com/eventscripts2/2013-04-21/379-804b28a522eb/es2-ob-windows-bld379.zip` ([archive](https://web.archive.org/web/20140810191136/http://build.eventscripts.com/eventscripts2/2013-04-21/379-804b28a522eb/es2-ob-windows-bld379.zip)) |

SHA-256 checksums: [SHA256SUMS](SHA256SUMS). The release announcement, "EventScripts Public Beta v2.1.1.379
(Apr-22-2013)", is [archived here](https://web.archive.org/web/20130603161432/http://forums.eventscripts.com/viewtopic.php?f=128&t=40765).

The `cstrike/` folder of this repository is the content of the Linux archive (without the precompiled `.pyc` files, which
Python rebuilds), plus `addons/es_shim.so` and three patched files. [`changes-vs-bld379.patch`](changes-vs-bld379.patch)
contains those changes and applies to the extracted archive:

```sh
mkdir es379 && cd es379
unzip ../es2-ob-linux-bld379.zip
patch -p1 < ../changes-vs-bld379.patch
```

The Windows archive is kept for preservation only: the fixes of this repository are Linux-only.
