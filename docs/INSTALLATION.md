# Installation and Storage

## Supported Python versions

Python 3.11, 3.12, and 3.13 are supported.

## Qt compatibility

The release pins PyQt6 6.11.0 and the Qt 6.11.0 runtime to matching builds. Setup installs the complete
tested package set from `requirements-lock.txt`, then verifies that the compiled and runtime Qt versions
match. A newer or mismatched package in an existing virtual environment may therefore be replaced.
This is intentional and improves reproducibility and native Windows stability.

## Source installation

Run `scripts/setup.ps1`, then `scripts/run.ps1`. Source installations are portable and keep writable
files within the repository.

The launcher enables software rendering and native Python fault diagnostics. Launch information and
native error output are appended to `.runtime/native-crash.log`.

## Packaged installation

Packaged Windows builds keep read-only application resources beside the executable and writable files
under `%LOCALAPPDATA%\GPC-DTwin`. This avoids permission problems in protected installation folders.
Set `GPC_DTWIN_HOME` before launch to use another writable location.

## Database migration

Version 1.0 and later use the stable filename `gpc_dtwin.sqlite3`. If a compatible
`gpc_dtwin_v09.sqlite3` exists in the same application data location, it is copied automatically on the
first 1.1.1 launch.

## Native access-violation diagnostics

Windows exit code `-1073741819` corresponds to a native access violation. Version 1.1.1 reduces this
risk by using matching Qt components, software rendering, timer-based chart discovery, stable canvas
reuse, and orderly chart-helper shutdown. When the code is encountered, `run.ps1` points to the native
crash log and recommends `scripts/release_check.ps1`.
