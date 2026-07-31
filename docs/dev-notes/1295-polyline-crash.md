# Issue #1295 — "Crashes when create shape on polyline with only one point"

## Attachment manifest

- Issue body (htlcnn, 2021-02-05): describes a Blender crash on import of a
  Revit export. Two attachments:
  - `KC NHA HIEU BO_detached_no_foundation.zip` — the full original Revit
    IFC export (2642 `IfcProduct` instances). Downloaded and unzipped;
    inspected directly.
  - `blender.crash.txt` — a Windows `EXCEPTION_ACCESS_VIOLATION` crash log
    from `_ifcopenshell_wrapper.pyd`. Read in full (849 lines). The stack
    trace is generic (opaque `PyInit__ifcopenshell_wrapper` frames only,
    no symbols) and does not by itself identify which element or code path
    crashed.
  - No images in the issue body.
- Comment (Moult, 2021-02-05T01:19:33Z): "Ah, I extracted out one of the
  crashy elements for convenience" with attachment `bork1.ifc.txt`.
  Downloaded via the raw URL, renamed to `bork1.ifc`, and opened directly
  (quoted in full below).
- Same timestamp +34s: Moult renamed the issue from "BlenderBIM crashes
  when importing IFC" to "Crashes when create shape on polyline with only
  one point" (confirmed via the issues/1295/timeline API, event `renamed`).
- Comment (BIMvoice, 2026-07-05T17:52:27Z): claimed `create_shape` on "an
  `IfcPolyline` with a single point" returns cleanly with 0 vertices.
- Comment (BIMvoice, 2026-07-19T17:43:15Z): closed the issue, re-claiming
  124 vertices, no crash, against `bork1.ifc`.
- Moult reopened 2026-07-26T10:42:51Z with **no comment text** (confirmed
  via the timeline API — the only `reopened` event, no accompanying
  issue comment near that timestamp).
- No other issues/PRs are cross-referenced in the timeline. No video.

## Conflict checks (before reading code)

```
gh api search/issues ... q='repo:IfcOpenShell/IfcOpenShell type:pr is:open 1295 in:title,body,comments'
  -> no results
gh api repos/IfcOpenShell/IfcOpenShell/issues/1295/timeline --jq 'cross-referenced'
  -> no results
gh pr list --search "polyline" --state open
  -> 20 open PRs mentioning "polyline", none about create_shape crashing
     on this file or on IfcIndexedPolyCurve/degenerate profiles
git for-each-ref refs/remotes/bimvoice/ | grep -iE '1295|polyline'
  -> bimvoice/8597-polyline-angle-threshold
     bimvoice/feat/polyline-comma-decimal-8262
     bimvoice/fix-8043-polyline-closing-edge
     bimvoice/fix/9006-door-tool-polyline-crash
  (674 bimvoice branches total; none address this crash)
```
No existing PR or branch covers this. Nothing to build on top of.

## Symptom, in the reporter's terms

Blender crashed (hard access-violation crash, not a Python exception) when
BlenderBIM imported an IFC file exported from Revit. Moult identified one
of the offending elements and extracted it into `bork1.ifc.txt` for a
minimal repro, then titled the issue "Crashes when create shape on
polyline with only one point."

## First correction: the title's mechanism does not match the file

Before reproducing, I checked what entity types `bork1.ifc` actually
contains:

```
$ grep -o "IFC[A-Z0-9]*(" bork1.ifc | sort -u
IFCAPPLICATION( IFCARBITRARYCLOSEDPROFILEDEF( IFCAXIS2PLACEMENT3D(
IFCBUILDING( IFCBUILDINGELEMENTPROXY( IFCBUILDINGSTOREY(
IFCCARTESIANPOINT( IFCCARTESIANPOINTLIST2D(
IFCCARTESIANTRANSFORMATIONOPERATOR3D( IFCCONVERSIONBASEDUNIT(
IFCDERIVEDUNIT( IFCDERIVEDUNITELEMENT( IFCDIMENSIONALEXPONENTS(
IFCDIRECTION( IFCEXTRUDEDAREASOLID( IFCGEOMETRICREPRESENTATIONCONTEXT(
IFCGEOMETRICREPRESENTATIONSUBCONTEXT( IFCINDEXEDPOLYCURVE(
IFCLOCALPLACEMENT( IFCMAPPEDITEM( IFCMEASUREWITHUNIT( IFCORGANIZATION(
IFCOWNERHISTORY( IFCPERSON( IFCPERSONANDORGANIZATION(
IFCPRODUCTDEFINITIONSHAPE( IFCPROJECT( IFCRATIOMEASURE(
IFCRELAGGREGATES( IFCRELCONTAINEDINSPATIALSTRUCTURE(
IFCREPRESENTATIONMAP( IFCSHAPEREPRESENTATION( IFCSITE( IFCSIUNIT(
IFCUNITASSIGNMENT(
```

There is **no `IFCPOLYLINE` entity anywhere in this file.** The single
`IfcBuildingElementProxy` (`#52`) gets its body via `IfcMappedItem` ->
`IfcRepresentationMap` -> three `IfcExtrudedAreaSolid`s, each built from an
`IfcArbitraryClosedProfileDef` wrapping an `IfcIndexedPolyCurve` over an
`IfcCartesianPointList2D`. Those point lists have 29-34 points each (not
one). I confirmed the same is true of the **full original Revit export**
(`grep -c "IFCPOLYLINE(" ... -> 0`).

So the title, and both of our earlier closing comments' stated mechanism
("`IfcPolyline` with a single point"), do not describe any entity present
in either the extracted repro or the original file. That claim was never
verified against the file's actual content — it should not have been
asserted as fact. This does not change the crash/no-crash verdict below,
but it is a factual error in our prior comments that needs correcting.

## Reproduction

Environment: python3.13 scratch copy of
`build/Darwin/arm64/10.15/install/python-3.13.6`, `ifcopenshell` sources
rsynced from this worktree's `src/ifcopenshell-python/ifcopenshell`
(`.so` excluded), confirmed `ifcopenshell.__file__` resolves into the
scratch copy. All 35 `ifcopenshell.api` submodules import cleanly
(`isodate`, `python-dateutil`, `networkx`, `typing_extensions`, `numpy`,
`shapely`, `lark` all present). Worktree HEAD `25713a486aa4`, VERSION
`0.8.6`.

`create_shape` directly on the extracted repro:

```
proxy count 1
#52=IfcBuildingElementProxy('0nSHrFAwfDN9VnxWGxxg5M', ...)
0nSHrFAwfDN9VnxWGxxg5M OK, verts: 124
```

`geom.iterator` (the pipeline `IfcConvert` uses) on the same file:

```
0nSHrFAwfDN9VnxWGxxg5M verts: 124
processed 1 shapes
```

`geom.iterator` on the **full original 20.9 MB Revit export**
(2642 `IfcProduct` instances, not just the one extracted element):

```
schema IFC4
products 2642
ok 2625 empty 0 time 5.636723041534424
```

No crash, no exception, no empty-geometry shape, in either the isolated
repro or the full original export that the crash was originally reported
against. (2642 vs. 2625 is products without a geometric representation,
e.g. spatial elements — not a failure.)

## Root cause

There is no reproducible crash on the current build. Whatever caused the
2021 access violation in `_ifcopenshell_wrapper.pyd` against IfcOpenShell
0.6.0b0-era code no longer triggers: `create_shape` and the iterator both
complete cleanly on the exact file Moult flagged as crashy, and on the
full original export. I have verified this by running it, not inferred it
from a diff.

Separately: our two prior closing comments asserted a specific mechanism
("`IfcPolyline` with a single point") that does not match any entity in
either file. That claim should not have been made without checking the
file content, and it should be retracted regardless of the crash verdict.

## Draft comment

> Re-reopened this to re-verify from scratch, including a correction to
> our own prior claim about the mechanism.
>
> First: I need to retract something from the two comments that closed
> this. We claimed the crash was `create_shape` on an `IfcPolyline` with a
> single point. That's wrong — I checked, and there is no `IFCPOLYLINE`
> entity anywhere in `bork1.ifc` or in the original
> `KC NHA HIEU BO_detached_no_foundation.ifc` export. The element in
> `bork1.ifc` builds its body from `IfcIndexedPolyCurve` over an
> `IfcCartesianPointList2D` with 29 points, wrapped in
> `IfcArbitraryClosedProfileDef` + `IfcExtrudedAreaSolid`, reached via
> `IfcMappedItem`. Sorry for the bad claim, and thanks for reopening
> rather than letting it stand.
>
> On the actual crash: I re-ran both `create_shape` and the
> `geom.iterator` pipeline (what `IfcConvert` uses) against `bork1.ifc`
> and got 124 vertices, no crash, no exception, both times. I also ran
> the full original 2642-product Revit export through `geom.iterator`
> (not just the one extracted element): 2625 of 2642 products process to
> non-empty geometry (the remaining 17 are spatial elements with no
> representation), zero crashes, zero empty shapes.
>
> So on current `ifcopenshell` (worktree HEAD `25713a486aa4`, 0.8.6) the
> access-violation from the original 2021 report does not reproduce, on
> either the extracted repro or the full file. I don't have a live 0.6.0b0
> build to bisect exactly which historical fix resolved it, but I'm
> confident the reported crash itself is gone. Flagging that the
> mechanism this issue's title describes never matched the data; happy
> to leave the title as-is for history or have someone update it.
