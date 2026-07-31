# Issue #4593: curves ignored in a mixed polygon/curve 2D representation

## Conflict check (before reading code)

All four checks ran, zero skipped.

- `search/issues type:pr is:open 4593 in:title,body,comments` returned one open PR:
  `#8345 geometry.add_representation: keep loose edges (curves) when a mesh also
  has faces (#4593)`, branch `fix-4593-add-repr-loose-edges`.
- Timeline cross-references: `#4606 BlenderBIM doesn't support representations with
  mixed polygons and curves` (the read-side counterpart) and `#8866` (our own PR
  review index).
- `bimvoice` remotes matching `4593`: `bimvoice/fix-4593-add-repr-loose-edges`,
  same branch as PR #8345.
- This PR and branch are our own prior work (BIMvoice commented on the issue on
  2026-07-07 and opened #8345 the same day). No unrelated third-party work exists
  for this issue.

## Reporter's symptom (jsaarane, 2024-04-29)

> When creating a custom 2D representation for an IFC type element the custom 2d
> drawing does not get saved and eventually if you click to another mode and back
> it changes to the default state. Also a save before does not fix the problem.

A follow-up from Andrej730 in the thread pinned the mechanism precisely:

> It's the issue with `geometry.add_representation` in case if mesh has polygons -
> it only adds polygons as fillareas ignoring loose edges (curves). So, currently,
> until we fix this, it's only possible to either save polygons only or curves
> only representations.

So the reported bug is: a 2D annotation mesh that mixes faces (fill areas) and
loose edges (curves) silently loses the curves, because
`create_annotation2d/3d_representation` in
`ifcopenshell/api/geometry/add_representation.py` only ever emitted
`IfcAnnotationFillArea` when the mesh had faces, with no code path to also emit
the loose edges.

## The commit that closed it, and what it actually did

Timeline for #4593 (`gh api .../issues/4593/timeline`):

- `2024-05-02T11:49:23Z` `referenced` commit `86cc2bf39abd0417bb33a6e4942a007616cb1247`
  ("fix bug using 'trace outlines' for reprsentation in ifc2x3"), authored by
  Andrej730.
- `2025-04-19T20:18:48Z` sboddy closes the issue: "Andrej stated that this issue
  is fixed (way-back-when)."
- `2025-04-19T21:51:54Z` Moult reopens: "Reopening since the fix was for a
  different issue."

`git show 86cc2bf39abd0417bb33a6e4942a007616cb1247` is a one-line fix:

```
-        for spline in self.settings["geometry"].splines:
+        for spline in curve_object_data.splines:
```

Its own commit message quotes the crash it fixes:

```
AttributeError: 'Mesh' object has no attribute 'splines'
```

in `create_curves_from_curve_ifc2x3`, reached only through the "Trace Outlines"
operator's curves-only code path
(`create_annotation2d_representation` -> `create_curves` ->
`create_curves_from_curve_ifc2x3`, used when `self.settings["geometry"]` is a
Blender Curve object, not a Mesh). That is a different bug: a crash when
generating an IFC2X3 curves-only annotation from a dummy curve object. It does
not touch the fill-area code path at all, and does nothing for a mesh that mixes
faces and loose edges.

## Verdict: Moult is right

The commit referenced when the issue was closed (`86cc2bf3`) fixed a crash in the
IFC2X3 curve-splines path. It did not touch
`create_annotation2d_representation` / `create_annotation3d_representation`,
which is the code Andrej730 identified as the actual root cause of the reported
symptom (loose edges dropped whenever the mesh also has faces). The two are
different bugs in the same file, both surfaced from the same issue thread. The
original bug was still live when the issue was closed in 2025.

## Reproduction (measured, not inferred)

I confirmed the original bug is real and reproduced it against the actual
`ifcopenshell.api.geometry.add_representation` code, run inside Blender 5.2
(`/opt/homebrew/bin/blender`, isolated via `BLENDER_USER_RESOURCES` pointed at a
throwaway temp directory, never touching the real profile). I built a minimal
Blender mesh (one quad face, plus one loose edge not touching the face) and
called `Usecase.create_annotation2d_representation()` directly.

Against the state of `add_representation.py` immediately before the fix commit
(`9bc7c3e835^`), for both IFC4 and IFC2X3:

```
schema=IFC4 2D representation items: ['IfcAnnotationFillArea']
schema=IFC2X3 2D representation items: ['IfcAnnotationFillArea']
```

The loose edge is silently dropped in both schemas, exactly as Andrej730
diagnosed and exactly as the reporter described.

## The fix already exists: PR #8345 (branch `fix-4593-add-repr-loose-edges`)

This was not new work needed from this session: `bimvoice/fix-4593-add-repr-loose-edges`
(commit `9bc7c3e835`, "Bonsai: keep loose edges when a 2D representation also has
faces") already fixes it, and PR #8345 is open against it, filed the same day as
our earlier BIMvoice comment on the issue (2026-07-07). The fix:

- Adds `create_loose_edge_curves()`, which reuses `create_curves_from_mesh` /
  `create_curves_from_mesh_ifc2x3` with `should_exclude_faces=True` to build
  curves straight from the mesh's loose edges.
- Fixes the underlying `should_exclude_faces` collection bug: it was
  `face_edges.union(...)` in a throwaway list comprehension, which builds and
  discards a new set each time and never actually populates `face_edges` (a
  no-op). Changed to `face_edges.update(...)`, which is what makes exclusion
  work at all.
- Guards against appending an empty trailing `edge_loop` (only relevant once the
  exclusion logic actually removes edges).
- Wires `create_loose_edge_curves()` into both
  `create_annotation2d_representation` and `create_annotation3d_representation`,
  appending an `IfcGeometricCurveSet` alongside the `IfcAnnotationFillArea` items
  when the mesh has both.

I re-ran the same reproduction against this fixed code (again inside Blender,
same isolated setup):

```
schema=IFC4 2D representation items: ['IfcAnnotationFillArea', 'IfcGeometricCurveSet']
schema=IFC2X3 2D representation items: ['IfcAnnotationFillArea', 'IfcGeometricCurveSet']
```

And the emitted IFC confirms the curve set is exactly the loose edge, not the
face's own edges (IFC4 output, abbreviated):

```
#2=IFCCARTESIANPOINTLIST2D(((0.,0.),(1.,0.),(1.,1.),(0.,1.),(2.,0.),(3.,0.)));
#3=IFCINDEXEDPOLYCURVE(#2,(IFCLINEINDEX((1,2)),IFCLINEINDEX((2,3)),IFCLINEINDEX((3,4)),IFCLINEINDEX((4,1))),$);
#4=IFCANNOTATIONFILLAREA(#3,$);
#6=IFCINDEXEDPOLYCURVE(#5,(IFCLINEINDEX((5,6))),$);
#7=IFCGEOMETRICCURVESET((#6));
```

Points 5 and 6 are `(2,0)` and `(3,0)`, i.e. exactly the loose edge I added and
nothing from the quad face. Same shape of result for IFC2X3
(`IFCPOLYLINE((#14,#15))` referencing only the loose edge's two points).

Note on method: `Usecase.create_annotation2d_representation()` was called
directly rather than through the public `add_representation()` entry point,
because that entry point unconditionally imports `bonsai.tool`, and importing
`bonsai.tool` standalone (outside Blender's addon-registration bootstrap)
hits a genuine circular import in Bonsai's package layout
(`bonsai.tool -> bonsai.tool.attribute -> bonsai.bim.helper -> bonsai.bim ->
...aggregate.operator` references `tool.Ifc.Operator` before `tool.Ifc` exists).
That import problem is orthogonal to this issue: neither the annotation-fill-area
path nor `create_curves_from_mesh` (the IFC4 loose-edge path) needs `bonsai.tool`
at all. The IFC2X3 loose-edge path calls `remove_doubles_from_mesh`, which does
need two `bonsai.tool.Blender` helpers purely to run bmesh doubles-removal; I
stubbed only those two functions (`get_bmesh_for_mesh`, `apply_bmesh`) with
direct `bmesh` calls to avoid pulling in the whole addon just for that. This
does not touch or explain away the code under test; it only avoids an unrelated
addon-loading ordering issue.

## CI status on PR #8345

`gh pr checks 8345` currently shows `compile-and-test` and `lint-formatting`
failing, both from the run at PR-open time (2026-07-07T10:14 UTC), i.e. before
v0.8.0 went green on 2026-07-24 (see `red-ci-is-baseline-not-ours.md`). I
independently checked the changed file against the repo's own lint config
(`~/.cache/ifcos-lint-venv/bin/black --config pyproject.toml` and `ruff check`,
run from inside the repo so the 120-character line length and repo ruff rules
apply, not the 88-character black default you get from linting a bare /tmp
copy): both pass cleanly on the fix commit's version of
`add_representation.py`. The CI red on the PR looks stale, not caused by this
diff; a re-run is warranted before treating it as a real blocker.

## Draft comment (for human review, not posted)

> Confirmed Moult's reopening. The commit referenced when this was closed,
> `86cc2bf3`, fixed an unrelated crash in the IFC2X3 "Trace Outlines" curves-only
> path (`'Mesh' object has no attribute 'splines'`). It never touched
> `create_annotation2d/3d_representation`, which is where Andrej730's diagnosis
> in this thread points: a mesh that mixes faces and loose edges only ever got
> the faces written out as `IfcAnnotationFillArea`, and the loose edges (curves)
> were silently dropped. I reproduced that directly against the pre-fix code (a
> mesh with one quad face and one loose edge produces only
> `IfcAnnotationFillArea`, for both IFC4 and IFC2X3).
>
> This is already fixed on our side in #8345, which emits the loose edges as an
> `IfcGeometricCurveSet` alongside the fill areas. I re-ran the same
> reproduction against that fix and confirmed the curve set contains exactly the
> loose edge (not the face's own edges) in both schemas. That PR's CI shows red,
> but the run predates v0.8.0's green baseline (2026-07-24); the diff itself
> passes black and ruff against the repo's own config, so the red looks stale
> and worth re-running rather than treating as a real failure.
