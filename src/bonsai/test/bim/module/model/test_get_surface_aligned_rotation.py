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

import math

import pytest
from mathutils import Matrix, Vector

from bonsai.bim.module.model.opening import get_surface_aligned_rotation

pytestmark = pytest.mark.model


def _old_flat_slab_rotation(voided_obj_matrix_world: Matrix) -> Matrix:
    return voided_obj_matrix_world.to_3x3().to_4x4() @ Matrix.Rotation(math.radians(-90), 4, "X")


def _matrices_are_close(a: Matrix, b: Matrix, tolerance: float = 1e-6) -> bool:
    return all(abs(a[i][j] - b[i][j]) < tolerance for i in range(3) for j in range(3))


def _is_proper_rotation(m3: Matrix, tolerance: float = 1e-6) -> bool:
    orthonormal = (m3 @ m3.transposed() - Matrix.Identity(3)).to_3x3()
    max_error = max(abs(orthonormal[i][j]) for i in range(3) for j in range(3))
    return max_error < tolerance and abs(m3.determinant() - 1.0) < tolerance


class TestFlatHost:
    def test_matches_old_formula_when_normal_is_local_z_and_host_unrotated(self):
        identity = Matrix.Identity(4)
        result = get_surface_aligned_rotation(identity, Vector((0.0, 0.0, 1.0)))
        assert _matrices_are_close(result, _old_flat_slab_rotation(identity))


class TestTiltedWholeObjectHost:
    @pytest.mark.parametrize("angle_degrees", [10, 30, 45])
    def test_matches_old_formula_for_various_tilts(self, angle_degrees):
        host_matrix = Matrix.Rotation(math.radians(angle_degrees), 4, "X")
        result = get_surface_aligned_rotation(host_matrix, Vector((0.0, 0.0, 1.0)))
        assert _matrices_are_close(result, _old_flat_slab_rotation(host_matrix))


class TestNegativeTiltIsUphillCorrected:
    def test_height_axis_always_points_uphill_regardless_of_tilt_sign(self):
        world_up = Vector((0.0, 0.0, 1.0))
        for angle_degrees in (10, 30, 45, -10, -30, -45):
            host_matrix = Matrix.Rotation(math.radians(angle_degrees), 4, "X")
            result = get_surface_aligned_rotation(host_matrix, Vector((0.0, 0.0, 1.0)))
            height_axis_world = result.to_3x3() @ Vector((0.0, 0.0, 1.0))
            assert height_axis_world.dot(world_up) >= -1e-9

    def test_old_formula_pointed_downhill_for_a_negative_tilt(self):
        world_up = Vector((0.0, 0.0, 1.0))
        host_matrix = Matrix.Rotation(math.radians(-20), 4, "X")
        old_height_axis_world = _old_flat_slab_rotation(host_matrix).to_3x3() @ Vector((0.0, 0.0, 1.0))
        assert old_height_axis_world.dot(world_up) < 0


class TestSlopedRoofFace:
    def test_thickness_axis_follows_the_face_normal(self):
        identity = Matrix.Identity(4)
        local_normal = Vector((0.0, -0.5, math.sqrt(3) / 2))
        result = get_surface_aligned_rotation(identity, local_normal)
        thickness_axis_world = result.to_3x3() @ Vector((0.0, 1.0, 0.0))
        assert (thickness_axis_world + local_normal.normalized()).length < 1e-6

    def test_is_a_proper_rotation(self):
        identity = Matrix.Identity(4)
        local_normal = Vector((0.3, -0.4, 0.8))
        assert _is_proper_rotation(get_surface_aligned_rotation(identity, local_normal).to_3x3())

    def test_does_not_blow_up_on_a_downward_facing_normal(self):
        identity = Matrix.Identity(4)
        result = get_surface_aligned_rotation(identity, Vector((0.0, 0.0, -1.0)))
        assert _is_proper_rotation(result.to_3x3())
        assert all(math.isfinite(v) for row in result for v in row)
