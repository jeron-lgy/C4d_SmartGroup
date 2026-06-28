# Smart Group Select for Cinema 4D 2025.2

Smart Group Select marks Null objects as selectable group roots. When enabled,
selecting a child object automatically selects the nearest enabled marked Null,
so move, rotate, and scale operate on the whole group.

The plugin also adds viewport boundary helpers, axis placement tools, and an
Octane light pass mask helper.

## Install

1. Download `SmartGroup_v1.0.0.zip` from the release page.
2. Extract it.
3. Copy the whole `SmartGroupNull` folder into your Cinema 4D plugins folder.
4. Restart Cinema 4D 2025.2.

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
  Moves selected Smart Group axes to the world bottom center while keeping child objects in place.
- `Axis Ground`
  Moves selected Smart Group axes to the world bottom center, then moves the group so the axis sits on world Y zero.
- `Light Mask`
  Applies Octane Object Tag light pass masks to selected objects.

## Notes

The plugin folder is `SmartGroupNull`; keep that folder name when installing.
