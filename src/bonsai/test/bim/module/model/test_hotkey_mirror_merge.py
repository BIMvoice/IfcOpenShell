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

"""#7991: Shift+M is shared between Merge and Mirror inside a Bonsai authoring tool
(``BimTool.bl_keymap``, workspace.py). An active LAYER2 element (wall, railing) used to force
a merge attempt and report an error outright whenever the rest of the selection did not also
qualify -- even when the user was pressing the "Mirror" button in the Align panel, not "Merge"
in Operations, both of which dispatch through the same ``bim.hotkey`` hotkey="S_M". Only a
selection that actually qualifies for a merge should take that path; anything else must fall
back to Mirror, exactly like a non-LAYER2 selection already does.

Also pins that Ctrl+M is untouched by any of this: ``BimTool.bl_keymap`` binds Shift+M only,
so it can never be intercepted by a Bonsai authoring tool's own keymap regardless of which
tool is active."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.model


def _stub():
    from bonsai.bim.module.model.workspace import Hotkey

    stub = SimpleNamespace()
    stub.hotkey_S_M = Hotkey.__dict__["hotkey_S_M"].__get__(stub)
    stub.is_layer2_merge_selection = Hotkey.is_layer2_merge_selection
    stub.reports = []
    stub.report = lambda level, message: stub.reports.append((level, message))
    return stub


def _wall(name):
    return SimpleNamespace(name=name)


def _fake_bpy(selection):
    """``bpy.context.selected_objects`` is a real bpy_struct property and cannot be patched
    in place; the whole ``bpy`` name workspace.py sees is replaced instead."""
    merge_wall = MagicMock()
    mirror_elements = MagicMock()
    fake = SimpleNamespace(
        context=SimpleNamespace(selected_objects=selection),
        ops=SimpleNamespace(bim=SimpleNamespace(merge_wall=merge_wall, mirror_elements=mirror_elements)),
    )
    return fake, merge_wall, mirror_elements


def test_two_matching_layer2_objects_still_merge():
    stub = _stub()
    stub.active_material_usage = "LAYER2"
    fake_bpy, merge_wall, mirror_elements = _fake_bpy([_wall("Wall1"), _wall("Wall2")])

    with (
        patch("bonsai.bim.module.model.workspace.bpy", fake_bpy),
        patch("bonsai.bim.module.model.workspace.tool.Ifc.get_entity", side_effect=lambda o: o),
        patch("bonsai.bim.module.model.workspace.tool.Model.get_usage_type", return_value="LAYER2"),
    ):
        stub.hotkey_S_M()

    merge_wall.assert_called_once()
    mirror_elements.assert_not_called()
    assert stub.reports == []


def test_active_layer2_with_a_non_layer2_selection_falls_back_to_mirror():
    """The bug: a wall was active (e.g. clicked last as the mirror plane) alongside slabs and
    a beam. The old code saw LAYER2 and refused with a merge-specific error instead of
    mirroring, exactly what made #7991 look "tool dependent"."""
    stub = _stub()
    stub.active_material_usage = "LAYER2"
    fake_bpy, merge_wall, mirror_elements = _fake_bpy([_wall("Wall1"), _wall("Slab1"), _wall("Beam1")])

    with (
        patch("bonsai.bim.module.model.workspace.bpy", fake_bpy),
        patch("bonsai.bim.module.model.workspace.tool.Ifc.get_entity", side_effect=lambda o: o),
        patch("bonsai.bim.module.model.workspace.tool.Model.get_usage_type", return_value="LAYER2"),
    ):
        stub.hotkey_S_M()

    merge_wall.assert_not_called()
    mirror_elements.assert_called_once()
    assert not any(level == {"ERROR"} for level, _ in stub.reports)


def test_active_layer2_with_two_selected_but_one_not_layer2_falls_back_to_mirror():
    """Exactly two objects selected, active is LAYER2, but the other one is not -- still not
    a valid merge pair, so this must mirror rather than error."""
    stub = _stub()
    stub.active_material_usage = "LAYER2"
    fake_bpy, merge_wall, mirror_elements = _fake_bpy([_wall("Wall1"), _wall("Slab1")])

    def usage_type(element):
        return "LAYER2" if element.name == "Wall1" else "LAYER3"

    with (
        patch("bonsai.bim.module.model.workspace.bpy", fake_bpy),
        patch("bonsai.bim.module.model.workspace.tool.Ifc.get_entity", side_effect=lambda o: o),
        patch("bonsai.bim.module.model.workspace.tool.Model.get_usage_type", side_effect=usage_type),
    ):
        stub.hotkey_S_M()

    merge_wall.assert_not_called()
    mirror_elements.assert_called_once()


def test_active_layer2_alone_still_reports_an_error_not_a_silent_no_op():
    """A single LAYER2 object selected qualifies for neither a merge nor a mirror (which
    needs a second object as the plane), so this must still report, not silently do nothing."""
    stub = _stub()
    stub.active_material_usage = "LAYER2"
    fake_bpy, merge_wall, mirror_elements = _fake_bpy([_wall("Wall1")])

    with (
        patch("bonsai.bim.module.model.workspace.bpy", fake_bpy),
        patch("bonsai.bim.module.model.workspace.tool.Ifc.get_entity", side_effect=lambda o: o),
        patch("bonsai.bim.module.model.workspace.tool.Model.get_usage_type", return_value="LAYER2"),
    ):
        stub.hotkey_S_M()

    merge_wall.assert_not_called()
    mirror_elements.assert_not_called()
    assert stub.reports and stub.reports[0][0] == {"ERROR"}


def test_ctrl_m_is_not_in_any_bonsai_tool_keymap():
    """Every Bonsai authoring tool (Wall, Slab, Beam, ...) shares ``BimTool.bl_keymap``
    (workspace.py) unmodified: none of them redefine it. That keymap binds Shift+M, never
    Ctrl+M, so a Bonsai tool's own keymap can never intercept Ctrl+M regardless of which
    tool is active -- Ctrl+M always falls through to the addon-global ``Object Mode``
    keymap where ``bim.override_object_mirror`` lives (module/model/__init__.py)."""
    from bonsai.bim.module.model import workspace

    ctrl_m_bindings = [
        item for item in workspace.BimTool.bl_keymap if item[1].get("type") == "M" and item[1].get("ctrl")
    ]
    assert ctrl_m_bindings == []

    shift_m_bindings = [
        item for item in workspace.BimTool.bl_keymap if item[1].get("type") == "M" and item[1].get("shift")
    ]
    assert len(shift_m_bindings) == 1
    assert shift_m_bindings[0][0] == "bim.hotkey"
