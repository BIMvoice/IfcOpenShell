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
#
# Generated with the assistance of an AI coding tool.

import json

import numpy as np

import ifcopenshell
import ifcopenshell.api

# Importing a submodule named after a builtin shadows that builtin inside
# ifcopenshell.api, so serialise_settings must not rely on one.
import ifcopenshell.api.type  # noqa: F401

# serialise_settings runs on every API call in applications that register a
# wildcard listener, so its cost must not scale with the size of an argument.
# These bounds are deliberately looser than the module's own caps: the tests
# pin the algorithmic property, not the exact sample size.
BIG = 1000
BOUND = 50


class Loud:
    """Counts how many times it is stringified."""

    calls = 0

    def __repr__(self):
        Loud.calls += 1
        return "loud"


class TestSerialiseSettingsIsBounded:
    def setup_method(self):
        Loud.calls = 0

    def test_a_large_dict_setting_is_described_not_stringified(self):
        settings = {"accumulator": {i: Loud() for i in range(BIG)}}

        result = json.loads(ifcopenshell.api.serialise_settings(settings))

        assert Loud.calls <= BOUND
        assert result["accumulator"]["cast_type"] == "dict"
        assert result["accumulator"]["length"] == BIG
        assert len(result["accumulator"]["value"]) <= BOUND

    def test_a_large_list_setting_is_described_not_stringified(self):
        settings = {"items": [Loud() for _ in range(BIG)]}

        result = json.loads(ifcopenshell.api.serialise_settings(settings))

        assert Loud.calls <= BOUND
        assert result["items"]["length"] == BIG
        assert len(result["items"]["value"]) <= BOUND

    def test_a_large_set_setting_is_described_not_stringified(self):
        settings = {"items": {(i, Loud()) for i in range(BIG)}}

        result = json.loads(ifcopenshell.api.serialise_settings(settings))

        assert Loud.calls <= BOUND
        assert result["items"]["length"] == BIG

    def test_a_large_container_nested_in_a_sampled_item_is_not_stringified(self):
        settings = {"layers": {1: (Loud(), [Loud() for _ in range(BIG)])}}

        result = json.loads(ifcopenshell.api.serialise_settings(settings))

        assert Loud.calls <= BOUND
        assert result["layers"]["value"][0][1] == {"cast_type": "tuple", "length": 2}

    def test_a_long_scalar_setting_is_truncated(self):
        settings = {"query": "x" * 100000}

        result = json.loads(ifcopenshell.api.serialise_settings(settings))

        assert len(result["query"]) <= 10000

    def test_a_large_entity_list_setting_is_sampled(self):
        ifc = ifcopenshell.file()
        walls = [ifc.createIfcWall() for _ in range(BIG)]

        result = json.loads(ifcopenshell.api.serialise_settings({"products": walls}))

        assert result["products"]["length"] == BIG
        assert len(result["products"]["value"]) <= BOUND
        assert result["products"]["value"][0]["cast_type"] == "entity_instance"

    def test_the_documented_caps_are_exported(self):
        assert ifcopenshell.api.MAX_SERIALISED_ITEMS <= BOUND
        assert ifcopenshell.api.MAX_SERIALISED_CHARS <= 10000


class TestSerialiseSettingsStillDescribesSmallSettings:
    def test_an_entity_instance_setting(self):
        ifc = ifcopenshell.file()
        wall = ifc.createIfcWall(Name="Wall")

        result = json.loads(ifcopenshell.api.serialise_settings({"product": wall}))

        assert result["product"] == {"cast_type": "entity_instance", "value": wall.id(), "Name": "Wall"}

    def test_a_small_entity_list_setting(self):
        ifc = ifcopenshell.file()
        wall = ifc.createIfcWall(Name="Wall")

        result = json.loads(ifcopenshell.api.serialise_settings({"products": [wall]}))

        assert result["products"]["value"] == [{"cast_type": "entity_instance", "value": wall.id(), "Name": "Wall"}]

    def test_an_ndarray_setting(self):
        result = json.loads(ifcopenshell.api.serialise_settings({"matrix": np.eye(2)}))

        assert result["matrix"] == {"cast_type": "ndarray", "value": [[1.0, 0.0], [0.0, 1.0]]}

    def test_a_scalar_setting(self):
        result = json.loads(ifcopenshell.api.serialise_settings({"is_si": True, "name": "Foo"}))

        assert result == {"is_si": "True", "name": "Foo"}
