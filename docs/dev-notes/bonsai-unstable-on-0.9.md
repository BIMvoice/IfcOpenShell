<!-- This file was generated with the assistance of an AI coding tool. -->
# What it takes to get a bonsai-unstable build from 0.9 (ifcviewer-wgpu)

Answering aothms: "What does it take to have a bonsai-unstable for v0.9?
Maybe that is the first thing to investigate."

Scope: diagnosis only. Nothing on `ifcviewer-wgpu` was changed. All commit
hashes, run IDs and file:line references below were read directly from the
repository and from `gh run` / `gh api` output on 2026-08-01.

## Biggest blocker, up front

The daily unstable build (`ci-bonsai-daily.yml`) does not compile
IfcOpenShell's C++ core. It downloads a **pinned, pre-built** Python wrapper
binary from a fixed S3 URL, keyed by a `BUILD_COMMIT` hash that is bumped by
hand in `src/ifcopenshell-python/Makefile`. On `ifcviewer-wgpu` that pin
still points at `e333c1c`, a commit that only exists in `v0.8.0`'s history,
built under the **old** static/monolithic mapping architecture.

`ifcviewer-wgpu` has since rewritten the C++/Python boundary this wrapper
exposes: schema-specific geometry mapping libraries are now built as
separate `SHARED` plugins instead of linked-in `OBJECT`/`STATIC` code
(`src/ifcgeom/mapping/CMakeLists.txt`), mapping functions take references
instead of pointers (all 93 files under `src/ifcgeom/mapping/` changed), and
the Python side dropped the `.wrapped_data` unwrapping pattern throughout
`ifcopenshell/geom/main.py` (272 lines changed). Verified: `git diff v0.8.0
origin/ifcviewer-wgpu -- src/ifcgeom/` shows 190 files changed,
+10554/-3670 lines, including new files `tree_plugin.cpp`, `tree_registry.cpp`,
`mapping/plugin.cpp`.

So even if someone flips the branch filter and reruns the existing daily
pipeline unmodified against `ifcviewer-wgpu`, it will happily package
`ifcviewer-wgpu`'s Python source together with a Python-C++ wrapper built
from **pre-rewrite** `v0.8.0` C++. Whether that specific combination breaks
at import time or partway through use, I did not runtime-test (see "what I
could not determine"), but the API shapes on the two sides of that boundary
have diverged, and that is a verified fact, not a guess.

## 1. How bonsai-unstable is produced today (on v0.8.0)

Three pieces, chained:

**a) `.github/workflows/ci-bonsai-daily.yml`** — triggered by:
```yaml
on:
  push:
    paths: [ '.github/workflows/ci-bonsai-daily.yml', 'src/bonsai/**', ... ]
    branches:
      - v0.8.0
  workflow_dispatch:
```
The `build` job runs, per platform x Python version matrix:
```yaml
- name: Compile
  run: |
    cd src/bonsai && make dist PLATFORM=${{ matrix.config.short_name }} PYVERSION=${{ matrix.pyver }}
```
then uploads the resulting zip as a GitHub Release asset tagged
`bonsai-${VERSION}-alpha${timestamp}` (e.g. currently
`bonsai-0.8.6-alpha2607311157`).

**b) `src/bonsai/Makefile`'s `dist` target** builds the Blender extension
zip: copies the addon tree, builds/downloads ~30 pure-Python wheel
dependencies, and pulls in the compiled IfcOpenShell Python wrapper via:
```make
cd ../ifcopenshell-python && make dist PLATFORM=$(PLATFORM)64 PYVERSION=$(PYVERSION) && mv dist/*.whl ../bonsai/build/wheels/
```

**c) `src/ifcopenshell-python/Makefile`'s `dist` target** is where the
native binary enters, and it does **not** compile anything:
```make
BINARY_VERSION:=0.8.6
BUILD_COMMIT:=e333c1c
IOS_URL:=https://s3.amazonaws.com/ifcopenshell-builds/ifcopenshell-python-$(PYNUMBER)-v$(BINARY_VERSION)-$(BUILD_COMMIT)-$(PLATFORM).zip
...
dist:
	...
	cd build/botbuild && wget $(IOS_URL) && unzip ifcopenshell-python*
	cp -r build/botbuild/ifcopenshell/*ifcopenshell_wrapper* build/ifcopenshell/
```
Verified reachable: `curl -sI` against
`https://s3.amazonaws.com/ifcopenshell-builds/ifcopenshell-python-311-v0.8.6-e333c1c-linux64.zip`
returned `200`, likewise for the `313`/`macosm164` and `313`/`win64`
variants.

That S3 binary is produced separately, by manually dispatching
`.github/workflows/build_rocky.yml` (Linux), `build_rocky_arm.yml`
(Linux ARM), `build_osx.yml` (macOS), `build_win.yml` (Windows) — all are
`on: workflow_dispatch` only, normally fanned out via
`.github/workflows/build_all.yml`, itself `workflow_dispatch` only. After a
build run, someone hand-edits `BUILD_COMMIT` in
`src/ifcopenshell-python/Makefile` (there's a `make bump NEW=<hash>`
helper target for this). History confirms the cadence: `git log --oneline
-- src/ifcopenshell-python/Makefile` shows "Bump build 3e7b739 -> 821cf7b"
then "Bump build 821cf7b > e333c1c", each a separate manual commit.

Once the release exists, `update-extensions-repo-and-run-tests` in
`ci-bonsai-daily.yml` checks out `IfcOpenShell/bonsai_unstable_repo`, runs
`python setup_extensions_repo.py --last-tag` (installs Blender, runs
`make test` inside it), then commits and pushes the regenerated
`index.json`/`readme.md` back to that repo — this is the actual
"bonsai-unstable" channel Blender's extension manager polls.

**Critical property of `--last-tag`, verified by reading
`bonsai_unstable_repo/setup_extensions_repo.py`:**
```python
if github_tag == "--last-tag":
    for i, release in enumerate(repo.get_releases()):
        if i >= 10:
            raise Exception(...)
        if release.tag_name.startswith("bonsai-"):
            github_tag = release.tag_name
            break
```
and `patch_index_json` **overwrites** `index.json`'s entire `data` array
each run — there is no per-branch namespace, no channel concept. It is a
single serialized stream: whichever `bonsai-*` release was created most
recently, from whatever branch, becomes the entire unstable channel.
Confirmed by reading the live `index.json` (cloned read-only from
`IfcOpenShell/bonsai_unstable_repo`): current single entry is
`"version": "0.8.6-alpha260731"`.

## 2. What that mechanism assumes about the branch

- A branch named exactly `v0.8.0` (push trigger) — `ifcviewer-wgpu` doesn't
  match, so today it would need `workflow_dispatch` (manual) to run at all.
- `VERSION` file content used to build the release tag and asset names.
  **Verified identical on both branches**: `cat VERSION` on my `v0.8.0`
  worktree and `git show origin/ifcviewer-wgpu:VERSION` both print `0.8.6`.
  This means an unmodified run from `ifcviewer-wgpu` would produce a release
  tag indistinguishable in pattern from a genuine `v0.8.0` alpha (e.g.
  `bonsai-0.8.6-alphaYYMMDDHHMM`), and given point 1's `--last-tag` logic,
  it would **silently replace** the existing v0.8.0 unstable channel rather
  than coexist as a separate "v0.9 unstable" channel.
- The pinned `BUILD_COMMIT`/`BINARY_VERSION` S3 binary, addressed above.
- `blender_manifest.toml`, `pyproject.toml` under `src/bonsai/`: byte-for-byte
  identical between the two branches (`git diff v0.8.0 origin/ifcviewer-wgpu
  -- src/bonsai/bonsai/blender_manifest.toml src/bonsai/pyproject.toml`
  produced no output), so nothing there currently blocks packaging.
- Module layout: `src/bonsai/bonsai/{bim,core,tool}` still exist at the same
  paths on both branches (only tree hashes differ, not the tree structure),
  so the `rm -rf build/bonsai/{bim,core,tool}/` step in the Makefile's
  `dist` target (used only to trim non-runtime dirs, unrelated to packaging
  the compiled add-on) still targets real paths.

## 3. What actually breaks, itemised with evidence

### 3a. Branch/version namespace collision (see "biggest blocker" framing above)
`ci-bonsai-daily.yml`'s push trigger is scoped to `v0.8.0` only, and even a
manual `workflow_dispatch` run from `ifcviewer-wgpu` would produce a release
tag using the same `VERSION=0.8.6` as the real v0.8.0 stream, feeding the
same single-channel `bonsai_unstable_repo`. Evidence: quotes above from
`ci-bonsai-daily.yml`, `VERSION`, and `setup_extensions_repo.py`.

### 3b. Pinned native binary is from the pre-rewrite architecture
Evidence: `BUILD_COMMIT:=e333c1c` unchanged between branches (`git diff
v0.8.0 origin/ifcviewer-wgpu -- src/ifcopenshell-python/Makefile` is empty);
`e333c1c` is an ancestor of `v0.8.0` but **not** of `origin/ifcviewer-wgpu`
(`git merge-base --is-ancestor e333c1c origin/ifcviewer-wgpu` fails); the
mapping-layer rewrite is verified via the `src/ifcgeom/` diff cited above.
I have not runtime-tested whether the old wrapper actually crashes when
loaded by `ifcviewer-wgpu`'s Python source — I can state the API surface
has diverged, not that a specific call fails, without doing that test.

### 3c. CI on `ifcviewer-wgpu` is red for real reasons, not the two known
repo-wide red herrings (FastMCP import error, lint-formatting exit 127)

Verified via `gh run list --repo IfcOpenShell/IfcOpenShell --branch
ifcviewer-wgpu --workflow ci.yml --limit 15`: **all 15** of the most recent
`ci` workflow runs on this branch, spanning 2026-07-30 to 2026-07-31
(run IDs 30503525637 through 30607788740), are `failure`.

Drilling into run `30607785887` (`push`, 2026-07-31): job `compile-and-test
(OFF)` shows `Build ifcopenshell` **succeeds** — the C++ actually compiles —
but `Test ifcopenshell-python` fails with genuine pytest failures, not
red herrings:
```
test/test_rules.py:45: AssertionError
E   AssertionError: assert 1 == 0
E    +  where 1 = len([{'level': 'error', 'message': 'IfcCorrectDimensions(SELF.UnitType, SELF.Dimensions)...
```
Also in the same run: `tests/test_validate.py::TestValidate::test_valid_model_has_no_issues`
fails (`assert [{'level': 'e... in subtype'}] == []`), and
`test_ids.py::TestIds::test_creating_a_minimal_ids_and_validating` fails.
The parallel `compile-and-test (ON)` job (same run) fails the same way,
plus one more: `FAILED
test/test_rules.py::test_file[.../fixtures/rules/pass-site-latitude-6-ifc2x3.ifc]
- AssertionError: assert 1 == 0`. Both jobs end with the literal line "One
or more tests failed".

Separately, `ci-lint` (run `30607785863`) fails at a genuine static-typing
bug, not the known exit-127 linter-never-ran red herring:
```
error[unresolved-reference]: Name `Any` used when not defined
   --> src/ifcopenshell-python/ifcopenshell/__init__.py:442:59
442 | def create_entity(type: str, schema: str = "IFC4", *args: Any, **kwargs: Any) -> entity_instance:
```
Verified: `git show origin/ifcviewer-wgpu:src/ifcopenshell-python/ifcopenshell/__init__.py`
imports `from typing import TYPE_CHECKING, Literal, Optional, Union, overload`
at line 65 — no `Any`. Because the file also has `from __future__ import
annotations` (line 57), this does not crash at import time (PEP 563 makes
annotations lazy strings), but the `ty` static type checker correctly flags
it, and that gate is red.

### 3d. Bonsai's own addon test suite and "does it load in Blender" check
have never run on this branch, in either direction
`ci-bonsai.yml` (`workflow_dispatch` only, used for stable releases) and
`ci-bonsai-daily.yml` are the only workflows that invoke `make test` for
`src/bonsai` inside an actual Blender process (via
`update-extensions-repo-and-run-tests`, which does `blender --command
extension install-file`, `reregister_bonsai.py`, then `make test`).
Verified via `gh run list --repo IfcOpenShell/IfcOpenShell --workflow
ci-bonsai-daily.yml --branch ifcviewer-wgpu` and the same for
`ci-bonsai.yml`: **zero runs** returned for either, on this branch, ever.
A zero here means my search found nothing; I have not independently proven
no one could have run it under a different branch label. But by the
matching evidence in 1) (push trigger scoped to `v0.8.0`) and 2) (no
`workflow_dispatch` run appears in the list), the straightforward reading
is that this check genuinely has not happened.

### 3e. New build-time dependencies appear in the C++/binary build workflows
(not in the Blender-addon packaging workflow itself)
Diffing `build_osx.yml` and `build_rocky.yml` between the branches:
`build_osx.yml` gained `brew install qt`, a `QT_DIR` env var, and
`dtolnay/rust-toolchain@stable`, with a new step comment: "The
bonsaiviewer-autodesk connector is a Rust crate; the 'Package .zip
archives' step below runs `cargo build --release` via
`packaging/build.py`." `build_rocky.yml` gained `dnf install ...
libxkbcommon-devel dbus-devel libX*-devel pango-devel cairo-devel
libstdc++-static`, `pip install aqtinstall`, and the same Rust toolchain
install, plus `BUILD_BONSAIVIEWER=ON QT_DIR=... --shared` passed to
`nix/build-all.py`. These are new requirements for producing the
IfcOpenShell native binaries (Qt6, a Rust toolchain, `aqtinstall`), not for
running `ci-bonsai-daily.yml` itself — the Blender-addon-facing Makefiles
are unchanged, so a Qt/Rust environment is only needed by whoever
re-dispatches the binary-build workflows to produce a fresh pinned build for
this branch (item 3b's fix).

### 3f. New top-level components, decoupled from the Bonsai addon build
`git ls-tree` diff of `src/` between branches shows new directories:
`src/bonsaiviewer`, `src/bonsaiviewer-autodesk`, `src/helpers`,
`src/ifcviewer`, `src/ifcviewer-minimal`, `src/ifcviewer-web`,
`src/plugin`, `src/wrappergen`, and `src/qtviewer` removed (renamed).
None of these appear in `src/bonsai/Makefile`'s `dist` target (unchanged,
confirmed no diff), so they do not currently affect Bonsai-addon packaging;
they have their own new workflow, `.github/workflows/build-bonsaiviewer-autodesk.yml`
(also new on this branch, currently failing per the `gh run list` output
above — "Build Bonsai Viewer Autodesk Connector" job).

### 3g. Workflow files are otherwise near-identical
`ci-bonsai-daily.yml` diff between branches is two `actions/checkout@v6` to
`@v7` bumps, nothing else. `src/bonsai/Makefile` and
`src/ifcopenshell-python/Makefile` have zero diff. `blender_manifest.toml`
and `src/bonsai/pyproject.toml` have zero diff.

### 3h. RC-schema `OffsetPoint()` issue named in the brief
`src/ifcgeom/mapping/IfcOpenCrossProfileDef.cpp:41` is **identical** on both
branches (`git show origin/ifcviewer-wgpu:src/ifcgeom/mapping/IfcOpenCrossProfileDef.cpp`
matches the local `v0.8.0`-derived worktree copy, both showing
`if (inst->OffsetPoint())` / `if (inst.OffsetPoint())` after the pointer-to-
reference rewrite). This is a pre-existing, branch-independent issue, not
something 0.9 introduced or fixed. I did not verify whether RC1-4 schemas
are in the default `SCHEMA_VERSIONS` build set on either branch (the
default is described in `nix/build-all.py` as "cmake default (8 schemas)"
without enumerating them in the one line I checked) — I could not confirm
from that alone whether this line currently blocks a default build on
either branch; establishing that needs either reading the CMake schema
list directly or a real build log showing which schemas were compiled.

## 4. What it would take, per item, with confidence

1. **Give the v0.9 unstable stream its own identity** (separate release-tag
   pattern and/or separate `bonsai_unstable_repo` channel, or at minimum
   bump `VERSION` on `ifcviewer-wgpu` to something like `0.9.0` so tags stop
   colliding with `v0.8.0`'s). Scope: touches `VERSION`,
   `ci-bonsai-daily.yml`'s branch filter, and very likely
   `bonsai_unstable_repo/setup_extensions_repo.py`'s single-channel
   `index.json` model (that repo's design assumes one stream; extending it
   is a design decision I'm not making here). **Low confidence on effort** —
   the `VERSION` bump and branch filter are each one line, high confidence;
   redesigning `bonsai_unstable_repo` for multiple channels is open-ended
   and depends on decisions the branch owners haven't made (parallel
   channels? replace 0.8.0's unstable outright when 0.8.0 freezes, as
   aothms's message suggests?).
2. **Produce a native binary built from `ifcviewer-wgpu`'s own C++** and
   re-pin `BUILD_COMMIT`/`BINARY_VERSION` in
   `src/ifcopenshell-python/Makefile` to point at it. Mechanism already
   exists (`workflow_dispatch` on `build_rocky.yml` / `build_osx.yml` /
   `build_win.yml` / `build_rocky_arm.yml` against this branch, then `make
   bump NEW=<hash>`), and I verified the binaries produced by that
   mechanism for the current pin are genuinely reachable on S3, so the path
   is proven to work in principle. **Medium confidence this is
   mechanically straightforward**; **low confidence on how long the build
   itself takes or whether it succeeds cleanly**, since the new
   `--shared`/`BUILD_BONSAIVIEWER=ON`/Qt/Rust path in those workflows is
   itself unverified by me — I did not dispatch them (no write access, and
   the task scope is diagnosis only).
3. **Fix the two concrete CI-red causes identified in 3c**: the `Any`
   import in `src/ifcopenshell-python/ifcopenshell/__init__.py:442` is a
   one-line fix, **high confidence**. The `test_rules.py` /
   `test_validate.py` / `test_ids.py` failures (IfcCorrectDimensions rule
   violation on a generated `IfcSIUnit`, plus IDS/validate assertions) look
   like a real regression in rule-generation or validation logic
   introduced somewhere in the 1079-commit range, not a flaky or
   environmental failure (they reproduce identically across both
   `compile-and-test (ON)` and `(OFF)` jobs). I have not traced which
   commit introduced them or how deep the fix goes, so **I cannot estimate
   this one** beyond "it is a real defect, not noise, and needs actual
   debugging."
4. **Run the Bonsai-addon test suite and a real Blender load once,
   anywhere**, since it has never executed on this branch. This is the
   cheapest way to find out whether item (2)'s ABI concern is real: dispatch
   `ci-bonsai-daily.yml` (it already supports `workflow_dispatch`) against
   `ifcviewer-wgpu` after re-pinning the binary. **High confidence this is
   easy to trigger**, **no confidence on what it will find** until it's
   run — that is precisely the open question.
5. **Decide whether the BonsaiViewer/wgpu/Rust connector components should
   ship inside the Bonsai Blender addon zip at all.** Right now they don't
   (3f) — the Makefile that builds the addon is untouched. If the plan is
   to keep them separate deliverables, no packaging work is needed here.
   If the plan is to bundle wgpu-viewer functionality into Bonsai itself,
   that's new packaging work not started. **This is a scope question for
   the branch owners, not something I can size** without knowing the
   intended product shape.

## 5. What I could not determine, and what would close the gap

- **Whether the old pinned wrapper actually breaks when loaded by
  `ifcviewer-wgpu`'s Python source, and how.** I verified the API surfaces
  diverged (3b) but did not build a local environment and import
  `ifcopenshell_wrapper` from the old binary against the new
  `ifcopenshell/geom/main.py` to observe an actual traceback. Closing this
  needs either that local repro or, more directly, item 4 above (a real
  daily-build dispatch).
- **Whether the RC1-4 default schema set includes the `OffsetPoint`-typed
  entity at all** (3h) — I read one line of `nix/build-all.py` describing
  "cmake default (8 schemas)" without enumerating them; I did not locate
  and read the actual CMake schema list or a build log showing which eight.
- **Whether `build_rocky.yml` / `build_osx.yml` / `build_win.yml` /
  `build_rocky_arm.yml` succeed end-to-end on `ifcviewer-wgpu` today.** The
  `ci` workflow's `compile-and-test` jobs prove the core C++ compiles
  (`Build ifcopenshell` step passes), but those four dedicated build
  workflows use a different flow (`--shared`, `BUILD_BONSAIVIEWER=ON`, Qt,
  Rust, AWS upload) that I could not dispatch (read-only `gh`, and the task
  forbids GitHub writes). Their own recent run history would need checking
  by someone with dispatch access, or their logs reviewed if they've been
  run manually by the branch owners already.
- **How deep the `test_rules.py`/`test_validate.py`/`test_ids.py`
  regression goes** — single bad rule, or a class of them. Would need a
  `git bisect` across the 1079-commit range or, faster, asking whoever owns
  the IDS/validation code on that branch.
