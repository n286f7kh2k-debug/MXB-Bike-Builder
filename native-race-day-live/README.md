# MXB Race Day Live — Native Rebuild

Fresh native Windows rebuild. The previous Python-hosted application is intentionally not used as a runtime dependency.

## Foundation goals

- Real Windows `MXB Race Day Live.exe`
- WPF/.NET shell with embedded application identity/icon
- Profile-first race-night home UI
- Minimal top navigation with secondary tools hidden in a menu
- Background automatic update checks
- Hot-swappable feature/UI modules so normal updates apply inside the running window without closing the app or refreshing the whole shell
- Transactional module staging, SHA-256 verification, atomic activation, and rollback
- Add larger features back one at a time only after the current layer is stable

## Update architecture

The native shell is intentionally small and stable. Normal releases update feature modules and assets instead of replacing the running executable. A module update is downloaded to a staging directory, verified, activated by switching the local module pointer, unloaded/reloaded, and then swapped into the existing shell content region. The main window remains open throughout the update.

A change to the shell executable itself is treated separately because Windows cannot overwrite a running executable in place. Normal product/UI/feature development should stay in hot-swappable modules so routine updates do not require a restart.
