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

"""Regression guard for #9001: the AXIS1 bisect plane must carry the layer
offset on the same axis it walks along (X), not on Z. A point/normal pair
whose offset sits off-axis silently drops OffsetFromReferenceLine."""

import types
from types import SimpleNamespace

import bpy
import pytest
from mathutils import Vector

from bonsai.bim.module.drawing.operator import CreateDrawing as subject

pytestmark = pytest.mark.drawing


@pytest.fixture(autouse=True)
def _require_real_bpy():
    if not isinstance(bpy, types.ModuleType) or hasattr(bpy, "_mock_name"):
        pytest.skip("requires real Blender (bpy is mocked or absent)")


def usage(direction):
    return SimpleNamespace(LayerSetDirection=direction)


def test_axis1_offset_lands_on_x_not_z():
    co, no = subject.get_material_layer_bisect_axes(usage("AXIS1"), 0.1705, Vector((0.0, 0.0, 1.0)))
    assert co == Vector((0.1705, 0.0, 0.0))
    assert no == Vector((1.0, 0.0, 0.0))


def test_axis2_offset_lands_on_y():
    co, no = subject.get_material_layer_bisect_axes(usage("AXIS2"), 0.1705, Vector((0.0, 0.0, 1.0)))
    assert co == Vector((0.0, 0.1705, 0.0))
    assert no == Vector((0.0, 0.0, 1.0)).cross(Vector((1.0, 0.0, 0.0)))


def test_axis3_offset_lands_on_z():
    co, no = subject.get_material_layer_bisect_axes(usage("AXIS3"), 0.1705, Vector((0.0, 0.0, 1.0)))
    assert co == Vector((0.0, 0.0, 0.1705))
    assert no == Vector((0.0, 0.0, 1.0))


def test_no_usage_falls_back_to_extrusion_vector():
    extrusion_vector = Vector((0.0, 0.0, 1.0))
    co, no = subject.get_material_layer_bisect_axes(None, 0.5, extrusion_vector)
    assert co == Vector((0.0, 0.0, 0.5))
    assert no == extrusion_vector


@pytest.mark.parametrize("direction", ["AXIS1", "AXIS2", "AXIS3"])
def test_offset_always_lands_on_the_axis_the_plane_walks_along(direction):
    """A zero offset must produce a plane through the origin; a non-zero offset
    must actually move it. Before the fix, AXIS1's co carried the offset on Z
    while no walked along X, so co.dot(no) stayed 0 regardless of offset."""
    extrusion_vector = Vector((0.0, 0.0, 1.0))
    co_zero, no = subject.get_material_layer_bisect_axes(usage(direction), 0.0, extrusion_vector)
    co_offset, _ = subject.get_material_layer_bisect_axes(usage(direction), 0.1705, extrusion_vector)
    assert co_zero.dot(no) == pytest.approx(0.0)
    assert co_offset.dot(no) == pytest.approx(0.1705)
