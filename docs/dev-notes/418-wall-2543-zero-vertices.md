# Issue #418: wall #2543 still produces zero vertices

## Attachment manifest

- **Issue body** (johanrd, 2018-07-12): steps to reproduce (`convert
  418--walls--segfault.ifc`), a comparison table of two commits x two OCCT
  versions, and one screenshot.
- **Screenshot** (`user-images.../42603162-...png`, viewed): a third-party
  viewer's render of the file. Two of the three walls are visible; the large
  foreground wall shows a small rectangular notch/opening near its right end
  (dashed outline, cast-in groove), consistent with a real, non-trivial
  opening cut rather than a full-depth hole.
- **Comment 1** (johanrd, 2018-09-17): closed, "not reproducible anymore ...
  from commit 08557c2".
- **Comment 2** (johanrd, 2019-07-22): reopened, "missing geometry when
  converting with 12e9f7b", pastes a warning log mentioning
  `IfcBooleanClippingResult` halfspace/boolean "yields unchanged volume" and
  "Multiple components in IfcConnectedFaceSet" for GlobalId
  `2BCTLkW3nFSQ3$WS7S2jdQ` (this is wall `#2543`, confirmed below).
- **Comment 3** (johanrd, 2019-10-03): still segfaults on OCCT 7.4.0.
- **Comment 4** (johanrd, 2020-11-15): with OCCT 7.5.0/7.3.0p4, no segfault,
  but one of three walls is missing.
- **Comment 5** (BIMvoice, 2026-07-05): re-tested on 0.8.5, segfault gone,
  reports wall `#2543` "yields 0 vertices", opening boolean "non-manifold".
- **Comment 6** (BIMvoice, 2026-07-19): closed the issue on the same basis.
- **Comment 7** (Moult, 2026-07-26): reopened. "1) only a human is allowed
  to close and 2) zero vertices isn't good enough."
- **Conflict checks** (all four run, no relevant PRs/branches missed): issue
  search for "418" in title/body/comments returned 4 hits, none of them
  actually about this issue (numeric coincidences, confirmed by grepping
  each body for "418" and getting zero matches for #7899, #8998, #8891).
  The issue timeline's cross-referenced entries are the same false
  positives. `git for-each-ref refs/remotes/bimvoice/` was grepped for
  `418|wall|non-manifold|boolean` and matched none of our branches. The
  actual match came from a different query: **PR #8772**,
  `fix-418-nonmanifold-opening-facesets`, already open in
  `IfcOpenShell/IfcOpenShell` itself (not a fork), authored by BIMvoice,
  title "ifcgeom: keep one copy of repeated faces in faceset helper
  duplicate removal", CI green (`build-ifcopenshell`, `lint-formatting`,
  `compile-and-test` all SUCCESS; only the unrelated `publish_website`
  check is red). Its body names this exact issue and file. This PR already
  contains the fix; see below.
- Video: none attached to this issue.

## What "zero vertices" refers to

Confirmed against the thread, not assumed: our closing comments (5 and 6)
described wall `#2543`'s body as "0 vertices" because its opening boolean
was rejected as non-manifold and the geometry was dropped rather than the
convert crashing. Moult's point 2 objects to that as a resting state: an
empty shape is not an acceptable substitute for the wall's actual geometry,
even though it no longer crashes. That is the objection this note answers.

## Reproduction

Used the prebuilt macOS `_ifcopenshell_wrapper.cpython-313-darwin.so` under
`build/Darwin/arm64/10.15/install/python-3.13.6` (unpatched, current
`v0.8.0`-branch code, no C++ build performed for this note), with the
repo's Python sources overlaid on top. `ifcopenshell.__file__` resolved
into the scratch copy at `/tmp/418-pyenv`, confirming the right code ran.

```
f = ifcopenshell.open("test/input/418--walls--segfault.ifc")
settings = ifcopenshell.geom.settings()
ifcopenshell.geom.create_shape(settings, f.by_id(2543))
```

Observed, directly, not inferred:

| element | result |
|---|---|
| `#26` (Basic Wall:241 IV Betong 400) | SUCCESS, verts=16, faces=28 |
| `#2543` (Basic Wall:241 IV Betong 200) | **SUCCESS, verts=0, faces=0** |
| `#4809` (Basic Wall:241 IV Betong 200, other instance) | SUCCESS, verts=395, faces=788 |

`create_shape` does not raise for `#2543` - it returns a valid `shape`
object whose `geometry.verts`/`geometry.faces` are both empty. This is
exactly what Moult is objecting to: a silent, "successful" empty result.

## Root cause (traced in the log, not guessed)

`ifcopenshell.get_log()` after the `#2543` call, in order:

1. `[Warning] [GEO169] 168 duplicate faces removed, 0 degenerate loops
   eliminated and 0 non-manifold edges` - the opening's
   `IfcConnectedFaceSet` lists the same face loop multiple times (product
   of however the authoring tool, apparently Revit via IFC export, wrote
   the opening's cast-in-groove solid).
2. Immediately after, 252 repetitions of the triple `[GEO159] Face
   boundary loop not included` / `[GEO162] Face with no boundaries` /
   `[GEO198] Failed to convert face:` - i.e. roughly 84 distinct faces each
   losing all three of their occurrences (168 removed + roughly 84
   originals never kept = far more faces gone than the 84 genuinely
   redundant ones).
3. `[Warning] Multiple components in IfcConnectedFaceSet`, `[Notice]
   Eliminated 2 disjoint operands` - the shell now has holes and splits
   into disconnected fragments.
4. `[Notice] Operand A is manifold` / `[Notice] Operand B 0 is
   non-manifold` - operand A is the wall's extruded body, operand B is the
   opening; B is the one damaged by step 2.
5. `[Notice] Boolean operation yields non-manifold result` - repeated
   across four increasing fuzziness retries (0.0, 1e-6, 1e-5, 1e-4). The
   boolean-robustness safety check in `boolean_utils.cpp` correctly
   refuses to accept a non-manifold subtraction result at every fuzziness
   it tries.
6. The subtraction is discarded entirely rather than accepted damaged, so
   wall `#2543` ends up with no body at all: 0 vertices.

Reading `src/ifcgeom/kernels/opencascade/faceset_helper.cpp` on the current
(unpatched) `v0.8.0` branch confirms the bug matches step 2 exactly.
`wires()` (around line 253) is:

```cpp
if (duplicates_.find(loop->identity()) != duplicates_.end()) {
    return false;
}
```

`duplicates_` is a `std::set<int>` populated once per identity the moment a
second occurrence of that loop is seen (`faceset_helper.cpp` around line
176: `duplicates_.insert(loop->identity())`). Because it is a `set`, not a
counter, `wires()` treats membership as "always skip this identity" -
**every** occurrence of a repeated face, including the first, legitimate
one, is dropped. A face that legitimately appears once should never be
touched; a face that appears N times should keep exactly one copy and drop
N-1. The current code drops all N. For wall `#2543`'s opening, that is 168
faces removed when only some smaller number were truly redundant repeats -
the rest were real geometry that got thrown away along with them, which is
exactly why the shell develops holes and the boolean goes non-manifold.

So: the input is not degenerate and no fallback is structurally missing -
this is a real bug in the duplicate-face collapse logic, one line away from
correct, and it is why real geometry is achievable here.

## The fix already exists

**PR #8772** (`fix-418-nonmanifold-opening-facesets`, open, CI green,
authored by BIMvoice) changes exactly this. It adds a
`std::map<int, int> duplicate_skips_remaining_` counting how many
*redundant* occurrences of each identity remain to be skipped, incremented
each time a duplicate is detected, and `wires()` now skips only while that
counter is positive:

```cpp
auto it = duplicate_skips_remaining_.find(loop->identity());
if (it != duplicate_skips_remaining_.end() && it->second > 0) {
    --it->second;
    return false;
}
```

`duplicates_` itself is left untouched and still used for the existing
"was anything deduplicated" flag/log line - only the per-occurrence skip
decision in `wires()` changes. This is a minimal, contained, two-file diff
(`OpenCascadeKernel.h` + `faceset_helper.cpp`, ~8 lines).

The PR body (self-reported by its author, not independently reproduced in
this note - no C++ build was performed here, see below) states that after
the fix wall `#2543` produces a closed, watertight body: 318 verts / 208
faces, bounding box 3.400 x 0.200 x 0.950 m matching the
`IfcExtrudedAreaSolid`, volume 0.6457 m3 vs 0.6460 m3 gross (i.e. the
cast-in groove correctly removes a small sliver), and that a sweep of all
258 files in `test/input` shows no other output changes. That numeric claim
is quoted here as what the PR says, not verified independently by this
note - see "What was not done" below.

## What was not done, and why

A second, patched build to independently confirm the 318/208 post-fix
numbers was started (Linux/x86_64 build via `docker/ifcos_env`, `PY_TGT
=py-311`) but was stopped mid-compile on instruction: the build container
shares a single 7.75 GiB memory ceiling with another agent's
higher-priority build in a sibling container, and IfcOpenShell's schema
translation units can peak around 2.5 GiB per `cc1plus` process, so
unthrottled `-j` parallelism risked OOM-killing both builds. The container
was killed, stopped and removed, and the scratch build output (~7.7 GiB)
was deleted. Nothing there needs to be resumed to close out this note: the
root cause is established directly from the log trace above, and the fix
already lives in an open, green-CI PR authored by us. If the 318/208
numbers need independent confirmation, that requires a `-j1` docker build
of `IfcOpenShell-Python` on PR #8772's branch, run only after any
higher-priority build in a shared container has finished.

## Bottom line

- Moult's "zero vertices isn't good enough" is correct and specific: the
  0-vertex result on `#2543` is a real bug (duplicate-face over-removal in
  `faceset_helper.cpp`), not an unavoidable consequence of bad input data.
- Real geometry is reachable. The fix is a one-line-of-logic, two-file
  change, already implemented, already open as PR #8772, already CI-green.
- This note performs no code changes. It documents the trace and points at
  the existing PR rather than opening a rival fix.

## Draft comment for Moult (for human review, not posted)

> You're right, zero vertices isn't good enough, and it isn't the only
> option here. Traced it: wall `#2543`'s opening has an `IfcConnectedFaceSet`
> that lists 168 faces as duplicates. Our current duplicate-removal code
> drops every occurrence of a repeated face identity instead of keeping one
> copy, so real faces vanish along with the true duplicates. That punches
> holes in the opening's shell, the shell goes non-manifold, and the
> boolean subtraction is (correctly) refused and discarded, which is why
> the wall ends up with nothing.
>
> That's a fixable bug, not bad input. #8772 already fixes it: keep one
> copy per repeated face instead of skipping all of them. It's open, small,
> and CI is green. Reproduced the current 0-vertex result directly against
> the file in this issue; haven't independently re-verified #8772's own
> post-fix numbers with a fresh build yet, but the code change is minimal
> and the logic is directly responsible for the symptom you flagged.
