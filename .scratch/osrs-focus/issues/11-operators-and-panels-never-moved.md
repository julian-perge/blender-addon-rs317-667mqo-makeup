# The operator and panel modules never moved into their own folders

Status: wontfix

The module design approved on 2026-11-04 moves the weighter, the texture tool, the Aether materials, the render style, the panels and the material colour list into `blender/operators/` and `blender/panels/`, largely unchanged except for calling `rs_layers` and `find_texture` ([architecture](../../../docs/agents/architecture.md)). Neither folder exists on 2026-11-09. Whether the move is still wanted is the owner's call.

## Comments

- 2026-11-10, triage with the user: needs-info. Whether the move is still wanted is the owner's call.
- 2026-11-10, design interview with the user: wontfix. The `rs_layers` and `find_texture` part of the design is already done (the weighter and the texture tool go through both). The rest is a file move that changes no behaviour, and a split by role (operators, panels) cuts across the feature grouping `blender/` grew after the design, such as the 14 `appearance_` modules. `blender/` stays flat with feature prefixes, and the owner wants no follow-up issue for feature packages. `docs/agents/architecture.md` says so.
