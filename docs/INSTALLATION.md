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
first compatible launch.

## Native access-violation diagnostics

Windows exit code `-1073741819` corresponds to a native access violation. Version 1.2.0 retains the native-stability safeguards that reduce this
risk by using matching Qt components, software rendering, timer-based chart discovery, stable canvas
reuse, and orderly chart-helper shutdown. When the code is encountered, `run.ps1` points to the native
crash log and recommends `scripts/release_check.ps1`.

## macOS ARM64 release build

The repository includes `.github/workflows/build-macos.yml` for Apple-silicon packaging. The workflow is intended to be run by GitHub Actions on the `macos-26` ARM64 runner rather than from the Windows development machine.

The workflow:

1. installs the pinned release stack from `requirements-lock.txt`;
2. verifies the ARM64 architecture and matching PyQt/Qt runtime;
3. runs non-GUI tests and the source self-check;
4. freezes `src/gpc_dtwin/app.py` with PyInstaller;
5. bundles reference data, template data, application resources, documentation, and licence files;
6. collects Matplotlib/scikit-learn package data and required SciPy submodules;
7. confirms the Cocoa Qt platform plugin is present;
8. runs `GPC-DTwin.app/Contents/MacOS/GPC-DTwin --self-check` before DMG creation;
9. verifies the final DMG and writes a SHA-256 checksum.

The generated DMG is an ARM64 package. Developer-ID signing and Apple notarization are separate distribution steps and require the appropriate Apple credentials/secrets.
