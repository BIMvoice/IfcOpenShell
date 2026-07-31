# ifcpatch: IFC2X3-only entity-name sweep

Sweep of every recipe in `src/ifcpatch/ifcpatch/recipes/` for IFC4-only
entity names used without a schema guard (a call site that crashes, or
would crash, the moment it runs against an IFC2X3 file).

Method: every literal entity-name string passed to `by_type()`,
`create_entity()`, `reassign_class()` and `is_a()` across all 39 recipe
files was extracted, then checked by introspection against
`ifcopenshell.ifcopenshell_wrapper.schema_by_name(...).declaration_by_name(...)`
for `IFC2X3`, `IFC4` and `IFC4X3_ADD2`. Attribute-level divergence
(entity present in both schemas, attribute not) was checked separately
with `all_attributes()` / `all_inverse_attributes()` diffs for every
entity a recipe actually dereferences attributes on.

**A load-bearing distinction found while doing this: `is_a("SomeClass")`
never raises, even if `SomeClass` does not exist in the file's schema —
it just returns `False`.** Verified:

```
>>> w.is_a('IfcMaterialConstituentSet')   # w is an IFC2X3 IfcWall
False
>>> w.is_a('IfcTotallyMadeUpClassName')
False
```

So every `is_a("IfcXxx")` call site in these recipes is schema-safe by
construction, regardless of whether `IfcXxx` exists in the current
schema. Only `by_type()`, `create_entity()` and `reassign_class()`
calls with a schema-specific literal are actually at risk, because
those need to resolve the class in the schema declaration before they
can do anything.

## Schema presence table

Every literal `Ifc*` entity name found across all 39 recipe files
(`grep -oE '"Ifc[A-Za-z0-9]+"'` plus the `by_type`/`reassign_class`/
`create_entity`/`is_a` call-site scan), checked against all three
schemas:

| Entity name | IFC2X3 | IFC4 | IFC4X3_ADD2 |
|---|---|---|---|
| Ifc2Sql (recipe name, not an entity) | N | N | N |
| IfcActorRole | Y | Y | Y |
| IfcAddress | Y | Y | Y |
| IfcAlignment | N | N | Y |
| IfcApplication | Y | Y | Y |
| IfcArcIndex | N | Y | Y |
| IfcBeam | Y | Y | Y |
| IfcBorehole | N | N | Y |
| IfcBuildingElementProxy | Y | Y | Y |
| IfcBuildingStorey | Y | Y | Y |
| IfcCartesianPoint | Y | Y | Y |
| IfcCartesianPointList2D | N | Y | Y |
| IfcCartesianPointList3D | N | Y | Y |
| IfcClassification | Y | Y | Y |
| IfcColourRgb | Y | Y | Y |
| IfcColourSpecification | Y | Y | Y |
| IfcContext | N | Y | Y |
| IfcCoordinateOperation | N | Y | Y |
| IfcCurveStyleFont | Y | Y | Y |
| IfcCurveStyleFontAndScaling | Y | Y | Y |
| IfcCurveStyleFontPattern | Y | Y | Y |
| IfcDiscreteAccessory | Y | Y | Y |
| IfcDocumentInformation | Y | Y | Y |
| IfcDoor | Y | Y | Y |
| IfcDoorStyle | Y | Y | N |
| IfcDoorType | N | Y | Y |
| IfcElement | Y | Y | Y |
| IfcElementQuantity | Y | Y | Y |
| IfcElementType | Y | Y | Y |
| IfcExternalInformation | N | Y | Y |
| IfcExternalReference | Y | Y | Y |
| IfcExternalReferenceRelationship | N | Y | Y |
| IfcGeographicElement | N | Y | Y |
| IfcGeometricRepresentationContext | Y | Y | Y |
| IfcGeometricRepresentationSubContext | Y | Y | Y |
| IfcGeotechnicalStratum | N | N | Y |
| IfcGroup | Y | Y | Y |
| IfcIndexedPolyCurve | N | Y | Y |
| IfcLibraryInformation | Y | Y | Y |
| IfcLineIndex | N | Y | Y |
| IfcLocalPlacement | Y | Y | Y |
| IfcMapConversion | N | Y | Y |
| IfcMapConversionScaled | N | N | Y |
| IfcMaterial | Y | Y | Y |
| IfcMaterialConstituentSet | N | Y | Y |
| IfcMaterialDefinition | N | Y | Y |
| IfcMaterialDefinitionRepresentation | Y | Y | Y |
| IfcMaterialLayer | Y | Y | Y |
| IfcMaterialLayerSet | Y | Y | Y |
| IfcMaterialLayerSetUsage | Y | Y | Y |
| IfcMaterialList | Y | Y | Y |
| IfcMaterialProfileSet | N | Y | Y |
| IfcMaterialUsageDefinition | N | Y | Y |
| IfcObjectDefinition | Y | Y | Y |
| IfcObjectPlacement | Y | Y | Y |
| IfcOrganization | Y | Y | Y |
| IfcOwnerHistory | Y | Y | Y |
| IfcPerson | Y | Y | Y |
| IfcPersonAndOrganization | Y | Y | Y |
| IfcPhysicalQuantity | Y | Y | Y |
| IfcPhysicalSimpleQuantity | Y | Y | Y |
| IfcPolygonalFaceSet | N | Y | Y |
| IfcPolyline | Y | Y | Y |
| IfcPreDefinedItem | Y | Y | Y |
| IfcPresentationItem | N | Y | Y |
| IfcPresentationLayerAssignment | Y | Y | Y |
| IfcPresentationStyle | Y | Y | Y |
| IfcProduct | Y | Y | Y |
| IfcProfileDef | Y | Y | Y |
| IfcProject | Y | Y | Y |
| IfcProjectedCRS | N | Y | Y |
| IfcProperty | Y | Y | Y |
| IfcPropertyAbstraction | N | Y | Y |
| IfcPropertyDefinition | Y | Y | Y |
| IfcPropertySet | Y | Y | Y |
| IfcPropertySetDefinition | Y | Y | Y |
| IfcPropertySingleValue | Y | Y | Y |
| IfcProxy | Y | Y | N |
| IfcRelAssigns | Y | Y | Y |
| IfcRelAssociates | Y | Y | Y |
| IfcRelAssociatesClassification | Y | Y | Y |
| IfcRelDefines | Y | Y | Y |
| IfcRelDefinesByProperties | Y | Y | Y |
| IfcRelDefinesByType | Y | Y | Y |
| IfcRelNests | Y | Y | Y |
| IfcRepresentation | Y | Y | Y |
| IfcRepresentationItem | Y | Y | Y |
| IfcRoot | Y | Y | Y |
| IfcShapeAspect | Y | Y | Y |
| IfcShapeRepresentation | Y | Y | Y |
| IfcSite | Y | Y | Y |
| IfcSlab | Y | Y | Y |
| IfcSpace | Y | Y | Y |
| IfcSpatialElement | N | Y | Y |
| IfcSpatialStructureElement | Y | Y | Y |
| IfcStyledItem | Y | Y | Y |
| IfcStyledRepresentation | Y | Y | Y |
| IfcSurfaceStyleLighting | Y | Y | Y |
| IfcSurfaceStyleRefraction | Y | Y | Y |
| IfcSurfaceStyleShading | Y | Y | Y |
| IfcSurfaceStyleWithTextures | Y | Y | Y |
| IfcSurfaceTexture | Y | Y | Y |
| IfcText | Y | Y | Y |
| IfcTextStyleForDefinedFont | Y | Y | Y |
| IfcTextStyleTextModel | Y | Y | Y |
| IfcTextStyleWithBoxCharacteristics | Y | N | N |
| IfcTextureCoordinate | Y | Y | Y |
| IfcTextureVertex | Y | Y | Y |
| IfcTriangulatedFaceSet | N | Y | Y |
| IfcTypeObject | Y | Y | Y |
| IfcTypeProduct | Y | Y | Y |
| IfcVirtualElement | Y | Y | Y |
| IfcWall | Y | Y | Y |
| IfcWindowStyle | Y | Y | N |
| IfcWindowType | N | Y | Y |

`IfcWindowType` / `IfcWindowStyle` / `IfcDoorStyle` are in the table
only to close out the specific question the previous audit note
raised. **Verified: `grep -rn "IfcWindowType\|IfcWindowStyle\|IfcDoorStyle"`
across the entire `src/ifcpatch/` tree returns zero matches.** No
recipe touches window or door types by name at all, so this specific
concern does not apply — it is a checked negative, not an absence
claim from memory.

## Call sites for every name missing from IFC2X3, guarded or not

| Recipe | Name | Guarded? | Status |
|---|---|---|---|
| RemoveRevitUniformatClassification.py:54,56 | `classification.HasReferences` (attribute, not entity) | No | **Confirmed broken.** Fixed on `bimvoice/fix/removerevituniformat-ifc2x3` (not yet in this worktree). |
| FixArchiCADToRevitDoorSwings.py:135 | `IfcDoorType` (`by_type`) | No | **Confirmed broken.** Fixed on `bimvoice/fix/archicad-doorswings-ifc2x3` (not yet in this worktree). |
| FixArchiCADToRevitDoorSwings.py:195,199,208 | `IfcArcIndex`/`IfcCartesianPointList2D`/`IfcLineIndex` | No | Same recipe/branch as above; reached only after the `IfcDoorType` call already crashes, so folded into the same fix. |
| FixRevit2025TINs.py:142 | `IfcGeographicElement` (`reassign_class`) | No | **Confirmed broken.** Fixed on `bimvoice/fix/fixrevit2025tins-ifc2x3-predefinedtype` (not yet in this worktree). |
| **AssignConstituentFractions.py:64** | `IfcMaterialConstituentSet` (`by_type`) | **No** | **New finding, fixed in this sweep** (see below). |
| MergeProjects.py:103 | `IfcProjectedCRS` (`by_type`) | Yes — `self.file.schema != "IFC2X3" and (crs := ...)` | Clean. |
| MergeProjects.py:168 | `IfcCoordinateOperation` (`is_a`) | N/A — `is_a` never raises | Clean by construction. |
| Migrate.py:126 | `IfcPolygonalFaceSet`/`IfcTriangulatedFaceSet` (`by_type`) | Yes — only called inside `_convert_face_sets_to_faceted_brep`, itself only reached when `is_downgrade_to_ifc2x3` and operating on `self.file` which is the IFC4/IFC4X3 *source* file, never the IFC2X3 target | Clean. |
| PurgeData.py (7 names: `IfcContext`, `IfcSpatialElement`, `IfcPropertyAbstraction`, `IfcMaterialDefinition`, `IfcMaterialUsageDefinition`, `IfcPresentationItem`, `IfcExternalInformation`) | `by_type` | Yes — every one of these sits behind `if self.file.schema == "IFC2X3": ... else: ...` | Clean; this recipe was already fully IFC2X3-aware. |
| SplitByBuildingStorey.py:74,76 | `IfcContext` (`by_type`) | Yes — `if self.file.schema == "IFC2X3": elements = ... IfcProject ... else: ... IfcContext ...` | Clean. |
| SetFalseOrigin.py:105,107 | `IfcMapConversion`/`IfcMapConversionScaled` (passed as `ifc_class` string) | Yes, one layer down — `ifcopenshell.api.georeference.add_georeferencing()` itself has `if file.schema == "IFC2X3":` before it ever reaches `create_entity(ifc_class, ...)` | Clean. Quoted from `add_georeferencing.py:48`: `if file.schema == "IFC2X3":`. |
| PatchStationReferentPosition.py:27 | `IfcAlignment` (`by_type`) | No | Not a schema-guard gap — the entire recipe (`IfcLinearPlacement`, `IfcAxis2PlacementLinear`, `IfcPointByDistanceExpression`) is IFC4X3-exclusive alignment/stationing content with no IFC2X3 equivalent whatsoever. There is no realistic path where an IFC2X3 file reaches this recipe with alignment data to act on. See ranking below. |
| AGS2IFC.py:210,250 | `IfcBorehole`/`IfcGeotechnicalStratum` (`create_entity`) | N/A | Not a defect — `patch()` always builds a brand-new `ifcopenshell.api.project.create_file(version="IFC4X3")` and ignores `self.file`'s schema entirely. |
| ExtractPropertiesToSQLite.py:163,170 | `IfcMaterialProfileSet`/`IfcMaterialConstituentSet` (`is_a`) | N/A — `is_a` never raises | Clean by construction; on IFC2X3 these branches are simply unreachable dead code, not crashes. |

## Attribute-level divergence checked

Beyond `HasReferences`/`Contains` (the known RemoveRevitUniformatClassification
defect), `all_attributes()`/`all_inverse_attributes()` were diffed
between IFC2X3 and IFC4 for every entity a recipe actually
dereferences attributes on: `IfcObjectPlacement`, `IfcLocalPlacement`,
`IfcRoot`, `IfcElement`, `IfcProduct`, `IfcBuildingStorey`,
`IfcCartesianPoint`, `IfcGeometricRepresentationContext`,
`IfcGeometricRepresentationSubContext`, `IfcOwnerHistory`,
`IfcRelAssociatesClassification`, `IfcTypeProduct`, `IfcTypeObject`.

Divergences found: `IfcElement`/`IfcProduct`/`IfcBuildingStorey` gain
`IsTypedBy`, `IsDeclaredBy`, `HasContext`, `Nests`, `IsNestedBy`,
`Declares` in IFC4 (nesting/context concepts new to IFC4);
`IfcCartesianPoint.LayerAssignment` (IFC4) vs `LayerAssignments`
(IFC2X3, plural); `IfcGeometricRepresentationContext.HasCoordinateOperation`
is IFC4-only. **None of these are dereferenced unguarded anywhere in
ifcpatch.** `HasCoordinateOperation` is read once, in
`ExtractElements.py:114`, via `getattr(ctx, "HasCoordinateOperation", ())`
— already safe by construction. The rest do not appear in the recipes
at all (verified by grep, zero matches).

## Reproductions

All four reproduced directly against the entity/attribute, in an
isolated interpreter built from `build/Darwin/arm64/10.15/install/python-3.13.6`
with the worktree's Python sources overlaid (`ifcopenshell.__file__`
resolved into the scratch copy, confirmed).

**1. RemoveRevitUniformatClassification — `IfcClassification.HasReferences`:**

```
>>> c = f.create_entity('IfcClassification', Name='Uniformat')  # f is IFC2X3
>>> c.HasReferences
AttributeError: entity instance of type 'IFC2X3.IfcClassification' has no attribute 'HasReferences'
```

**2. FixArchiCADToRevitDoorSwings — `by_type("IfcDoorType")`:**

```
>>> f.by_type('IfcDoorType')  # f is IFC2X3
RuntimeError: Entity with name 'IfcDoorType' not found in schema 'IFC2X3'
```

**3. FixRevit2025TINs — `reassign_class(..., "IfcGeographicElement")`:**

```
>>> ifcopenshell.util.schema.reassign_class(f, w, 'IfcGeographicElement')  # f is IFC2X3
ValueError: Class of #2=IfcBuildingElementProxy(...) could not be changed to
IfcGeographicElement as the class does not exist in schema IFC2X3.
```

**4. AssignConstituentFractions — `by_type("IfcMaterialConstituentSet")` (new finding):**

```
>>> f = ifcopenshell.file(schema='IFC2X3')
>>> f.create_entity('IfcProject', GlobalId=ifcopenshell.guid.new(), Name='P')
>>> Patcher(f, logging.getLogger('t')).patch()
RuntimeError: Entity with name 'IfcMaterialConstituentSet' not found in schema 'IFC2X3'
```

This crashes on **any** IFC2X3 file passed to the recipe, whether or
not it has material constituents — `by_type()` resolves the class
name against the schema declaration before it does anything else, so
the crash happens before the loop body is ever entered.

## Ranking

| Recipe | Vendor / workflow | Likelihood target users are on IFC2X3 | Status |
|---|---|---|---|
| RemoveRevitUniformatClassification | Undoes a Revit export bug; Revit's default export is IFC2X3 | Very high — this is the recipe's primary target | Already fixed on `bimvoice/fix/removerevituniformat-ifc2x3` |
| FixArchiCADToRevitDoorSwings | Undoes an ArchiCAD/Revit door-swing interop issue; ArchiCAD exports IFC2X3 routinely | Very high | Already fixed on `bimvoice/fix/archicad-doorswings-ifc2x3` |
| FixRevit2025TINs | Undoes a Revit 2025 TIN export bug | High (same vendor pattern) | Already fixed on `bimvoice/fix/fixrevit2025tins-ifc2x3-predefinedtype` |
| AssignConstituentFractions | General Reference View MVD cleanup, offered generically in the recipe list to any user/file | Low-to-moderate — Bonsai lets any user run any recipe against any open file, and this one crashes unconditionally on IFC2X3 rather than being a graceful no-op | **Fixed in this sweep** |
| PatchStationReferentPosition | Alignment/stationing content, IFC4X3-exclusive by definition | Effectively zero — there is no IFC2X3 concept of an alignment to act on | Not fixed; not a schema-guard gap, just inherently out of scope for IFC2X3 |

## Conflict check and skipped work

```
gh pr list --repo IfcOpenShell/IfcOpenShell --state open --search "ifcpatch"
gh pr list --repo IfcOpenShell/IfcOpenShell --state open --search "IFC2X3"
git fetch bimvoice && git for-each-ref refs/remotes/bimvoice/ | grep -iE 'ifcpatch|ifc2x3|recipe'
```

Skipped (already fixed on an existing `bimvoice` branch, verified by
reading the branch's diff, not just its name):

- `RemoveRevitUniformatClassification.py` — `bimvoice/fix/removerevituniformat-ifc2x3`, commit `c5c76128e6`.
- `FixArchiCADToRevitDoorSwings.py` — `bimvoice/fix/archicad-doorswings-ifc2x3`, commit `b8b6044b37` (plus a preceding `020a7c0f2b` for an unrelated unguarded-attribute crash in the same file).
- `FixRevit2025TINs.py` — `bimvoice/fix/fixrevit2025tins-ifc2x3-predefinedtype`, commit `ce222b4532`.

3 recipes skipped. One recipe (`AssignConstituentFractions.py`) had
its own branch on `bimvoice`
(`fix/ifcpatch-constituent-fractions-zero-width`), but reading its
diff shows it fixes an unrelated zero-width-constituent bug (`width :=`
truthiness dropping a legitimate `0.0` width) — it does not touch the
`IfcMaterialConstituentSet` schema-guard issue, so that recipe was not
double-fixed.

None of the other 34 recipes had any *literal* name from the schema
table appear unguarded, so no further fixes were needed. This check is
necessarily scoped to string literals passed directly to `by_type`/
`create_entity`/`reassign_class`/`is_a`; call sites that build the
class name from a variable were traced to their assignment
individually:

- `MergeStyles.py:48` — `by_type(ifc_class)` where `ifc_class` iterates
  a literal tuple `("IfcColourRgb", "IfcSurfaceStyleShading",
  "IfcPresentationStyle")`, all present in every schema per the table.
- `Migrate.py:159` — `by_type(ifc_class)` where `ifc_class` iterates
  `ifcopenshell.util.schema.geometry_classes_introduced_after(self.schema,
  source_schema=self.file.schema)`, i.e. it is derived from the
  file's own schema, called on `self.file` — safe by construction.
- `OffsetStoreyElevations.py:60`, `RemoveSiteRepresentation.py:48`,
  `ResetSpatialElementLocations.py:64`, `SetRefElevation.py:60` — all
  four call `is_a(ifc_class)`, never `by_type`, so they inherit the
  "`is_a` never raises" safety above regardless of what `ifc_class`
  holds.

## Fix shipped

Branch `fix/ifcpatch-constituent-fractions-ifc2x3` (pushed to
`bimvoice`), commit `36fb218467`:

- `src/ifcpatch/ifcpatch/recipes/AssignConstituentFractions.py`: added
  `if self.file.schema == "IFC2X3": return` at the top of `patch()`,
  following the `DowngradeIndexedPolyCurve.py` precedent — material
  constituent sets are a Reference View MVD / IFC4 concept with no
  IFC2X3 equivalent, so there is nothing to convert on an IFC2X3 file.
- `src/ifcpatch/test/test_AssignConstituentFractions.py` (new): an
  IFC4 test that builds a constituent set with two constituents and a
  `Qto_WallBaseQuantities` complex-quantity pset by hand, runs the
  recipe, and asserts the fractions come out as `1/3` and `2/3`; and
  an `IFC2X3` bootstrap-subclass test asserting the recipe runs to
  completion without raising on a bare IFC2X3 file.

Verified: `pytest -p no:pytest-blender test/test_AssignConstituentFractions.py`
— 2 passed. Full `test/` suite in `src/ifcpatch`: 64 passed, 1 skipped,
5 failed — the failures are all in `test_MergeProject.py`
(`test_reusing_geometric_contexts`, `test_using_the_georeferencing_of_the_original_project`,
`test_merging_three_or_more_projects`, both plain and IFC2X3 variants),
pre-existing and unrelated to this change (present before this sweep's
commit, in an unrelated recipe).

`black` and `ruff check` pass clean on both changed files.
