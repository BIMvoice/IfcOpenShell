# Bonsai - OpenBIM Blender Add-on
# Copyright (C) 2026
#
# This file is part of Bonsai.
#
# Bonsai is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Bonsai is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Bonsai.  If not, see <http://www.gnu.org/licenses/>.
#
# This file was generated with the assistance of an AI coding tool.

"""Guards ``bim.mirror_elements`` against mirroring shared type geometry.

When a typed occurrence's body is an ``IfcMappedItem``, the mapped
representation belongs to the type and is shared with every sibling
occurrence. Inverting it in place would silently mirror the whole family.
``MirrorElements`` must refuse that and route such occurrences through
``assign_inverted_type`` instead, which mirrors a private copy of the type.

Also pins the single-axis rule in ``get_mirror_axes``: flipping two local
axes at once is a 180 degree rotation, not a reflection, and would leave
``reflect_placement`` composing two determinant +1 matrices."""

from types import SimpleNamespace
from unittest.mock import patch

import bpy
import ifcopenshell
import numpy as np
import pytest
from mathutils import Matrix, Vector

from test.bim.bootstrap import NewFile

pytestmark = pytest.mark.model


def _mapped_type_file():
    """An IFC4 file with one type carrying a triangle, mapped by two occurrences."""
    f = ifcopenshell.file(schema="IFC4")
    context = f.create_entity(
        "IfcGeometricRepresentationContext",
        ContextType="Model",
        CoordinateSpaceDimension=3,
        WorldCoordinateSystem=f.create_entity(
            "IfcAxis2Placement3D", Location=f.create_entity("IfcCartesianPoint", Coordinates=(0.0, 0.0, 0.0))
        ),
    )
    points = [f.create_entity("IfcCartesianPoint", Coordinates=c) for c in ((0.0, 0.0), (3.0, 0.0), (0.5, 1.0))]
    profile = f.create_entity(
        "IfcArbitraryClosedProfileDef",
        ProfileType="AREA",
        OuterCurve=f.create_entity("IfcPolyline", Points=points + [points[0]]),
    )
    solid = f.create_entity(
        "IfcExtrudedAreaSolid",
        SweptArea=profile,
        Position=f.create_entity(
            "IfcAxis2Placement3D", Location=f.create_entity("IfcCartesianPoint", Coordinates=(0.0, 0.0, 0.0))
        ),
        ExtrudedDirection=f.create_entity("IfcDirection", DirectionRatios=(0.0, 0.0, 1.0)),
        Depth=1.0,
    )
    mapped_representation = f.create_entity(
        "IfcShapeRepresentation",
        ContextOfItems=context,
        RepresentationIdentifier="Body",
        RepresentationType="SweptSolid",
        Items=[solid],
    )
    representation_map = f.create_entity(
        "IfcRepresentationMap",
        MappingOrigin=f.create_entity(
            "IfcAxis2Placement3D", Location=f.create_entity("IfcCartesianPoint", Coordinates=(0.0, 0.0, 0.0))
        ),
        MappedRepresentation=mapped_representation,
    )
    element_type = f.create_entity("IfcFurnitureType", GlobalId="0" * 22, RepresentationMaps=[representation_map])

    occurrences = []
    for _ in range(2):
        target = f.create_entity(
            "IfcCartesianTransformationOperator3D",
            LocalOrigin=f.create_entity("IfcCartesianPoint", Coordinates=(0.0, 0.0, 0.0)),
            Scale=1.0,
        )
        mapped_item = f.create_entity("IfcMappedItem", MappingSource=representation_map, MappingTarget=target)
        occurrence = f.create_entity(
            "IfcFurniture",
            GlobalId="1" * 22,
            Representation=f.create_entity(
                "IfcProductDefinitionShape",
                Representations=[
                    f.create_entity(
                        "IfcShapeRepresentation",
                        ContextOfItems=context,
                        RepresentationIdentifier="Body",
                        RepresentationType="MappedRepresentation",
                        Items=[mapped_item],
                    )
                ],
            ),
        )
        occurrences.append(occurrence)
    return f, element_type, occurrences, solid


def _profile_coordinates(solid):
    return [tuple(p.Coordinates) for p in solid.SweptArea.OuterCurve.Points]


def _operator():
    """A plain stand-in carrying the operator's methods.

    ``bpy.types.Operator`` subclasses cannot be instantiated outside an operator
    call, and none of the methods under test need operator state beyond
    ``unsupported_items``."""
    from bonsai.bim.module.model.product import MirrorElements

    methods = (
        "find_uninvertible_items",
        "get_mirror_axes",
        "invert_general_object",
        "invert_representation",
        "get_mirror_plane_point",
        "is_type_owned_mapping",
        "reflect_placement",
    )
    # __dict__ rather than getattr so staticmethod descriptors survive the copy
    stub = type("MirrorElementsStub", (), {name: MirrorElements.__dict__[name] for name in methods})()
    stub.unsupported_items = set()
    return stub


def test_mirroring_a_mapped_occurrence_leaves_the_shared_type_untouched():
    from bonsai.bim.module.model.product import SharedMappedGeometryError

    ifc_file, _, occurrences, solid = _mapped_type_file()
    coordinates_before = _profile_coordinates(solid)
    operator = _operator()

    with patch("bonsai.tool.Ifc.get", return_value=ifc_file):
        with pytest.raises(SharedMappedGeometryError):
            operator.invert_general_object(occurrences[0])

    assert _profile_coordinates(solid) == coordinates_before


def test_a_privately_mapped_representation_is_still_mirrored():
    """A mapping used by a single occurrence and owned by no type is safe to invert."""
    ifc_file, element_type, occurrences, solid = _mapped_type_file()
    # Detach the type and the second occurrence so only one IfcMappedItem is left.
    ifc_file.remove(occurrences[1].Representation.Representations[0].Items[0])
    element_type.RepresentationMaps = None
    representation_map = occurrences[0].Representation.Representations[0].Items[0].MappingSource

    operator = _operator()
    coordinates_before = _profile_coordinates(solid)
    with patch("bonsai.tool.Ifc.get", return_value=ifc_file):
        assert len(representation_map.MapUsage) == 1
        assert operator.is_type_owned_mapping(occurrences[0].Representation.Representations[0].Items[0]) is False
        with patch("bonsai.tool.Ifc.get_object", return_value=None):
            with patch("bonsai.tool.Geometry.reload_representation"):
                operator.invert_general_object(occurrences[0], (1.0, 0.0, 0.0))

    coordinates_after = _profile_coordinates(solid)
    assert coordinates_after != coordinates_before
    assert [round(-x, 6) for x, _ in coordinates_before] == [round(x, 6) for x, _ in coordinates_after]


def test_reflect_placement_across_a_reference_is_an_exact_reflection():
    """The placement maths, independent of IFC: a point must land at its mirror image."""
    operator = _operator()
    obj = SimpleNamespace(matrix_world=Matrix.Translation((2.0, 0.0, 0.0)), location=None)
    # bound_box all zeros, as for an empty, so the plane passes through the reference origin
    reference = SimpleNamespace(matrix_world=Matrix.Translation((5.0, 0.0, 0.0)), bound_box=[(0.0, 0.0, 0.0)] * 8)
    operator.reflect_placement(obj, reference, (1.0, 0.0, 0.0), {}, 0)

    # A local point p maps to matrix_world @ (P_local @ p); with the object at x=2 and the
    # plane at x=5, a point 1 unit along local +x sits at x=3 and must end up at x=7.
    p = Vector((1.0, 0.0, 0.0))
    assert np.allclose(list(obj.matrix_world @ Vector((-p.x, p.y, p.z))), [7.0, 0.0, 0.0])


def test_the_mirror_plane_passes_through_the_middle_of_the_reference():
    """An IFC origin is arbitrary, so the plane has to sit at what the user can see.

    The reference here spans local x 0..4 with its origin at the near corner, so the plane is
    at x = 2 in local terms, which is x = 12 in the world.
    """
    operator = _operator()
    corners = [(x, y, z) for x in (0.0, 4.0) for y in (0.0, 1.0) for z in (0.0, 3.0)]
    # get_object_bounding_box reads bound_box[0] as the minimum and bound_box[6] as the maximum
    bound_box = [(0.0, 0.0, 0.0), None, None, None, None, None, (4.0, 1.0, 3.0), None]
    reference = SimpleNamespace(matrix_world=Matrix.Translation((10.0, 0.0, 0.0)), bound_box=bound_box)
    assert list(operator.get_mirror_plane_point(reference)) == [12.0, 0.5, 1.5]
    assert corners  # the bounds above describe a real box

    obj = SimpleNamespace(matrix_world=Matrix.Translation((3.0, 0.0, 0.0)), location=None)
    operator.reflect_placement(obj, reference, (1.0, 0.0, 0.0), {}, 0)
    # the object origin sits 9 units to the left of the plane, so it lands 9 to the right
    assert np.allclose(list(obj.matrix_world.translation), [21.0, 0.0, 0.0])


def test_adjust_last_operation_undoes_the_previous_run_first():
    """Blender's redo path re-runs execute without firing the undo handler, so the previous
    run's inversion is still in the IFC. Inverting X then Y composes into a 180 degree
    rotation. Mirroring is its own inverse, so the previous run is replayed to cancel it."""
    from bonsai.bim.module.model.product import MirrorElements

    replayed = []

    class Stub:
        _execute = MirrorElements._execute
        revert_last_run = MirrorElements.revert_last_run
        resolve_selection = MirrorElements.__dict__["resolve_selection"]
        mirror_axis = "Y"

        def mirror_obj(self, context, obj, mirror_ref=None, axis_index=0):
            replayed.append((obj.name, axis_index))
            return True

        def report(self, level, message):
            pass

    target = SimpleNamespace(name="target", select_get=lambda: True)
    context = SimpleNamespace(active_object=target, selected_objects=[target])

    Stub.find_object = staticmethod(lambda name: target if name == "target" else None)
    with patch("bonsai.tool.Ifc.get", return_value=None):
        MirrorElements._last_run = {
            "objects": ["target"],
            "reference": None,
            "axis_index": 0,
            "file": id(None),
        }
        Stub()._execute(context)

    assert replayed == [("target", 0), ("target", 1)], "the X run must be replayed before Y"
    MirrorElements._last_run = None


def test_a_fresh_invocation_does_not_undo_the_previous_run():
    from bonsai.bim.module.model.product import MirrorElements

    replayed = []

    class Stub:
        _execute = MirrorElements._execute
        revert_last_run = MirrorElements.revert_last_run
        resolve_selection = MirrorElements.__dict__["resolve_selection"]
        mirror_axis = "Y"

        def mirror_obj(self, context, obj, mirror_ref=None, axis_index=0):
            replayed.append((obj.name, axis_index))
            return True

        def report(self, level, message):
            pass

    target = SimpleNamespace(name="target", select_get=lambda: True)
    context = SimpleNamespace(active_object=target, selected_objects=[target])

    with patch("bonsai.tool.Ifc.get", return_value=None):
        MirrorElements._last_run = {"objects": ["target"], "reference": None, "axis_index": 0, "file": id(None)}
        stub = Stub()
        stub.is_fresh_invocation = True
        stub._execute(context)

    assert replayed == [("target", 1)], "a button or hotkey run must not undo anything"
    MirrorElements._last_run = None


def test_a_stale_run_from_another_project_is_not_replayed():
    from bonsai.bim.module.model.product import MirrorElements

    replayed = []

    class Stub:
        revert_last_run = MirrorElements.revert_last_run
        find_object = staticmethod(lambda name: None)

        def mirror_obj(self, context, obj, mirror_ref=None, axis_index=0):
            replayed.append(obj.name)
            return True

    MirrorElements._last_run = {"objects": ["target"], "reference": None, "axis_index": 0, "file": 12345}
    with patch("bonsai.tool.Ifc.get", return_value=None):
        Stub().revert_last_run(None)
    assert replayed == []
    MirrorElements._last_run = None


def test_a_reference_is_kept_even_when_its_selection_flag_lags():
    """Losing the reference falls back to an in-place mirror, which on a wall's Y is invisible.

    That silent fallback is what made a wall mirror look like it did nothing. With more than
    one object selected the active object is the reference, selection flag or not.
    """
    from bonsai.bim.module.model.product import MirrorElements

    target = SimpleNamespace(name="target", select_get=lambda: True)
    reference = SimpleNamespace(name="reference", select_get=lambda: False)
    context = SimpleNamespace(active_object=reference, selected_objects=[target, reference])

    objs, mirror_ref = MirrorElements.__dict__["resolve_selection"].__func__(context)
    assert [o.name for o in objs] == ["target"]
    assert mirror_ref is reference


def test_the_mirror_plane_ignores_an_active_object_that_is_not_selected():
    """Blender keeps an object active after deselecting it. It is not a visible mirror plane."""
    from bonsai.bim.module.model.product import MirrorElements

    target = SimpleNamespace(name="target", select_get=lambda: True)
    ghost = SimpleNamespace(name="ghost", select_get=lambda: False)
    context = SimpleNamespace(active_object=ghost, selected_objects=[target])

    seen = []

    class Stub:
        _execute = MirrorElements._execute
        revert_last_run = MirrorElements.revert_last_run
        resolve_selection = MirrorElements.__dict__["resolve_selection"]
        mirror_axis = "X"

        def mirror_obj(self, context, obj, mirror_ref=None, axis_index=0):
            seen.append((obj.name, mirror_ref.name if mirror_ref else None))
            return True

        def report(self, level, message):
            pass

    Stub()._execute(context)
    assert seen == [("target", None)], "a deselected active object must not become the mirror plane"


def test_get_mirror_axes_never_flips_more_than_one_axis():
    operator = _operator()
    obj = SimpleNamespace(matrix_world=Matrix.Identity(4))
    for angle in (0, 30, 45, 60, 90, 135):
        reference = SimpleNamespace(matrix_world=Matrix.Rotation(np.radians(angle), 4, "Z"))
        axes = operator.get_mirror_axes(obj, reference)
        assert sum(axes) == 1.0, f"{angle} degrees produced {axes}"


def test_get_mirror_axes_without_a_reference_uses_the_local_yz_plane():
    operator = _operator()
    obj = SimpleNamespace(matrix_world=Matrix.Identity(4))
    assert operator.get_mirror_axes(obj, None) == (1.0, 0.0, 0.0)


def test_get_mirror_axes_without_a_reference_honours_the_chosen_axis():
    operator = _operator()
    obj = SimpleNamespace(matrix_world=Matrix.Identity(4))
    assert operator.get_mirror_axes(obj, None, 1) == (0.0, 1.0, 0.0)
    assert operator.get_mirror_axes(obj, None, 2) == (0.0, 0.0, 1.0)


def test_get_mirror_axes_uses_the_chosen_axis_of_the_reference():
    """A reference turned 90 degrees about Z has its local Y pointing along world -X."""
    operator = _operator()
    obj = SimpleNamespace(matrix_world=Matrix.Identity(4))
    reference = SimpleNamespace(matrix_world=Matrix.Rotation(np.radians(90), 4, "Z"))
    assert operator.get_mirror_axes(obj, reference, 0) == (0.0, 1.0, 0.0)
    assert operator.get_mirror_axes(obj, reference, 1) == (1.0, 0.0, 0.0)
    assert operator.get_mirror_axes(obj, reference, 2) == (0.0, 0.0, 1.0)


def test_a_swept_solid_reports_that_it_cannot_be_inverted_along_z():
    """ShapeBuilder.mirror is 2D, so a Z mirror must be refused rather than half applied."""
    ifc_file, _, occurrences, _ = _mapped_type_file()
    element_type = ifc_file.by_type("IfcFurnitureType")[0]
    operator = _operator()

    with patch("bonsai.tool.Ifc.get", return_value=ifc_file):
        assert operator.find_uninvertible_items(element_type, (1.0, 0.0, 0.0)) == set()
        assert operator.find_uninvertible_items(element_type, (0.0, 1.0, 0.0)) == set()
        assert operator.find_uninvertible_items(element_type, (0.0, 0.0, 1.0)) == {"IfcExtrudedAreaSolid along Z"}


def test_find_uninvertible_items_refuses_shared_type_geometry_before_mutating():
    from bonsai.bim.module.model.product import SharedMappedGeometryError

    ifc_file, _, occurrences, solid = _mapped_type_file()
    coordinates_before = _profile_coordinates(solid)
    operator = _operator()

    with patch("bonsai.tool.Ifc.get", return_value=ifc_file):
        with pytest.raises(SharedMappedGeometryError):
            operator.find_uninvertible_items(occurrences[0], (1.0, 0.0, 0.0))


class TestDuplicateThenMirrorEndToEnd(NewFile):
    """#7991: IFC Duplicate a typed occurrence, select the duplicate with the original,
    then Mirror. The duplicate shares its body with the original via the type's
    IfcMappedItem (bonsai.core.root.copy_class -> type.map_type_representations), so this
    is the ``is_typed_occurrence`` / ``assign_inverted_type`` path exercised end to end
    through real ``bpy.ops`` calls rather than through the operator's bare methods, unlike
    the tests above.

    Also pins that ``bim.override_object_mirror`` -- what Ctrl+M actually runs -- reaches
    ``bim.mirror_elements`` rather than Blender's own ``transform.mirror``, which only
    negatively scales the Blender object and never touches the IFC representation."""

    TRIANGLE_2D = ((0.0, 0.0), (2.0, 0.0), (0.3, 1.0))
    DEPTH = 1.0

    def _make_triangle_representation(self, ifc_file, context):
        points = [ifc_file.create_entity("IfcCartesianPoint", Coordinates=c) for c in self.TRIANGLE_2D]
        profile = ifc_file.create_entity(
            "IfcArbitraryClosedProfileDef",
            ProfileType="AREA",
            OuterCurve=ifc_file.create_entity("IfcPolyline", Points=points + [points[0]]),
        )
        solid = ifc_file.create_entity(
            "IfcExtrudedAreaSolid",
            SweptArea=profile,
            Position=ifc_file.create_entity(
                "IfcAxis2Placement3D",
                Location=ifc_file.create_entity("IfcCartesianPoint", Coordinates=(0.0, 0.0, 0.0)),
            ),
            ExtrudedDirection=ifc_file.create_entity("IfcDirection", DirectionRatios=(0.0, 0.0, 1.0)),
            Depth=self.DEPTH,
        )
        shape_rep = ifc_file.create_entity(
            "IfcShapeRepresentation",
            ContextOfItems=context,
            RepresentationIdentifier="Body",
            RepresentationType="SweptSolid",
            Items=[solid],
        )
        return shape_rep, solid

    def _make_blender_mesh(self, name):
        import bmesh

        mesh = bpy.data.meshes.new(name)
        bm = bmesh.new()
        bottom = [bm.verts.new((x, y, 0.0)) for x, y in self.TRIANGLE_2D]
        top = [bm.verts.new((x, y, self.DEPTH)) for x, y in self.TRIANGLE_2D]
        bm.faces.new(bottom)
        bm.faces.new(list(reversed(top)))
        n = len(self.TRIANGLE_2D)
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new([bottom[i], bottom[j], top[j], top[i]])
        bm.to_mesh(mesh)
        bm.free()
        return mesh

    def _profile_points(self, entity_type):
        solid = entity_type.RepresentationMaps[0].MappedRepresentation.Items[0]
        return [tuple(round(c, 6) for c in p.Coordinates) for p in solid.SweptArea.OuterCurve.Points]

    def _setup_typed_occurrence(self):
        """A real IFC4 project with one asymmetric IfcFurnitureType and one occurrence
        typed to it via the production ``type.assign_type`` path, exactly like Bonsai's
        own "assign type" / "add type instance" authoring flow."""
        import ifcopenshell.api.root
        import ifcopenshell.api.spatial
        import ifcopenshell.util.representation

        import bonsai.core.type
        import bonsai.tool as tool

        bpy.ops.bim.create_project()
        ifc_file = tool.Ifc.get()
        storey = ifc_file.by_type("IfcBuildingStorey")[0]
        body_context = ifcopenshell.util.representation.get_context(ifc_file, "Model", "Body", "MODEL_VIEW")
        collection = tool.Ifc.get_object(storey).users_collection[0]

        type_element = ifcopenshell.api.root.create_entity(ifc_file, ifc_class="IfcFurnitureType", name="ChairType")
        type_shape_rep, _ = self._make_triangle_representation(ifc_file, body_context)
        rep_map = ifc_file.create_entity(
            "IfcRepresentationMap",
            MappingOrigin=ifc_file.create_entity(
                "IfcAxis2Placement3D", Location=ifc_file.create_entity("IfcCartesianPoint", Coordinates=(0.0, 0.0, 0.0))
            ),
            MappedRepresentation=type_shape_rep,
        )
        type_element.RepresentationMaps = [rep_map]

        type_mesh = self._make_blender_mesh("ChairType-mesh")
        type_obj = bpy.data.objects.new("ChairType", type_mesh)
        collection.objects.link(type_obj)
        tool.Ifc.link(type_element, type_obj)
        tool.Ifc.link(type_shape_rep, type_mesh)

        occurrence = ifcopenshell.api.root.create_entity(ifc_file, ifc_class="IfcFurniture", name="Chair-1")
        ifcopenshell.api.spatial.assign_container(ifc_file, products=[occurrence], relating_structure=storey)

        mesh = self._make_blender_mesh("Chair-1-mesh")
        obj = bpy.data.objects.new("Chair-1", mesh)
        collection.objects.link(obj)
        tool.Ifc.link(occurrence, obj)
        obj.matrix_world = Matrix.Identity(4)
        bpy.context.view_layer.update()

        bonsai.core.type.assign_type(tool.Ifc, tool.Model, tool.Type, occurrence, type_element)
        tool.Ifc.link(occurrence.Representation.Representations[0], mesh)

        return ifc_file, type_element, occurrence, obj

    def test_mirroring_a_duplicate_and_its_original_leaves_the_shared_type_untouched(self):
        import ifcopenshell.util.element

        import bonsai.tool as tool

        ifc_file, type_element, occurrence, obj = self._setup_typed_occurrence()
        profile_before = self._profile_points(type_element)

        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.bim.override_object_duplicate_move(is_interactive=False)
        bpy.context.view_layer.update()

        dup_obj = bpy.data.objects["Chair-1.001"]
        dup_element = tool.Ifc.get_entity(dup_obj)
        assert ifcopenshell.util.element.get_type(dup_element) == type_element
        dup_obj.location = (5.0, 0.0, 0.0)
        bpy.context.view_layer.update()

        bpy.ops.object.select_all(action="DESELECT")
        dup_obj.select_set(True)
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj  # last-selected: the mirror plane

        # This is exactly what Ctrl+M runs (bim.override_object_mirror -> bim.mirror_elements),
        # not Blender's own transform.mirror.
        result = bpy.ops.bim.override_object_mirror("INVOKE_DEFAULT")
        bpy.context.view_layer.update()

        assert result == {"FINISHED"}
        assert round(dup_obj.matrix_world.to_3x3().determinant(), 6) == 1.0, "a true mirror inverts geometry, not scale"

        dup_type_after = ifcopenshell.util.element.get_type(dup_element)
        assert dup_type_after != type_element, "the duplicate must get its own inverted type, not mirror the original"
        assert self._profile_points(type_element) == profile_before, "the shared type must not be corrupted"
        mirrored = self._profile_points(dup_type_after)
        assert mirrored == [(-x, y) for x, y in profile_before], "the duplicate's new type must be a true X mirror"

    def test_ctrl_m_keymap_reaches_the_real_mirror_operator(self):
        wm = bpy.context.window_manager
        km = wm.keyconfigs.addon.keymaps.get("Object Mode")
        assert km is not None
        matches = [
            kmi
            for kmi in km.keymap_items
            if kmi.idname == "bim.override_object_mirror" and kmi.type == "M" and kmi.ctrl
        ]
        assert len(matches) == 1, "Ctrl+M must be bound globally, not only inside a specific workspace tool"
