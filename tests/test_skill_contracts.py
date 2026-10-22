"""Contract tests between the program and the documentation it is read against.

`make check` covers the Python scripts, but the skills and the judge's rubric are markdown, and
every contract they share with the program that parses or builds them -- or with each other -- is
currently stated twice. Two copies drift the moment only one is edited, and nothing fails when
they do: the runner keeps emitting a marker the parser no longer knows, or one half of a
deliberately duplicated policy gets "fixed" on its own.

Each test here extracts a vocabulary from one surface and compares it against the other, rather
than asserting that a given sentence is present. Rewording that keeps both sides in step passes;
changing one side alone fails. That is the only drift these tests exist to catch.

Two other kinds of contract used to live in this file and do not any more:
`test_domain_vocabulary_contracts.py` holds the two that compare two vocabularies of the program's
own domain with no document in between, and `test_pipeline_invariants.py` holds the six that scan
the tree instead of comparing two copies of the same prose.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

import pytest
from conftest import _ROOT, _read, _rel

from slice_runner.domain.exceptions import InvalidVerdictError
from slice_runner.domain.issue_label import IssueLabel
from slice_runner.domain.outcome import Outcome
from slice_runner.domain.prior_finding_ruling import PriorFindingState
from slice_runner.domain.ruling import Ruling
from slice_runner.domain.severity import Severity
from slice_runner.domain.verdict import Verdict
from slice_runner.infrastructure.cited_finding import CitedFinding
from slice_runner.infrastructure.cli import Cli
from slice_runner.infrastructure.gh_run_repository import GhRunRepository
from slice_runner.infrastructure.local_skill_library import LocalSkillLibrary
from slice_runner.infrastructure.parent_body import ParentBody
from slice_runner.infrastructure.process import ProcessOutput
from slice_runner.infrastructure.slice_verifier_judge import SliceVerifierJudge
from slice_runner.infrastructure.subissue_body import SubissueBody
from slice_runner.infrastructure.verdict_payload import FindingPayload, PriorFindingRulingPayload, VerdictPayload
from slice_runner.tests.doubles import GhCallDoubles, ScriptedProcess
from slice_runner.tests.mothers.verdict_mother import FindingMother

if TYPE_CHECKING:
    from pathlib import Path

_SPEC = _ROOT / "skills" / "slice-spec" / "SKILL.md"


_PROGRAM_JUDGE = SliceVerifierJudge.adversarial()
"""The judge the PROGRAM builds, which owns its rubric, its tools and what it may read.

The old flow's `agents/slice-verifier.md` had no consumer left once the skill that invoked it was
retired, and is gone; the program owns the judge, so every contract about what it tells the judge is
measured against this.
"""


def _program_rubric() -> str:
    return _PROGRAM_JUDGE.rubric


_PARENT_EXAMPLE = "### El issue padre"
_SUBISSUE_EXAMPLE = "### Una subissue por slice"
_HARD_RULES = "### Reglas duras"
_AUTHORING_STEPS = "## Steps — modo autoria (por defecto)"
_VALIDATE = "## Steps — modo `validate`"

_SUBISSUE_TITLE = re.compile(r"`(slice-\d+ \([^`)]+\): [^`]+)`")
_KEBAB_TITLE = re.compile(r"^slice-\d\d \((?:[a-z]+: )?[a-z0-9]+(?:-[a-z0-9]+)*\): \S")
_MACRO_LABEL = re.compile(r"`((?:estado|bloqueada|abortada):[a-z-]+)`")
_LABELLED_LINE_WRITTEN = re.compile(r"^([A-Z]{4,})\s*:", re.MULTILINE)
_LABELLED_LINE_NAMED = re.compile(r"`([A-Z]{4,})\s*:")
_CONFIRMATION_ANCHORS = ("no crees nada sin el troceo confirmado", "sin volcar la spec")
"""Short anchors for the gate criterion, which has no second surface to compare against.

`slice-spec` creates issues in someone else's repository, so the gate -- nothing is created without the
slicing the person confirmed -- is the whole safety of the step. The bodies are not printed: they are
written for the program to parse, and the person reads them on GitHub. Nothing else in the tree states
it, so this is a claim about the prose rather than a comparison; reword the sentence and the anchors move
with it.
"""

_UNDERSTANDING_ANCHORS = (
    "el fichero existe no cumple",
    "declara que esa vara se aplico",
    "no un informe",
    "decisiones del agente",
)
"""Same kind of claim as `_CONFIRMATION_ANCHORS`, for the pause that publishes what got understood.

The agent's own decisions are listed apart so the person can veto them: whatever did not pass the two
filters of the design reference was decided without asking, and this is the only place it surfaces.

None of the four has a second surface to compare against: step `1b` confirms pointers -- a path, an
issue number -- never whether the behaviour behind them was understood, and the feature's
acceptance criteria are confirmed here and never written to the parent issue. So this is a claim
about the prose, and rewording any of them moves its anchor with it.

The third one is what keeps the other two from decaying into a gate nobody reads. `check-alignment`
asks for the understanding to be succinct so it stays scannable, and this repo has already paid for
what happens otherwise: an understanding whose whole body said `test` went through the downstream
gate. An unscannable pause gets waved through, and a pause that gets waved through catches nothing.
"""

_EXISTING_PIECE_ANCHORS = ("que hace hoy esa pieza", "una ruta que existe deja de cumplir")
"""Anchors for the rule that a `- pieza:` line names behaviour, not just that a path exists.

Step `1b` already confirms the pointer -- the path itself -- so a `- pieza:` line that only restates
it is a file census a spec could pass without anybody reading what the code does. Same kind of claim
as `_CONFIRMATION_ANCHORS`: no second surface parses this prose, so the anchors travel with the
sentence in the hard rules and in the matching `validate` checklist item.
"""

_EXISTING_PIECE_LOCATION_ANCHOR = "reportandola como `issue padre`"
"""Where the `validate` checklist owes reporting the `- pieza:` deviation it just learned to catch.

`_VALIDATE_ANCHORS` already contains the literal string `issue padre`, but it is satisfied by an
unrelated checklist item, so deleting this phrase alone leaves that broader test green. This anchor
is scoped to the sentence under test, not the whole `validate` section.
"""

_VALIDATE_ANCHORS = (
    "la regla que incumple y su ubicacion",
    "issue padre",
    "slice-NN (#numero)",
    "en el titulo, en la etiqueta o en el cuerpo",
)
"""Same kind of claim as `_CONFIRMATION_ANCHORS`, for the other half of what `validate` owes.

Checking the new shape is measured by comparing vocabularies; *reporting* each deviation with its rule
and its location is prose, and there is no second surface to compare it against -- the location is only
useful to the person reading the report. It is not decoration either: with the spec split across a
parent and twelve subissues, a deviation without its location is one the person has to go and find.
Nothing else in the tree states it, so the anchors travel with the sentence.
"""

_SUBISSUE_LINES = frozenset({"REPO", "INTENCION", "DECISION", "ACEPTACION", "SENAL", "EXCLUYE", "SUSTITUYE"})
"""The six labelled lines a subissue body carries, written down instead of derived from the example.

`REPO:`, `SENAL:`, `EXCLUYE:` and `SUSTITUYE:` all have a consumer in the program now, read by
`SubissueBody` and measured by the tests above and below. `INTENCION:` and `ACEPTACION:` travel as prose
to the implementer and to the judge, with no second surface to compare the set against, and
deriving it from the very example under test approves whatever the example happens to say: drop
`SENAL:` from the three regions at once and all three sets still match. So the set is an external claim
about the prose, with its reason next to it, like `_CONFIRMATION_ANCHORS`.
"""

_OPTIONAL_SUBISSUE_LINES = frozenset({"DISENO"})
"""The labelled lines a subissue body may carry, which the example does not write.

`DISENO:` names a design the parent declares under `## Diseno`, and only a slice that builds something
visual carries it, so the example -- which is what a model copies into every spec -- leaves it out on
purpose: written there, every slice would cite a design. The rules and the `validate` checklist still
have to name it, because a label nobody is told about is one nobody writes and `validate` approves the
absence of. `SubissueBody` reads it, but `_SUBISSUE_LINES` and this set are held against the prose, not
against the parser, for the same reason the first one is not derived from the example.
"""

_DESIGN_HEADING = "`## Diseno`"

_SUBISSUE_SECTIONS = (
    ("## Repositorio", frozenset({"REPO"})),
    ("## Por qué", frozenset({"INTENCION"})),
    ("## Criterios de aceptación", frozenset({"ACEPTACION"})),
    ("## Fuera de alcance", frozenset({"EXCLUYE"})),
    ("## Qué sustituye", frozenset({"SUSTITUYE"})),
    ("## Decisiones", frozenset({"DECISION", "DISENO"})),
    ("## Señal en producción", frozenset({"SENAL"})),
)
"""The headings a subissue body groups its lines under, in order, for the person reviewing it on GitHub.

The program ignores them -- `SubissueBody` only reads lines that start with their label -- so nothing
parses this prose and the claim is held against the example alone.
"""


def _without_fences(markdown: str) -> str:
    return re.sub(r"^```.*?^```\n", "", markdown, flags=re.DOTALL | re.MULTILINE)


def _spec_example(heading: str) -> str:
    """The fenced example a section of `slice-spec` carries, taken from the file, not restated here.

    Read from the raw text on purpose: the parent's example contains `##` lines of its own, so
    cutting the section by headings first would truncate it at the format it is documenting.
    """
    text = _read(_SPEC)
    at = text.find(f"\n{heading}\n")
    assert at != -1, f"cannot find `{heading}` in {_rel(_SPEC)}"

    block = re.search(r"```markdown\n(.*?)^```", text[at:], re.DOTALL | re.MULTILINE)
    assert block, f"`{heading}` in {_rel(_SPEC)} carries no fenced example"

    return block.group(1)


def _spec_prose(heading: str) -> str:
    """The prose of a section, fenced examples removed, so a rule is read from the rule."""
    stripped = _without_fences(_read(_SPEC))
    at = stripped.find(f"\n{heading}\n")
    assert at != -1, f"cannot find `{heading}` in {_rel(_SPEC)}"

    body = stripped[at + len(heading) + 2 :]
    end = re.search(r"^#{2,4} ", body, re.MULTILINE)

    return body[: end.start()] if end else body


def test_the_parent_issue_slice_spec_documents_is_one_the_program_reads_whole() -> None:
    """The parent carries the intention, the yardstick and the commands, and `ParentBody` is what reads it.

    The example in the skill is what a model imitates, so it is the real contract: a heading renamed on
    one side alone gives a parent the program parses as empty, and `Prechecks` then refuses to run a
    perfectly written spec -- or, worse, runs it with no yardstick. Parsing the documented example is
    the only way to measure that the two sides still agree.
    """
    parsed = ParentBody.parse(_spec_example(_PARENT_EXAMPLE), repo=None)

    assert parsed.intention, "the documented parent carries no `## Intencion` the program can read"
    assert parsed.sources, "the documented parent carries no source the program can read"
    assert parsed.controls.commands, "the documented parent carries no control command the program can read"
    assert parsed.decisions, "the documented parent carries no `## Decisiones` line the program can read"


_WORKSPACE_MARKER_CONTRACT = _ROOT / "contract" / "workspace-marker.json"
_UUID_PATTERN = "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"


def _workspace_marker_contract() -> dict[str, object]:
    contract: dict[str, object] = json.loads(_read(_WORKSPACE_MARKER_CONTRACT))

    return contract


def _workspace_marker_shape() -> re.Pattern[str]:
    template = _workspace_marker_contract()["marker"]
    assert isinstance(template, str)
    assert template.count("<uuid>") == 1, f"the marker template carries no single `<uuid>`: {template}"

    return re.compile("^" + re.escape(template).replace(re.escape("<uuid>"), _UUID_PATTERN) + "$")


def _parent_example_without_the_marker() -> str:
    lines = _spec_example(_PARENT_EXAMPLE).rstrip("\n").split("\n")
    assert _workspace_marker_shape().match(lines[-1]), "the documented parent does not end with the marker"

    return "\n".join(lines[:-1]) + "\n"


def test_every_example_of_the_workspace_marker_contract_has_the_shape_of_its_template() -> None:
    examples = _workspace_marker_contract()["examples"]
    assert isinstance(examples, list)
    assert examples, "the workspace marker contract carries no example"

    shape = _workspace_marker_shape()
    misfits = [example for example in examples if not (isinstance(example, str) and shape.match(example))]

    assert misfits == [], f"examples that are not the marker the template declares: {misfits}"


def test_the_parent_example_slice_spec_documents_ends_with_a_workspace_marker_of_the_contract_shape() -> None:
    last_line = _spec_example(_PARENT_EXAMPLE).rstrip("\n").split("\n")[-1]

    assert _workspace_marker_shape().match(last_line), f"the documented parent ends with `{last_line}`, not a marker"


@pytest.mark.parametrize("repo", [None, "tu-org/infra-alertas"])
def test_the_workspace_marker_does_not_change_what_the_program_reads_from_the_documented_parent(
    repo: str | None,
) -> None:
    with_marker = ParentBody.parse(_spec_example(_PARENT_EXAMPLE), repo=repo)
    without_marker = ParentBody.parse(_parent_example_without_the_marker(), repo=repo)

    assert with_marker.intention == without_marker.intention
    assert with_marker.sources == without_marker.sources
    assert with_marker.controls == without_marker.controls
    assert with_marker.decisions == without_marker.decisions


def test_the_exemption_line_slice_spec_documents_is_read_as_an_exemption_and_never_as_a_command() -> None:
    """`- ninguno: <motivo>` declares that a repo has no controls; it is not a control called `ninguno`.

    It used to come out of the parser as `ControlCommand(name="ninguno", command=<the reason>)`, which
    means whoever runs the controls would hand a sentence of Spanish prose to a shell. Empty and exempt
    still are not the same thing: with no controls and no exemption the prechecks fail closed, and a
    declared exemption is treated as an exempt layer with nothing to run. The target repo comes out of
    the subissue example, so this also pins that a slice with `REPO:` has the subsection of its repo.
    """
    target = SubissueBody.parse(_spec_example(_SUBISSUE_EXAMPLE)).repo
    assert target, "the documented subissue carries no `REPO:`, so there is no target repo to filter by"

    controls = ParentBody.parse(_spec_example(_PARENT_EXAMPLE), repo=target).controls

    assert controls.declared, f"the documented parent declares nothing for {target}, which fails closed"
    assert controls.exemption_reason, f"the exemption the parent documents for {target} carries no reason"
    assert controls.commands == (), (
        f"the exemption line documented for {target} came back as {controls.commands}: a reason for "
        f"having no controls has become a command someone would try to execute"
    )


def _documented_subissue_title() -> str:
    titles: list[str] = _SUBISSUE_TITLE.findall(_spec_prose(_SUBISSUE_EXAMPLE))
    assert len(titles) == 1, f"expected exactly one subissue title under `{_SUBISSUE_EXAMPLE}`, found {titles}"

    return titles[0]


def test_the_documented_subissue_groups_each_labelled_line_under_its_heading_in_order() -> None:
    """The headings are for the person who reviews the slicing on GitHub right after it is created.

    Without them the body is a flat run of capitalised prefixes where why the slice exists, what it
    leaves out and when it is done cannot be told apart at a glance.
    """
    expected = {label: heading for heading, labels in _SUBISSUE_SECTIONS for label in labels}
    headings: list[str] = []
    misplaced: list[str] = []
    current = ""
    for line in _spec_example(_SUBISSUE_EXAMPLE).splitlines():
        if line.startswith("## "):
            current = line
            headings.append(line)
            continue
        written = _LABELLED_LINE_WRITTEN.match(line)
        if written and expected.get(written.group(1)) != current:
            misplaced.append(f"{written.group(1)} under {current or 'no heading'}")

    assert headings == [heading for heading, _ in _SUBISSUE_SECTIONS], (
        f"the example under `{_SUBISSUE_EXAMPLE}` uses the headings {headings}"
    )
    assert not misplaced, f"the example under `{_SUBISSUE_EXAMPLE}` puts {misplaced}"


def test_the_subissue_slice_spec_documents_is_read_by_the_program_as_the_slice_it_names() -> None:
    """Title, label and body of the documented subissue, read by the program that consumes them.

    The identifier in the title is what orders the slices -- `GhRunRepository` sorts by it and rejects a
    title without it -- and the name is what derives the branch and the commit scope, so it has to be
    kebab-case. The macro state arrives as a label, not as a marker in the text. And the execution state
    block is absent: it belongs to the machine, so a documented body that already carried one would have
    the skill writing a run that never happened.

    The six labelled lines are asserted, not just `REPO:`, because all six now have a consumer: the
    intention, the criteria, the signal, what is excluded and what is replaced travel into the prompts
    of the implementer and of the judge. Parsing them is fail-soft by design -- a line the parser does
    not recognise is not an error, it is an empty field -- so a rename on one side alone would leave both
    agents working with an empty yardstick and nothing at all would break. `_SUBISSUE_LINES` already
    claims the example writes the six; this is what checks the program reads the six.
    """
    title = _documented_subissue_title()
    label = {"id": "LA_kwDOThEBoM8AAAACu6gVcw", "name": IssueLabel.PENDING.value, "description": "", "color": "5319e7"}
    recorded = [
        {
            "number": 44,
            "title": title,
            "body": _spec_example(_SUBISSUE_EXAMPLE),
            "labels": [label],
            "state": "OPEN",
        }
    ]
    process = ScriptedProcess(ProcessOutput(code=0, stdout=json.dumps(recorded), stderr=""))

    children = GhRunRepository(call=GhCallDoubles.wired(process)).read_children(
        repo="alcaptar/slice-runner", parent=43, expected=1
    )

    assert _KEBAB_TITLE.match(title), f"the documented title {title!r} does not carry `slice-NN (name-kebab):`"
    assert children[0].slice_id.canonical == title.split(" ", 1)[0]
    assert children[0].repo, "the documented subissue carries no target repo the program can read"
    assert children[0].intention, "the documented subissue carries no `INTENCION:` the program can read"
    assert children[0].criteria, "the documented subissue carries no `ACEPTACION:` the program can read"
    assert children[0].decisions, "the documented subissue carries no `DECISION:` the program can read"
    assert children[0].signal, "the documented subissue carries no `SENAL:` the program can read"
    assert children[0].excludes, "the documented subissue carries no `EXCLUYE:` the program can read"
    assert children[0].replaces, "the documented subissue carries no `SUSTITUYE:` the program can read"
    assert children[0].label is IssueLabel.PENDING
    assert children[0].run is None, (
        "the documented subissue body already carries an execution state block, which is the machine's"
    )


def test_the_labelled_lines_of_a_subissue_are_the_same_in_the_example_the_rules_and_the_validate_checklist() -> None:
    """Three surfaces of one contract, all inside `slice-spec`: what it shows, demands and checks.

    The example is what a model copies, the rules are what it is told, and `validate` is what catches a
    spec that does not comply. A label added to the rules but not to the example is written by nobody; a
    label in the example that `validate` does not know is one whose absence is approved as valid, which
    is the failure mode that makes the mode worthless. The set the three are held to is
    `_SUBISSUE_LINES` and not the example itself: derived from the example, the three could agree on
    dropping one and nothing would notice.
    """
    written = set(_LABELLED_LINE_WRITTEN.findall(_spec_example(_SUBISSUE_EXAMPLE)))
    assert written == _SUBISSUE_LINES, (
        f"the example under `{_SUBISSUE_EXAMPLE}` writes {sorted(written)}, and a subissue body carries "
        f"{sorted(_SUBISSUE_LINES)}: the intention, the criteria, the signal, what is excluded and the "
        f"target repo"
    )

    demanded = set(_LABELLED_LINE_NAMED.findall(_spec_prose(_HARD_RULES)))
    checked = set(_LABELLED_LINE_NAMED.findall(_spec_prose(_VALIDATE)))

    allowed = written | _OPTIONAL_SUBISSUE_LINES

    assert demanded == allowed, (
        f"the example and the hard rules of {_rel(_SPEC)} disagree on the lines of a subissue: "
        f"only in the rules {sorted(demanded - allowed)}, only in the example {sorted(allowed - demanded)}"
    )
    assert checked == allowed, (
        f"the example and the validate checklist of {_rel(_SPEC)} disagree on the lines of a subissue: "
        f"only in validate {sorted(checked - allowed)}, only in the example {sorted(allowed - checked)}"
    )


def test_the_optional_lines_a_subissue_may_carry_are_never_written_by_the_example() -> None:
    """The example writes the mandatory lines and none of the optional ones.

    Held apart from the comparison above so that the failure names which half moved: an example that
    starts writing `DISENO:` makes every copied spec cite a design the parent does not declare.
    """
    written = set(_LABELLED_LINE_WRITTEN.findall(_spec_example(_SUBISSUE_EXAMPLE)))

    assert written.isdisjoint(_OPTIONAL_SUBISSUE_LINES), (
        f"the example under `{_SUBISSUE_EXAMPLE}` writes {sorted(written & _OPTIONAL_SUBISSUE_LINES)}, which are "
        f"optional: a model copies the example into every subissue"
    )


def test_the_parent_section_that_declares_the_designs_is_named_by_the_rules_and_the_validate_checklist() -> None:
    """`ParentBody` reads `## Diseno`, so the two places that tell a person about it have to name it.

    A heading renamed in one of them leaves a parent that declares designs under a name the program does
    not read: the designs never travel and nothing says why.
    """
    assert _DESIGN_HEADING in _spec_prose(_HARD_RULES), f"the hard rules of {_rel(_SPEC)} do not name {_DESIGN_HEADING}"
    assert _DESIGN_HEADING in _spec_prose(_VALIDATE), (
        f"the validate checklist of {_rel(_SPEC)} does not name {_DESIGN_HEADING}"
    )


_USER_STORY_KEY_LINE = re.compile(r"## Historia de usuario\s*\n\s*([A-Z][A-Z0-9]*-\d+)")
_USER_STORY_TITLE = re.compile(r"`([A-Z][A-Z0-9]*-\d+ slice-\d+ \([^`)]+\): [^`]+)`")


def test_the_user_story_key_the_parent_documents_is_the_one_the_program_reads_from_the_subissue_title() -> None:
    """The key the parent declares has to be the same one `GhRunRepository` parses out of the title.

    `SLICE_HEADING` already carries an optional `key` group that `read_children` composes into the
    canonical identifier, but nothing writes it yet: this is the contract between what `slice-spec`
    documents as the parent's declared key and what the program's own expression reads back out of the
    documented subissue title, parsed with that expression rather than restated by hand.
    """
    text = _read(_SPEC)
    key_match = _USER_STORY_KEY_LINE.search(text)
    assert key_match, f"{_rel(_SPEC)} does not document a `## Historia de usuario` example carrying a key"
    declared_key = key_match.group(1)

    title_match = _USER_STORY_TITLE.search(text)
    assert title_match, f"{_rel(_SPEC)} does not document a subissue title carrying a user story key"
    title = title_match.group(1)

    parsed = GhRunRepository.SLICE_HEADING.match(title)
    assert parsed, f"the documented keyed title {title!r} is not parseable by `GhRunRepository.SLICE_HEADING`"
    assert parsed.group("key") == declared_key, (
        f"the parent documents the key {declared_key!r} but the documented subissue title parses as "
        f"{parsed.group('key')!r}: the two halves of the contract disagree"
    )


_USER_STORY_VALIDATE_ANCHORS = (
    "declara `## Historia de usuario` pero alguna subissue no lleva la clave en el titulo",
    "no empieza por esa clave seguida de `slice-NN`",
    "reportala como `slice-NN (#numero)`, en el titulo",
    "la clave va delante del `slice-NN`",
)
"""Anchors for the checklist item that catches a parent/subissue mismatch on the user story key.

Same kind of claim as `_VALIDATE_ANCHORS`: there is no second surface to compare this rule against, since
the key travels only through the title and the parent's own section, so this pins the sentence that
reports the deviation with its rule and its location.

Each anchor is a phrase from the new bullet only, not a bare substring: `validate`'s intro paragraph
already contains `slice-NN (#numero)` and `en el titulo` on their own (for the location of any
subissue deviation), so anchoring on those alone would stay green even if the bullet itself were
deleted. Anchoring on the longer phrases pins the bullet, not the paragraph that precedes it.
"""


_PARENT_USER_STORY_ANCHORS = (
    "pero su propio titulo no abre con la clave, o no lleva",
    "la etiqueta `origen:<clave>`",
    "reportalo como `issue padre`, diciendo cual de las dos",
)
"""Anchors for the checklist item that catches a parent not carrying its own user story key.

The key reaches the parent by two surfaces the program never reads -- its title and its label -- so
neither can be compared against anything the way `SLICE_HEADING` compares the documented subissue
title. Both exist for the same job: finding the whole feature in a listing without opening it, which
is also why losing one silently is easy. This pins the sentence that reports the deviation.
"""


def test_validate_reports_a_parent_that_does_not_carry_its_own_user_story_key() -> None:
    """`validate` has to catch a parent whose title or label drops the key its body declares.

    Same shape as the checklist anchors above: prose with no second surface, so the test pins the
    sentence instead of comparing two copies of a vocabulary.
    """
    prose = " ".join(_spec_prose(_VALIDATE).split())

    missing = [anchor for anchor in _PARENT_USER_STORY_ANCHORS if anchor not in prose]
    assert not missing, (
        f"the `validate` mode of {_rel(_SPEC)} no longer states {missing}: a parent that declares a "
        f"user story has to carry it in its own title and label, or the deviation goes unreported"
    )


def test_validate_reports_the_missing_user_story_key_with_its_rule_and_location() -> None:
    """`validate` has to catch a parent declaring a user story whose subissues do not carry it.

    Same shape as `test_the_validate_mode_reports_every_deviation_with_its_rule_and_where_it_lives`: the
    checklist item is prose with no second surface, so this pins the sentence rather than a vocabulary.
    """
    prose = " ".join(_spec_prose(_VALIDATE).split())

    missing = [anchor for anchor in _USER_STORY_VALIDATE_ANCHORS if anchor not in prose]
    assert not missing, (
        f"the `validate` mode of {_rel(_SPEC)} no longer states {missing}: a parent declaring a user "
        f"story whose subissue titles do not carry it needs to be caught and reported with its location"
    )


_QUANTITY_RULE_ANCHORS = (
    "el numero es parte del criterio y no un detalle del test",
    "assertea exactamente ese numero",
    "la vara no es la palabra, es si el caso de uno discrimina",
)
"""Anchors for the rule that a criterion asking for a quantity has to say how many."""

_QUANTITY_VALIDATE_ANCHORS = (
    "Un criterio que pide una cantidad dice cuantas",
    "el implementador lo pinea con una y quien juzga exige varias",
)
"""Anchors for the same yardstick as a `validate` checklist item, which is what makes it run."""

_QUANTITY_QUESTION = "¿el caso de uno se distingue de lo que el programa ya hacia?"
"""The question both halves share, so neither can drift into its own wording."""


def test_the_quantity_yardstick_is_both_explained_and_run_when_a_spec_is_validated() -> None:
    """A yardstick that is explained but never executed is the failure this repo is built around.

    The two halves have to move together: the rule states why a criterion asking for a quantity has to
    say how many -- with the case that measured it -- and the `validate` checklist is what applies it to
    a spec. Writing only the rule leaves it as advice nobody runs; writing only the checklist item
    leaves the deviation reported without the reason that makes it obvious. Anchoring the same question
    in both is what keeps the two from drifting into different rules with the same name.
    """
    rules = " ".join(_spec_prose("### Reglas duras").split())
    validate = " ".join(_spec_prose(_VALIDATE).split())

    missing_rule = [anchor for anchor in _QUANTITY_RULE_ANCHORS if anchor not in rules]
    missing_check = [anchor for anchor in _QUANTITY_VALIDATE_ANCHORS if anchor not in validate]

    assert not missing_rule, f"the rules of {_rel(_SPEC)} no longer state {missing_rule}"
    assert not missing_check, (
        f"the `validate` mode of {_rel(_SPEC)} no longer states {missing_check}: without it the "
        f"yardstick is explained but never applied to a spec"
    )
    without_the_question = [
        half for half, prose in (("las reglas", rules), ("`validate`", validate)) if _QUANTITY_QUESTION not in prose
    ]
    assert not without_the_question, (
        f"{without_the_question} de {_rel(_SPEC)} ya no hacen la pregunta que reconoce la desviacion: "
        f"con una sola de las dos mitades son dos reglas con un nombre"
    )


_REPLACES_VALIDATE_ANCHORS = (
    "Ninguna slice sin `SUSTITUYE:`, y ninguna `SUSTITUYE: si` sin las dos mitades",
    "es la misma desviacion: sin el mecanismo de vuelta atras",
    "tiene que ser la que corresponde al sujeto",
)
"""Anchors for the checklist item that catches a missing `SUSTITUYE:` and an incomplete `SUSTITUYE: si`.

Same kind of claim as `_USER_STORY_VALIDATE_ANCHORS`: the two halves of this bullet -- the line missing
entirely, and a `si` that names only one of the two things it owes -- are both prose with no second
surface to compare against, so this pins the sentence that reports each one instead of a vocabulary.
"""


def test_validate_reports_a_missing_replaces_line_and_an_incomplete_si_declaration() -> None:
    """`validate` has to catch both a subissue without `SUSTITUYE:` and one whose `si` skips a half.

    A `SUSTITUYE: si` that names what it replaces but not how to roll it back leaves the judge's rollout
    item with nothing to demand from the diff, which is the exact failure mode the line exists to close.
    """
    prose = " ".join(_spec_prose(_VALIDATE).split())

    missing = [anchor for anchor in _REPLACES_VALIDATE_ANCHORS if anchor not in prose]
    assert not missing, (
        f"the `validate` mode of {_rel(_SPEC)} no longer states {missing}: a subissue missing "
        f"`SUSTITUYE:` or declaring `SUSTITUYE: si` without both halves needs to be caught and reported"
    )


def test_the_macro_state_slice_spec_writes_is_a_label_of_the_vocabulary_and_never_a_marker_in_the_text() -> None:
    """The state moved out of the prose and into a GitHub label, and both halves need measuring.

    A label the skill invents is one nothing reads -- `GhRunRepository` only recognises members of
    `IssueLabel` and returns `None` for anything else, so an invented one reads as "no state at all".
    The markers are the other half: as long as the checkbox and the `[estado]` marker survive anywhere
    in the skill, a model has two ways to write the state and only one of them is read.
    """
    documented = set(_MACRO_LABEL.findall(_read(_SPEC)))
    assert documented, f"{_rel(_SPEC)} names no macro state label at all"

    unknown = sorted(documented - set(IssueLabel))
    assert not unknown, f"{_rel(_SPEC)} names {unknown}, which `IssueLabel` does not know and nothing reads"
    assert IssueLabel.PENDING.value in documented, (
        f"{_rel(_SPEC)} no longer names {IssueLabel.PENDING.value}, the state every slice starts in"
    )

    text = _read(_SPEC)
    leftovers = [marker for marker in ("- [ ]", "- [x]", "[pendiente]", "[en-curso]") if marker in text]
    assert not leftovers, (
        f"{_rel(_SPEC)} still writes {leftovers}: the state of a slice is a label, and a marker in the "
        f"text is a second place to write it that nothing reads"
    )


def test_the_step_that_creates_the_issues_waits_for_the_confirmed_slicing_and_does_not_dump_the_bodies() -> None:
    """Creating the tree is the one irreversible thing this skill does, and it does it in someone's repo.

    A parent plus one subissue per slice, each with `--parent` -- that flag is what makes them children,
    and the program finds them with `parent-issue:<repo>#<n>`, so a subissue created without it is
    invisible to the run -- and with `--label`, because the state is a label from the moment it is
    created. Before any of that the person has confirmed the slicing; the bodies themselves are not
    printed, because they are written for the program and the person reads them on GitHub.
    """
    steps = re.split(r"^(?=\d+[a-z]?\.\s)", _spec_prose(_AUTHORING_STEPS), flags=re.MULTILINE)
    creating = [step for step in steps if "gh issue create" in step]
    assert len(creating) == 1, f"expected exactly one step of {_rel(_SPEC)} to create issues, found {len(creating)}"

    step = creating[0]
    for flag in ("--parent", "--label"):
        assert flag in step, f"the creating step of {_rel(_SPEC)} does not pass {flag}"

    missing = [anchor for anchor in _CONFIRMATION_ANCHORS if anchor not in step]
    assert not missing, (
        f"the creating step of {_rel(_SPEC)} no longer states {missing}: nothing else in the tree says "
        f"that nothing is created before the person confirms the slicing"
    )


def test_the_step_between_the_repo_search_and_the_slicing_publishes_what_it_understood_and_waits() -> None:
    """Neither half of this pause has anywhere else to be measured against.

    Step `1b` only confirms pointers -- a path, an issue number -- never whether the behaviour behind
    them was understood, and the feature's acceptance criteria used to appear only inside the
    subissues the slicing step writes, with nobody having seen the whole list first. This step is the
    one place both get shown and confirmed before any slice is cut.
    """
    steps = re.split(r"^(?=\d+[a-z]?\.\s)", _spec_prose(_AUTHORING_STEPS), flags=re.MULTILINE)
    pause = [step for step in steps if step.strip().startswith("1c.")]
    assert len(pause) == 1, f"expected exactly one step of {_rel(_SPEC)} numbered `1c.`, found {len(pause)}"

    step = pause[0]
    missing = [anchor for anchor in _UNDERSTANDING_ANCHORS if anchor not in step]
    assert not missing, (
        f"step `1c.` of {_rel(_SPEC)} no longer states {missing}: nothing else in the tree confirms that "
        f"the code was understood, proposes the feature's acceptance criteria before cutting, or keeps "
        f"the pause short enough to be read instead of waved through"
    )


def test_the_validate_mode_reports_every_deviation_with_its_rule_and_where_it_lives() -> None:
    """The other half of what `validate` owes, and the one that only exists as prose.

    Checking the new shape is measured by comparing vocabularies; reporting is not, and a mode that
    finds a deviation and does not say where it is leaves the person searching a parent plus one
    subissue per slice. The locations are the artifacts themselves -- the parent's body, or a subissue
    named by its identifier and number, and within it the title, the label or the body -- so this is a
    claim about the paragraph, whitespace normalised so rewrapping a line is free.
    """
    prose = " ".join(_spec_prose(_VALIDATE).split())

    missing = [anchor for anchor in _VALIDATE_ANCHORS if anchor not in prose]
    assert not missing, (
        f"the `validate` mode of {_rel(_SPEC)} no longer states {missing}: a deviation reported without "
        f"its rule and its location is one the person has to go and find"
    )


_PIECE_LINE = re.compile(r"^- pieza: \S+ - (.+?)(?=\n- |\Z)", re.MULTILINE | re.DOTALL)


def test_the_existing_piece_lines_name_behaviour_and_the_documented_example_shows_it() -> None:
    """`- pieza:` used to pass by naming a path that exists; now it owes what that path does today.

    The hard rules state the bar, `validate` catches a spec written under the old one, and the
    parent's example is what a model copies verbatim -- so a rule that tightened without the example
    following would have the skill teaching the very shape it now rejects. This is the comparison
    `docs/conventions/testing.md` asks for between two copies of the same contract: reword one side
    and the other stays behind.
    """
    hard_rules = _spec_prose(_HARD_RULES)
    missing_in_rules = [anchor for anchor in _EXISTING_PIECE_ANCHORS if anchor not in hard_rules]
    assert not missing_in_rules, (
        f"the hard rules of {_rel(_SPEC)} no longer state {missing_in_rules}: a `- pieza:` line that "
        f"only names a path that exists has to stop being enough"
    )

    validate_prose = _spec_prose(_VALIDATE)
    missing_in_validate = [anchor for anchor in _EXISTING_PIECE_ANCHORS if anchor not in validate_prose]
    assert not missing_in_validate, (
        f"the `validate` checklist of {_rel(_SPEC)} no longer states {missing_in_validate}: it has to "
        f"catch a `- pieza:` line that only names an existing path"
    )
    assert _EXISTING_PIECE_LOCATION_ANCHOR in validate_prose, (
        f"the `validate` checklist of {_rel(_SPEC)} no longer states {_EXISTING_PIECE_LOCATION_ANCHOR!r}: "
        f"a deviation reported without its location is one the person has to go and find"
    )

    example = _spec_example(_PARENT_EXAMPLE)
    pieces = _PIECE_LINE.findall(example)
    assert pieces, f"the documented parent under {_PARENT_EXAMPLE} carries no `- pieza:` line to check"
    for tail in pieces:
        assert "existe" not in tail, (
            f"the documented `- pieza:` line {tail!r} still describes the piece as existing, which is "
            f"exactly what the tightened rule rejects"
        )


_RUN_COMMAND = re.compile(r"slice-runner run\s+((?:[^`\n]|\n(?!\s*\n))+?)(?=`|\n\s*\n|$)")
_PLACEHOLDER = re.compile(r"<[^>]+>")


def _argv_of(command: str) -> list[str]:
    """The command as the parser would receive it: one line, placeholders filled, no continuations."""
    flattened = " ".join(command.replace("\\\n", " ").split())

    return ["run", *(_PLACEHOLDER.sub(lambda m: "1" if m.group() in ("<N>", "<padre>") else "x", flattened)).split()]


def test_every_command_slice_spec_teaches_parses_and_leaves_the_worktree_to_the_program() -> None:
    """The skill teaches the launch command on four surfaces, and a flag renamed would leave them stale.

    The program mounts the worktree of the slice itself, so the command carries no path for it: the
    value by omission is the one the program derives, not the directory where the caller stands --
    the measured mechanism behind the judge reading a branch of someone else's slice 31 times out of
    32. This compares the prose against `Cli.parser()` rather than against another copy of the prose,
    so it also fails when a flag is renamed or dropped from the program and the skill still teaches it,
    or when a taught command hands a path to the worktree and takes the choice away from the program.
    """
    taught = set(_RUN_COMMAND.findall(_read(_SPEC)))
    derived_by_the_program = Cli.parser().parse_args(["run", "1", "--repo", "x", "--base", "x"]).worktree

    assert taught, f"{_rel(_SPEC)} teaches no launch command at all"
    assert derived_by_the_program is None
    for command in sorted(taught):
        argv = _argv_of(command)
        parsed = Cli.parser().parse_args(argv)
        assert parsed.worktree is derived_by_the_program, (
            f"{_rel(_SPEC)} teaches `slice-runner run {' '.join(argv[1:])}`, which names a worktree by hand "
            f"when the program mounts its own"
        )


_REGISTER_COMMAND = re.compile(r"slice-runner register ([^`\n]+)`")


def test_slice_spec_registers_the_pending_slices_after_the_last_subissue_with_a_parseable_command() -> None:
    authoring = _spec_prose(_AUTHORING_STEPS)
    creation = authoring[authoring.index("5. **") : authoring.index("6. **Cierra**")]
    registered = _REGISTER_COMMAND.findall(creation)

    assert len(registered) == 1, f"step 5 of {_rel(_SPEC)} has to teach `slice-runner register` exactly once"
    assert creation.index("slice-runner register") > creation.index("--label estado:pendiente")
    argv = ["register", *_PLACEHOLDER.sub(lambda m: "1" if m.group() == "<N>" else "x", registered[0]).split()]
    parsed = Cli.parser().parse_args(argv)
    assert (parsed.command, parsed.issue, parsed.repo) == ("register", 1, "x/x")
    assert "no se deshace nada ni se repite la creacion" in " ".join(creation.split())


_WORKTREE_SECTION = "## El worktree de una slice"
_MOUNTS_A_WORKTREE = re.compile(r"git worktree add")
_NEXT_STEP = re.compile(r"\n\d+[a-z]?\. \*\*|\n## ")
_STEPS_THAT_SPEAK_OF_A_WORKTREE = (
    "6. **Cierra**",
    "7. **Propon el reparto en paralelo",
)


def test_the_skill_teaches_no_recipe_for_a_worktree_and_the_steps_that_speak_of_one_cite_the_section() -> None:
    """A recipe by hand is a second source of truth next to the program that mounts the tree.

    It used to live in one section because its three conditions failed silently and sat only in a
    design note. The program now mounts the tree, so the section tells what the program does and the
    steps that mention a worktree cite it instead of restating it; a `git worktree add` anywhere in
    the skill is a person being taught to do by hand what can diverge from what the program does.
    This measures the shape, not the wording.
    """
    spec = _read(_SPEC)

    assert spec.find(_WORKTREE_SECTION) != -1, f"{_rel(_SPEC)} has no `{_WORKTREE_SECTION}` section"
    assert not _MOUNTS_A_WORKTREE.search(spec), (
        f"{_rel(_SPEC)} teaches `git worktree add`: the program mounts the worktree of a slice itself"
    )
    for step in _STEPS_THAT_SPEAK_OF_A_WORKTREE:
        at = spec.find(step)
        assert at != -1, f"{_rel(_SPEC)} no longer has the step starting `{step}`"
        rest = spec[at + len(step) :]
        ends_at = min(
            (m.start() for m in _NEXT_STEP.finditer(rest) if m.start() > 0),
            default=len(rest),
        )
        following = rest[:ends_at]
        assert _WORKTREE_SECTION.removeprefix("## ") in following, (
            f"the step starting `{step}` speaks of a worktree without citing `{_WORKTREE_SECTION}`"
        )


def _json_shape(value: object) -> object:
    """Structural skeleton of a parsed JSON value: keys and scalar types, no example data.

    Comparing shapes rather than text makes the check insensitive to reformatting, key order,
    and changes to the illustrative values, while still catching a renamed, added, or dropped
    field -- which is the only thing that would actually break the orchestrator's parsing.
    """
    if isinstance(value, dict):
        return {key: _json_shape(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_json_shape(item) for item in value]
    return type(value).__name__


def _sole_json_block_in(markdown: str, *, where: str = "the program's rubric") -> object:
    blocks = re.findall(r"```json\n(.*?)```", markdown, re.DOTALL)
    assert len(blocks) == 1, f"expected exactly one ```json block in {where}, found {len(blocks)}"
    return json.loads(blocks[0])


def _granted_tools() -> set[str]:
    return set(_PROGRAM_JUDGE.tools)


def test_the_program_does_not_grant_the_judge_what_its_own_rubric_says_he_does_not_have() -> None:
    """The rubric tells the judge it has no `Bash`, "a proposito", and builds three items on that.

    It is what stops it from trying to run lint or tests, and what justifies handing it the diff
    already computed. Granting `Bash` would make the rubric a lie the judge reads first, and the judge
    would have no way to know which half is true. The old flow enforced the same thing structurally,
    through the `tools:` header of a now-retired `agents/slice-verifier.md`; the program has no header,
    so this is where it gets enforced.
    """
    rubric = _program_rubric()
    assert "No tienes `Bash`" in rubric, (
        "the program's rubric no longer tells the judge it has no `Bash`; either restore it or stop "
        "building the 'you do not run anything' items on a premise that is not stated"
    )

    assert "Bash" not in _granted_tools(), (
        f"the argv grants {sorted(_granted_tools())}, and its own rubric tells the judge it has no `Bash`"
    )


def test_the_rubric_reads_excludes_as_a_prohibition_and_never_as_a_permission() -> None:
    """`EXCLUYE` is what the spec wrote down as deliberately out of this slice's scope, and the

    implementer's brief tells it not to build what that line names. So item 5 has to fail a diff that
    builds it anyway: read as a permission, the line would have the judge wave through exactly what the
    other half of the pipeline forbids, and the two prompts would contradict each other on the same
    input.
    """
    rubric = _program_rubric()
    assert "Contrasta esto contra el `EXCLUYE`" in rubric, (
        "the program's rubric no longer tells the judge to contrast item 5's speculative-behaviour check "
        "against `EXCLUYE`, so what the spec forbade would be judged as if nobody had ever written it down"
    )
    assert "el diff construye lo que el `EXCLUYE` prohibia" in rubric, (
        "the program's rubric no longer fails a diff that builds what `EXCLUYE` declared out of scope, so "
        "the line stopped being a prohibition for the judge while it still is one for the implementer"
    )
    assert "`EXCLUYE` tampoco cubra" not in rubric, (
        "the program's rubric exempts from item 5's FAIL condition what `EXCLUYE` names, which reads the "
        "line as a list of permissions: it is a list of prohibitions"
    )


def test_the_rubric_lists_excludes_among_the_inputs_that_can_arrive_empty() -> None:
    """`EXCLUYE` travels the same fail-soft path as `SENAL`: a slice that never declares one parses to

    an empty field, not an error. Without the rubric saying so, the judge reading an empty `EXCLUYE`
    line has no way to tell "nothing was declared out of scope" from "the input never reached me", and
    the two need different verdicts (see the paragraph on reporting missing inputs).
    """
    rubric = _program_rubric()
    assert "Siete de esos campos pueden llegarte vacios" in rubric, (
        "the program's rubric still says a different count of fields can arrive empty, but "
        "`SUSTITUYE`, `EXCLUYE`, `SENAL` and what the implementer declared left out all travel the "
        "same fail-soft path and need to be counted together"
    )
    assert "el `EXCLUYE`" in rubric, (
        "the program's rubric no longer names `EXCLUYE` among the inputs that can arrive empty"
    )
    assert "el `SUSTITUYE`" in rubric, (
        "the program's rubric no longer names `SUSTITUYE` among the inputs that can arrive empty"
    )
    assert "lo que el implementador declaro dejar fuera" in rubric, (
        "the program's rubric no longer names what the implementer declared left out among the inputs "
        "that can arrive empty, so a slice resumed straight into verify has no reading for it"
    )


def test_the_rubric_does_not_read_empty_deviations_as_nothing_declared() -> None:
    rubric = _program_rubric()
    assert "eso es un dato y no un insumo que falte" not in rubric, (
        "the rubric promises `deviations` always arrives filled, but a resumed slice or `verify` without "
        "an issue leaves it empty"
    )
    assert "Una lista de desviaciones vacia no prueba que no se declarase ninguna" in rubric, (
        "the rubric no longer tells the judge that empty `deviations` can hide a declaration made in an "
        "earlier invocation, so item 10 would turn it into a high-severity finding"
    )


def test_the_rubric_demands_what_the_slice_declared_when_it_replaces_something() -> None:
    """`SUSTITUYE: si` names what it owes; item 2 has to fail a diff that does not bring it.

    Without this, a slice that declares it replaces something live could still land with no way back --
    the anti-pattern `slicing.md` names. And the second half is not always a rollback mechanism: it is
    one for a deployed service, and what happens to what is already written for a program that gets
    installed, where going back **is** reinstalling. A rubric that only knows the first shape turns
    every slice of the second kind into an invented high-severity finding, which is worse than the
    medium it was meant to replace.
    """
    rubric = " ".join(_program_rubric().split())
    assert "SUSTITUYE: si" in rubric, (
        "the program's rubric no longer contrasts item 2 against a `SUSTITUYE: si` declaration"
    )
    assert "lo que la segunda mitad de la linea nombra" in rubric, (
        "the program's rubric no longer demands the diff bring what the `SUSTITUYE: si` line names"
    )
    assert "Exigir un flag a un programa que se instala es un hallazgo inventado" in rubric, (
        "the program's rubric no longer warns that the second half changes with the subject, so it "
        "would demand a rollback flag from a program whose way back is reinstalling"
    )
    assert "es **FAIL (severity high)**, citando la linea de `SUSTITUYE`" in rubric, (
        "the program's rubric demands what the line names but no longer blocks with severity high "
        "when it is missing from the diff"
    )


def test_both_halves_of_the_replaces_contract_know_the_second_half_changes_with_the_subject() -> None:
    """The skill writes the line and the rubric reads it: a shape only one of them knows is a trap.

    Measured, and this test exists because it happened: the skill was taught that the second half of
    `SUSTITUYE: si` is a rollback mechanism for a deployed service and what happens to what is already
    written for a program that gets installed -- while the rubric still demanded the mechanism. That
    combination turns every slice of the second kind into a high-severity finding for not bringing a
    flag that cannot exist. Neither side alone is wrong; the pair is.
    """
    spec = " ".join(_read(_SPEC).split())
    rubric = " ".join(_program_rubric().split())

    for surface, text in (("the skill", spec), ("the program's rubric", rubric)):
        assert "sin redeploy" in text, (
            f"{surface} no longer names the deployed-service shape of the second half of `SUSTITUYE: si`"
        )
        assert "se instala" in text, (
            f"{surface} no longer names the installed-program shape of the second half of "
            f"`SUSTITUYE: si`, so one side would demand a rollback the other never asked for"
        )


def test_the_rubric_treats_a_declared_no_replacement_as_refutable_against_the_diff() -> None:
    """`SUSTITUYE: no` is a claim about the diff, not an exemption from item 2.

    A slice that declares it replaces nothing but whose diff changes behaviour that already existed in
    production is exactly the silent in-place swap the line exists to catch; treating the declaration as
    true by default would make it decoration.
    """
    rubric = " ".join(_program_rubric().split())
    assert "SUSTITUYE: no" in rubric, "the program's rubric no longer contrasts item 2 against `SUSTITUYE: no`"
    assert "el diff cambia comportamiento que ya existia" in rubric, (
        "the program's rubric no longer fails a `SUSTITUYE: no` slice whose diff changes behaviour that "
        "already existed in production"
    )
    assert (
        "en produccion pese a la declaracion, es **FAIL (severity high)**, citando la linea y el cambio "
        "que la contradice" in rubric
    ), (
        "the program's rubric treats a contradicted `SUSTITUYE: no` as refutable but no longer blocks "
        "with severity high when the diff proves it wrong"
    )


def test_the_rubric_judges_rollout_as_before_when_replaces_is_empty_and_not_as_missing_data() -> None:
    """An empty `SUSTITUYE` is every spec written before this line existed, not a missing input.

    Same shape as the `EXCLUYE` paragraph right above: the item still has its general trigger to fall
    back on, so a judge reading an empty line has no reason to return "sin veredicto por falta de dato"
    on the item that is the whole reason this rubric calls out the pattern as a recurrent failure.
    """
    rubric = " ".join(_program_rubric().split())
    assert "Si viene vacio, juzga el patron de rollout" in rubric, (
        "the program's rubric no longer tells the judge how to treat an empty `SUSTITUYE`: derive the "
        "rollout item from the general trigger instead of reporting it as missing data"
    )


def test_the_rubric_reads_an_empty_list_of_prior_findings_as_the_first_round_not_missing_data() -> None:
    """An empty list here means round one, the opposite of what emptiness means for the six fields above.

    Without this the judge has no way to tell "nothing survived from last time" from "this input never
    reached me", and the paragraph right above already claims the second reading for six other fields:
    the two would collide on the same rubric if this one were not called out apart from them.
    """
    rubric = " ".join(_program_rubric().split())
    assert "La lista de hallazgos de la ronda anterior vacia no es lo mismo que un insumo que no llego." in rubric, (
        "the program's rubric no longer distinguishes an empty prior-findings list from a missing input"
    )
    assert "esta es la primera verificacion de la slice" in rubric, (
        "the program's rubric no longer tells the judge that an empty prior-findings list means this "
        "is the first verification of the slice"
    )


def test_the_rubric_demands_a_verdict_on_every_prior_finding_with_a_reason_to_retire_one() -> None:
    """Every previous finding needs a fate, and retiring one without saying why is the silent U-turn

    this whole slice exists to close: 12 of 32 followable highs evaporated across a round with nobody
    saying why, and each one cost a round of implementation plus one of verification.
    """
    rubric = " ".join(_program_rubric().split())
    assert "pronunciate sobre **cada uno**" in rubric, (
        "the program's rubric no longer demands a verdict on every finding of the previous round"
    )
    for fate in ("**corregido**", "**sigue**", "**retirado**"):
        assert fate in rubric, f"the program's rubric no longer offers {fate} as a fate for a prior finding"
    assert "el `reason` de la entrada tiene que decir por que" in rubric, (
        "the program's rubric no longer demands a written reason in `reason` when a prior finding is retired"
    )


def test_the_rubric_treats_prior_findings_as_precedent_and_not_as_a_yardstick_to_drag_along() -> None:
    """Keeping a finding alive means re-citing it against the current diff, not repeating last round's

    citation as if nothing had moved: what changed between rounds may have shifted the line or fixed
    the file halfway, and dragging the old citation forward would report something no longer true.
    """
    rubric = " ".join(_program_rubric().split())
    assert "Son antecedente, no vara." in rubric, (
        "the program's rubric no longer declares prior findings a precedent instead of a yardstick"
    )
    assert "vuelve a citarlo contra el diff de esta ronda" in rubric, (
        "the program's rubric no longer requires re-citing a finding that still stands against the "
        "current diff instead of dragging the old citation forward"
    )


_PRIOR_FINDING_VOCABULARY = {
    "identificador": "id",
    "regla": "rule",
    "ruta": "path",
    "linea": "line",
    "severidad": "severity",
    "evidencia": "evidence",
    "detalle": "detail",
}


def _prior_findings_bullet() -> str:
    """The rubric's own description of what a prior finding carries."""
    bullet = re.search(
        r"^- \*\*Los hallazgos que tu mismo levantaste en la ronda anterior\*\*(.*?)\n(?=- |\n)",
        _program_rubric(),
        re.DOTALL | re.MULTILINE,
    )
    assert bullet, "cannot find the prior-findings bullet in the program's rubric"
    return bullet.group(1)


def _excludes_bullet() -> str:
    """The rubric's own description of what `EXCLUYE` is: a prohibition, never a permission."""
    bullet = re.search(
        r"^- \*\*El `EXCLUYE` que declaro la slice\*\*(.*?)\n(?=- |\n)",
        _program_rubric(),
        re.DOTALL | re.MULTILINE,
    )
    assert bullet, "cannot find the EXCLUYE bullet in the program's rubric"
    return bullet.group(1)


def _debt_bullet() -> str:
    """The rubric's own description of what the implementer declared left out."""
    bullet = re.search(
        r"^- \*\*Lo que el implementador declaro dejar fuera\*\*(.*?)\n(?=- |\n)",
        _program_rubric(),
        re.DOTALL | re.MULTILINE,
    )
    assert bullet, "cannot find the debt bullet in the program's rubric"
    return bullet.group(1)


_PROHIBITION_NOT_PERMISSION_VOCABULARY = {"prohibicion", "permiso"}


def test_the_debt_bullet_shares_the_polarity_the_excludes_bullet_already_declares() -> None:
    """A declared gap cannot buy its way out of a criterion any more than `EXCLUYE` can buy its way in.

    `EXCLUYE` already tells the judge that a declared exclusion is a prohibition, never a permission --
    the diff still fails for building what it named. `left_out` needs the same reading, or a slice could
    dodge a criterion just by writing the gap down in its report instead of an unexplained omission.
    Comparing the two bullets' vocabulary, instead of asserting a literal sentence in only one of them,
    is what catches a rewrite that keeps the words in the excludes bullet but drops them from the debt
    one -- or the other way round.
    """
    excludes_words = {word for word in _PROHIBITION_NOT_PERMISSION_VOCABULARY if word in _excludes_bullet()}
    debt_words = {word for word in _PROHIBITION_NOT_PERMISSION_VOCABULARY if word in _debt_bullet()}

    assert excludes_words == _PROHIBITION_NOT_PERMISSION_VOCABULARY, (
        "the excludes bullet lost the prohibition/permission vocabulary this contract compares against"
    )
    assert debt_words == excludes_words, (
        f"the debt bullet and the excludes bullet disagree on polarity: only in excludes "
        f"{sorted(excludes_words - debt_words)}, only in debt {sorted(debt_words - excludes_words)}"
    )


def test_the_prior_finding_fields_the_rubric_names_are_the_ones_the_prompt_actually_carries() -> None:
    """The bullet states what a prior finding brings; `CitedFinding` is what actually composes it.

    `evidence` and `detail` used to be thrown away composing the cite, while the bullet only ever
    promised regla/ruta/linea/severidad -- the two sides agreed by both being incomplete. Extracting a
    field here without saying so in the bullet is silent again, the other way round.

    The comparison is against the cite the judge's invocation sends, not against the whole prompt: the
    rubric's own JSON example already contains a `"line": 42` and a `"medium"`, so measuring against
    the full text would mark those fields as carried regardless of what the cite actually says. The
    identifier is composed by `JudgeInvocation` itself, not by `CitedFinding`: it is the judge's own
    numbering of that round, and the implementer's prompt -- the other consumer of `CitedFinding` --
    never carries it.
    """
    bullet = _prior_findings_bullet()
    documented = {field for word, field in _PRIOR_FINDING_VOCABULARY.items() if re.search(rf"\b{word}\b", bullet)}

    finding = FindingMother.with_line(line=42)
    cite = f"`f1` {CitedFinding.of(finding)}"
    carried_values = {
        "id": "f1",
        "rule": finding.rule,
        "path": finding.path,
        "line": str(finding.line),
        "severity": str(finding.severity),
        "evidence": finding.evidence,
        "detail": finding.detail,
    }
    carried = {field for field, value in carried_values.items() if value in cite}

    assert documented == carried, (
        f"the rubric's description of a prior finding and what the prompt actually carries disagree: "
        f"only in the rubric {sorted(documented - carried)}, only in the prompt {sorted(carried - documented)}"
    )


_SKILL_ORDER_RE = re.compile(r"(?:corre|carga)[^.]*?`([a-z][a-z0-9-]{4,})`", re.IGNORECASE)


def _skills_the_rubric_orders() -> set[str]:
    """The skills the rubric tells the judge to load, taken from the rubric itself."""
    return set(_SKILL_ORDER_RE.findall(_program_rubric()))


def test_every_skill_the_rubric_orders_is_one_the_judge_can_actually_load() -> None:
    """The whole invariant in one place: ordered skill -> `Skill` granted -> and reachable.

    It used to be two contracts measuring halves -- one that `Skill` is granted, one that the rubric
    does not promise a file that is not there -- and neither caught the real hole: the rubric ordered
    two skills whose `references/` sat outside every granted directory, so items 1 and 8 were judged
    with no yardstick and the verdict came back just as clean. Measured live: without the grant the
    envelope carries `permission_denials` and the judge answers that it has no permission.

    That hole is why `Judge` exists as one object. This is the test that object makes possible.

    Reachability needs a machine that has the library, so it is skipped where there is none (the
    continuous integration runner has no `~/.claude`); what always runs is the tools half.
    """
    ordered = _skills_the_rubric_orders()
    assert ordered, (
        "no skill is ordered anywhere in the program's rubric. Either the items that loaded one are "
        "gone -- and then `Skill` should stop being granted -- or the sentence changed shape and this "
        "contract stopped measuring anything"
    )

    assert "Skill" in _granted_tools(), (
        f"the rubric orders {sorted(ordered)} but the judge is granted only {sorted(_granted_tools())}"
    )

    trees = LocalSkillLibrary().directories()
    if not trees:
        pytest.skip("this machine has no skill library, so reachability cannot be measured from here")

    unreachable = sorted(name for name in ordered if not _somewhere_under(trees, name))
    assert not unreachable, (
        f"the rubric orders {unreachable}, the judge is granted {[str(tree) for tree in trees]}, and "
        f"nothing under them is named like that: those items would be judged with an empty yardstick"
    )


def _somewhere_under(trees: tuple[Path, ...], name: str) -> bool:
    return any(next(tree.rglob(name), None) is not None for tree in trees)


def _diff_bullet() -> str:
    """The rubric's own description of the diff it hands the judge."""
    bullet = re.search(
        r"^- \*\*El diff completo de la slice\*\*(.*?)(?=^- \*\*)", _program_rubric(), re.DOTALL | re.MULTILINE
    )
    assert bullet, "cannot find the diff bullet in the program's rubric"
    return bullet.group(1)


def test_the_rubric_does_not_promise_a_file_the_program_no_longer_writes() -> None:
    """The diff travels inside the prompt, so `slice.diff` is a path that no longer exists.

    A rubric that still named it would send the judge to open a file that was never written -- and
    the judge has `Read`, so it would fail silently rather than loudly, and then judge whatever it
    could reach instead. That failure mode is exactly why the diff moved into the prompt: what is
    already in front of the judge cannot be skipped. `GitDiffReader` writing nothing is pinned in
    `src/slice_runner/tests/infrastructure/test_git_diff_reader.py`; this guards the prose.
    """
    assert "slice.diff" not in _program_rubric(), (
        "the program's rubric still names `slice.diff`, but the program writes no patch: the diff "
        "travels inside the prompt. Either the file came back or the sentence has to go"
    )


def test_the_rubric_describes_the_diff_range_the_program_actually_produces() -> None:
    """The rubric told the judge the diff was `<base>...HEAD` while the script diffs the index.

    It was true once and stopped being true when the range moved to `--cached --merge-base`, for a
        reason recorded in `docs/conventions/infrastructure.md`: the commit happens after verification, so
        against `HEAD` there would be nothing to see. Nobody updated the sentence that travels to the judge,
        and nothing measured it -- the other contract tests here compare closed vocabularies, not prose
        describing a git range. The range is now produced by `GitDiffReader`, whose behaviour is pinned in
        `src/slice_runner/tests/infrastructure/test_git_diff_reader.py`.

        A false premise about what it is looking at is how a judge produces confidently wrong findings:
        expecting commits, or reasoning about history that is not in the range.

        This test guards the sentence only; the behaviour is pinned by the reader's own tests.
    """
    bullet = _diff_bullet()

    assert "..HEAD" not in bullet, (
        "the program's rubric describes the diff as a range ending at `HEAD`, but `GitDiffReader` "
        "diffs the staged index against the branch-point. The judge would be told it looks at committed "
        "history when it looks at the index"
    )
    assert "indice" in bullet.lower(), (
        "the program's rubric no longer tells the judge that the diff is the index. Omitting it is "
        "not enough: the judge has to know it is looking at what the commit will be, not at history"
    )


def _documented_finding() -> dict[str, object]:
    """The single example finding in the rubric, which is where the verdict's fields are stated."""
    schema = _sole_json_block_in(_program_rubric())
    assert isinstance(schema, dict)
    findings = schema["findings"]
    assert isinstance(findings, list)
    assert findings
    first = findings[0]
    assert isinstance(first, dict)
    return first


def test_the_finding_keys_in_the_rubric_are_the_ones_the_program_maps_its_fields_to() -> None:
    """The rubric states the finding's keys; the program's fields reach them through one mapping.

    A key documented but not aliased is dropped on the way in -- silently, because the JSON schema
    the program sends is generated from those same aliases, so the judge is never even asked for it.
    The reverse makes the program demand a key the rubric never told the judge to emit.
    """
    documented = set(_documented_finding())

    mapped = FindingPayload.contract_keys()
    assert documented == mapped, (
        f"the finding in the program's rubric and the aliases of `FindingPayload` disagree: "
        f"only in the rubric {sorted(documented - mapped)}, only in the program {sorted(mapped - documented)}"
    )


def test_the_verdict_top_level_keys_in_the_rubric_are_the_ones_the_program_emits() -> None:
    """The rubric's example JSON is the whole verdict, not just its findings.

    Adding `prior_rulings` to `VerdictPayload` without touching this example -- or the other way
    round -- leaves one side of the contract stale: the judge would be told a shape the program does
    not parse, or the program would accept a field the judge is never shown.
    """
    schema = _sole_json_block_in(_program_rubric())
    assert isinstance(schema, dict)

    documented = set(schema)
    emitted = set(VerdictPayload.model_fields)
    assert documented == emitted, (
        f"the top-level keys of the rubric's example verdict and `VerdictPayload` disagree: only in the "
        f"rubric {sorted(documented - emitted)}, only in the program {sorted(emitted - documented)}"
    )


def _documented_pronouncement() -> dict[str, object]:
    """The single example pronouncement in the rubric, where a prior ruling's fields are stated."""
    schema = _sole_json_block_in(_program_rubric())
    assert isinstance(schema, dict)
    prior_rulings = schema["prior_rulings"]
    assert isinstance(prior_rulings, list)
    assert prior_rulings
    first = prior_rulings[0]
    assert isinstance(first, dict)
    return first


def test_the_pronouncement_keys_in_the_rubric_are_the_ones_the_program_maps_its_fields_to() -> None:
    """Same drift the finding keys test guards against, on the pronouncement the judge emits per finding."""
    documented = set(_documented_pronouncement())

    mapped = PriorFindingRulingPayload.contract_keys()
    assert documented == mapped, (
        f"the pronouncement in the program's rubric and the aliases of `PriorFindingRulingPayload` "
        f"disagree: only in the rubric {sorted(documented - mapped)}, only in the program "
        f"{sorted(mapped - documented)}"
    )


def test_the_pronouncement_states_in_the_rubric_are_the_ones_the_program_accepts() -> None:
    """Same drift as the ruling/severity vocabularies, on the three fates a prior finding can be given."""
    documented = {value.strip() for value in str(_documented_pronouncement()["state"]).split("|")}

    assert documented == set(PriorFindingState)


_SEVERITY_CONSEQUENCE = re.compile(r"^  - `(high|medium|low)` -> (.+)$", re.MULTILINE)
_SENDS_IT_BACK = "vuelve al implementador"
_IS_A_VETO = f"el veredicto es {Ruling.FAIL}"


def _documented_consequence_of() -> dict[Severity, str]:
    return {Severity(level): said for level, said in _SEVERITY_CONSEQUENCE.findall(_program_rubric())}


def _forces_a_veto(severity: Severity) -> bool:
    try:
        Verdict(ruling=Ruling.PASS, findings=(FindingMother.without_line(severity=severity),))
    except InvalidVerdictError:
        return True

    return False


def _sends_the_slice_back(severity: Severity) -> bool:
    """What the program really does with one finding of this severity, both halves of it.

    A `PASS` carrying a `high` is refused by `Verdict` itself, so the severity that forces `FAIL` is
    read from that refusal rather than restated here; the rest go through `Outcome.of_the_verdict`.
    """
    if _forces_a_veto(severity):
        return True

    passing = Verdict(ruling=Ruling.PASS, findings=(FindingMother.without_line(severity=severity),))

    return Outcome.of_the_verdict(passing) is not Outcome.DONE


def test_the_severity_the_rubric_says_sends_the_slice_back_is_the_only_one_the_program_sends_back() -> None:
    """The rubric tells the judge what each level costs, and the program is what makes that true.

    This is the drift that already happened once and nobody could see: the rubric promised that
    `medium` and `low` "no bloquean por si solos" while `Outcome.of_the_verdict` sent every non-`low`
    finding back for a round of corrections. The judge was writing "esto no bloquea" next to a
    `medium` and the program was ordering a correction for it, ten times out of ten, because neither
    side can observe the other: the judge never sees what its own verdict caused.
    """
    documented = {severity: _SENDS_IT_BACK in said for severity, said in _documented_consequence_of().items()}

    assert documented == {severity: _sends_the_slice_back(severity) for severity in Severity}, (
        "the rubric and the program disagree on which severity sends the slice back to the implementer"
    )


def test_the_severity_the_rubric_calls_a_veto_is_the_one_a_passing_verdict_cannot_carry() -> None:
    """The other half of the same scale, and the one a level's destination alone does not pin.

    A rubric that told the judge to emit `PASS` with a `high` still sends the slice back, so the test
    above passes while the judge is being asked for a verdict `Verdict.__post_init__` throws away as
    incoherent -- it would burn a call per round and never reach the implementer.
    """
    documented = {severity: _IS_A_VETO in said for severity, said in _documented_consequence_of().items()}

    assert documented == {severity: _forces_a_veto(severity) for severity in Severity}, (
        "the rubric and the program disagree on which severity a passing verdict cannot carry"
    )


def test_the_verdicts_and_severities_in_the_rubric_are_the_ones_the_program_accepts() -> None:
    """Same drift, on the two closed vocabularies.

    These reach the judge as `enum` values in `--json-schema`, so a level in the rubric that the
    program does not know is one the judge is forbidden from emitting -- and one the program knows
    but the rubric does not document is dead vocabulary nobody will ever produce.
    """
    schema = _sole_json_block_in(_program_rubric())
    assert isinstance(schema, dict)

    assert {v.strip() for v in str(schema["ruling"]).split("|")} == set(Ruling)
    assert {s.strip() for s in str(_documented_finding()["severity"]).split("|")} == set(Severity)


def test_every_slice_title_slice_spec_documents_yields_a_name_git_accepts_as_a_branch() -> None:
    """The titles the skill shows are what a model imitates, so they have to survive `git switch -c`.

    `slice-spec` used to document an optional conventional-commit type inside the parentheses --
    `slice-03 (refactor: extraer-repo)` -- and the program consumed it nowhere: `GhRunRepository` takes
    the whole parentheses as the name, so the branch came out as `slice/03-refactor: extraer-repo` and
    git refused it. The run died on 2026-08-11 having already marked the subissue in progress, published
    the understanding and paid for the call, which is the worst moment to find out.

    Parsing the documented titles with the program's own expression is what keeps the two sides honest:
    a title the skill teaches and the program cannot turn into a branch fails here instead of mid-run.

    Covers both documented title shapes: the plain `slice-NN (name): title` and the one prefixed with a
    user story key, `HU-123 slice-NN (name): title`. Counting titles would not tell them apart -- the
    skill documents several plain ones, so any count stays green after the keyed example disappears --
    so the keyed shape is asserted by the `key` group the program itself parses out.
    """
    titles = re.findall(r"`((?:[A-Z][A-Z0-9]*-\d+ )?slice-\d+ \([^)]+\)[^`]*)`", _read(_SPEC))

    assert titles, "slice-spec documents no slice title, so this contract has nothing to measure"

    keyed = []
    for title in titles:
        parsed = GhRunRepository.SLICE_HEADING.match(title)
        assert parsed, f"the program cannot read the title slice-spec documents: {title}"
        name = parsed["name"]
        assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name), (
            f"the title `{title}` yields the name `{name}`, which git will not take as a branch"
        )
        if parsed["key"]:
            keyed.append(title)

    assert keyed, (
        "slice-spec documents no title carrying a user story key, so the shape this guard was widened "
        "for is going unmeasured while the rest of the titles keep it green"
    )


class TestSliceSpecDesignDecidedBeforeSlicing:
    _REFERENCES = _SPEC.parent / "references"

    @classmethod
    def _skill_and_references(cls) -> dict[str, str]:
        paths = [_SPEC, *sorted(cls._REFERENCES.glob("*.md"))]
        return {str(path.relative_to(_ROOT)): _read(path) for path in paths}

    @staticmethod
    def _flat(text: str) -> str:
        return " ".join(text.split())

    @staticmethod
    def _step(text: str, opening: str) -> str:
        start = text.index(opening)
        following = re.search(r"\n\d+[a-z]?\. \*\*", text[start + len(opening) :])
        end = start + len(opening) + following.start() if following else len(text)
        return text[start:end]

    def test_no_document_of_the_skill_mentions_the_alignment_pause_or_the_commands_that_lift_it(self) -> None:
        forbidden = re.compile(r"alineaci|slice-runner go|slice-runner review", re.IGNORECASE)

        documents = self._skill_and_references()
        offenders = {name: forbidden.findall(text) for name, text in documents.items() if forbidden.search(text)}

        assert not offenders, f"the alignment pause is retired but still mentioned: {offenders}"

    def test_the_always_visited_branches_no_longer_hold_domain_architecture_or_contracts_asked_of_the_person(
        self,
    ) -> None:
        reference = _read(self._REFERENCES / "diseno.md")
        branches = reference.split("## Lo que el agente recorre siempre")[1].split("## Cuando se acaba")[0]
        labels = [label.lower() for label in re.findall(r"^- \*\*(.+?)\*\*", branches, re.MULTILINE)]

        assert labels, "the always-visited branches list no branch"
        for moved in ("dominio", "arquitectura", "contratos"):
            offenders = [label for label in labels if moved in label]
            assert not offenders, f"`{moved}` is back in the branches the agent visits on its own: {offenders}"

    def test_the_design_reference_has_an_architecture_block_before_what_reaches_the_person_naming_its_parts_in_order(
        self,
    ) -> None:
        reference = _read(self._REFERENCES / "diseno.md")

        assert "## El bloque de arquitectura" in reference
        assert reference.index("## El bloque de arquitectura") < reference.index("## Que llega a la persona")
        block = self._flat(reference.split("## El bloque de arquitectura")[1].split("## Que llega a la persona")[0])
        positions = [
            block.lower().index(part)
            for part in ("agregados", "objetos de valor", "flujo de dependencias", "fronteras")
        ]
        assert positions == sorted(positions)
        assert "antes de cualquier otra pregunta de diseno" in block

    def test_the_architecture_block_marks_what_a_convention_source_already_decides_instead_of_asking_it(self) -> None:
        reference = _read(self._REFERENCES / "diseno.md")
        block = self._flat(reference.split("## El bloque de arquitectura")[1].split("## Que llega a la persona")[0])

        assert "decidido por <fichero>" in block
        assert re.search(r"decidido por <fichero>.{0,200}no se pregunta", block)

    def test_the_architecture_block_sends_dependent_questions_to_a_second_block_and_closes_in_one_line_without_domain(
        self,
    ) -> None:
        reference = _read(self._REFERENCES / "diseno.md")
        block = self._flat(reference.split("## El bloque de arquitectura")[1].split("## Que llega a la persona")[0])

        assert re.search(r"segundo bloque", block)
        assert re.search(r"sin dominio ni arquitectura.{0,200}una linea con su motivo", block)

    def test_the_second_block_belongs_to_the_architecture_block_and_skips_the_filters_too(self) -> None:
        reference = _read(self._REFERENCES / "diseno.md")
        block = self._flat(reference.split("## El bloque de arquitectura")[1].split("## Que llega a la persona")[0])

        assert re.search(r"segundo bloque \*\*es parte del bloque de arquitectura\*\*", block)
        assert re.search(r"tampoco pasa por los dos filtros, y lo que decide es de la persona", block)

    def test_each_open_decision_of_the_block_brings_two_paths_and_a_grounded_recommendation(self) -> None:
        reference = _read(self._REFERENCES / "diseno.md")
        block = self._flat(reference.split("## El bloque de arquitectura")[1].split("## Que llega a la persona")[0])

        assert re.search(r"al menos dos caminos.{0,80}`cast-wide`", block)
        assert re.search(r"recomendacion con su base.{0,40}`answer-injection`", block)

    def test_a_part_of_the_block_with_nothing_open_nor_decided_by_convention_is_left_out(self) -> None:
        reference = _read(self._REFERENCES / "diseno.md")
        block = self._flat(reference.split("## El bloque de arquitectura")[1].split("## Que llega a la persona")[0])

        assert re.search(
            r"un apartado sin nada abierto ni nada decidido por convencion no se escribe", block, re.IGNORECASE
        )

    def test_the_architecture_block_defers_target_repo_frontiers_and_contracts_to_the_second_block(self) -> None:
        reference = _read(self._REFERENCES / "diseno.md")
        block = self._flat(reference.split("## El bloque de arquitectura")[1].split("## Que llega a la persona")[0])

        assert re.search(
            r"repo destino.{0,300}no van en el primer bloque.{0,200}segundo.{0,200}fuentes y controles", block
        )

    def test_the_design_reference_says_the_agent_decides_only_what_is_outside_the_block_and_misses_the_filters(
        self,
    ) -> None:
        reference = _read(self._REFERENCES / "diseno.md")
        why = self._flat(reference.split("## Para que existe")[1].split("## Primero se investiga")[0])
        filters = self._flat(reference.split("## Que llega a la persona")[1].split("## Como se pregunta")[0])

        assert re.search(r"le llegan siempre el dominio, la arquitectura y los contratos", why)
        assert re.search(r"Lo que no es del bloque y no pasa los filtros lo decide el agente", filters)
        assert "sin pasar por los dos filtros" in self._flat(reference)

    def test_the_three_closing_conditions_of_the_design_also_require_the_architecture_block_answered_or_closed(
        self,
    ) -> None:
        skill = _read(_SPEC)
        closings = {
            "diseno.md": _read(self._REFERENCES / "diseno.md")
            .split("## Cuando se acaba")[1]
            .split("## La refutacion")[0],
            "step 1": self._step(skill, "1. **Disena"),
            "step 1c": self._step(skill, "\n1c. **"),
        }

        for name, text in closings.items():
            assert re.search(r"bloque de arquitectura", self._flat(text)), f"{name} does not mention the block"

        assert re.search(r"bloque de arquitectura.{0,80}(contestado|cerrado)", self._flat(closings["diseno.md"]))
        assert re.search(r"bloque de arquitectura.{0,80}(contestado|cerrado)", self._flat(closings["step 1"]))
        assert re.search(r"bloque de arquitectura.{0,80}(contestado|cerrado)", self._flat(closings["step 1c"]))

    def test_step_one_asks_the_architecture_block_first_and_keeps_its_phrase_about_discovering_the_other_repo(
        self,
    ) -> None:
        step = self._flat(self._step(_read(_SPEC), "1. **Disena"))

        assert re.search(r"primero el bloque de arquitectura", step)
        assert "antes de decidir sus contratos" in step

    def test_step_1c_leaves_domain_architecture_and_contracts_out_of_the_agent_decisions(self) -> None:
        step = self._flat(self._step(_read(_SPEC), "\n1c. **"))
        agent = step[step.index("**Las decisiones del agente**") :]

        assert re.search(r"sin incluir el dominio, la arquitectura y los contratos, que son de la persona", agent)

    def test_the_principle_and_the_description_say_domain_architecture_and_contracts_are_always_asked(self) -> None:
        skill = _read(_SPEC)
        description = self._flat(skill.split("---")[1])
        principle = self._flat(
            skill[skill.index("- **El diseno se investiga y se interroga") :].split("\n- **Formato")[0]
        )

        for text in (description, principle):
            assert re.search(r"dominio, (la )?arquitectura y (los )?contratos se preguntan siempre", text)

    def test_the_design_reference_asks_file_class_and_test_strategy_only_when_the_target_conventions_do_not_cover_them(
        self,
    ) -> None:
        design = self._flat(_read(self._REFERENCES / "diseno.md"))

        assert re.search(r"nombres de ficheros y clases", design, re.IGNORECASE)
        assert re.search(r"estrategia de tests", design)
        assert re.search(r"solo se preguntan si las fuentes de convencion del repo destino no los cubren", design)

    def test_the_parent_repo_discovery_runs_before_the_first_question(self) -> None:
        skill = _read(_SPEC)

        discovery = skill.index("slice-runner discover-conventions <repo>")
        first_round = skill.index("**Disena investigando primero")

        assert discovery < first_round

    def test_the_skill_discovers_through_the_subcommands_and_names_no_script_nor_linked_directory(self) -> None:
        skill = _read(_SPEC)

        assert "slice-runner discover-conventions" in skill
        assert "slice-runner discover-controls" in skill
        for retired in ("discover_conventions", "discover_controles", "skills/slice-runner"):
            assert retired not in skill, f"slice-spec still names `{retired}`"

    def test_a_target_repo_is_discovered_as_soon_as_the_design_decides_there_is_work_in_it_and_before_its_contracts(
        self,
    ) -> None:
        skill = self._flat(_read(_SPEC))

        assert re.search(
            r"en cuanto el diseno decide que hay trabajo en (otro|ese) repo.{0,400}antes de decidir sus contratos",
            skill,
            re.DOTALL | re.IGNORECASE,
        )

    def test_the_design_reference_asks_the_person_only_what_is_ambiguous_and_changes_what_gets_built(self) -> None:
        design = self._flat(_read(self._REFERENCES / "diseno.md"))

        assert "**Es ambigua de verdad**" in design
        assert "**Cambia lo que se construye**" in design
        assert "Un caso raro solo entra con un puntero" in design
        assert "toda la frontera" not in design

    def test_the_slicing_step_waits_for_the_short_slicing_list_to_be_confirmed(self) -> None:
        step = self._flat(self._step(_read(_SPEC), "2d. **"))

        assert "lista corta" in step
        assert "espera confirmacion del troceo" in step

    def test_the_closing_step_of_the_design_publishes_the_decisions_with_the_code_and_the_criteria(self) -> None:
        step = self._step(_read(_SPEC), "1c. **")

        assert "decisiones" in step.lower()

    def test_the_slicing_step_routes_each_decision_to_its_slice_to_the_parent_or_to_the_exemption(self) -> None:
        step = self._step(_read(_SPEC), "2. **Trocea")

        assert "`DECISION:`" in step
        assert "`## Decisiones`" in step
        assert "DECISION: ninguna - <motivo>" in step

    def test_a_criterion_is_no_longer_allowed_to_fix_where_a_piece_lives(self) -> None:
        skill = self._flat(_read(_SPEC))

        assert "Un criterio puede fijar donde vive una pieza" not in skill
        assert re.search(r"donde vive una pieza es una decision", skill, re.IGNORECASE)

    def test_the_design_reference_has_a_visual_branch_that_names_the_section_the_chosen_variant_is_copied_to(
        self,
    ) -> None:
        reference = _read(self._REFERENCES / "diseno.md")
        branches = reference.split("## Lo que el agente recorre siempre")[1].split("## Cuando se acaba")[0]
        visual = self._flat(branches[branches.index("visual") :])

        assert _DESIGN_HEADING in visual, f"the visual branch of the design reference does not name {_DESIGN_HEADING}"
        assert re.search(r"variantes", visual)
        assert re.search(r"solo la (variante )?elegida", visual)
        assert "### <nombre>" in visual
        assert "<summary>" in visual

    def test_the_visual_branch_looks_for_the_palette_of_the_target_repo_before_the_first_mockup(self) -> None:
        reference = _read(self._REFERENCES / "diseno.md")
        branches = reference.split("## Lo que el agente recorre siempre")[1].split("## Cuando se acaba")[0]
        visual = self._flat(branches[branches.index("visual") :])

        assert re.search(r"paleta del repo destino.{0,200}antes de la primera maqueta", visual, re.IGNORECASE)

    def test_the_step_that_creates_the_spec_says_each_design_section_carries_only_the_chosen_variant(self) -> None:
        step = self._flat(self._step(_read(_SPEC), "5. **Crea"))

        assert re.search(r"cada `### <nombre>` lleva solo la variante elegida", step)


class TestTheJudgeDoesNotDowngradeAnUnmetCriterion:
    @staticmethod
    def _item_five() -> str:
        rubric = " ".join(_program_rubric().split())

        return rubric.split("5. **Conformidad con los criterios de aceptacion")[1].split("6. **Manipulacion de tests")[
            0
        ]

    def test_reading_the_code_does_not_accredit_a_criterion_no_test_pins_nor_lower_it_below_high(self) -> None:
        item = self._item_five()

        assert re.search(
            r"la lectura acotada sirve para encontrar incumplimientos, pero no acredita un criterio que ningun "
            r"test fija",
            item,
            re.IGNORECASE,
        )
        assert re.search(
            r"concluir por lectura que el codigo lo cumple no rebaja a `medium` ni a `low` un criterio sin test, "
            r"uno cuyo codigo no cumple su intencion ni un comportamiento que ningun criterio pidio: "
            r"los tres son `high`",
            item,
        )

    def test_the_evidence_of_an_unpinned_criterion_is_the_criterion_as_it_arrives_plus_the_missing_test(
        self,
    ) -> None:
        item = self._item_five()

        assert re.search(
            r"la evidencia de un criterio que ningun test fija es el criterio tal como llega en "
            r"\"criterios de aceptacion\" mas la ausencia de test en el diff, y ese hallazgo no baja por "
            r"\"Evidencia antes de bloquear\"",
            item,
            re.IGNORECASE,
        )
