# MXB Race Day Live — Native Rebuild Roadmap

## Foundation
- Native Windows WPF shell (`MXB Race Day Live.exe`)
- Embedded application identity/icon
- Profile-first race-night UI
- Hot-swappable feature modules
- Background update checks and in-window module replacement
- Deep MX Bikes profile/content integration

## Add back one feature at a time
1. Profile home / rider card
2. Profile editing and media customization
3. MX Bikes environment detection and active profile sync
4. Find a Race / race details / My Races
5. Championships and results
6. Wallet / payments
7. Live race features
8. Garage and loadout management

## Future customization tools
- Gear customization workspace
  - jerseys / pants / gloves / boots / helmets / protection
  - paint and texture assignment
  - race number / name / font support
  - preview against the exact selected MX Bikes gear model when readable
  - package/export workflow compatible with MX Bikes content structure

- 3D model creator workspace
  - import source meshes
  - model hierarchy / part management
  - transforms and attachment points
  - material / texture assignment
  - MX Bikes-oriented export pipeline
  - bike, rider and gear content targets
  - preview and validation before install

These editors will be separate feature modules so their dependencies and rendering workloads do not slow the core race-day app when the user is not using them.
