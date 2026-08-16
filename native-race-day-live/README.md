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

## Theme direction

The existing UI now uses a fixed game-dashboard composition rather than the old long vertical utility layout: left-side navigation, compact HUD modules, image-backed rider identity when profile images exist, electric-blue accents, compact glowing borders, stronger hierarchy, and aggressive motocross-style typography. Theme passes must restyle existing screens without adding product sections or functionality unless explicitly requested. The v1.0.15 dashboard pass keeps the existing feature set intact while changing the page composition to match the supplied game-UI reference much more closely.

## First checkpoint

The first checkpoint intentionally contains only the native shell, profile-card home feature, persistent rider profile, MX Bikes environment/profile detection, Launch MX Bikes, and the live feature updater. Larger race-day systems are being added back one at a time after the native foundation is validated.

The Windows build publishes a self-contained `MXB Race Day Live.exe` and a separate `MXBRaceDayLive.Profile.dll` module. There is no Python launcher or Python-owned window in this rebuild.

## Garage / 3D preview

The Garage reads installed MX Bikes bike IDs and loadout state without launching MX Bikes. Plain readable EDF geometry continues to use the native Race Day Live viewer. Creator-sealed OEM geometry now routes to an internal Race Day Live component based on the public iNsane/dmkrtz3DViewer workflow instead of requiring Frost or a second manually installed application. Race Day Live owns the component under its LocalAppData folder, starts it hidden, embeds its window inside the Garage, and uses the clicked MX Bikes bike ID to automatically target the closest matching bike entry. MX Bikes itself remains closed.

The public iNsane viewer package is obtained from its publisher endpoint by Race Day Live on demand and cached inside the app's own component directory. Users are not asked to separately install Frost or iNsane's viewer. If the publisher endpoint blocks automated package retrieval, the Garage reports that component-download problem instead of falling back to the sealed EDF parser.

The iNsane component's required .NET 6 Desktop Runtime is also provisioned privately under Race Day Live's LocalAppData component folder. Runtime provisioning is deliberately lazy: it happens only when a sealed-bike preview is opened, never during hot-module activation, so viewer setup cannot break the in-app update transaction.

## Settings / Game File Links

The profile home includes a Settings entry with a Game File Links page. Users can manually link the MX Bikes install folder, user-data folder, mods root, bikes folder, rider folder, helmets, boots, and an optional paints location. Each row includes a folder browser and live found/missing state. Links are stored under Race Day Live's LocalAppData settings directory. The manually linked Bikes folder is merged into the Garage scan and wins for duplicate bike IDs so users can override incorrect auto-detection without changing MX Bikes itself.

## Update architecture

The native shell is intentionally small and stable. Normal releases update feature modules and assets instead of replacing the running executable. A module update is downloaded to a staging directory, SHA-256 verified, loaded next to the current module, and rendered in the existing content region. Only after successful activation is the new module persisted as the startup version. The main window remains open throughout the update; a failed module leaves the existing feature running.

A change to the shell executable itself is treated separately because Windows cannot overwrite a running executable in place. Normal product/UI/feature development should stay in hot-swappable modules so routine updates do not require a restart.