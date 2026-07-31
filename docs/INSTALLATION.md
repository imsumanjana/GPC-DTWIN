# Installation and Storage

## Supported Python versions

Python 3.11, 3.12, and 3.13 are supported.

## Source installation

Run `scripts/setup.ps1`, then `scripts/run.ps1`. Source installations are portable and keep writable
files within the repository.

## Packaged installation

Packaged Windows builds keep read-only application resources beside the executable and writable files
under `%LOCALAPPDATA%\GPC-DTwin`. This avoids permission problems in protected installation folders.
Set `GPC_DTWIN_HOME` before launch to use another writable location.

## Database migration

Version 1.0 uses the stable filename `gpc_dtwin.sqlite3`. If a compatible `gpc_dtwin_v09.sqlite3`
exists in the same application data location, it is copied automatically on the first v1.0.1 launch.
