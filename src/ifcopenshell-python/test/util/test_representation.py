# IfcOpenShell - IFC toolkit and geometry engine
# Copyright (C) 2026 Dion Moult <dion@thinkmoult.com>
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

import ifcopenshell.util.representation as subject
import test.bootstrap


class TestGetPartOfProduct(test.bootstrap.IFC4):
    def test_returns_representation_for_a_product(self):
        context = self.file.createIfcGeometricRepresentationSubContext()
        shape = self.file.createIfcShapeRepresentation(ContextOfItems=context)
        element = self.file.createIfcWall(
            Representation=self.file.create_entity("IfcProductDefinitionShape", Representations=[shape])
        )
        assert subject.get_part_of_product(element, context) == element.Representation

    def test_returns_none_for_a_type_product_with_no_representation_maps(self):
        context = self.file.createIfcGeometricRepresentationSubContext()
        type = self.file.createIfcWallType()
        assert type.RepresentationMaps is None
        assert subject.get_part_of_product(type, context) is None

    def test_returns_matching_representation_map_for_a_type_product(self):
        context = self.file.createIfcGeometricRepresentationSubContext()
        map = self.file.createIfcRepresentationMap(
            MappedRepresentation=self.file.createIfcShapeRepresentation(ContextOfItems=context)
        )
        type = self.file.createIfcWallType(RepresentationMaps=[map])
        assert subject.get_part_of_product(type, context) == map

    def test_returns_none_when_no_representation_map_matches_the_context(self):
        context = self.file.createIfcGeometricRepresentationSubContext()
        other_context = self.file.createIfcGeometricRepresentationSubContext()
        map = self.file.createIfcRepresentationMap(
            MappedRepresentation=self.file.createIfcShapeRepresentation(ContextOfItems=other_context)
        )
        type = self.file.createIfcWallType(RepresentationMaps=[map])
        assert subject.get_part_of_product(type, context) is None


class TestGetPartOfProductIFC2X3(test.bootstrap.IFC2X3):
    def test_returns_none_for_a_type_product_with_no_representation_maps(self):
        context = self.file.createIfcGeometricRepresentationSubContext()
        type = self.file.createIfcWallType()
        assert type.RepresentationMaps is None
        assert subject.get_part_of_product(type, context) is None

    def test_returns_none_for_a_type_product_even_with_matching_representation_maps(self):
        # As documented, get_part_of_product always returns None for IFC2X3
        # type products, since IFC2X3 does not fully support shape aspects.
        context = self.file.createIfcGeometricRepresentationSubContext()
        map = self.file.createIfcRepresentationMap(
            MappedRepresentation=self.file.createIfcShapeRepresentation(ContextOfItems=context)
        )
        type = self.file.createIfcWallType(RepresentationMaps=[map])
        assert subject.get_part_of_product(type, context) is None


class TestGetMissingOpeningContextIds(test.bootstrap.IFC4):
    def add_opening(self, wall, context, identifier="Body"):
        opening = self.file.createIfcOpeningElement(
            Representation=self.file.create_entity(
                "IfcProductDefinitionShape",
                Representations=[
                    self.file.createIfcShapeRepresentation(ContextOfItems=context, RepresentationIdentifier=identifier)
                ],
            )
        )
        self.file.createIfcRelVoidsElement(RelatingBuildingElement=wall, RelatedOpeningElement=opening)
        return opening

    def test_returns_nothing_when_the_opening_shares_the_host_context(self):
        body = self.file.createIfcGeometricRepresentationSubContext()
        wall = self.file.createIfcWall()
        self.add_opening(wall, body)
        assert subject.get_missing_opening_context_ids(self.file, [body.id()]) == set()
        assert subject.get_missing_opening_context_ids(self.file, [body.id()], [wall]) == set()

    def test_returns_the_opening_context_when_it_is_not_allowed(self):
        body = self.file.createIfcGeometricRepresentationSubContext()
        other = self.file.createIfcGeometricRepresentationSubContext()
        wall = self.file.createIfcWall()
        self.add_opening(wall, other)
        assert subject.get_missing_opening_context_ids(self.file, [body.id()]) == {other.id()}
        assert subject.get_missing_opening_context_ids(self.file, [body.id()], [wall]) == {other.id()}

    def test_prefers_the_body_representation_context(self):
        body = self.file.createIfcGeometricRepresentationSubContext()
        other = self.file.createIfcGeometricRepresentationSubContext()
        box = self.file.createIfcGeometricRepresentationSubContext()
        wall = self.file.createIfcWall()
        opening = self.add_opening(wall, other)
        opening.Representation.Representations = list(opening.Representation.Representations) + [
            self.file.createIfcShapeRepresentation(ContextOfItems=box, RepresentationIdentifier="Box")
        ]
        assert subject.get_missing_opening_context_ids(self.file, [body.id()]) == {other.id()}

    def test_ignores_openings_of_other_elements_when_elements_are_given(self):
        body = self.file.createIfcGeometricRepresentationSubContext()
        other = self.file.createIfcGeometricRepresentationSubContext()
        wall = self.file.createIfcWall()
        unrelated = self.file.createIfcWall()
        self.add_opening(unrelated, other)
        assert subject.get_missing_opening_context_ids(self.file, [body.id()], [wall]) == set()

    def test_includes_openings_inherited_from_an_aggregate(self):
        body = self.file.createIfcGeometricRepresentationSubContext()
        other = self.file.createIfcGeometricRepresentationSubContext()
        aggregate = self.file.createIfcElementAssembly()
        part = self.file.createIfcWall()
        self.file.createIfcRelAggregates(RelatingObject=aggregate, RelatedObjects=[part])
        self.add_opening(aggregate, other)
        assert subject.get_missing_opening_context_ids(self.file, [body.id()], [part]) == {other.id()}

    def test_ignores_openings_without_a_representation(self):
        body = self.file.createIfcGeometricRepresentationSubContext()
        wall = self.file.createIfcWall()
        opening = self.file.createIfcOpeningElement()
        self.file.createIfcRelVoidsElement(RelatingBuildingElement=wall, RelatedOpeningElement=opening)
        assert subject.get_missing_opening_context_ids(self.file, [body.id()]) == set()


class TestGetMissingOpeningContextIdsIFC2X3(test.bootstrap.IFC2X3):
    def test_returns_the_opening_context_when_it_is_not_allowed(self):
        body = self.file.createIfcGeometricRepresentationContext()
        other = self.file.createIfcGeometricRepresentationContext()
        wall = self.file.createIfcWall()
        opening = self.file.createIfcOpeningElement(
            Representation=self.file.create_entity(
                "IfcProductDefinitionShape",
                Representations=[
                    self.file.createIfcShapeRepresentation(ContextOfItems=other, RepresentationIdentifier="Body")
                ],
            )
        )
        self.file.createIfcRelVoidsElement(RelatingBuildingElement=wall, RelatedOpeningElement=opening)
        assert subject.get_missing_opening_context_ids(self.file, [body.id()]) == {other.id()}
        assert subject.get_missing_opening_context_ids(self.file, [body.id()], [wall]) == {other.id()}
