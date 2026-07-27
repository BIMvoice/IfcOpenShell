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

"""Voids on IFC4 Reference View files.

A Reference View exporter writes the host body already cut and gives the
matching IfcOpeningElement a Reference representation only, so the importer
skips the booleans. An opening Bonsai authors is different: it carries a Body
representation and nothing has cut the host yet. Treating both the same made
a door's hole show in the session and vanish on reload, measured on
Perspective générique.ifc (6.527 m3 uncut, 6.200 m3 cut) and on
DigitalHub_FM-ARC_v2.ifc."""

import ifcopenshell
import pytest

pytestmark = pytest.mark.geometry


def _host_with_opening(representation_identifier):
    ifc = ifcopenshell.file(schema="IFC4")
    context = ifc.create_entity(
        "IfcGeometricRepresentationContext",
        ContextType="Model",
        CoordinateSpaceDimension=3,
    )
    wall = ifc.create_entity("IfcWall", GlobalId=ifcopenshell.guid.new())
    opening = ifc.create_entity("IfcOpeningElement", GlobalId=ifcopenshell.guid.new())
    if representation_identifier is not None:
        representation = ifc.create_entity(
            "IfcShapeRepresentation",
            ContextOfItems=context,
            RepresentationIdentifier=representation_identifier,
            RepresentationType="Tessellation",
            Items=[],
        )
        opening.Representation = ifc.create_entity("IfcProductDefinitionShape", Representations=[representation])
    ifc.create_entity(
        "IfcRelVoidsElement",
        GlobalId=ifcopenshell.guid.new(),
        RelatingBuildingElement=wall,
        RelatedOpeningElement=opening,
    )
    return wall


def test_body_opening_still_has_to_be_subtracted():
    from bonsai.bim.import_ifc import IfcImporter

    assert IfcImporter.has_subtractive_void(_host_with_opening("Body")) is True


def test_reference_only_opening_was_already_baked_in():
    from bonsai.bim.import_ifc import IfcImporter

    assert IfcImporter.has_subtractive_void(_host_with_opening("Reference")) is False


def test_opening_without_geometry_was_already_baked_in():
    from bonsai.bim.import_ifc import IfcImporter

    assert IfcImporter.has_subtractive_void(_host_with_opening(None)) is False


def test_host_without_openings_is_not_affected():
    from bonsai.bim.import_ifc import IfcImporter

    ifc = ifcopenshell.file(schema="IFC4")
    wall = ifc.create_entity("IfcWall", GlobalId=ifcopenshell.guid.new())
    assert IfcImporter.has_subtractive_void(wall) is False
