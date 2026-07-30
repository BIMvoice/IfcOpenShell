# IfcOpenShell - IFC toolkit and geometry engine
# Copyright (C) 2026 IfcOpenShell contributors
#
# This file is part of IfcOpenShell.
#
# IfcOpenShell is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# IfcOpenShell is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with IfcOpenShell.  If not, see <http://www.gnu.org/licenses/>.

"""Collateral-damage harness for ifcopenshell.api operations.

Ordinary unit tests for an API usecase only assert things about the entity
the usecase was called on. That structurally cannot catch bugs where an
operation on entity A silently corrupts entity B, and B is unrelated to the
call. IFC's placements, property sets, materials, and classification
references are all "many-to-one": several products may legitimately share
one IfcLocalPlacement, one IfcPropertySet, one IfcMaterial, or one
IfcClassificationReference. Any code that mutates one of those shared
entities in place, instead of only touching the referrer it was asked to
touch, silently damages every other referrer.

This harness builds a small fixture with genuine sharing of that kind,
snapshots every product's placement/container/psets/material/classification,
runs one ifcopenshell.api operation, saves the file to disk and reloads it
(in-session state hides this bug class), and asserts that every product
*not* named as a legitimate target of the operation is byte-identical to
its "before" snapshot. Only entities the operation says it is allowed to
touch may differ.

See #9114 (reassigning an IfcSlab's storey silently moved an unrelated
IfcWall to the origin, visible only after save/reload) for the motivating
report.
"""

import dataclasses
import os
import sys
import tempfile
from typing import Any, Callable, Optional

if os.path.abspath(os.path.join(os.path.dirname(__file__), "..")) == sys.path[0]:
    # Don't import ifcopenshell from local directory, because it most likely
    # does not contain the built binary
    sys.path[0:1] = []

import numpy
import pytest

import ifcopenshell
import ifcopenshell.api.aggregate
import ifcopenshell.api.classification
import ifcopenshell.api.geometry
import ifcopenshell.api.material
import ifcopenshell.api.owner.settings
import ifcopenshell.api.project
import ifcopenshell.api.pset
import ifcopenshell.api.root
import ifcopenshell.api.spatial
import ifcopenshell.api.unit
import ifcopenshell.util.classification
import ifcopenshell.util.element
import ifcopenshell.util.placement


def _configure_owner(file: ifcopenshell.file) -> None:
    ifcopenshell.api.owner.settings.get_user = lambda ifc: (ifc.by_type("IfcPersonAndOrganization") or [None])[0]
    ifcopenshell.api.owner.settings.get_application = lambda ifc: (ifc.by_type("IfcApplication") or [None])[0]
    ifcopenshell.api.pre_listeners = {}
    ifcopenshell.api.post_listeners = {}


# ---------------------------------------------------------------------------
# Fixture: a small model with genuine many-to-one sharing.
# ---------------------------------------------------------------------------
#
# test/files/basic.ifc (the only pre-existing top level fixture) contains a
# single product and no sharing at all, so it cannot exercise the bug class
# this harness targets. There is nothing under test/fixtures either. This
# fixture is therefore built here, through the public API, so it stays valid
# across schema/API changes and is easy to read.
#
# Sharing built into this fixture:
#   - "door" and "column" point to the *same* IfcLocalPlacement instance
#     (IfcObjectPlacement.PlacesObject is 0:*, so this is spec-legal).
#   - "wall" and "slab" have distinct IfcLocalPlacement wrappers, but those
#     wrappers share the *same* IfcAxis2Placement3D as their RelativePlacement
#     (a common pattern in real authoring tools that intern axis placements).
#   - "wall", "slab" and "column" share one IfcPropertySet through a single
#     IfcRelDefinesByProperties.RelatedObjects list.
#   - "wall" and "door" share one IfcMaterial.
#   - "wall" and "column" share one IfcClassificationReference.


def build_fixture() -> tuple[ifcopenshell.file, dict[str, str]]:
    """Builds a fixture model with genuine shared references and returns
    (file, roles) where roles maps a logical name to a stable GlobalId."""
    file = ifcopenshell.api.project.create_file(version="IFC4")
    _configure_owner(file)

    project = ifcopenshell.api.root.create_entity(file, ifc_class="IfcProject", name="Test Project")
    ifcopenshell.api.unit.assign_unit(file)

    site = ifcopenshell.api.root.create_entity(file, ifc_class="IfcSite", name="Site")
    building = ifcopenshell.api.root.create_entity(file, ifc_class="IfcBuilding", name="Building")
    storey_a = ifcopenshell.api.root.create_entity(file, ifc_class="IfcBuildingStorey", name="Storey A")
    storey_b = ifcopenshell.api.root.create_entity(file, ifc_class="IfcBuildingStorey", name="Storey B")

    ifcopenshell.api.aggregate.assign_object(file, products=[site], relating_object=project)
    ifcopenshell.api.aggregate.assign_object(file, products=[building], relating_object=site)
    ifcopenshell.api.aggregate.assign_object(file, products=[storey_a, storey_b], relating_object=building)

    wall = ifcopenshell.api.root.create_entity(file, ifc_class="IfcWall", name="Wall")
    slab = ifcopenshell.api.root.create_entity(file, ifc_class="IfcSlab", name="Slab")
    column = ifcopenshell.api.root.create_entity(file, ifc_class="IfcColumn", name="Column")
    door = ifcopenshell.api.root.create_entity(file, ifc_class="IfcDoor", name="Door")

    ifcopenshell.api.spatial.assign_container(file, products=[wall, slab, column, door], relating_structure=storey_a)

    # Give every product its own distinct absolute placement first.
    for i, product in enumerate([wall, slab, column, door]):
        matrix = numpy.eye(4)
        matrix[0][3] = float((i + 1) * 1000)
        matrix[1][3] = float((i + 1) * 500)
        ifcopenshell.api.geometry.edit_object_placement(file, product=product, matrix=matrix, is_si=True)

    # Shared IfcLocalPlacement instance: column and door literally point to
    # the same entity. This is legal per IfcObjectPlacement.PlacesObject (0:*).
    column.ObjectPlacement = door.ObjectPlacement

    # Shared IfcAxis2Placement3D sub-entity: wall and slab keep their own
    # IfcLocalPlacement wrapper, but the RelativePlacement (axis + point)
    # underneath is the exact same entity.
    slab.ObjectPlacement.RelativePlacement = wall.ObjectPlacement.RelativePlacement

    # Shared property set across wall, slab, column.
    pset = ifcopenshell.api.pset.add_pset(file, wall, "Foo_SharedPset")
    ifcopenshell.api.pset.edit_pset(file, pset=pset, properties={"SharedProp": "original"})
    pset_rel = next(r for r in file.by_type("IfcRelDefinesByProperties") if r.RelatingPropertyDefinition == pset)
    pset_rel.RelatedObjects = [wall, slab, column]

    # Shared material between wall and door.
    material = ifcopenshell.api.material.assign_material(file, products=[wall, door], type="IfcMaterial")
    material.Name = "Shared Concrete"

    # Shared classification reference between wall and column.
    classification = ifcopenshell.api.classification.add_classification(file, classification="Uniclass")
    reference = ifcopenshell.api.classification.add_reference(
        file,
        products=[wall, column],
        identification="Ss_25_10_30",
        name="Shared reference",
        classification=classification,
    )

    roles = {
        "project": project.GlobalId,
        "storey_a": storey_a.GlobalId,
        "storey_b": storey_b.GlobalId,
        "wall": wall.GlobalId,
        "slab": slab.GlobalId,
        "column": column.GlobalId,
        "door": door.GlobalId,
    }
    return file, roles


def write_and_reload(file: ifcopenshell.file) -> ifcopenshell.file:
    """Saves `file` to a temporary .ifc file and reloads it from disk.

    This is the essential step: several known bugs (#9114, #9124, #9122,
    #9125, #9120) only manifest after a save/reload round trip and are
    invisible while inspecting the live in-session model.
    """
    fd, path = tempfile.mkstemp(suffix=".ifc")
    os.close(fd)
    try:
        file.write(path)
        return ifcopenshell.open(path)
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# Snapshotting
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class ProductSnapshot:
    ifc_class: str
    name: Optional[str]
    container: Optional[str]  # GlobalId of the direct spatial container, or None
    placement: Optional[numpy.ndarray]  # absolute 4x4 matrix, or None
    psets: dict[str, Any]
    material: Any  # a hashable/comparable content signature, or None
    classifications: frozenset


def _material_signature(material: Optional[ifcopenshell.entity_instance]) -> Any:
    if material is None:
        return None
    if material.is_a("IfcMaterial"):
        return ("IfcMaterial", material.Name)
    if material.is_a("IfcMaterialList"):
        return ("IfcMaterialList", tuple(sorted(m.Name for m in material.Materials or [])))
    # Material sets / usages: describe by type + constituent material names.
    layers = getattr(material, "MaterialLayers", None) or getattr(material, "MaterialConstituents", None)
    if layers:
        names = tuple(sorted((getattr(l, "Material", None) or l).Name for l in layers if getattr(l, "Material", None)))
        return (material.is_a(), names)
    return (material.is_a(), getattr(material, "Name", None))


def _classification_signature(product: ifcopenshell.entity_instance) -> frozenset:
    try:
        references = ifcopenshell.util.classification.get_references(product, should_inherit=False)
    except Exception:
        return frozenset()
    result = set()
    for reference in references:
        system = ifcopenshell.util.classification.get_classification(reference)
        result.add((reference.Identification, reference.Name, getattr(system, "Name", None)))
    return frozenset(result)


def snapshot_products(file: ifcopenshell.file) -> dict[str, ProductSnapshot]:
    """Snapshots every IfcProduct in `file`, keyed by GlobalId."""
    snapshot: dict[str, ProductSnapshot] = {}
    for product in file.by_type("IfcProduct"):
        if not product.is_a("IfcRoot"):
            continue
        placement = getattr(product, "ObjectPlacement", None)
        matrix = ifcopenshell.util.placement.get_local_placement(placement) if placement else None
        container = ifcopenshell.util.element.get_container(product, should_get_direct=True)
        snapshot[product.GlobalId] = ProductSnapshot(
            ifc_class=product.is_a(),
            name=getattr(product, "Name", None),
            container=container.GlobalId if container else None,
            placement=matrix.copy() if matrix is not None else None,
            psets=ifcopenshell.util.element.get_psets(product, psets_only=True, should_inherit=False),
            material=_material_signature(ifcopenshell.util.element.get_material(product, should_inherit=False)),
            classifications=_classification_signature(product),
        )
    return snapshot


# ---------------------------------------------------------------------------
# The generic assertion: nothing changed except what was declared allowed.
# ---------------------------------------------------------------------------


def assert_no_collateral_damage(
    before: dict[str, ProductSnapshot],
    after: dict[str, ProductSnapshot],
    allowed: dict[str, set],
) -> None:
    """Asserts that only the entities/dimensions named in `allowed` differ
    between `before` and `after`.

    `allowed` may contain the keys "placement", "container", "psets",
    "material", "classifications" (each a set of GlobalIds permitted to
    change in that dimension), plus "new" and "removed" (sets of GlobalIds
    permitted to appear/disappear).
    """
    allowed_new = allowed.get("new", set())
    allowed_removed = allowed.get("removed", set())

    unexpected_new = set(after) - set(before) - allowed_new
    assert not unexpected_new, (
        f"Operation created unexpected new product(s) that were not declared: "
        f"{[(g, after[g].ifc_class, after[g].name) for g in unexpected_new]}"
    )

    unexpected_removed = set(before) - set(after) - allowed_removed
    assert not unexpected_removed, (
        f"Operation removed unexpected product(s) that were not declared: "
        f"{[(g, before[g].ifc_class, before[g].name) for g in unexpected_removed]}"
    )

    for guid in set(before) & set(after):
        b = before[guid]
        a = after[guid]
        label = f"{b.ifc_class} '{b.name}' ({guid})"

        if guid not in allowed.get("placement", set()):
            both_none = b.placement is None and a.placement is None
            if not both_none:
                assert b.placement is not None and a.placement is not None, (
                    f"{label} placement appeared/disappeared and should not have: "
                    f"before={b.placement}, after={a.placement}"
                )
                assert numpy.allclose(b.placement, a.placement, atol=1e-6), (
                    f"{label} moved and should not have (not a target of this operation).\n"
                    f"before:\n{b.placement}\nafter:\n{a.placement}"
                )

        if guid not in allowed.get("container", set()):
            assert b.container == a.container, (
                f"{label} spatial container changed from {b.container} to {a.container} "
                "and should not have (not a target of this operation)."
            )

        if guid not in allowed.get("psets", set()):
            assert b.psets == a.psets, (
                f"{label} property sets changed and should not have "
                f"(not a target of this operation).\nbefore={b.psets}\nafter={a.psets}"
            )

        if guid not in allowed.get("material", set()):
            assert b.material == a.material, (
                f"{label} material changed from {b.material} to {a.material} "
                "and should not have (not a target of this operation)."
            )

        if guid not in allowed.get("classifications", set()):
            assert b.classifications == a.classifications, (
                f"{label} classification references changed from {b.classifications} to {a.classifications} "
                "and should not have (not a target of this operation)."
            )


# ---------------------------------------------------------------------------
# Operations under test. Each one performs exactly one ifcopenshell.api call
# and declares which entities/dimensions it is legitimately allowed to touch.
# ---------------------------------------------------------------------------


def op_spatial_assign_container(file: ifcopenshell.file, roles: dict[str, str]) -> dict[str, set]:
    wall = file.by_guid(roles["wall"])
    storey_b = file.by_guid(roles["storey_b"])
    ifcopenshell.api.spatial.assign_container(file, products=[wall], relating_structure=storey_b)
    # assign_container is documented to re-localize the placement so the
    # absolute position is preserved, so placement is deliberately *not*
    # in the allowed set: it must come back identical.
    return {"container": {roles["wall"]}}


def op_spatial_unassign_container(file: ifcopenshell.file, roles: dict[str, str]) -> dict[str, set]:
    door = file.by_guid(roles["door"])
    ifcopenshell.api.spatial.unassign_container(file, products=[door])
    return {"container": {roles["door"]}}


def op_aggregate_assign_object(file: ifcopenshell.file, roles: dict[str, str]) -> dict[str, set]:
    wall = file.by_guid(roles["wall"])
    column = file.by_guid(roles["column"])
    ifcopenshell.api.aggregate.assign_object(file, products=[column], relating_object=wall)
    # column becomes a part of wall: its direct spatial container goes away
    # (it is now reached indirectly through wall), absolute placement must
    # be preserved.
    return {"container": {roles["column"]}}


def op_geometry_edit_object_placement(file: ifcopenshell.file, roles: dict[str, str]) -> dict[str, set]:
    door = file.by_guid(roles["door"])
    matrix = numpy.eye(4)
    matrix[0][3] = 9999.0
    ifcopenshell.api.geometry.edit_object_placement(file, product=door, matrix=matrix, is_si=True)
    # door shares its IfcLocalPlacement instance with column in this
    # fixture; moving door must not move column.
    return {"placement": {roles["door"]}}


def op_root_copy_class(file: ifcopenshell.file, roles: dict[str, str]) -> dict[str, set]:
    wall = file.by_guid(roles["wall"])
    before_guids = {p.GlobalId for p in file.by_type("IfcProduct")}
    copy = ifcopenshell.api.root.copy_class(file, product=wall)
    after_guids = {p.GlobalId for p in file.by_type("IfcProduct")} - before_guids
    assert copy.GlobalId in after_guids
    return {"new": after_guids}


def op_root_remove_product(file: ifcopenshell.file, roles: dict[str, str]) -> dict[str, set]:
    column = file.by_guid(roles["column"])
    guid = column.GlobalId
    ifcopenshell.api.root.remove_product(file, product=column)
    # column shared its placement with door and its pset with wall/slab;
    # removing it must not take those down with it.
    return {"removed": {guid}}


def op_classification_add_reference(file: ifcopenshell.file, roles: dict[str, str]) -> dict[str, set]:
    slab = file.by_guid(roles["slab"])
    wall = file.by_guid(roles["wall"])
    existing_reference = next(iter(ifcopenshell.util.classification.get_references(wall, should_inherit=False)))
    ifcopenshell.api.classification.add_reference(file, products=[slab], reference=existing_reference)
    return {"classifications": {roles["slab"]}}


def op_pset_edit_pset(file: ifcopenshell.file, roles: dict[str, str]) -> dict[str, set]:
    wall = file.by_guid(roles["wall"])
    slab = file.by_guid(roles["slab"])
    column = file.by_guid(roles["column"])
    pset = next(
        r.RelatingPropertyDefinition
        for r in wall.IsDefinedBy
        if r.is_a("IfcRelDefinesByProperties") and r.RelatingPropertyDefinition.Name == "Foo_SharedPset"
    )
    ifcopenshell.api.pset.edit_pset(file, pset=pset, properties={"SharedProp": "edited"})
    # wall, slab and column all legitimately share this one pset: editing
    # it is *supposed* to change it for all three. Their placement,
    # container, material and classifications must stay untouched though.
    return {"psets": {roles["wall"], roles["slab"], roles["column"]}}


OPERATIONS: dict[str, Callable[[ifcopenshell.file, dict[str, str]], dict[str, set]]] = {
    "spatial.assign_container": op_spatial_assign_container,
    "spatial.unassign_container": op_spatial_unassign_container,
    "aggregate.assign_object": op_aggregate_assign_object,
    "geometry.edit_object_placement": op_geometry_edit_object_placement,
    "root.copy_class": op_root_copy_class,
    "root.remove_product": op_root_remove_product,
    "classification.add_reference": op_classification_add_reference,
    "pset.edit_pset": op_pset_edit_pset,
}


@pytest.mark.parametrize("operation_name", list(OPERATIONS))
def test_operation_causes_no_collateral_damage(operation_name: str) -> None:
    _configure_owner(ifcopenshell.api.project.create_file())  # reset owner hooks between parametrized runs

    file, roles = build_fixture()
    file = write_and_reload(file)
    _configure_owner(file)
    before = snapshot_products(file)

    allowed = OPERATIONS[operation_name](file, roles)

    file = write_and_reload(file)
    after = snapshot_products(file)

    assert_no_collateral_damage(before, after, allowed)


# ---------------------------------------------------------------------------
# Regression demonstration: #9124, a shared caller matrix scaled twice.
# ---------------------------------------------------------------------------
#
# ifcopenshell.api.geometry.edit_object_placement.Usecase.convert_matrix_to_si
# used to mutate the caller's numpy matrix object in place. If a caller
# reuses that same matrix object across two edit_object_placement() calls
# for two different products (a legitimate pattern: e.g.
# spatial.assign_container/aggregate.assign_object both do exactly this
# kind of "compute once, place many" when localising placements) the second
# call silently applied the unit scale a second time on top of the first
# call's mutation, producing a corrupted placement for every element after
# the first. This is fixed on branch api-audit-geometry-profile-fixes
# (PR #9124), which is NOT YET merged into v0.8.0 at the time of writing, so
# this repository's current source still reproduces the bug.


def test_regression_9124_reusing_matrix_across_products_does_not_double_convert() -> None:
    file, roles = build_fixture()
    wall = file.by_guid(roles["wall"])
    slab = file.by_guid(roles["slab"])

    matrix = numpy.array(
        (
            (1.0, 0.0, 0.0, 1000.0),
            (0.0, 1.0, 0.0, 2000.0),
            (0.0, 0.0, 1.0, 3000.0),
            (0.0, 0.0, 0.0, 1.0),
        )
    )
    matrix_before = matrix.copy()

    # Both calls intend to place their product at the exact same position,
    # reusing the same numpy array, in project units (is_si=False), exactly
    # like spatial.assign_container/aggregate.assign_object do internally.
    ifcopenshell.api.geometry.edit_object_placement(file, product=wall, matrix=matrix, is_si=False)
    ifcopenshell.api.geometry.edit_object_placement(file, product=slab, matrix=matrix, is_si=False)

    file = write_and_reload(file)
    wall = file.by_guid(roles["wall"])
    slab = file.by_guid(roles["slab"])

    wall_matrix = ifcopenshell.util.placement.get_local_placement(wall.ObjectPlacement)
    slab_matrix = ifcopenshell.util.placement.get_local_placement(slab.ObjectPlacement)

    assert numpy.array_equal(matrix, matrix_before), "caller's matrix object must not be mutated by the API call"
    assert numpy.allclose(
        wall_matrix, matrix_before, atol=1e-6
    ), f"wall should be at the requested position.\nrequested:\n{matrix_before}\nactual:\n{wall_matrix}"
    assert numpy.allclose(slab_matrix, matrix_before, atol=1e-6), (
        "slab should be at the SAME requested position as wall (both calls reused the same matrix). "
        f"If this is off by a factor of the unit scale, the caller's matrix was double-converted.\n"
        f"requested:\n{matrix_before}\nactual:\n{slab_matrix}"
    )
