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

"""Where a door or window lands when it is dropped into an imported wall.

``get_wall_axis`` reads the wall run off ``bound_box`` min_x/max_x, so every
caller that positions a filling from it assumes the wall's placement X is the
wall reference line. Only an IfcMaterialLayerSetUsage makes that true. Across
a corpus of real models, hosts carrying a plain IfcMaterial, an
IfcMaterialConstituentSet or a bare IfcMaterialLayerSet produced doors rotated
by exactly the angle between the placement X and the wall run: 89.11, 84.74,
43.87, 21.44, 14.32 degrees. ``has_layer2_reference_line`` is the gate that
sends those hosts down the geometry-derived path instead."""

import ifcopenshell
import pytest

pytestmark = pytest.mark.model


def _wall_with_material(schema, material_builder):
    ifc = ifcopenshell.file(schema=schema)
    wall = ifc.create_entity("IfcWall", GlobalId=ifcopenshell.guid.new())
    material = material_builder(ifc)
    if material is not None:
        ifc.create_entity(
            "IfcRelAssociatesMaterial",
            GlobalId=ifcopenshell.guid.new(),
            RelatedObjects=[wall],
            RelatingMaterial=material,
        )
    return ifc, wall


def _layer_set(ifc, thickness):
    material = ifc.create_entity("IfcMaterial", Name="Concrete")
    layer = ifc.create_entity("IfcMaterialLayer", Material=material, LayerThickness=thickness)
    return ifc.create_entity("IfcMaterialLayerSet", MaterialLayers=[layer], LayerSetName="Wall")


def test_layer_set_usage_keeps_the_reference_line_path():
    from bonsai import tool

    def build(ifc):
        return ifc.create_entity(
            "IfcMaterialLayerSetUsage",
            ForLayerSet=_layer_set(ifc, 0.2),
            LayerSetDirection="AXIS2",
            DirectionSense="POSITIVE",
            OffsetFromReferenceLine=0.0,
        )

    _ifc, wall = _wall_with_material("IFC4", build)
    assert tool.Model.has_layer2_reference_line(wall) is True


def test_plain_material_has_no_reference_line():
    from bonsai import tool

    _ifc, wall = _wall_with_material("IFC4", lambda ifc: ifc.create_entity("IfcMaterial", Name="Concrete"))
    assert tool.Model.has_layer2_reference_line(wall) is False


def test_layer_set_without_usage_has_no_reference_line():
    from bonsai import tool

    _ifc, wall = _wall_with_material("IFC4", lambda ifc: _layer_set(ifc, 0.2))
    assert tool.Model.has_layer2_reference_line(wall) is False


def test_no_material_has_no_reference_line():
    from bonsai import tool

    _ifc, wall = _wall_with_material("IFC4", lambda ifc: None)
    assert tool.Model.has_layer2_reference_line(wall) is False


def test_axis3_usage_is_not_a_wall_reference_line():
    from bonsai import tool

    def build(ifc):
        return ifc.create_entity(
            "IfcMaterialLayerSetUsage",
            ForLayerSet=_layer_set(ifc, 0.2),
            LayerSetDirection="AXIS3",
            DirectionSense="POSITIVE",
            OffsetFromReferenceLine=0.0,
        )

    _ifc, wall = _wall_with_material("IFC4", build)
    assert tool.Model.has_layer2_reference_line(wall) is False


def test_zero_thickness_layer_set_has_no_usable_reference_line():
    from bonsai import tool

    def build(ifc):
        return ifc.create_entity(
            "IfcMaterialLayerSetUsage",
            ForLayerSet=_layer_set(ifc, 0.0),
            LayerSetDirection="AXIS2",
            DirectionSense="POSITIVE",
            OffsetFromReferenceLine=0.0,
        )

    _ifc, wall = _wall_with_material("IFC4", build)
    assert tool.Model.has_layer2_reference_line(wall) is False


def test_filling_rotation_puts_local_y_into_the_wall_and_z_up():
    from mathutils import Vector

    from bonsai import tool

    inward = Vector((0.0, 1.0, 0.0))
    matrix = tool.Model.get_filling_rotation(inward)
    assert (matrix.to_3x3() @ Vector((0.0, 1.0, 0.0)) - inward).length < 1e-6
    assert (matrix.to_3x3() @ Vector((0.0, 0.0, 1.0)) - Vector((0.0, 0.0, 1.0))).length < 1e-6
    assert matrix.to_3x3().determinant() == pytest.approx(1.0)


def test_filling_rotation_follows_a_skewed_wall_face():
    import math

    from mathutils import Vector

    from bonsai import tool

    inward = Vector((math.cos(math.radians(37.0)), math.sin(math.radians(37.0)), 0.0))
    matrix = tool.Model.get_filling_rotation(inward)
    local_x = matrix.to_3x3() @ Vector((1.0, 0.0, 0.0))
    assert abs(local_x.dot(inward)) < 1e-6


def _box_wall_obj(length=2.25, thickness=0.25, height=3.7):
    """A plain rectangular host, local X the run, local Y the thickness.

    Mirrors 220133_FR01_21_STR_ABI_Maquette Structure Existant.ifc wall
    0uYDwZ93n9Yv21PSEbL1im: a short host (2.25 m run, 0.25 m thick) whose end
    caps are ordinary, clickable faces, not slivers a user would never hit."""
    import bpy

    verts = [
        (0, 0, 0),
        (length, 0, 0),
        (length, thickness, 0),
        (0, thickness, 0),
        (0, 0, height),
        (length, 0, height),
        (length, thickness, height),
        (0, thickness, height),
    ]
    faces = [
        (0, 1, 2, 3),  # bottom
        (4, 7, 6, 5),  # top
        (0, 4, 5, 1),  # y=0 side (normal -Y)
        (1, 5, 6, 2),  # x=length end cap (normal +X)
        (2, 6, 7, 3),  # y=thickness side (normal +Y)
        (3, 7, 4, 0),  # x=0 end cap (normal -X)
    ]
    mesh = bpy.data.meshes.new("Wall")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new("Wall", mesh)
    obj.matrix_world.identity()
    # closest_point_on_mesh needs an evaluated mesh, which only exists once
    # the object is in the scene.
    bpy.context.scene.collection.objects.link(obj)
    bpy.context.view_layer.update()
    return obj


def test_wall_face_frame_stays_parallel_to_the_run_on_a_side_face():
    from mathutils import Vector

    from bonsai import tool

    obj = _box_wall_obj()
    result = tool.Model.get_wall_face_frame(obj, Vector((1.0, 0.0, 1.0)))
    assert result is not None
    inward, _point = result
    assert abs(inward.normalized().dot(Vector((1.0, 0.0, 0.0)))) < 1e-6


def test_wall_face_frame_stays_parallel_to_the_run_on_an_end_cap():
    """The clicked-face heuristic can't tell an end cap is a side of the wall
    (its own normal runs along the run axis, not across it), so it used to
    fall through to the caller's placement-X axis, which is exactly the wrong
    axis for a host with no AXIS2 reference line: on
    220133_FR01_21_STR_ABI_Maquette Structure Existant.ifc wall
    0uYDwZ93n9Yv21PSEbL1im that produced an 84.74 degree misoriented door
    whenever the click landed on one of its end caps. ``get_wall_face_frame``
    must resolve the end cap itself, using which side of the host's own
    centreline the click landed on, and stay parallel to the run either way."""
    from mathutils import Vector

    from bonsai import tool

    obj = _box_wall_obj()
    for end_x in (0.0, 2.25):
        result = tool.Model.get_wall_face_frame(obj, Vector((end_x, 0.1, 1.0)))
        assert result is not None, f"end cap at x={end_x} must not fall back to the placement axis"
        inward, _point = result
        assert (
            abs(inward.normalized().dot(Vector((1.0, 0.0, 0.0)))) < 1e-6
        ), "an end-cap click must still come out parallel to the wall run, not the host's placement X"


def test_wall_face_frame_picks_the_near_side_on_an_end_cap():
    from mathutils import Vector

    from bonsai import tool

    obj = _box_wall_obj()
    near_y0 = tool.Model.get_wall_face_frame(obj, Vector((0.0, 0.05, 1.0)))
    near_yT = tool.Model.get_wall_face_frame(obj, Vector((0.0, 0.2, 1.0)))
    assert near_y0 is not None and near_yT is not None
    # Clicking near the y=0 edge of the end cap should point away from the y=0
    # side (into the wall body, towards y=thickness), and vice versa.
    assert near_y0[0].dot(Vector((0.0, 1.0, 0.0))) > 0
    assert near_yT[0].dot(Vector((0.0, 1.0, 0.0))) < 0
