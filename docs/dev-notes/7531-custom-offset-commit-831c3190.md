# Issue #7531: investigate commit 831c3190 (custom offset persistence)

## Conflict check (before reading code)

All four checks ran, zero skipped.

- `search/issues type:pr is:open 7531 in:title,body,comments`: no results, no
  open PR references issue 7531.
- Timeline cross-references: one issue, `#7690 Changing the 'custom offset' for
  OffsetFromReferenceLine sometimes changes other instances as well`.
- `gh pr list --search "OffsetFromReferenceLine"`: no open PRs.
- `bimvoice` remotes matching `7531`: none.
- No existing work (ours or anyone else's open PR) targets this issue directly.

## Reporter's symptom (theoryshaw, 2026-01-04)

> Custom Offset for slabs, doesn't seem to be saving

with a screenshot of the material panel's "Use Custom Offset" section.

## Timeline

- `2026-01-04T19:15:39-06:00` Ryan Schultz (openingdesign.com, external
  contributor) commits `831c3190`, "Fix #7531: Add BBIM_MaterialLayer pset for
  custom offset persistence and UI improvements."
- `2026-01-04T19:15:43Z` theoryshaw (the reporter) closes the issue themselves,
  same day, presumably right after testing the fix.
- `2026-02-16T04:51:15Z` Moult reopens: "Reopening because I'd like to further
  investigate commit 831c3190."

## What commit 831c3190 actually did

Before this commit, "Use Custom Offset" was pure Blender UI state
(`obj.BIMObjectMaterialProperties.use_custom_offset` / `.custom_offset` /
`.custom_wall_reference` / `.custom_slab_reference`), never written into the IFC
file. It only affected the live geometry regeneration for as long as those
Blender properties held their value; nothing round-tripped through a save and
reload, matching the reported symptom exactly.

The commit adds a new `BBIM_MaterialLayer` pset (Bonsai's established naming
convention for tool-authored parametric-recipe psets, alongside existing ones
like `BBIM_Window`, `BBIM_Railing`, `BBIM_Array`, `BBIM_Batting`) attached to
the product, with `UseCustomOffset`, `CustomOffset`, `CustomWallReference`,
`CustomSlabReference`. `EnableEditingAssignedMaterial` loads it into the
Blender props on edit start; `EditAssignedMaterial` saves the Blender props
into it on edit completion. It also touches unrelated UI layout code and one
`format_distance()` sign-handling fix for negative imperial distances.

## What I tested, and what I found: a real, severe defect in the commit

I extracted the exact arithmetic `tool.Model.get_material_layer_custom_offset`
adds and ran it (pure Python, no Blender needed for this part, since it is
plain float math over `unit_scale`, `thickness`, and `custom_offset`).

Before this commit, the "custom offset -> `OffsetFromReferenceLine`" formula
kept every intermediate value in Blender's internal SI (metre) units and only
converted to the IFC file's native length unit once, at the very end
(`return layer_offset / unit_scale`).

Commit 831c3190 changed the live-editing branch (`props.use_custom_offset`
True, which is the path exercised every time a user ticks "Use Custom Offset"
and drags the offset field, i.e. exactly the reporter's own interactive
workflow) to pre-convert `custom_offset = props.custom_offset / unit_scale`
before the same formula, while leaving the rest of the formula (`thickness *
unit_scale`, etc.) unchanged. That mixes an SI-to-native conversion with a
native-to-SI conversion inside the same subtraction, which is only harmless
when `unit_scale == 1` (a metre-based IFC project).

Measured, for a 200mm-thick layer set, a millimetre-based IFC file
(`unit_scale = 0.001`, a very common project unit for architecture in Bonsai),
and a user-requested 50mm custom offset from the layer set's center:

```
pre-fix  (831c3190^) OffsetFromReferenceLine  = -50.0 mm      (correct)
post-fix (831c3190)  OffsetFromReferenceLine  = 49900.0 mm    (wrong: ~998x, wrong sign)
```

For a metre-based file the bug is invisible (`ratio post/pre = 1.0x`), which
is presumably why it was not caught in the same-day close: a metre-scale test
file hides it completely, and any project using millimetres (or any other
non-metre length unit) would see the custom offset put the wall or slab layer
roughly a thousand times further from its reference line than requested, with
the sign flipped. That is a severe, user-visible geometry corruption, not a
cosmetic issue.

A parallel bug exists in the pset-reload branch: `save_custom_offset_to_pset`
stores `CustomOffset` in the file's *native* unit
(`props.custom_offset / unit_scale`), but the commit's own
`get_material_layer_custom_offset` read it back as `pset.get("CustomOffset",
0.0)` with no conversion, i.e. treated a native-unit value as if it were SI.
So even the newly-added persistence path (the whole point of this commit,
addressing "doesn't seem to be saving") reintroduces the wrong number on
reload for any non-metre file.

## This is already fixed on `origin/v0.8.0` (not by us)

Both of these unit bugs have already been corrected, independently of this
task, by Bruno Perdigão:

- `95fcf9e35c` "fix custom_offset scale material layers" (2026-06-16) reverts
  the live-editing branch's arithmetic back to the pre-831c3190, SI-consistent
  form.
- `156c6183eb` "fix custom offset unit scale when loading from pset."
  (2026-06-16) adds the missing `* unit_scale` when reading `CustomOffset` back
  out of the pset.

Both commits are on `origin/v0.8.0` today (`git branch -r --contains` confirms
both). I re-ran the exact current-HEAD arithmetic through the same test:

```
current HEAD (post Bruno's 95fcf9e35c + 156c6183eb): OffsetFromReferenceLine = -50.0 mm
matches pre-831c3190 correct value of -50.0 mm: True
```

So whatever prompted Moult's "I'd like to further investigate" on
2026-02-16, if it was this unit-scale problem, is resolved as of 2026-06-16.
I found no other defect in 831c3190's own diff (the pset naming, the
persistence wiring, the UI layout changes, and the `format_distance()` sign
fix all look correct and are unrelated to the unit bug).

## A separate, still-open concern: shared `IfcMaterialLayerSetUsage` (relevant to #7690, not caused by 831c3190)

While tracing how the custom offset ends up on disk, I found that
`DumbWallPlaner`/`DumbSlabPlaner`'s `change_thickness()` writes the computed
offset directly onto whatever `ifcopenshell.util.element.get_material(element)`
returns: `material.OffsetFromReferenceLine = position.z`, with no check for
whether that `IfcMaterialLayerSetUsage` entity is exclusively used by this one
product.

I verified with `ifcopenshell.api.material.assign_material` (no Blender
needed) that assigning `type="IfcMaterialLayerSetUsage"` to two products in one
call, which is a documented, intended usage pattern of that API (see its own
docstring example, and its grouping-by-`(material_set, layer_set_direction)`
logic), creates a **single shared** usage entity for both products:

```
usage_a id: 16 #16=IfcMaterialLayerSetUsage(#7,.AXIS2.,.POSITIVE.,0.,$)
usage_b id: 16 #16=IfcMaterialLayerSetUsage(#7,.AXIS2.,.POSITIVE.,0.,$)
SAME ENTITY: True

Before: wall_a offset = 0.0  wall_b offset = 0.0
After writing wall_a's custom offset only:
  wall_a offset = 0.075
  wall_b offset = 0.075
```

Writing one product's offset changes both, which is exactly the behaviour
`#7690` reports ("sometimes changes other instances as well"). I checked
Bonsai's own call sites (`grep` across the codebase): every place Bonsai itself
calls `material.assign_material(..., type="IfcMaterialLayerSetUsage")` passes a
single-product list, and `root.copy_class` (used when duplicating an object in
Blender) explicitly deep-copies the usage entity so duplicates do not share
one. So this exact hazard does not appear to be reachable through Bonsai's own
object-creation or duplication flows today; it would only bite on a file whose
`IfcMaterialLayerSetUsage` entities are already shared across occurrences,
e.g. one authored by another tool, or by code that calls the API directly with
a batch of products the way the docstring itself demonstrates.

This is a real, verified latent hazard in `change_thickness()`'s unguarded
write, but it is not something commit 831c3190 introduced or touched, and it
is not something I have confirmed is what the `#7690` reporter actually hit
(I have not inspected their file). Per this task's scope for #7531 I have not
implemented anything for it; it belongs with `#7690`, which is where it is
already tracked.

## Draft comment (for human review, not posted)

> I dug into commit 831c3190. It introduces a real, severe unit-conversion bug:
> for any IFC file whose project length unit is not metres (millimetres is very
> common), applying a custom offset produces an `OffsetFromReferenceLine`
> roughly 1000x too large with the sign flipped, because the live-editing
> arithmetic mixes a value already converted to the file's native unit with
> terms still in SI metres. I confirmed this by running the exact formula the
> commit added: a 50mm offset on a 200mm layer, in a millimetre-unit file,
> should produce -50mm; the commit's code produces 49900mm. The parallel
> pset-reload path had the equivalent bug in the other direction.
>
> Both are already fixed on `origin/v0.8.0`, independently of this
> investigation, by Bruno Perdigão's `95fcf9e35c` and `156c6183eb` (2026-06-16).
> I re-ran the same formula against current HEAD and it now produces the
> correct -50mm. I did not find any other defect in 831c3190 itself.
>
> Separately, while tracing this I confirmed (with a small script against
> `ifcopenshell.api.material.assign_material`) that `IfcMaterialLayerSetUsage`
> can be shared across multiple products when assigned together, and Bonsai's
> `change_thickness()` writes `OffsetFromReferenceLine` onto that entity with no
> check for exclusive ownership, which would explain `#7690`'s "changes other
> instances" report on a file with shared usages. Bonsai's own creation and
> duplication code paths avoid ever sharing a usage, so I have not confirmed
> this is what `#7690`'s reporter hit, but it is a real gap worth someone
> checking their file for. That is a `#7690` question, not a 831c3190 one; I
> have not touched it here.
