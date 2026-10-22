"""Invariants against the tree itself, not two copies of the same prose.

Two of the tests here scan the repo instead of comparing a script to a skill: that no call to an
external process is launched without a cap, and that every repo path cited in the docs still
exists. `CLAUDE.md` names the
cap on every external call one of the principles the pipeline does not break, and
`docs/conventions/como-se-escribe.md` cites this file as the contract of cited paths. The fourth
test pins what counts as "launching a process" for the cap check, so a scan that only knows
`subprocess.run` cannot pass silently as the whole rule. The fifth scans `conduct_slice.py` for the
same reason: it pins that every call which writes with the harness discards and retries a
`MeasuredCallError`, instead of trusting prose to keep a fourth such call from being added bare.
The sixth pins the fifth's own mechanism: a `self._x.y(...)` the scan has never seen counts as
harness-writing by default, so a step added later on a brand new port turns the suite red instead
of passing by omission the way naming only the three known calls would have.

The seventh scans every module of the program for a durable store composing its own path instead
of asking `DurableLedger` for one: a call to `ClaudeConfig.root()`, a `*.jsonl` literal, or the
segments `log`/`trace` cited next to `slice-runner` in the same path expression. It is not a list of
the stores that exist today -a well-formed new one that only names `DurableLedger` never trips it-,
which is what the eighth, its meta-test, proves against synthetic source: without it, a scan that
finds nothing and one that is broken read the same.

The ninth scans every module that builds a `DurableLedger` for the vocabulary of a harness turn
(`HarnessTurn`, `TurnLog`, `TurnPayload`): a turn's number, tool and target are what
`tool_use_log.py` already writes when a call ends, so a store that names that vocabulary would be
writing the same row twice. It is not a list of stores either, and the tenth, its meta-test, proves
against synthetic source that a ledger naming that vocabulary trips it and a well-formed one does
not.

The eleventh scans every class inheriting `LedgerRow`, `ReadableLedgerRow` or `StampedRow` for a
coordinate -`ts`, `repo`, `issue`, `slice_id`- declared again instead of taken from `StampedRow`,
the single base that now carries the four. It names what MAY redeclare a field, not what may not,
so the twelfth, its meta-test, proves a class the scan has never seen still turns red by default.
The thirteenth scans for the canonical slice text composed by hand -peeling `"slice-"` off a
string, or `:02d`-formatting an ordinal- anywhere outside `CanonicalSliceId`, the one place that
format is allowed to exist, and the fourteenth is its meta-test.

The fifteenth scans every module of the program for `AliasChoices`, the shape that let a payload
reread a key from an earlier generation of the log next to the one it writes today. With the
reader and the writer collapsed into the same model, nothing left has a reason to carry it: a
payload that uses it again is tolerating a shape this program no longer writes, which is the same
regression `MetricsLedgerRowPayload` used to be. It is not a list of today's offenders -a
well-formed payload that never imports `AliasChoices` never trips it-, which is what the
sixteenth, its meta-test, proves against synthetic source.
"""

from __future__ import annotations

import ast
import fnmatch
import re
import tomllib

import pytest
from conftest import _ROOT, _read, _tracked

from slice_runner.infrastructure.slice_implementer_brief import SliceImplementerBrief

_UNSCANNED = {
    "skills/slice-spec/references/observabilidad.md": "documenta rutas de otros repos",
    "docs/12-factor.md": "fechado: lo que se leyo un dia, no se actualiza",
    "docs/maturity-map.md": "fechado: lo que se leyo un dia, no se actualiza",
    "docs/research-agent-loops.md": "fechado: lo que se leyo un dia, no se actualiza",
}
"""What is not scanned at all, each for a reason about what the file IS.

`observabilidad.md` is a reference doc about OTHER repos -- every path in it belongs to the tree of
the repos it talks about, not to this one.
The three dated docs are what was read on a given day: `CLAUDE.md` declares that they are not
updated and that what they cite may already be retired, so a stale path there is the same point.
"""

_EXEMPT: dict[str, str] = {}
"""No token is exempt today.

The only exemption this ever needed was a path of the smoke fixture, which spoke in its own
coordinates while living under our tree; the smoke was retired on 2026-08-28. The map stays because
the check names what does NOT count rather than what does, and a new document that speaks in
someone else's coordinates would need its entry here rather than a widened scan.
"""

_BACKTICKED = re.compile(r"`([^`\n]+)`")
_PATHLIKE = re.compile(r"^[\w.][\w./-]*$")
"""What counts as a claim about this repo's tree.

The docs here do not use markdown links for local files; they cite paths in backticks. So the
thing to validate is not `[x](y)` -- there are none -- but every backticked token that claims
something about this tree. A token qualifies only when its first component is a tracked top-level
entry: that keeps bare filenames (`metrics.py`), paths in other repos (`other/metrics.py`),
and branch patterns (`slice/NN-name`) out by construction, instead of by an allowlist that would
have to grow forever.
"""


def _parent_dirs(path: str) -> list[str]:
    parts = path.split("/")[:-1]
    return ["/".join(parts[: index + 1]) for index in range(len(parts))]


def _claimed_repo_paths(markdown: str, top_level: frozenset[str]) -> set[str]:
    """Backticked tokens that read as a path into this repo's tree."""
    claimed = set()
    for raw in _BACKTICKED.findall(markdown):
        token = raw.strip().rstrip("/")
        if not _PATHLIKE.match(token) or "/" not in token:
            continue
        if token.split("/", 1)[0] in top_level:
            claimed.add(token)
    return claimed


@pytest.mark.integration
def test_every_repo_path_cited_in_the_docs_still_exists() -> None:
    """A path in the prose is a claim about the tree, and a rename breaks it silently.

    Not hypothetical: deleting a batch of design docs once left five dead pointers to them in the
    decision record. Nothing failed, and they stayed dead until this check existed.


    `git ls-files` reads the index, so a doc deleted in the worktree without staging the deletion is still
    listed. Reading it would raise here and bury the real assert under a traceback about the local mess,
    which is not what this test is about.
    """
    tracked = _tracked("*")
    top_level = frozenset(path.split("/", 1)[0] for path in tracked)
    known = set(tracked) | {parent for path in tracked for parent in _parent_dirs(path)}

    for skipped, reason in _UNSCANNED.items():
        assert skipped in known, (
            f"the unscanned entry `{skipped}` ({reason}) is gone; drop it from _UNSCANNED "
            f"instead of leaving a stale exemption that silently widens the check"
        )

    broken: dict[str, list[str]] = {}
    still_cited: set[str] = set()
    for source in _tracked("*.md"):
        if any(source == skip or source.startswith(f"{skip}/") for skip in _UNSCANNED):
            continue
        if not (_ROOT / source).exists():
            continue
        for claimed in _claimed_repo_paths(_read(_ROOT / source), top_level):
            if claimed in _EXEMPT:
                still_cited.add(claimed)
            elif claimed not in known:
                broken.setdefault(claimed, []).append(source)

    assert still_cited == set(_EXEMPT), (
        f"these exemptions are no longer cited anywhere and must be removed: {sorted(set(_EXEMPT) - still_cited)}"
    )
    assert not broken, "the docs cite paths that are not in the tree:\n" + "\n".join(
        f"  {path}  <- cited in {', '.join(sorted(sources))}" for path, sources in sorted(broken.items())
    )


_LAUNCHERS = _tracked("src/slice_runner/*.py", "skills/*/scripts/*.py", "tests/*.py")


_LAUNCHING_CALLS = {
    "subprocess": frozenset({"run", "call", "check_call", "check_output", "Popen"}),
    "os": frozenset({"system", "popen"}),
    "_subprocess": frozenset({"run", "call", "check_call", "check_output", "Popen"}),
}
"""Every spelling of "start an external process" in the stdlib this repo could reach for.

`Popen` and `os.system`/`os.popen` take no `timeout` at all, so they have no capped spelling and
always count as uncapped -- which is the point: the cap is not optional here.
"""


def _receiver_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "self":
        return node.attr

    return None


def _launches_a_process(node: ast.Call) -> bool:
    return isinstance(node.func, ast.Attribute) and node.func.attr in _LAUNCHING_CALLS.get(
        _receiver_name(node.func.value) or "", frozenset()
    )


def _uncapped_calls(source: str) -> list[int]:
    """Lines that launch an external process without a `timeout`, which is a call with no cap."""
    tree = ast.parse(source)
    called = (node for node in ast.walk(tree) if isinstance(node, ast.Call))

    return sorted(
        node.lineno
        for node in called
        if _launches_a_process(node) and not any(keyword.arg == "timeout" for keyword in node.keywords)
    )


@pytest.mark.integration
def test_no_call_to_an_external_process_is_launched_without_a_cap() -> None:
    """`CLAUDE.md` says every call to an external process carries a cap per call, and prose is not a cap.

    A call that never comes back hangs the whole run with no diagnosis and no bounded cost, and the
    yardstick that would catch it was written for the skills only, so nobody reviewing the program had
    anything to fail it with -- which is what happened while judging slice-17. The program funnels every
    launch through `LocalProcess`, so one uncapped `subprocess.run` anywhere here is one hole in a rule
    that otherwise holds by construction: this measures the tree instead of trusting the funnel.
    """
    uncapped = {path: lines for path in _LAUNCHERS if (lines := _uncapped_calls(_read(_ROOT / path)))}

    assert not uncapped, "these calls launch a process with no cap on how long it may take:\n" + "\n".join(
        f"  {path}: line(s) {', '.join(str(line) for line in lines)}" for path, lines in sorted(uncapped.items())
    )


def test_the_scan_counts_as_uncapped_every_way_of_launching_a_process_not_only_subprocess_run() -> None:
    """A yardstick that only knows one launcher measures the habit, not the rule.

    `subprocess.run` is what this repo happens to write today, so a scan that keys on it passes a
    `Popen`, a `check_output` or an `os.system` with no cap at all -- and the rule the scan exists to
    enforce says *every* call, not every call written the usual way. `Popen` and `os.system` take no
    `timeout`, so there is no capped spelling of them: they count as uncapped wherever they appear.
    """
    source = "\n".join(
        [
            "import os",
            "import subprocess",
            "subprocess.run(['x'], timeout=1)",
            "subprocess.run(['x'])",
            "subprocess.check_output(['x'])",
            "subprocess.Popen(['x'])",
            "os.system('x')",
        ]
    )

    assert _uncapped_calls(source) == [4, 5, 6, 7]


def test_the_scan_counts_a_launch_through_the_module_a_class_receives_and_still_asks_it_for_a_cap() -> None:
    source = "\n".join(
        [
            "class Edge:",
            "    def capped(self):",
            "        return self._subprocess.run(['x'], timeout=1)",
            "    def uncapped(self):",
            "        return self._subprocess.run(['x'])",
            "    def popen(self):",
            "        return self._subprocess.Popen(['x'])",
            "    def unrelated(self):",
            "        return self._other.run(['x'])",
        ]
    )

    assert _uncapped_calls(source) == [5, 7]


_CONDUCT_SLICE = "src/slice_runner/application/actions/conduct_slice.py"

_KNOWN_NOT_HARNESS_WRITING = {
    ("_budgets", "cost_exhausted"),
    ("_budgets", "exhausted"),
    ("_budgets", "wait_exhausted"),
    ("_catch_up", "execute"),
    ("_check_sources", "execute"),
    ("_clock", "sleep"),
    ("_close", "execute"),
    ("_commit", "execute"),
    ("_deliver", "execute"),
    ("_forum", "any_pull_request"),
    ("_forum", "pull_request_state"),
    ("_machine", "after"),
    ("_mount", "execute"),
    ("_mount_comparison", "execute"),
    ("_prechecks", "execute"),
    ("_pull_request", "body"),
    ("_pull_request", "commit_message"),
    ("_pull_request", "title"),
    ("_read_captures", "execute"),
    ("_read_ci", "execute"),
    ("_read_pull_request", "execute"),
    ("_record_closure", "execute"),
    ("_record_start", "execute"),
    ("_record_step", "execute"),
    ("_reopen", "execute"),
    ("_repository", "clear_run"),
    ("_repository", "flag_unmerged_pull_request"),
    ("_repository", "remove_label"),
    ("_repository", "write_label"),
    ("_repository", "write_malformed_response"),
    ("_repository", "write_precheck_reason"),
    ("_repository", "write_run"),
    ("_rescue", "execute"),
    ("_retire", "execute"),
    ("_run_controls", "execute"),
    ("_select", "execute"),
    ("_stage", "execute"),
}
"""Every other `self._x.y(...)` call in `conduct_slice.py`, named instead of guessed.

The scan cannot know from the syntax alone whether a brand new `self._x.y(...)` writes with the
harness: that is a fact about the type of `_x`, not about the call site. Naming what does NOT
write with it, instead of what does, is what makes a step added later without this treatment fall
on the unsafe side by default -- the opposite of the allowlist this replaced, which stayed silent
about anything it had never heard of. The cost is this list: a call that is genuinely not
harness-writing but is missing from it is misclassified as one, which only means it must be added
here, not that anything breaks.
"""


def _as_a_harness_writing_call(node: ast.AST) -> tuple[str, str] | None:
    if not (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Attribute)
        and isinstance(node.func.value.value, ast.Name)
        and node.func.value.value.id == "self"
    ):
        return None
    pair = (node.func.value.attr, node.func.attr)

    return None if pair in _KNOWN_NOT_HARNESS_WRITING else pair


def _catches_a_measured_call_error(handler: ast.ExceptHandler) -> bool:
    caught = handler.type
    if caught is None:
        return False
    names = caught.elts if isinstance(caught, ast.Tuple) else [caught]

    return any(isinstance(name, ast.Name) and name.id == "MeasuredCallError" for name in names)


def _harness_writing_calls(source: str) -> tuple[int, list[int]]:
    """Every call that writes with the harness, and the lines among them not guarded by a `try`."""
    total = 0
    unguarded: list[int] = []

    def _walk(node: ast.AST, *, guarded: bool) -> None:
        nonlocal total
        if isinstance(node, ast.Call) and _as_a_harness_writing_call(node) is not None:
            total += 1
            if not guarded:
                unguarded.append(node.lineno)
        if isinstance(node, ast.Try):
            body_guarded = guarded or any(_catches_a_measured_call_error(handler) for handler in node.handlers)
            for statement in node.body:
                _walk(statement, guarded=body_guarded)
            for other in (*node.handlers, *node.orelse, *node.finalbody):
                _walk(other, guarded=guarded)
            return
        for descendant in ast.iter_child_nodes(node):
            _walk(descendant, guarded=guarded)

    _walk(ast.parse(source), guarded=False)

    return total, unguarded


def test_no_call_that_writes_with_the_harness_in_conduct_slice_escapes_the_discard_and_retry_treatment() -> None:
    """A call to the harness is discarded the same way implementing and verifying already are.

    A rejection nobody catches does not stop at one call: it kills the whole run before anything is
    written or branched, which is the bug the slice-02 worktree-recovery mechanism exists to undo. The
    total pins the call count too, so a fourth harness-writing call added later without this treatment
    turns the suite red instead of slipping through unnoticed.
    """
    total, unguarded = _harness_writing_calls(_read(_ROOT / _CONDUCT_SLICE))

    assert not unguarded, (
        f"{_CONDUCT_SLICE} calls the harness at line(s) {', '.join(str(line) for line in unguarded)} "
        f"without discarding and retrying a MeasuredCallError, unlike every other harness-writing call"
    )
    assert total == 2, (
        f"{_CONDUCT_SLICE} calls the harness {total} time(s) to write with it, expected exactly 2 "
        f"(implement, verify): a call added or removed here changes what this pins"
    )


def test_a_self_call_not_named_safe_is_treated_as_harness_writing_even_if_the_scan_has_never_seen_it() -> None:
    """The scan cannot tell a new harness-writing step from a new safe one by syntax alone.

    So it does not try: anything on `self` that is not on `_KNOWN_NOT_HARNESS_WRITING` counts as
    harness-writing by default, which is the only way a fourth call added bare -- to a brand new
    port this file has never heard of -- turns the suite red instead of passing by omission, the
    way the three-item allowlist this replaced would have.
    """
    source = "\n".join(
        [
            "class ConductSlice:",
            "    def _implementing(self, progress):",
            "        try:",
            "            self._implement.execute(progress)",
            "        except MeasuredCallError:",
            "            pass",
            "        self._summarize.publish(progress)",
        ]
    )

    assert _harness_writing_calls(source) == (2, [7])


_NOT_A_DURABLE_STORE = {
    "src/slice_runner/infrastructure/durable_ledger.py": "es la pieza comun: compone la ruta bajo runs/ para los demas",
    "src/slice_runner/infrastructure/claude_config.py": (
        "resuelve la raiz de configuracion de la herramienta, no un almacen"
    ),
    "src/slice_runner/infrastructure/local_conversation_log.py": (
        "lee la transcripcion que escribe el harness bajo projects/, no una fila que este programa anexa"
    ),
    "src/slice_runner/infrastructure/local_plugin_registry.py": (
        "lee settings.json de la herramienta, no un log append-only"
    ),
    "src/slice_runner/infrastructure/local_skill_library.py": (
        "resuelve rutas de skills bajo la raiz de configuracion, no un log append-only"
    ),
    "src/slice_runner/infrastructure/control_logs_directory.py": (
        "el log de un control no es un almacen durable: no son filas JSON anexadas, es la salida de "
        "texto de un build, escrita entera de una vez, que alguien lee para arreglar lo que fallo"
    ),
}
"""What is exempt from the scan below, each for a reason about what the module IS.

Not a list of the durable stores that exist today: a store that never composes its own path -- it
only asks `DurableLedger` for one by name -- never trips the scan and needs no entry here.
"""


def _is_claude_config_root_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "root"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "ClaudeConfig"
    )


def _is_a_jsonl_literal(value: object) -> bool:
    return isinstance(value, str) and fnmatch.fnmatch(value, "*.jsonl")


def _div_chain_string_literals(node: ast.AST) -> list[str]:
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        return _div_chain_string_literals(node.left) + _div_chain_string_literals(node.right)
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    return []


def _cites_a_retired_segment_next_to_slice_runner(literals: list[str]) -> bool:
    return "slice-runner" in literals and ("log" in literals or "trace" in literals)


def _composes_its_own_durable_store_path(source: str) -> bool:
    """A module trips this by calling `ClaudeConfig.root()`, writing a `*.jsonl` literal, or citing

    `log`/`trace` next to `slice-runner` in the same tuple, list, set, or `/` chain -- the three
    shapes every durable store composed its own path with before it went through `DurableLedger`.
    """
    for node in ast.walk(ast.parse(source)):
        if _is_claude_config_root_call(node):
            return True
        if isinstance(node, ast.Constant) and _is_a_jsonl_literal(node.value):
            return True
        if isinstance(node, ast.Tuple | ast.List | ast.Set):
            literals = [elt.value for elt in node.elts if isinstance(elt, ast.Constant) and isinstance(elt.value, str)]
            if _cites_a_retired_segment_next_to_slice_runner(literals):
                return True
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            if _cites_a_retired_segment_next_to_slice_runner(_div_chain_string_literals(node)):
                return True

    return False


@pytest.mark.integration
def test_no_durable_store_composes_its_own_path_instead_of_asking_the_shared_ledger_for_one() -> None:
    """`infrastructure.md`: durable stores live under one directory and one naming pattern.

    Not hypothetical: before this test existed, four stores kept composing `("slice-runner", "log",
    "<name>.jsonl")` by hand next to the three that already went through `DurableLedger`, and nothing
    here would have caught an eighth store being born the same way outside the pattern.
    """
    candidates = [path for path in _tracked("src/slice_runner/*.py") if not path.startswith("src/slice_runner/tests/")]

    for exempt, reason in _NOT_A_DURABLE_STORE.items():
        assert exempt in candidates, (
            f"the exemption `{exempt}` ({reason}) is gone; drop it from _NOT_A_DURABLE_STORE "
            f"instead of leaving a stale exemption that silently widens the check"
        )

    offending = [
        path
        for path in candidates
        if path not in _NOT_A_DURABLE_STORE and _composes_its_own_durable_store_path(_read(_ROOT / path))
    ]

    assert not offending, "these modules compose their own durable-store path instead of asking `DurableLedger`:\n" + (
        "\n".join(f"  {path}" for path in offending)
    )


def test_the_scan_catches_every_shape_a_module_could_compose_its_own_durable_store_path_with() -> None:
    """A scan that finds nothing and a scan that is broken read the same without this.

    A well-formed new store that only names `DurableLedger` by constructor keyword must stay
    invisible to the scan -- turning this into a list of today's stores is exactly what the
    acceptance criteria this pins forbids.
    """
    calling_root = "\n".join(
        [
            "from slice_runner.infrastructure.claude_config import ClaudeConfig",
            "class Foo:",
            "    def elsewhere(self, name):",
            '        return ClaudeConfig.root() / "elsewhere" / name',
        ]
    )
    naming_a_jsonl_literal = 'LEDGER = "metrics.jsonl"'
    naming_a_jsonl_literal_through_an_f_string = "\n".join(
        [
            "class Foo:",
            "    def path(self, name):",
            '        return f"{name}.jsonl"',
        ]
    )
    citing_log_next_to_slice_runner = "\n".join(
        [
            "class Foo:",
            "    def path(self, root):",
            '        return root / "slice-runner" / "log"',
        ]
    )
    citing_trace_next_to_slice_runner_in_a_tuple = "\n".join(
        [
            "class Foo:",
            '    SEGMENTS = ("slice-runner", "trace")',
        ]
    )
    a_well_formed_new_store = "\n".join(
        [
            "from slice_runner.infrastructure.durable_ledger import DurableLedger",
            "class Foo:",
            "    def __init__(self):",
            '        self._ledger = DurableLedger(name="foo", row=FooPayload)',
        ]
    )

    assert _composes_its_own_durable_store_path(calling_root)
    assert _composes_its_own_durable_store_path(naming_a_jsonl_literal)
    assert _composes_its_own_durable_store_path(naming_a_jsonl_literal_through_an_f_string)
    assert _composes_its_own_durable_store_path(citing_log_next_to_slice_runner)
    assert _composes_its_own_durable_store_path(citing_trace_next_to_slice_runner_in_a_tuple)
    assert not _composes_its_own_durable_store_path(a_well_formed_new_store)


_TURN_VOCABULARY = frozenset({"HarnessTurn", "TurnLog", "TurnPayload"})
"""What a harness turn is called wherever it already lives, in `turn_log.py` and `turn_payload.py`."""


def _referenced_names(tree: ast.Module) -> set[str]:
    named = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    imports = (node for node in ast.walk(tree) if isinstance(node, ast.ImportFrom))
    imported = {alias.asname or alias.name for node in imports for alias in node.names}

    return named | imported


def _builds_a_durable_ledger_naming_a_turn(source: str) -> bool:
    """A module trips this by constructing `DurableLedger` while its tree also names a harness

    turn -- through an import, a type annotation, or the `row=` it hands the ledger.
    """
    tree = ast.parse(source)
    builds_a_ledger = any(
        isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "DurableLedger"
        for node in ast.walk(tree)
    )

    return builds_a_ledger and bool(_TURN_VOCABULARY & _referenced_names(tree))


@pytest.mark.integration
def test_no_durable_ledger_names_the_vocabulary_of_a_harness_turn() -> None:
    """`infrastructure.md`: a turn's number, tool and target is what the tool-use ledger already

    writes when a call ends, so anexing it again per turn would write the same row twice. This
    measures the tree instead of trusting that nobody wires a `LocalTurnLog` tomorrow.
    """
    candidates = [path for path in _tracked("src/slice_runner/*.py") if not path.startswith("src/slice_runner/tests/")]

    offending = [path for path in candidates if _builds_a_durable_ledger_naming_a_turn(_read(_ROOT / path))]

    assert not offending, "these modules build a durable ledger that names the turn vocabulary:\n" + (
        "\n".join(f"  {path}" for path in offending)
    )


_STAMPED_ROW_BASES = frozenset({"LedgerRow", "ReadableLedgerRow", "StampedRow"})
_COORDINATE_FIELDS = frozenset({"ts", "repo", "issue", "slice_id"})
_STAMPED_ROW_BASE_CLASSES = frozenset({"StampedRow"})

_MAY_REDECLARE_COORDINATES: dict[str, str] = {}
"""What is exempt from the scan below, each for a reason about what the class needs.

Empty on purpose: with the four coordinates obligatory on `StampedRow` and no payload left that
needs to tolerate any of them missing, no payload has a reason left to redeclare a coordinate.
`StampedRow` is not listed here: it never trips the scan, it is the one place the four fields are
declared for the tree to inherit.
"""


def _classes_inheriting_a_stamped_base(source: str) -> dict[str, ast.ClassDef]:
    found: dict[str, ast.ClassDef] = {}
    for node in ast.walk(ast.parse(source)):
        if (
            isinstance(node, ast.ClassDef)
            and node.name not in _STAMPED_ROW_BASE_CLASSES
            and any(isinstance(base, ast.Name) and base.id in _STAMPED_ROW_BASES for base in node.bases)
        ):
            found[node.name] = node

    return found


def _redeclared_coordinate_fields(class_node: ast.ClassDef) -> list[str]:
    return [
        statement.target.id
        for statement in class_node.body
        if isinstance(statement, ast.AnnAssign)
        and isinstance(statement.target, ast.Name)
        and statement.target.id in _COORDINATE_FIELDS
    ]


@pytest.mark.integration
def test_no_payload_declares_a_coordinate_of_its_own_instead_of_taking_it_from_stamped_row() -> None:
    """`infrastructure.md`: the four coordinates are declared in one place the payloads take them from.

    Not hypothetical: before `StampedRow` existed, `spend.jsonl` never carried a `slice_id` at all and
    `tool-uses.jsonl` never carried `ts`, `repo` or `issue` -- each payload wrote whichever subset of the
    four it felt like, because there was no single place asking the question. Naming what MAY redeclare a
    field, instead of what may not, is what makes a ninth payload copying `ts: str | None = None` by hand
    turn the suite red instead of passing by omission.
    """
    candidates: set[str] = set()
    offending: dict[str, list[str]] = {}
    for path in _tracked("src/slice_runner/*.py"):
        if path.startswith("src/slice_runner/tests/"):
            continue
        for name, class_node in _classes_inheriting_a_stamped_base(_read(_ROOT / path)).items():
            candidates.add(name)
            redeclared = _redeclared_coordinate_fields(class_node)
            if redeclared and name not in _MAY_REDECLARE_COORDINATES:
                offending[f"{path}::{name}"] = redeclared

    for exempt, reason in _MAY_REDECLARE_COORDINATES.items():
        assert exempt in candidates, (
            f"the exemption `{exempt}` ({reason}) is gone; drop it from _MAY_REDECLARE_COORDINATES "
            f"instead of leaving a stale exemption that silently widens the check"
        )

    assert not offending, "these classes redeclare a coordinate instead of taking it from StampedRow:\n" + (
        "\n".join(f"  {where}: {fields}" for where, fields in sorted(offending.items()))
    )


def test_the_scan_catches_a_redeclared_coordinate_even_on_a_class_it_has_never_seen() -> None:
    """A allow-list of what MAY redeclare only works if everything else counts as a violation by default.

    A class the scan has never heard of, inheriting `StampedRow` and declaring `ts` on its own, must turn
    red the same way a known offender would -- the point of naming exceptions instead of offenders.
    """
    redeclaring = "\n".join(
        [
            "from slice_runner.infrastructure.stamped_row import StampedRow",
            "class BrandNewPayload(StampedRow):",
            "    ts: str",
            "    session: str",
        ]
    )
    inheriting_cleanly = "\n".join(
        [
            "from slice_runner.infrastructure.stamped_row import StampedRow",
            "class BrandNewPayload(StampedRow):",
            "    session: str",
        ]
    )

    redeclaring_classes = _classes_inheriting_a_stamped_base(redeclaring)
    assert _redeclared_coordinate_fields(redeclaring_classes["BrandNewPayload"]) == ["ts"]

    clean_classes = _classes_inheriting_a_stamped_base(inheriting_cleanly)
    assert _redeclared_coordinate_fields(clean_classes["BrandNewPayload"]) == []


_CANONICAL_SLICE_ID_MODULE = "src/slice_runner/domain/canonical_slice_id.py"


def _composes_the_canonical_slice_text_by_hand(source: str) -> bool:
    """A module trips this by peeling `"slice-"` off a string, or by `:02d`-formatting an ordinal.

    Those are the two shapes every canonical slice identifier was composed with by hand before
    `CanonicalSliceId` existed to own the question.
    """
    for node in ast.walk(ast.parse(source)):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "removeprefix"
            and any(isinstance(arg, ast.Constant) and arg.value == "slice-" for arg in node.args)
        ):
            return True
        if isinstance(node, ast.FormattedValue) and node.format_spec is not None:
            for spec_piece in ast.walk(node.format_spec):
                if (
                    isinstance(spec_piece, ast.Constant)
                    and isinstance(spec_piece.value, str)
                    and "02d" in spec_piece.value
                ):
                    return True

    return False


@pytest.mark.integration
def test_no_module_other_than_canonical_slice_id_composes_the_canonical_slice_text_by_hand() -> None:
    """`infrastructure.md`: the text that names a slice comes from `SliceIdentity`, never composed in place.

    Not hypothetical: `SliceIdentity.branch` used to peel `"slice-"` off its own `canonical` string by
    hand, next to `MetricsLedgerRowPayload`'s own `f"...-{ordinal:02d}"` -- two redactions of the same
    format that only `CanonicalSliceId` should own now.
    """
    offending = [
        path
        for path in _tracked("src/slice_runner/*.py")
        if path != _CANONICAL_SLICE_ID_MODULE
        and not path.startswith("src/slice_runner/tests/")
        and _composes_the_canonical_slice_text_by_hand(_read(_ROOT / path))
    ]

    assert not offending, "these modules compose the canonical slice text by hand:\n" + (
        "\n".join(f"  {path}" for path in offending)
    )


def test_the_scan_catches_a_durable_ledger_that_names_the_turn_vocabulary_and_leaves_a_clean_one_be() -> None:
    """A well-formed ledger that never mentions a turn must stay invisible to the scan.

    Turning this into a list of today's stores is exactly what the acceptance criteria this pins
    forbids: what trips it is naming the vocabulary next to `DurableLedger`, not a fixed name.
    """
    a_turn_ledger = "\n".join(
        [
            "from slice_runner.infrastructure.turn_payload import TurnPayload",
            "from slice_runner.infrastructure.durable_ledger import DurableLedger",
            "class Foo:",
            "    def __init__(self):",
            '        self._ledger = DurableLedger(name="turns", row=TurnPayload)',
        ]
    )
    a_well_formed_ledger = "\n".join(
        [
            "from slice_runner.infrastructure.durable_ledger import DurableLedger",
            "class Foo:",
            "    def __init__(self):",
            '        self._ledger = DurableLedger(name="foo", row=FooPayload)',
        ]
    )

    assert _builds_a_durable_ledger_naming_a_turn(a_turn_ledger)
    assert not _builds_a_durable_ledger_naming_a_turn(a_well_formed_ledger)


def test_the_scan_catches_every_shape_a_module_could_compose_the_canonical_slice_text_with() -> None:
    peeling_the_prefix_off = "\n".join(
        [
            "class Foo:",
            "    def branch(self, canonical):",
            '        return canonical.removeprefix("slice-")',
        ]
    )
    formatting_the_ordinal = "\n".join(
        [
            "class Foo:",
            "    def canonical(self, ordinal):",
            '        return f"slice-{ordinal:02d}"',
        ]
    )
    an_unrelated_removeprefix = "\n".join(
        [
            "class Foo:",
            "    def instruction(self, stripped):",
            '        return stripped.removeprefix("RETRY: ")',
        ]
    )
    an_unrelated_format_spec = "\n".join(
        [
            "class Foo:",
            "    def rendered(self, cost):",
            '        return f"{cost:.2f}"',
        ]
    )

    assert _composes_the_canonical_slice_text_by_hand(peeling_the_prefix_off)
    assert _composes_the_canonical_slice_text_by_hand(formatting_the_ordinal)
    assert not _composes_the_canonical_slice_text_by_hand(an_unrelated_removeprefix)
    assert not _composes_the_canonical_slice_text_by_hand(an_unrelated_format_spec)


def _uses_alias_choices(source: str) -> bool:
    """A module trips this by importing or naming `AliasChoices` anywhere in its tree.

    Its only job was rereading a key from an earlier generation of the log next to the one the
    program writes today. With the reader and the writer collapsed into the same model, a payload
    that still names it is tolerating a shape this program no longer writes.
    """
    return "AliasChoices" in _referenced_names(ast.parse(source))


@pytest.mark.integration
def test_no_payload_of_the_program_rereads_an_earlier_shape_with_alias_choices() -> None:
    """`infrastructure.md`: a contract we fix ourselves has no earlier form left to tolerate.

    Not hypothetical: `MetricsLedgerRowPayload` carried nine of these to reread the Spanish keys a
    retired script used to write, and `SeverityCountPayload` carried three more for `alta`/`media`/
    `baja`. This measures the tree instead of trusting that nobody reaches for the same shape the
    next time a key changes.
    """
    candidates = [path for path in _tracked("src/slice_runner/*.py") if not path.startswith("src/slice_runner/tests/")]

    offending = [path for path in candidates if _uses_alias_choices(_read(_ROOT / path))]

    assert not offending, "these modules use AliasChoices to reread an earlier generation's key:\n" + (
        "\n".join(f"  {path}" for path in offending)
    )


def test_the_scan_catches_alias_choices_wherever_it_is_imported_or_used() -> None:
    importing_it = "\n".join(
        [
            "from pydantic import AliasChoices, Field",
            "class Foo:",
            "    x: int = Field(validation_alias=AliasChoices('x', 'y'))",
        ]
    )
    a_well_formed_payload = "\n".join(
        [
            "from pydantic import Field",
            "class Foo:",
            "    x: int",
        ]
    )

    assert _uses_alias_choices(importing_it)
    assert not _uses_alias_choices(a_well_formed_payload)


_BRIEF_PROHIBITIONS_HEADING = "## Lo que NO tocas"


def _executables_not_forbidden(brief: str, executables: frozenset[str]) -> list[str]:
    start = brief.index(_BRIEF_PROHIBITIONS_HEADING) + len(_BRIEF_PROHIBITIONS_HEADING)
    following = re.search(r"^## ", brief[start:], flags=re.MULTILINE)
    section = brief[start : start + following.start()] if following else brief[start:]

    return sorted(name for name in executables if f"`{name}`" not in section)


def test_the_implementer_brief_forbids_launching_any_executable_of_the_program() -> None:
    declared = tomllib.loads(_read(_ROOT / "pyproject.toml"))["project"]["scripts"]

    assert declared, "pyproject.toml declares no executable, so this invariant measures nothing"
    assert not _executables_not_forbidden(SliceImplementerBrief.TEXT, frozenset(declared)), (
        "the implementer brief does not forbid these executables of the program under "
        f"`{_BRIEF_PROHIBITIONS_HEADING}`: the implementer could verify itself and spend outside the slice budget"
    )


def test_the_brief_scan_does_not_count_a_mention_outside_the_section_as_a_prohibition() -> None:
    mentioned_elsewhere = "\n".join(
        [
            "## Lo que recibes",
            "`slice-runner` se menciona aqui.",
            _BRIEF_PROHIBITIONS_HEADING,
            "- `git`.",
            "## Lo que devuelves",
        ]
    )
    forbidden_in_the_section = "\n".join(
        [
            "## Lo que recibes",
            _BRIEF_PROHIBITIONS_HEADING,
            "- `slice-runner`.",
            "## Lo que devuelves",
        ]
    )
    executables = frozenset({"slice-runner"})

    assert _executables_not_forbidden(mentioned_elsewhere, executables) == ["slice-runner"]
    assert _executables_not_forbidden(forbidden_in_the_section, executables) == []
