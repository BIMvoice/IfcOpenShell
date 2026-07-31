# Issue #1000: MergeProjects does not deduplicate spatial structure

## Context

Issue #1000 asks how to merge the spatial structure (site, building, storey)
and containment relationships when federating two IFC files, not just the
`IfcProject` element.

On 2026-07-25/26 an AI-assisted comment on the issue (posted from the
BIMvoice account) claimed:

> "The `MergeProjects` ifcpatch recipe federates multiple IFC files into one
> model, deduplicating the project and reusing spatial structure and
> geometric contexts..."

and the issue was closed on that basis. Moult reopened it:

> "Reopening because the AI comment is wrong - this is not yet implemented.
> The MergeProjects patch recipe does not deduplicate spatial structure."

Moult is correct. This note records the verification, so the claim is never
repeated without evidence again.

## What the code says (quoted, not summarised)

`src/ifcpatch/ifcpatch/recipes/MergeProjects.py`, the `Patcher.__init__`
docstring, lines 41-45:

```
"""Merge two or more IFC models into one

Note that other than combining the two (or more) IfcProject elements into
one, no further processing will be done. This means that you may end up
with duplicate spatial hierarchies (i.e. 2 sites, 2 buildings, etc).
```

The recipe's own docstring says the opposite of what our AI comment claimed.

The `merge()` method (lines 140-154) confirms it:

```python
original_project = self.file.by_type("IfcProject")[0]
merged_project = self.file.add(other.by_type("IfcProject")[0])

for element in other.by_type("IfcGeometricRepresentationContext"):
    new = self.file.add(element)
    self.added_contexts.add(new)

for element in other:
    self.file.add(element)

for inverse in self.file.get_inverse(merged_project):
    ifcopenshell.util.element.replace_attribute(inverse, merged_project, original_project)
self.file.remove(merged_project)

self.reuse_existing_contexts()
```

Only two kinds of entity get special handling: `IfcProject` (rewired onto the
original project, then the incoming duplicate is removed) and
`IfcGeometricRepresentationContext` (reused via `reuse_existing_contexts()` /
`get_equivalent_existing_context()`, lines 160-197, matched on
`ContextType`/`ContextIdentifier`/`TargetView`). Every other element from
`other`, including `IfcSite`, `IfcBuilding`, and `IfcBuildingStorey`, is
carried over verbatim by the bare `for element in other: self.file.add(element)`
loop. There is no code path anywhere in this file that inspects
`IfcSite`, `IfcBuilding`, or `IfcBuildingStorey` for equivalence.

## Demonstration

Two minimal IFC4 files were built, each with `IfcProject -> IfcSite("Site")
-> IfcBuilding("Building A") -> IfcBuildingStorey("Level 1") -> IfcWall`,
using distinct GlobalIds per file but identical names, then merged with
`ifcpatch.recipes.MergeProjects.Patcher`.

Entity counts:

```
BEFORE MERGE
  model_a: {'IfcProject': 1, 'IfcSite': 1, 'IfcBuilding': 1, 'IfcBuildingStorey': 1, 'IfcWall': 1}
  model_b: {'IfcProject': 1, 'IfcSite': 1, 'IfcBuilding': 1, 'IfcBuildingStorey': 1, 'IfcWall': 1}

AFTER MergeProjects.merge()
  merged : {'IfcProject': 1, 'IfcSite': 2, 'IfcBuilding': 2, 'IfcBuildingStorey': 2, 'IfcWall': 2}
```

`IfcProject` was deduplicated to 1, as documented. `IfcSite`, `IfcBuilding`,
and `IfcBuildingStorey` were NOT deduplicated: both instances survive with
identical names even though only their GlobalId differs, exactly the
"2 sites, 2 buildings" scenario the docstring warns about:

```
IfcBuildingStorey entities in merged output:
  #13 Name='Level 1' GlobalId=0Cty7$Y$L4gu6Hb8gGCX3d
  #31 Name='Level 1' GlobalId=1Dtz8%Z%M5hv7Ic9hHDY4h

IfcBuilding entities in merged output:
  #12 Name='Building A' GlobalId=0Cty7$Y$L4gu6Hb8gGCX3c
  #30 Name='Building A' GlobalId=1Dtz8%Z%M5hv7Ic9hHDY4g

IfcSite entities in merged output:
  #11 Name='Site' GlobalId=0Cty7$Y$L4gu6Hb8gGCX3b
  #29 Name='Site' GlobalId=1Dtz8%Z%M5hv7Ic9hHDY4f
```

The two walls remain contained in their own, separate `IfcBuildingStorey`
instances rather than a shared one:

```
'Wall in Project A' contained in IfcBuildingStorey #13 Name='Level 1'
'Wall in Project B' contained in IfcBuildingStorey #31 Name='Level 1'
```

Verified by running `Patcher(a, filepaths=["model_b.ifc"]).patch()` and
inspecting `result.by_type(...)` directly, not inferred from reading the
code.

## Test suite baseline

`pytest src/ifcpatch/test/test_MergeProject.py -p no:pytest-blender`:
6 passed, 4 failed. The 4 failures are all
`AssertionError: assert 4 == 2` / `assert 3 == 2` on
`IfcGeometricRepresentationContext` counts in
`test_reusing_geometric_contexts` and `test_merging_three_or_more_projects`
(IFC4 and IFC2X3 variants). These are the known duplicate-representation-context
defect tracked in #8700, with an open fix in PR #8707 (`fix-mergeprojects-dup-contexts`,
unmerged as of this note). They are unrelated to spatial-structure deduplication
and pre-exist this investigation; nothing here changes that count.

## Conflict check

Searched open PRs and unlinked `bimvoice` branches for existing work on
spatial-structure deduplication in `MergeProjects` before starting:

- PR #8992 (`BIMvoice:fix/mergeprojects-duplicate-globalid`): fixes duplicate
  `GlobalId`s produced by the merge, does not touch spatial-structure
  deduplication.
- PR #8707 (`theoryshaw:fix-mergeprojects-dup-contexts`): fixes duplicate
  `IfcGeometricRepresentationContext`s left behind by the merge (#8700), does
  not touch spatial-structure deduplication.
- PR #9038 (`BIMvoice:fix/extractelements-ifc2x3-georeferencing`): unrelated
  recipe (`ExtractElements`).
- 672 `bimvoice` remote branches were enumerated with
  `git for-each-ref refs/remotes/bimvoice/`; branches matching
  `merge|1000|spatial` were `feat-4779-material-merge`,
  `fix-4443-spatial-qto-shortcut`, `fix-6906-mirror-merge-decouple`,
  `fix/7151-trim-merge-poll`, `fix/8934-spatial-panel-regex-filter`,
  `fix/mergeprojects-duplicate-globalid` (= PR #8992 above),
  `plan-drawing-spatial-containers`, `test/mergeprojects-multi-file-7973`.
  None of these deduplicate spatial structure; `plan-drawing-spatial-containers`
  touches the Bonsai drawing module (unrelated file paths), and
  `test/mergeprojects-multi-file-7973` (PR-less, matches commit
  `9d6f079dc8`) only adds a 3+-file merge regression test, asserting current
  (non-deduplicating) spatial-structure behaviour incidentally by using
  distinct project names, not exercising deduplication.

No open work addresses spatial-structure deduplication. This is genuinely
unclaimed.

## Whether to fix it here: design questions, not answered by this note

Deduplicating `IfcSite`/`IfcBuilding`/`IfcBuildingStorey` is a real feature
with decisions a maintainer should make, not this note:

1. **Match key.** By `Name` alone (as demonstrated above, both files used
   "Level 1")? By `GlobalId` (only helps if both files were derived from a
   shared source, e.g. re-exports of the same federated model)? By
   `Name` + elevation for storeys? Names collide accidentally across
   unrelated disciplines' exports; GlobalId matches require shared
   provenance that federated multi-author IFC rarely has.
2. **Conflicting attributes on a "match".** If two storeys share a name but
   differ in elevation, is that a merge, two named-the-same-but-distinct
   storeys, or an error to surface to the user? Same question for
   `IfcSite` geolocation and `IfcBuilding` address.
3. **What happens to elements contained in the discarded duplicate.**
   `IfcRelContainedInSpatialStructure`, `IfcRelAggregates`, and every element
   that referenced the removed duplicate need re-pointing to the surviving
   instance, similar to how `merge()` already re-points `IfcProject`
   inverses at lines 150-152. Property sets, quantity sets, and any
   duplicate-specific relationships would need a policy (keep, merge, or
   flag as conflicting).
4. **Scope of "spatial structure".** `IfcSpace` and multi-storey elements
   spanning storeys are additional edge cases beyond the site/building/storey
   chain this note tested.

This note does not propose an implementation for those questions. It only
establishes that the gap exists as described, with numbers.

## Draft comment for #1000 (not posted)

> We were wrong to close this: the earlier AI-assisted comment claimed
> `MergeProjects` deduplicates spatial structure. It does not, and its own
> docstring says so directly: "you may end up with duplicate spatial
> hierarchies (i.e. 2 sites, 2 buildings, etc)."
>
> We verified this by merging two IFC4 files that share identically named
> Site/Building A/Level 1 structure. `IfcProject` is deduplicated (1 in the
> output, as documented), but `IfcSite`, `IfcBuilding`, and
> `IfcBuildingStorey` are not: the merge produced 2 of each, with the two
> walls left in two separate "Level 1" storeys rather than a shared one.
> `MergeProjects` only special-cases `IfcProject` and
> `IfcGeometricRepresentationContext`; everything else from the second file
> is added as-is.
>
> Deduplicating spatial structure is a real feature but needs a design
> decision before it can be built: what counts as a match (name, GlobalId,
> elevation, or some combination), what happens when a "match" has
> conflicting attributes (e.g. same storey name, different elevation), and
> how contained elements and relationships get re-pointed onto the surviving
> instance. Happy to build it once there is a decision on those, or to open
> a scoped PR for a specific matching rule if you want to pick one.
