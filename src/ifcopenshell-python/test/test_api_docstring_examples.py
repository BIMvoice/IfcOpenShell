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

# This file was generated with the assistance of an AI coding tool.

import ast
import importlib
import re
import textwrap
from pathlib import Path

import pytest

import ifcopenshell
import ifcopenshell.api
import ifcopenshell.api.owner.settings as owner_settings
import ifcopenshell.api.root

API_DIR = Path(ifcopenshell.api.__file__).parent


def extract_blocks(docstring):
    blocks = []
    lines = docstring.expandtabs().split("\n")
    in_examples = False
    i = 0
    while i < len(lines):
        if re.match(r"\s*Examples?\s*:?\s*$", lines[i]):
            in_examples = True
        directive = re.match(r"(\s*)\.\. code::\s*python\s*$", lines[i])
        if directive and in_examples:
            indent = len(directive.group(1))
            body = []
            i += 1
            while i < len(lines) and (not lines[i].strip() or len(lines[i]) - len(lines[i].lstrip()) > indent):
                body.append(lines[i])
                i += 1
            blocks.append(textwrap.dedent("\n".join(body)).strip("\n"))
        else:
            i += 1
    return blocks


def collect_examples():
    params = []
    for path in sorted(API_DIR.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        module = ".".join(path.relative_to(API_DIR).with_suffix("").parts)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and (docstring := ast.get_docstring(node, clean=False)):
                for index, code in enumerate(extract_blocks(docstring)):
                    marks = []
                    if "/path/to" in code:
                        marks.append(pytest.mark.skip(reason="placeholder path"))
                    params.append(pytest.param(code, id=f"{module}.{node.name}[{index}]", marks=marks))
    return params


@pytest.mark.parametrize("code", collect_examples())
def test_api_docstring_example_runs(code):
    model = ifcopenshell.file()
    ifcopenshell.api.root.create_entity(model, ifc_class="IfcProject")
    for kind, name in set(re.findall(r"ifcopenshell\.(api|util)\.(\w+)", code)):
        importlib.import_module(f"ifcopenshell.{kind}.{name}")
    saved = owner_settings.get_user, owner_settings.get_application
    try:
        exec(compile(code, "<docstring example>", "exec"), {"ifcopenshell": ifcopenshell, "model": model})
    finally:
        owner_settings.get_user, owner_settings.get_application = saved
