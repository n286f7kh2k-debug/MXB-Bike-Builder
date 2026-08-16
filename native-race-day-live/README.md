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
- Deep MX Bikes integration through a dedicated native service layer
- Frost/public MXB format research retained as a reference for future asset, gear and 3D tooling
- Add larger features back one at a time only after the current layer is stable

## First checkpoint

The first checkpoint intentionally contains only the native shell, profile-card home feature, persistent rider profile, MX Bikes environment/profile detection, Launch MX Bikes, and the live feature updater. Larger race-day systems are being added back one at a time after the native foundation is validated.

The Windows build publishes a self-contained `MXB Race Day Live.exe` and a separate `MXBRaceDayLive.Profile.dll` module. There is no Python launcher or Python-owned window in this rebuild.

## Garage / 3D preview

The Garage reads installed MX Bikes bike IDs and loadout state without launching MX Bikes. Plain readable EDF geometry uses the native Race Day Live viewer. Creator-sealed EDF geometry is routed through an external authorized preview provider instead of being mis-parsed or replaced with a fake model. The first sealed-bike provider can attach to the user's installed MXB App/Frost renderer, drive its normal Studio controls to the clicked bike ID, and host the working renderer inside the Race Day Live Garage while MX Bikes remains closed. The bridge uses the Windows UI Automation support already provided by the WPF Windows desktop runtime, so no separate automation runtime is installed.

## Update architecture

The native shell is intentionally small and stable. Normal releases update feature modules and assets instead of replacing the running executable. A module update is downloaded to a staging directory, SHA-256 verified, loaded next to the current module, and rendered in the existing content region. Only after successful activation is the new module persisted as the startup version. The main window remains open throughout the update; a failed module leaves the existing feature running.

A change to the shell executable itself is treated separately because Windows cannot overwrite a running executable in place. Normal product/UI/feature development should stay in hot-swappable modules so routine updates do not require a restart.