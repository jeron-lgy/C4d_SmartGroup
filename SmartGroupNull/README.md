# Smart Group Select for Cinema 4D 2025.2

Smart Group Select marks Null objects as selectable group roots. When enabled,
selecting a child object automatically selects the nearest enabled marked Null,
so move, rotate, and scale operate on the whole group.

The custom tag creates a viewport helper cube named `__SGN_Boundary_Box`
under the marked Null. The helper is forced to wire display with a Display tag
and is disabled for rendering. Helpers are automatically assigned to the
`SGN Boundary Helpers` layer. The layer's Manager Visibility is turned off only
when the plugin creates it for the first time; later user changes are preserved.

## Install

1. Copy the whole `SmartGroupNull` folder into your Cinema 4D plugins folder.
2. Restart Cinema 4D 2025.2.
3. Open the Extensions/Plugins menu and use the Smart Group Select commands.

Common Windows plugin location:

```text
C:\Users\<you>\AppData\Roaming\Maxon\Maxon Cinema 4D 2025_*\plugins
```

## Commands

- `Mark Group`
  Adds the Smart Group tag to selected Null objects.
- `Unmark`
  Removes the Smart Group tag from selected objects.
- `Master Toggle`
  Toggles all Smart Group behavior on or off.
- `Toggle Group`
  Toggles the per-tag enable switch for selected Smart Groups.
- `Axis Bottom`
  Moves selected Smart Group axes to the world bottom center while
  keeping child objects in place.
- `Axis Ground`
  Moves selected Smart Group axes to the bottom center, then
  moves the group so that the axis sits on world Y zero.
- `Light Mask`
  Opens a Sun/Env/1-32 selector and applies the Octane Object Tag light pass
  mask to selected objects. Objects without an Octane Object Tag receive one.

## Tag Options

- `Enable Group`
  Enables selection redirection for this Null.
- `Show Box`
  Shows or hides the viewport box for this Null.
- `Box Color`
  Controls the viewport box color.
- `Box Padding`
  Expands the viewport box by a fixed scene-unit amount.

## Behavior

- Only object mode is redirected. Point, edge, and polygon editing are left alone.
- If a selected child belongs to an enabled Smart Group, selection jumps to
  that Null.
- In nested groups, the nearest enabled Smart Group wins.
- Multi-selection is supported. Children from different groups are collapsed to
  their corresponding Nulls.
- Objects outside Smart Groups stay selected normally.
- Axis bottom-center placement uses the marked Null's current local orientation.

## Notes

The plugin IDs are local development IDs. If you publish this plugin publicly,
replace them with registered IDs from Maxon.
