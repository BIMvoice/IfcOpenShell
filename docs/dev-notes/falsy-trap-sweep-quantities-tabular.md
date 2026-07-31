# Falsy-empty-container trap sweep: quantities and tabular I/O

This file was generated with the assistance of an AI coding tool.

Continuation of the falsy-trap sweep (`""`, `0`, `0.0`, `False`, `[]`, `{}`,
`set()` all being falsy, so a bare truthiness test cannot distinguish
"empty but meaningful" from "unset"). See `ifcfm/cobie24.py`'s 43-site sweep
for the archetype this hunts.

## Existing-work check (done before picking a target)

```
gh pr list --repo IfcOpenShell/IfcOpenShell --state open --limit 400 \
  --json number,title --jq '.[] | select(.title|test("ifc5d|ifccsv|falsy|zero|None|guard";"i"))'
```

Both of the top two priority packages already have open PRs squarely on this
archetype, filed the same day as this sweep:

- **PR #9113** ("ifc5d: fix four wrong-number defects in cost export, cost
  import and weight quantities") covers `ifc5Dspreadsheet.py::get_cost_items_data`,
  `csv2ifc.py::get_row_cost_data`, and `qto.py`'s `get_weight` /
  `get_weight_profile_based` branches. Its own body explicitly walks all
  seven `results[...] = value` branches in `qto.py::calculate` and states
  which ones are correct as-is (`get_segment_length`), which is the same
  mechanical-enumeration standard this sweep uses.
- **PR #9116** ("ifcclash/ifccsv: stop dropping a real clash, a wrong
  summary total, and silently ignored Country on reimport") covers
  `ifcclash.py::process_clash_set`, `ifccsv.py::export`'s summary row, and
  `ifccsv.py::process_row`'s `SKIP_PATTERNS` substring bug, and explicitly
  checked `ifcopenshell.util.selector`'s numeric coercions (plain
  `float()`/`int()`, no locale exposure).

**Verdict: `src/ifc5d/` and `src/ifccsv/` are saturated for this archetype.**
Re-auditing them from scratch would either duplicate #9113/#9116 or need to
falsify their "these branches are correct" claims, which their bodies
already justify with a specific counter-example (`get_segment_length`).
Moved to priority 3: `src/bonsai/bonsai/tool/`, numeric parts only, per the
brief (dimensions, offsets, elevations, counts, indices; skip display/label
fallbacks such as `Name or "Unnamed"`).

Also checked `bimvoice/*` branches and the open-PR file lists for anything
already touching `bonsai/tool/*.py` for this archetype, to avoid
re-discovering already-fixed spots. Files with an existing open PR touching
them (skip re-verdicting, but still screened for *other*, unrelated
candidates in the same file): `structural.py` (#9153), `georeference.py`,
`sequence.py`, `spatial.py` (#9103), `duplicate.py`, `geometry.py`,
`model.py`, `root.py` (#9100), `blender.py` (#9087), `drawing.py`,
`library.py`, `profile.py` (#9171), `cost.py` (#9129).

## Method

Environment: `build/Darwin/arm64/10.15/install/python-3.13.6` copied to a
scratch dir, repo Python sources rsynced over (`--exclude='*.so'`, and with
`PYTHONNOUSERSITE=1` to stop `/Users/petruc/.local` shadowing the scratch
copy). Installed `isodate python-dateutil networkx typing_extensions numpy
shapely lark pytest`; all 35 `ifcopenshell.api` submodules import cleanly
(`aggregate` through `unit`). Scratch dir deleted after use.

`bonsai/tool/*.py` imports `bpy`, so most of it cannot be exercised without
a live Blender process. Where a candidate's surrounding logic is pure
Python (no `bpy`/`bpy.context` dependency), it was reproduced directly.
Where it required live Blender state, it was traced to its producer and
either resolved analytically (the fallback value is provably a no-op) or
left unconfirmed and reported as such, not claimed as a verified defect.

### Enumeration

Grep passes across all 68 files in `src/bonsai/bonsai/tool/` (12,005 lines):

1. `` or 0`` / `` or 0.0`` / `` or 1`` / `` or 1.0`` literal fallbacks: 25 hits.
2. `.get(...) or ...` fallback pattern: 24 hits (10 overlap with #1).
3. `if <numeric-looking-name>:` bare truthiness (`if quantity:`, `if value:`,
   `if count:`, `if width:`, `if height:`, `if length:`, `if depth:`,
   `if offset:`, `if elevation:`, `if index:`, `if rate:`, `if cost:`,
   `if amount:`, `if duration:`, `if thickness:`, `if radius:`, `if angle:`,
   `if area:`, `if volume:`, `if weight:`, `if total:`, `if number:`,
   `if qty:`): 2 hits.
4. `if not x.get(`, `if props.properties.get(...)`: 29 hits (27 were
   `tool.Ifc.get()`/schema-presence checks, not this archetype; 2 relevant).
5. `if not obj.Attribute:` on IFC numeric attributes (`.Depth`, `.Width`,
   `.Height`, `.Radius`, `.Angle`, `.Elevation`, `.Length`, `.Thickness`,
   etc.): 0 hits.
6. Accumulator pattern `x = x or ...`: 5 hits, all string/object defaults
   (`name or "My " + ifc_class`, `context or bpy.context`), 0 numeric.

Plus full manual reads of the smaller, most quantity-adjacent files end to
end: `qto.py` (189 lines), `slab.py` (74), `array.py` (226), `resource.py`
(505, cost-value section), `cost.py` (1121, cost-value and quantity
sections), `numeric_input.py` (168), `attribute.py` (95), `pset_template.py`
(146), `layer.py`, `boundary.py`, `connection.py`, `covering.py`.

**Total distinct candidates traced: 62.** (25 + 24 + 2 + 2 relevant from
pass 4, minus 10 overlap between pass 1/2, plus 21 read manually with no
grep match, netting to roughly this figure; exact per-file breakdown above.)

### Verdicts

**56 of 62 are no-ops or legitimate guards, not defects:**

- **~30 are no-op fallbacks**, where the fallback value equals the falsy
  value itself, so a genuine `0`/`0.0` reaching the line produces the exact
  same output with or without the `or`. Examples: `cost.py:303`
  (`total_quantity or 0`), `resource.py:220`
  (`ValueComponent[0] or 0`), `drawing.py:463-464`
  (`pset.get(x, 0.0) or 0.0`), `style.py:904/912/1102`
  (`d.get("Transparency") or 0.0`), `wall.py:392`
  (`get_x_angle(wall_a) or 0.0` only changes the `None`, i.e.
  non-parametric-body, case, never a real `0.0`).
- **~15 are `Name or "Unnamed"`-shaped string display fallbacks**
  (`material.py`, `pset_template.py`), explicitly out of scope per the
  brief.
- **6 are legitimate divide-by-zero / degenerate-input guards**, not
  data-loss: `cad.py:520/521/1127` (`np.linalg.norm(d1) or 1`, guarding
  vector normalisation of a zero-length vector), `style.py:610`
  (`len(range(0, n, step)) or 1`, guarding a texture-sampling average
  denominator), `clip_box.py:500/936/937` (no-op forms of the same
  pattern).
- **2 are existence checks on Blender `PropertyGroup` collection items**
  (`pset.py:237,456`, `if props.properties.get(prop.Name):`), which fall
  under the confirmed-negative "truthiness on an entity-like wrapper"
  category: a present `PropertyGroup` item is never falsy.
- **3 are index/`.index()` no-ops** (`cost.py:915`, `sequence.py:870`,
  `array.py:224`): `.index()` returning `0` and being tested with
  `or 0` is a no-op; `array.py:224`'s `return i` inside a loop is never
  truthiness-gated at all.

**1 is a real defect, already fixed by an open PR:**

- `cost.py:951`, `new.total_quantity = quantity or 1`. A cost item whose
  parametric quantity against a product is genuinely `0` (e.g. a wall with
  `0` net area once fully covered by openings) displayed as `1` in the
  "assigned cost items" UI list. **This is PR #9129**
  ("Bonsai: stop showing a legitimate zero cost-item quantity as 1"),
  already open, already has a regression test. Not re-fixed here to avoid
  a duplicate/conflicting change on the same line.

**1 was traced in depth and rejected as not a defect, despite matching the
surface pattern:**

- `resource.py:277` and the identical shape at `cost.py:512`:
  `"ValueComponent": prop.float_value or 1` when writing a Resource or
  Cost Item's `IfcCostValue.UnitBasis` back to the IFC file (via
  `ifcopenshell.api.cost.edit_cost_value`). Reproduced the arithmetic
  directly (no `bpy` needed, `edit_cost_value` is pure `ifcopenshell`):

  ```
  user entered: 0.0
  actually written ValueComponent: 1.0
  ```

  This looked like the flagship archetype (a rate value's denominator
  silently substituted). Traced to its consumer,
  `bonsai/bim/module/cost/data.py:177`:
  `data["TotalCost"] = data["TotalAppliedValue"] * cost_quantity /
  data["UnitBasisValueComponent"]`, a genuine division. A `UnitBasis`
  ValueComponent of `0` has no sane interpretation ("cost per 0 units")
  and would raise `ZeroDivisionError` on the very next property-panel
  refresh. Unlike a cost item's quantity (which can legitimately be `0`,
  confirmed by #9129) or a COBie custom property (which can legitimately
  be `0`/`False`), a rate's own unit-basis denominator cannot legitimately
  be `0` in this model. Per "answer from the producer, not the variable
  name": the producer here is a UI text field, but the domain (a
  denominator) rules `0` out regardless of what the user typed. Excluded.
  Not fixed.

**1 lower-severity, unconfirmed candidate, reported but not fixed:**

- `polyline.py:253`, `if area:` in `Polyline.calculate_area`, the live
  numeric readout shown while interactively drawing a slab/space footprint.
  `get_number_value("AREA")` returns either a `float` (including a genuine
  `0.0` for a degenerate/collinear polygon) or the empty string `""` (no
  value typed yet) — never `None`. Testing both with one bare `if area:`
  means a real zero-area polygon leaves the on-screen area readout showing
  the previous non-zero value instead of updating to `0`. This does not
  reach the IFC file (`props.product_cost_items`-style transient UI state
  only) and self-corrects on the next mouse move. Confirming it requires a
  live modal Blender session (`bpy.context.scene.unit_settings`), which
  was not set up for this one low-severity, non-persisting candidate given
  the time budget. **Reported as an observation, not a verified finding.**
  Not fixed.

## Ratio

**62 candidates mechanically enumerated and traced. 1 confirmed defect
found, already covered by an open PR (#9129). 0 new fixes in this sweep.**

`src/bonsai/bonsai/tool/` reads as largely clean for this specific
archetype: most `or`-fallbacks already default to the same value the falsy
case would produce (no-ops), the genuine numeric-denominator guards are
deliberate, and the one real hit was independently found and fixed by
another pass on the same day. This retires the archetype hunt in
`bonsai/tool/` unless a future pass wants to go past the ~68-file, ~12k-line
surface covered here (the largest unswept files, `cad.py`, `raycast.py`,
`snap.py`, `spatial.py`, `clip_box.py`, `system.py`, `geometry.py`,
`model.py`, were grep-screened across all patterns above but not fully
read end to end; a deeper pass there is the natural next step if this
archetype is revisited).

## No fixes pushed

No code changes accompany this note. The one confirmed defect found
(`cost.py:951`) is already fixed on an open PR; shipping a second,
independent fix to the same line would conflict rather than help. No other
candidate cleared the evidence bar for a confirmed, fixable defect.
