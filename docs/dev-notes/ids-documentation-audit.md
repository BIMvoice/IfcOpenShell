# IDS User Manual audit: gaps found via real ifctester defects

Scope: `Documentation/UserManual/` and `Documentation/ImplementersDocumentation/` on
`buildingSMART/IDS` at `development` (fetched fresh via `gh api ...?ref=development`),
cross-checked against `Schema/ids.xsd` (also `development`) and against
`src/ifctester/ifctester/facet.py` in this repository.

Method: for each of five ifctester verdict bugs found and fixed in the last week
(#9203, #9205, #9142, #9188, #9189, all in `IfcOpenShell/IfcOpenShell`), the User
Manual and Implementers Documentation were searched for the rule the buggy code
got wrong. Every quote below was fetched directly from the `development` branch
during this audit; every code claim was read directly from `facet.py` in this
worktree, and one schema claim (totalDigits/fractionDigits/whiteSpace legality)
was checked empirically with `xmlschema` 4.3.2 against the real `ids.xsd`, not
argued from reading the XSD by eye.

Ranked by consequence, false passes first.

---

## Finding 1 (highest consequence, false pass): PartOf's `predefinedType` parameter is not documented at all

**What the docs say.** `Documentation/UserManual/partof-facet.md`'s Parameters table (lines 17-23)
lists exactly two parameters for PartOf:

> | **Entity** | Yes | An entity facet | ... |
> | **Relation** | No | string | ... |

There is no `predefinedType` row. The word "predefinedType" does not appear
anywhere in `partof-facet.md`.

Compare `entity-facet.md`, which gives `predefinedType` extensive treatment: a
dedicated "IFC Predefined Types" section (lines 42-81) with a five-step decision
procedure for how `USERDEFINED` should be resolved:

> ELSE IF: the object has a `PredefinedType` with a value `USERDEFINED` -> The
> value of the predefined type is in the `ObjectType` attribute of that object.

and a worked examples table (lines 66-71) that explicitly covers querying for
the literal string `USERDEFINED`:

> | IFCWALL | USERDEFINED | IFCWALL | USERDEFINED | - | pass |
> | IFCWALL | USERDEFINED | IFCWALL | USERDEFINED | FOO | pass |

Both rows show that asking for `predefinedType="USERDEFINED"` must match the
*raw* IFC `PredefinedType` attribute literally, not the substituted `ObjectType`
text used for every other predefined type value. This literal-match behaviour
is deliberate and agreed by the maintainers: issue
[buildingSMART/IDS#306](https://github.com/buildingSMART/IDS/issues/306) records
"We agreed that the USERDEFINED predefined type should be a valid match", and
issue [#178](https://github.com/buildingSMART/IDS/issues/178) has Dion Moult
confirming the same design in the Entity facet's own thread.

**What the schema does.** `Schema/ids.xsd` lines 51-56 define PartOf's nested
`entity` element with the *same* `entityType` complex type Entity itself uses:

```xml
<xs:complexType name="partOfType">
    <xs:sequence>
        <xs:element name="entity" type="ids:entityType" minOccurs="1"/>
    </xs:sequence>
    <xs:attribute name="relation" type="ids:relations" use="optional" />
</xs:complexType>
```

and `entityType` (lines 32-37) includes `predefinedType`. So a PartOf
specification with `predefinedType="USERDEFINED"` on its nested entity is
schema-legal, and the buildingSMART test suite already contains fixtures using
`.USERDEFINED.` inside `partof` test cases (e.g.
`Documentation/ImplementersDocumentation/TestCases/partof/pass-a_group_predefined_type_must_match_exactly_2_2.ifc`,
which encodes `IFCINVENTORY(...,'BUNNY',.USERDEFINED.,...)`), but every one of
those fixtures queries a *substituted* value (`BUNNY`), never the literal string
`USERDEFINED`. I enumerated all 24 files under
`Documentation/ImplementersDocumentation/TestCases/partof/`: none has "userdefined"
in its name, and none of the six `predefinedType`-related test cases queries
`predefinedType="USERDEFINED"` literally. The Entity facet, by contrast, got a
dedicated test case for exactly this
(`Documentation/ImplementersDocumentation/TestCases/entity/pass-userdefined_predefined_types_may_be_specified.ids`,
added by PR [#307](https://github.com/buildingSMART/IDS/pull/307) closing issue #306)
that PartOf never received.

**What ifctester actually does.** `src/ifctester/ifctester/facet.py` line 232-260,
`Entity.__call__`:

```python
if self.predefinedType == "USERDEFINED":
    is_pass = ifcopenshell.util.element.is_userdefined_type(inst)
    ...
else:
    predefined_type = ifcopenshell.util.element.get_predefined_type(inst)
    is_pass = predefined_type == self.predefinedType
```

Entity special-cases the literal `USERDEFINED` query, exactly matching the
`entity-facet.md` examples table. `PartOf.__call__` (lines 506-624) never does
this, at any of its six relation branches (aggregate: line 538, group: line 562,
contained-in: line 576, nest: line 592, voids/fills: line 618, no-relation
ancestor walk: line 516). Every site instead does:

```python
predefined_type = ifcopenshell.util.element.get_predefined_type(parent)
if predefined_type == self.predefinedType:
    is_pass = True
```

`get_predefined_type()` never returns the literal string `"USERDEFINED"`; it
substitutes the custom `ObjectType`/`ElementType`/`ProcessType` text instead.
So `predefined_type == "USERDEFINED"` is always false when the IDS query is
literally `predefinedType="USERDEFINED"`.

**Consequence, verified by running it (PR #9203).** IFC4, an `IfcSpace`
containing an `IfcWall`, checked with
`PartOf(predefinedType="USERDEFINED", cardinality="prohibited")`:

- Before the fix: PASS, reason `PROHIBITED`.
- Correct: FAIL. The wall genuinely sits in a userdefined-type space, which the
  prohibition forbids.

A model that violates a prohibition is reported compliant. This is the false
pass this audit is looking for.

**Why the docs plausibly let this happen.** The USERDEFINED substitution rule
is fully documented, but only on the Entity facet's own page. partof-facet.md's
"Entity" parameter row says only "An entity facet", with no pointer to
entity-facet.md's predefined-type section and no restatement of the rule.
Someone implementing PartOf's predefined-type comparison by re-deriving it
independently at each of six call sites (as ifctester did) has no local text
telling them the literal-`USERDEFINED` special case applies here too.

**Proposed wording**, for `partof-facet.md`'s Parameters table:

> | **PredefinedType** (`predefinedType`) | No | A predefined type for the
> nested Entity facet, following the same interpretation (including the
> `USERDEFINED` substitution rule) as the [Entity Facet](entity-facet.md#ifc-predefined-types). |

---

## Finding 2 (false pass): the manual never states that `IFCLOGICAL` "UNKNOWN" is a present value, not an absent one

**What the docs say.** `attribute-facet.md`'s Applicability table (line 37) is
the only place the manual defines what "populated" means for any attribute:

> Description | - | Applies to all entities having a *Description* filled in
> (not Null or missing).

No facet page, and no Implementers document, ever discusses `IFCLOGICAL`'s
three-valued nature (`TRUE`/`FALSE`/`UNKNOWN`) or states whether a value that is
literally named `UNKNOWN` counts as "not Null". I searched
`attribute-facet.md`, `property-facet.md`, `specifications.md`,
`Implementers/DataTypes.md` and `Implementers/developer-guide.md` for "logical"
or "UNKNOWN": the only hit is `Implementers/DataTypes.md` line 201, a single
table row mapping `IFCLOGICAL` to its XML base type (`xs:string`), with no
discussion of its semantics.

**What ifctester actually does.** `facet.py` line 349, inside
`Attribute.__call__`'s emptiness check:

```python
if attribute_type == "LOGICAL" and value == "UNKNOWN":
    is_empty = True
```

A present, explicitly-set `IFCLOGICAL` value of `UNKNOWN` is treated identically
to a genuinely absent attribute.

**Consequence, verified by running it (PR #9205, defect 2).**
`IfcPresentationLayerWithStyle.LayerOn = "UNKNOWN"`, a real, present value:

- `cardinality="required"`: before, FAIL (`FALSEY`); correct is PASS.
- `cardinality="prohibited"`: before, **PASS**; correct is FAIL.

The prohibited case is the false pass: a present value reported as absent means
a prohibition is silently satisfied, and a non-compliant model passes.

**This is a recurring failure, not a one-off.** The identical bug was already
found and fixed once before in the sibling `Property` facet
(referenced in #9205's body as "already-fixed #8161"); `Attribute` repeated it
independently. Two independent implementers of two different facets in the same
codebase made the same mistake, which is itself evidence the manual's silence
on this point is a real gap rather than a one-off coding slip. It also matches
public reports: buildingSMART/IDS issue
[#353](https://github.com/buildingSMART/IDS/issues/353), "fail-a_logical_unknown_is_considered_false_and_will_not_pass",
argues the opposite direction of the same ambiguity: that an official test
case's expected FAIL verdict for a LOGICAL UNKNOWN value is itself wrong,
because "Value is not specified, and any non-empty value must be allowed."
That issue is about a different requirement shape (value unspecified, not
cardinality=prohibited), but it is the same root ambiguity: is `UNKNOWN` a
value or an absence.

**Proposed wording**, for `attribute-facet.md`'s Applicability section, after
line 37:

> Note: for `IFCLOGICAL` attributes, the value `UNKNOWN` is a present, non-null
> value (one of the three literal values of the type), not an absence. An
> attribute explicitly set to `UNKNOWN` satisfies "filled in" the same way
> `TRUE` or `FALSE` would.

The same sentence would fit `property-facet.md`'s applicability section, since
`IFCLOGICAL` properties have the identical ambiguity (and did, in the earlier,
already-fixed #8161).

---

## Finding 3 (false pass, but see the caveat): `totalDigits`, `fractionDigits` and `whiteSpace` are structurally legal, and the manual's own documents disagree about whether they should work

**What `restrictions.md` says.** Nothing. It lists exactly four restriction
kinds (Enumeration, Pattern, Bounds, Length) and never mentions `totalDigits`,
`fractionDigits`, or `whiteSpace`. Verified: `grep` for all six literal XSD
facet names (`minInclusive`, `maxInclusive`, `minExclusive`, `maxExclusive`,
`minLength`, `maxLength`) plus `totalDigits`, `fractionDigits`, `whiteSpace`
against the fetched `restrictions.md` returns zero matches for all nine.

**What `Implementers/developer-guide.md` says, and this is the important part.**
Line 52-55, under a heading literally titled "Restrictions":

> XSD also includes a **Total Digits** and a **Fraction Digits** restriction.
> These will not be supported in IDS as they have limited utility.
> For the complete list of valid restrictions, see the [XML base types table](DataTypes.md#XML-base-types).

This is not silence, it is an explicit statement that these two facets should
**not** be supported. This directly qualifies the framing this audit started
from (that they are merely "undocumented"): one of the two User Manual document
sets does address them, and says implementers should leave them out.

**What the schema actually permits, checked empirically, not argued.** I built
a minimal IDS document with an `Attribute` requirement carrying
`<xs:restriction base="xs:string"><xs:totalDigits value="3"/><xs:fractionDigits value="2"/><xs:whiteSpace value="collapse"/></xs:restriction>`
and validated it against the real `ids.xsd` (fetched from `development`) with
`xmlschema` 4.3.2 (the same library ifctester itself uses):

```
VALID: totalDigits + fractionDigits + whiteSpace all accepted by ids.xsd
```

`ids.xsd` line 42 embeds the generic W3C `xs:restriction` element inside
`idsValue`, so any standard XSD restriction facet, including the two the
developer guide says are unsupported, is schema-valid inside an IDS file.

**What ifctester actually does, both before and after PR #9142.**
`Restriction.parse()` (`facet.py` line 1018) accepts any constraint key with no
filtering, and `Restriction.asdict()` (line 1034) explicitly lists `totalDigits`
and `fractionDigits` among the constraints it serializes back out (line
1039-1049). So an IDS author can write, save, and reload `totalDigits` and
`fractionDigits` restrictions today, and see them echoed in a report, exactly
as PR #9142 states: "already parsed and round-tripped correctly through
Restriction.parse() and asdict()". But `Restriction.__eq__` (line 1056-1094,
the actual enforcement) has no `totalDigits`, `fractionDigits`, or `whiteSpace`
branch: the `if`/`elif` chain checks `enumeration`, `pattern`, `length`,
`maxLength`, `minLength`, `maxExclusive`, `maxInclusive`, `minExclusive`,
`minInclusive` only, then falls through to `return True`. I verified `whiteSpace`
has the identical unenforced status right now (it is absent from both the
`__eq__` chain and the `asdict()` cast-exemption list), and is not touched by
PR #9142, whose stated scope was `totalDigits`/`fractionDigits` only.

**Consequence, verified by running it (PR #9142).**

```
3.14159 == restriction(fractionDigits=2)   ->  True    wrong, 5 fraction digits
123456  == restriction(totalDigits=3)      ->  True    wrong, 6 digits
```

An `Attribute` requirement with `fractionDigits=2` against
`IfcWall(Name="42.123456")` reported `spec.status = True` before the fix. This
is "a checker reporting a pass it never performed", per #9142's own framing.

**The caveat, stated plainly.** Whether this is actually a documentation *gap*
or ifctester correctly implementing an authoring-time allowance while (before
#9142) correctly declining to enforce a facet the developer guide says has
"limited utility" is genuinely unclear from the source material. `property-facet.md`
line 111 shows the User Manual does have a precedent for "structurally present,
deliberately not checked" fields: the `uri` attribute is described as "optional
metadata that is not subject to IDS checking - the IFC model does not need to
have the same or any URI." If `totalDigits`/`fractionDigits` were meant to be
the same kind of deliberate no-op, the pre-#9142 behaviour (accept at parse
time, never enforce) would be correct, not a bug, and #9142's enforcement
change would need reconciling with the developer guide rather than the other
way round. I did not find text anywhere resolving which of these two readings
is correct; that ambiguity is itself the finding.

**Proposed wording.** Two independent, complementary changes, since the actual
intended behaviour is buildingSMART's call and I am not proposing which:

1. `restrictions.md` should state the current position at all, whichever it
   is, rather than being silent. If the developer-guide's "not supported"
   stands, add one sentence: "`totalDigits` and `fractionDigits`, while
   structurally legal per the underlying `xs:restriction` element, are not
   supported by IDS; see [developer guide](../ImplementersDocumentation/developer-guide.md#restrictions)."
2. `Implementers/developer-guide.md`'s "Restrictions" section should say what
   "not supported" means operationally for a conforming checker: must it
   reject an IDS file containing `totalDigits`/`fractionDigits` as invalid at
   load time, or may it silently accept and ignore the constraint (in which
   case `whiteSpace`, structurally identical and equally unmentioned, needs
   the same explicit ruling)?

---

## Finding 4 (false fail, corroborated by a public issue): `Attribute` (and every other facet)'s "optional + no value" combination is declared "not allowed" but never given a fallback meaning

**What the docs say.** This pattern repeats identically across every facet
page that has a Requirements table:

- `attribute-facet.md` line 46: "OPTIONAL | Description | - | :x: | Optionality
  does not make sense - no added field to require."
- `property-facet.md` line 148: the same wording, "Optionality does not make
  sense - no added field to require."
- `classification-facet.md` line 35, `material-facet.md` line 57,
  `partof-facet.md` lines 40-41: the same "Not allowed" framing.

None of these six occurrences states what a checker must do if it nonetheless
encounters this combination in a real file. Nothing in `ids.xsd` structurally
forbids it: `conditionalCardinality` (xsd lines 277-283) permits `optional` on
`attribute` regardless of whether a `value` child element is present. The
generic cardinality rule in `specifications.md` line 102 does generalise
correctly if applied ("Matching entities either don't have the property, or if
they do, it is of the expected datatype and value" - with no value/datatype
specified, that reduces to "always pass"), but it is stated once, in a
different file, in the context of a property example, and none of the six
per-facet "not allowed" rows cross-references it.

**What ifctester actually does.** `facet.py` line 308-333,
`Attribute.__call__`:

```python
values = [getattr(inst, self.name, None)]
...
is_pass = bool(values)   # [None] is a non-empty list: True
if not is_pass:
    if self.cardinality == "optional":
        return AttributeResult(True)   # never reached when values == [None]
    reason = {"type": "NOVALUE"}
if is_pass:
    ... # None is later found to be "empty" here, at line 339
    if non_empty_values:
        values = non_empty_values
    else:
        is_pass = False
        reason = {"type": "FALSEY"}    # optional cardinality never re-checked
```

The `optional` short-circuit only fires when the attribute name does not
resolve to a forward attribute at all (`values == []`). For a valid but merely
unset attribute, `getattr(inst, self.name, None)` returns `None`, so
`values == [None]`, a non-empty list, and the short-circuit is skipped.

**Consequence, verified by running it (PR #9205, defect 1).**
`IfcWall.Description` left unset, `cardinality="optional"`:

- Before: FAIL, reason `FALSEY`.
- Correct: PASS. Having nothing to check on an absent attribute is the entire
  point of `optional`.

This is a false fail (a compliant model reported non-compliant), which is why
it ranks below the false-pass findings, but it is the more commonly hit defect
of the two in #9205, per that PR's own text.

**Already reported publicly, independently of this audit.** buildingSMART/IDS
issue [#402](https://github.com/buildingSMART/IDS/issues/402),
"TestCase pass-specification_optionality_and_facet_optionality_can_be_combined
not passes", reports exactly this failure mode against ifcTester directly. I
fetched the referenced fixture pair from `development`:
`pass-specification_optionality_and_facet_optionality_can_be_combined.ids`
has `<attribute cardinality="optional"><name>Description</name><value>Foobar</value></attribute>`,
and its matching `.ifc` fixture is `IFCWALL('...',$,'Waldo',$,$,$,$,$,$)`, i.e.
`Description` is `$` (null). Per `attribute-facet.md`'s own OPTIONAL+value row
("if the attribute exists, it needs to have the value Answer... lack of
property is allowed"), this should PASS. The reporter in #402 ran this exact
fixture through ifcTester and got `passed: False`, which is the same code path
as #9205's defect 1 (`values == [None]` never triggers the optional
short-circuit), just reached via a slightly different fixture shape (a value
constraint is present here, whereas #9205's repro has none). This is
independent, pre-existing, public evidence for the same underlying code defect.

**Proposed wording**, for `attribute-facet.md`'s (and the other five facets')
Requirements tables, one added sentence after the existing "not allowed" text:

> If this combination is present in a file despite being discouraged, a
> conforming checker must treat it as always satisfied: there is no value or
> data type to check, so presence or absence of the attribute is irrelevant.

---

## Finding 5 (false fail): property-facet.md never says how "populated" is determined for table-valued properties

**What the docs say.** `property-facet.md` line 108 defines "populated" for
the common (single-value) case only: "The property must exist in the specified
property set and have a non-empty value." The "Supported types of properties"
section (lines 41-68) explains how *value matching* differs across single,
bounded, list, table and enumerated properties, but never explains how mere
*existence/non-emptiness* (the REQUIRED-with-no-value-constraint case) should
be evaluated for a table property specifically, where the underlying IFC
structure (`IfcPropertyTableValue.DefiningValues`/`DefinedValues`) has no
single scalar to check.

**What ifctester actually does.** `facet.py` line 832-861, the
`IfcPropertyTableValue` branch of `Property.__call__`:

```python
for attribute in ["Defining", "Defined"]:
    column_values = props[pset_name][prop_entity.Name][f"{attribute}Values"]
    if not column_values:
        continue
    data_type = column_values[0].is_a()
    if self.dataType and data_type.lower() == self.dataType.lower():
        ...
        values.extend(column_values)
if not values:
    is_pass = False
    reason = {"type": "DATATYPE", ...}
```

Column values are only collected into `values` **inside** the
`if self.dataType and ...` guard. When no `dataType` constraint is specified
(the common case, since `dataType` is optional per `property-facet.md` line
109), that condition is always false, so `values` stays empty regardless of
what the table actually contains, and the property is reported failed.

**Consequence, verified by running it (PR #9188).** Every `IfcPropertyTableValue`
property is reported failed regardless of its contents, whenever no `dataType`
constraint is specified. A compliant model (one that genuinely has the table
property populated) is told it is not: a false fail, per #9188's own framing
("This is a wrong verdict rather than a crash: a compliant model is told it is
not.").

**Relation to a public issue.** buildingSMART/IDS issue
[#337](https://github.com/buildingSMART/IDS/issues/337), "Data type mismatch in
applicability bypasses checking", reports a related but distinct symptom in the
same theme (a `dataType` constraint silently excluding a matching property from
applicability when the model's actual IFC type differs), confirmed against
both usBIM and ifcTester by the reporter. It is not the same code path (that
one is about a `dataType` *mismatch*, this finding is about *no* `dataType`
constraint at all on a table property specifically), so it is not a duplicate,
but it is evidence that dataType-related silent exclusion is a recurring shape
of bug across implementations, which the manual's silence on table-property
existence checking does not help.

**Proposed wording**, for `property-facet.md`, after line 68 (end of the
"Supported types of properties" section):

> For `IfcPropertyTableValue` properties, "has a non-empty value" (for a
> REQUIRED requirement with no `value` or `dataType` constraint) means at
> least one `DefiningValues` or `DefinedValues` entry is present; the
> `dataType` constraint, if specified, additionally restricts which column(s)
> are considered.

---

## Finding 6 (report-display only, specification verdict unaffected): the manual states requirements are "ignored" under a prohibited specification, but not what status an ignored requirement should report

**What the docs say.** `specifications.md`'s Cardinality-of-the-applicability-entity
table (line 81) is explicit:

> | 0 | 0 | prohibited | No wall with IsExternal property should be found in
> the model, requirements are ignored in the verification of models |

**What ifctester actually does.** `Specification.validate()` unconditionally
runs `facet.status = not bool(facet.failures)` for every requirement facet.
Under a prohibited specification, requirement facets are deliberately never run
against matched elements (consistent with "requirements are ignored"), so
`facet.failures` stays empty and every requirement facet is marked `status = True`
("passed"), even when the specification itself fails because a prohibited
element was found.

**Consequence, verified by running it (PR #9189).** The Json, Html and Ods
reporters render green "pass" requirement rows directly underneath a red
failing specification. This does not change the specification's own pass/fail
verdict, which stays correct; it is a report-legibility bug, not a wrong
compliance verdict, which is why it ranks last.

**Assessment.** `specifications.md` correctly and clearly describes the
underlying behaviour ("ignored"). It is silent only on the narrower, purely
implementation-facing question of what boolean a report should display for a
facet that was never evaluated, and I don't think this narrower question is
naturally answerable from a user-facing manual: it is a reporting API contract,
which is squarely `Implementers/developer-guide.md` territory, and that
document does not cover it either. No proposed manual wording; flagging for
completeness since the audit brief asked for the full ranked list.

---

## Minor items, verified and refined from the pre-supplied list

These were given as background for this audit rather than derived here. I
verified each directly against the fetched `development` content rather than
repeating them unchecked, and refined two of them where my own reading did
not exactly match the starting description.

- **Typo, confirmed.** `restrictions.md` line 56: "A **Max Lenght** of 5..."
  should be "Max Length".
- **Facet-name correspondence, refined.** The pre-supplied note says
  "Enumeration and Pattern do use real names... Bounds and Length are prose."
  Checked directly: `restrictions.md` never states the literal XSD attribute
  name for *any* of the four restriction kinds (verified: zero matches for
  `minInclusive`, `maxInclusive`, `minExclusive`, `maxExclusive`, `minLength`,
  `maxLength`, and even `xs:enumeration`/`xs:pattern`, anywhere in the file).
  The real distinction is narrower: the heading word "Enumeration" and
  "Pattern" each correspond one-to-one with a single XSD facet name
  (`enumeration`, `pattern`), so a reader can correctly guess the XML element
  from the heading alone. "Bounds" corresponds to none of the four actual
  facet names it covers (`minInclusive`/`maxInclusive`/`minExclusive`/`maxExclusive`);
  "Length" only partially and ambiguously corresponds to its three
  (`length`/`minLength`/`maxLength`), and the prose ("Min Length", "Max
  Length", spaced and capitalised) does not spell the camelCase attribute
  names either way.
- **Missing Bounds example table, refined.** The pre-supplied note says
  "Bounds has no example table while Enumeration and Pattern both do."
  Checked directly: only **Pattern** (lines 28-38) has an example table in
  `restrictions.md`. Enumeration has none either (lines 10-18 are pure prose).
  So the real gap is narrower than stated: Bounds is missing a table that only
  one of the other three sections actually has. It is still the most
  consequential place for a missing table, though, because the content that
  would fill it already exists elsewhere in the manual: `property-facet.md`
  lines 52-68 has a fully worked 13-row inclusive/exclusive bounded-value
  table, just for property bounded values specifically rather than for the
  general-purpose Bounds restriction, and `restrictions.md`'s own Bounds
  section (lines 48-50) does not link to it.
- **`whiteSpace`, upgraded from "unmentioned" to "verified unenforced".**
  Confirmed schema-legal via the same `xmlschema` validation as Finding 3
  (validated in the same test document). Confirmed absent from both
  `Restriction.__eq__`'s constraint list and `Restriction.asdict()`'s
  cast-exemption list in the current `facet.py`, meaning it exhibits the
  identical "accepted, round-tripped, never enforced" defect that
  totalDigits/fractionDigits had before PR #9142, and it is not fixed by that
  PR either.

---

## Already raised by others (not duplicated here)

- [#449](https://github.com/buildingSMART/IDS/pull/449) (our own open PR):
  Pattern facet whole-value matching. Not duplicated in this audit per
  instruction.
- [#306](https://github.com/buildingSMART/IDS/issues/306) / [#307](https://github.com/buildingSMART/IDS/pull/307) / [#178](https://github.com/buildingSMART/IDS/issues/178):
  established that literal `predefinedType="USERDEFINED"` matching is
  deliberate design for the Entity facet, and added its test case. Neither
  touches PartOf; Finding 1 above is the PartOf-specific gap this left behind.
- [#214](https://github.com/buildingSMART/IDS/issues/214): "current agreement
  with USERDEFINED does enable to check misspelling of predefinedType",
  general unease about the same USERDEFINED design, Entity-facet scope.
- [#353](https://github.com/buildingSMART/IDS/issues/353): disputes an
  official test case's FAIL verdict for a LOGICAL UNKNOWN value, the same
  root ambiguity as Finding 2, different requirement shape.
- [#298](https://github.com/buildingSMART/IDS/issues/298): "IfcLogical
  representation in XML base", also LOGICAL-related, not read in full detail
  here since #353 is the closer match to Finding 2; flagging its existence.
- [#402](https://github.com/buildingSMART/IDS/issues/402): public,
  independent report of the exact code path behind Finding 4, against a
  slightly different fixture. Quoted and used as corroborating evidence above
  rather than re-reported.
- [#403](https://github.com/buildingSMART/IDS/issues/403): "Empty string and
  cardinality of requirements", a closely related but distinct ambiguity
  (IFCLABEL empty string vs null under REQUIRED) to Finding 2's LOGICAL
  UNKNOWN vs null.
- [#430](https://github.com/buildingSMART/IDS/issues/430), filed by Dion
  Moult: "Symmetry is broken between applicability and requirements due to
  nullness", the general-purpose version of the presence/nullness ambiguity
  underlying Findings 2 and 4.
- [#144](https://github.com/buildingSMART/IDS/issues/144): "Remove
  cardinality checks for attributes", proposes removing attribute cardinality
  entirely because its interpretation is "vague", the same general area as
  Finding 4.
- [#206](https://github.com/buildingSMART/IDS/issues/206): "Interpretation of
  PROHIBITED for property requirement", a different complaint (mandatory
  dataType under PROHIBITED feels wrong to the reporter) in the same general
  cardinality-interpretation area; current `property-facet.md` already
  documents the PROHIBITED+dataType combination as disallowed, which may
  postdate this issue.
- [#337](https://github.com/buildingSMART/IDS/issues/337): "Data type
  mismatch in applicability bypasses checking", related but distinct symptom
  to Finding 5, discussed there.
- [#423](https://github.com/buildingSMART/IDS/issues/423), [#218](https://github.com/buildingSMART/IDS/issues/218), [#195](https://github.com/buildingSMART/IDS/issues/195):
  question the legitimacy/design of embedding raw `xs:restriction` inside
  `idsValue` at the schema level. Background to Finding 3's structural
  permissiveness, not the same complaint (these are about the mechanism being
  invalid as XSD authoring practice, not about which specific facets should
  be supported).
- [#386](https://github.com/buildingSMART/IDS/issues/386): "Cardinality of
  Applicability", argues `optional` should not exist for applicability at
  all. Different scope (applicability, not requirements) from all findings
  above.

## Checked and found fine

- `units.md`: consistent SI unit table, not implicated in any of the five
  ifctester bugs, no defect found.
- `ids-metadata.md`: descriptive metadata guidance only, no checking
  semantics, not implicated.
- `Implementers/tolerance.md`: precisely specifies the float equality
  tolerance formula and explicitly states tolerance does not apply to ranges;
  matches ifctester's `is_x()` usage pattern seen in `facet.py`, no
  discrepancy found.
- `classification-facet.md` and `material-facet.md`: their Requirements
  tables are internally consistent with each other and with
  `attribute-facet.md`/`property-facet.md` (same "optional + no value = not
  allowed" pattern discussed in Finding 4); no additional facet-specific
  defect found in ifctester's `Classification`/`Material` classes during this
  audit (not exhaustively re-verified line by line; PR #9205's own "Checked
  and clean" section already covers `Classification` and `Material`
  including IFC2X3).
- `Implementers/ifc2x3-occurrence-type-mapping-table.md`: read, describes the
  IFC2X3 occurrence/type mapping referenced from `entity-facet.md`'s "Special
  cases in IFC2X3" section; consistent with that section's description, not
  implicated in any of the five bugs.
- `Implementers/repository-policy.md`: branch/versioning policy only, not
  relevant to verdict semantics.
