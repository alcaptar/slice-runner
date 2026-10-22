"""The state block does not lose a field between `Run` and `RunPayload`.

`Run` and `RunPayload` each declare the same list of fields three times: the dataclass, the
keywords `from_domain` writes, and the keywords `to_domain` reads back. Every field carries a
default on both sides, so forgetting one in any of those three copies compiles, passes `mypy` and
passes the suite -- the field is simply never persisted and quietly returns to its default on
every resumption. It already happened with `resolved_a_conflict`, which lived only in memory and
sent a dead invocation's merge back to the implementer.

`RunPayload` is the only place that serializes a `Run` -- `TransitionPayload`,
`TransitionRequestPayload` and `SubissueBody` compose it, they do not re-serialize -- so a contract
over this one pair covers every place the state block is written or read.

The one declared asymmetry is `spend_before_reopening`: a key `RunPayload` still declares with no
field in `Run`, kept on purpose as read-compatibility for state blocks a slice already wrote before
that field was retired from the domain. It is named here as an exception, not silently excluded, so the
day it is retired this contract goes red instead of staying quiet about the widening.
"""

from __future__ import annotations

import ast

import pytest
from conftest import _ROOT, _read

_RUN_PATH = "src/slice_runner/domain/run.py"
_PAYLOAD_PATH = "src/slice_runner/infrastructure/run_payload.py"

_READ_COMPATIBILITY_ONLY = {
    "corrected": "read-only compatibility for state blocks written while the understanding was still corrected",
    "alignment": "read-only compatibility for state blocks written while the understanding was still aligned",
    "understanding_pending": "read-only compatibility for state blocks written by the generation before `alignment`",
    "understand_discards": "read-only compatibility for state blocks written while the understanding still ran",
    "spend_before_reopening": (
        "read-only compatibility for state blocks written before `Run.spend_before_reopening` was "
        "retired. Retirable once no in-flight run still carries it."
    ),
}


def _mentions_class_var(annotation: ast.expr) -> bool:
    return any(isinstance(node, ast.Name) and node.id == "ClassVar" for node in ast.walk(annotation))


def _declared_fields(source: str, class_name: str, *, trusted_base: str | None = None) -> set[str]:
    """Names of the annotated attributes declared in the body of `class_name`, minus `ClassVar`.

    Fails closed when `class_name` inherits from a base other than `object`: this scan only walks
    `class_name`'s own body, so a field declared in an unwalked base would be missing from the
    result while the caller reads it as complete -- the same false-green the `**` guard in
    `_construction_keywords` exists to prevent. `trusted_base` is the one named exception: pass the
    base's name when it is documented to declare no fields of its own, as `RunPayload` does for
    `ContractModel`, the shared base every contract model in this repo inherits by convention
    (`docs/conventions/infrastructure.md`) for behaviour, not data.
    """
    tree = ast.parse(source)
    classes = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef) and node.name == class_name]
    assert len(classes) == 1, f"expected exactly one `class {class_name}` in the source, found {len(classes)}"

    definition = classes[0]
    untrusted_bases = [
        base for base in definition.bases if not (isinstance(base, ast.Name) and base.id in {"object", trusted_base})
    ]
    assert not untrusted_bases, (
        f"`class {class_name}` inherits from a base other than `object`, and this scan only walks its own "
        f"body -- it cannot claim to see every field"
    )

    return {
        statement.target.id
        for statement in definition.body
        if isinstance(statement, ast.AnnAssign)
        and isinstance(statement.target, ast.Name)
        and not _mentions_class_var(statement.annotation)
    }


def _construction_keywords(source: str, method: str, constructor: str) -> set[str]:
    """Keyword names of the single call to `constructor(...)` inside `def method`.

    Fails closed on anything that would make a set of keyword names an unreliable measurement: no
    such call, more than one, or a `**` expansion that could carry keywords the scan cannot see.
    """
    tree = ast.parse(source)
    functions = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == method]
    assert len(functions) == 1, f"expected exactly one `def {method}` in the source, found {len(functions)}"

    calls = [
        node
        for node in ast.walk(functions[0])
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == constructor
    ]
    assert len(calls) == 1, f"expected exactly one call to `{constructor}(...)` inside `{method}`, found {len(calls)}"

    call = calls[0]
    assert not any(keyword.arg is None for keyword in call.keywords), (
        f"`{method}` calls `{constructor}(...)` with a `**` expansion, which can carry keywords this scan cannot see"
    )

    return {keyword.arg for keyword in call.keywords if keyword.arg is not None}


def test_every_field_of_run_survives_the_payload_in_both_directions() -> None:
    """Renaming `Run`, `from_domain` and `to_domain` together stays green; touching only one goes red.

    A field `from_domain` never writes is lost on every save; a field `to_domain` never reads back
    is lost on every resumption even if it made it into the block on disk. Comparing sets of names,
    not order or prose, is what makes a three-way rename pass and a one-sided edit fail.
    """
    run_fields = _declared_fields(_read(_ROOT / _RUN_PATH), "Run")
    written = _construction_keywords(_read(_ROOT / _PAYLOAD_PATH), "from_domain", "cls")
    read_back = _construction_keywords(_read(_ROOT / _PAYLOAD_PATH), "to_domain", "Run")

    not_written = run_fields - written
    not_read_back = run_fields - read_back

    assert not not_written, f"`RunPayload.from_domain` never writes: {sorted(not_written)}"
    assert not not_read_back, f"`RunPayload.to_domain` never reads back: {sorted(not_read_back)}"


def test_no_key_the_payload_declares_lacks_a_field_in_run_unless_it_is_there_only_to_read_old_blocks() -> None:
    """The inverse direction: a payload key with no field in `Run` is dead weight unless it is named.

    This is what keeps the `spend_before_reopening` exception from widening by precedent -- a new
    key added to `RunPayload` without a matching `Run` field has to be named here, in the open, or
    this test goes red the day it is added.
    """
    run_fields = _declared_fields(_read(_ROOT / _RUN_PATH), "Run")
    payload_fields = _declared_fields(_read(_ROOT / _PAYLOAD_PATH), "RunPayload", trusted_base="ContractModel")

    unexplained = payload_fields - run_fields - set(_READ_COMPATIBILITY_ONLY)

    assert not unexplained, (
        f"`RunPayload` declares {sorted(unexplained)} with no matching field in `Run` and no entry in "
        f"`_READ_COMPATIBILITY_ONLY` explaining why"
    )


def test_a_field_declared_only_in_a_base_class_makes_the_scan_fail_closed_instead_of_missing_it() -> None:
    """A synthetic form the scan has never seen must turn the contract red, not pass by omission.

    `a_field_the_scan_has_never_seen` lives in `_SyntheticBase`, not in the body of `Run` itself --
    a form `_declared_fields` cannot walk. If it silently returned only the body fields, the field
    would read as "not a `Run` field" and the real contract would pass green while a base-declared
    field went unserialized, exactly the allow-list failure `docs/conventions/testing.md` warns
    against. Instead, the scan has to refuse to answer.
    """
    synthetic_run = "\n".join(
        [
            "class _SyntheticBase:",
            "    a_field_the_scan_has_never_seen: int = 0",
            "",
            "",
            "class Run(_SyntheticBase):",
            "    step: str",
        ]
    )

    with pytest.raises(AssertionError, match="base other than `object`"):
        _declared_fields(synthetic_run, "Run")


def test_every_read_compatibility_entry_still_names_a_key_the_payload_declares() -> None:
    """A retired exception has to make this contract go red, not rot inside the allow-list.

    `_READ_COMPATIBILITY_ONLY` exists to name a payload key that outlived its `Run` field on
    purpose. If that key is later dropped from `RunPayload` too, the entry becomes an exception for
    something that no longer exists -- silent debt the module docstring already promises this
    contract catches.
    """
    payload_fields = _declared_fields(_read(_ROOT / _PAYLOAD_PATH), "RunPayload", trusted_base="ContractModel")

    stale = set(_READ_COMPATIBILITY_ONLY) - payload_fields

    assert not stale, f"`_READ_COMPATIBILITY_ONLY` still names {sorted(stale)}, which `RunPayload` no longer declares"
