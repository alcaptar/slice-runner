from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.closed_slice_metrics import ClosedSliceMetrics
    from slice_runner.domain.closed_slice_record import ClosedSliceRecord
    from slice_runner.domain.closed_slice_scope import ClosedSliceScope
    from slice_runner.domain.grouped_metrics import GroupedMetrics
    from slice_runner.domain.measurement import Measurement
    from slice_runner.domain.role_spend import RoleSpend
    from slice_runner.domain.slice_rates import SliceRates
    from slice_runner.domain.spend_averages import SpendAverages


class ClosedSliceMetricsView:
    WIDTH = 480
    HEIGHT = 220

    @classmethod
    def rendered(
        cls,
        *,
        scope: ClosedSliceScope,
        records: tuple[ClosedSliceRecord, ...],
        role_spend: tuple[RoleSpend, ...],
        metrics: ClosedSliceMetrics,
    ) -> str:
        return (
            '<!doctype html><html><head><meta charset="utf-8"><title>slice-runner metrics</title></head><body>'
            f"{cls._header(scope=scope, records=records)}"
            f"{cls._gaps()}"
            f"{cls._rates_section(metrics)}"
            f"{cls._duplicates(records)}"
            f"{cls._cost_against_size(records)}"
            f"{cls._spend_by_role(role_spend)}"
            f"{cls._rounds_over_time(records)}"
            "</body></html>"
        )

    @staticmethod
    def _header(*, scope: ClosedSliceScope, records: tuple[ClosedSliceRecord, ...]) -> str:
        named_repo = scope.repo or "every repo"
        return (
            f"<section><h1>slice-runner metrics</h1>"
            f"<p>{named_repo}, from {scope.since.isoformat()} to {scope.until.isoformat()}: "
            f"{len(records)} closed slice(s)</p>"
            "</section>"
        )

    @staticmethod
    def _gaps() -> str:
        return (
            "<section><h2>what this view cannot say</h2><ul>"
            "<li>configuration: budgets and models by role travel as the snapshot the run closed with, "
            "and today every run shares the same defaults, so no variation is shown yet</li>"
            "</ul></section>"
        )

    @staticmethod
    def _duplicates(records: tuple[ClosedSliceRecord, ...]) -> str:
        counted: dict[tuple[str, int, str], int] = {}
        for record in records:
            key = (record.repo, record.issue, record.slice_id)
            counted[key] = counted.get(key, 0) + 1

        repeated = {key: count for key, count in counted.items() if count > 1}
        if not repeated:
            return "<section><h2>slices closed more than once</h2><p>no slice was recorded more than once</p></section>"

        rows = "".join(
            f'<li data-repo="{repo}" data-issue="{issue}" data-slice-id="{slice_id}" data-rows="{count}">'
            f"{repo}#{issue} {slice_id}: {count} rows</li>"
            for (repo, issue, slice_id), count in repeated.items()
        )
        return f"<section><h2>slices closed more than once</h2><ul>{rows}</ul></section>"

    @classmethod
    def _cost_against_size(cls, records: tuple[ClosedSliceRecord, ...]) -> str:
        measured = tuple(record for record in records if record.diff is not None and record.spend is not None)
        if not measured:
            return (
                "<section><h2>cost against size</h2>"
                "<p>no slice in this window measured both its size and its spend</p></section>"
            )

        sizes = tuple(record.diff.lines_added + record.diff.lines_deleted for record in measured)  # type: ignore[union-attr]
        widest = max(sizes) or 1
        costliest = max(record.spend.cost_usd for record in measured) or 1  # type: ignore[union-attr]
        points = "".join(
            f'<circle data-slice-id="{record.slice_id}" data-lines="{lines}" '
            f'data-cost-usd="{record.spend.cost_usd}" '  # type: ignore[union-attr]
            f'cx="{cls._scaled(lines, widest, cls.WIDTH)}" '
            f'cy="{cls.HEIGHT - cls._scaled(record.spend.cost_usd, costliest, cls.HEIGHT)}" r="4"/>'  # type: ignore[union-attr]
            for record, lines in zip(measured, sizes, strict=True)
        )
        return (
            "<section><h2>cost against size</h2>"
            f'<svg viewBox="0 0 {cls.WIDTH} {cls.HEIGHT}" width="{cls.WIDTH}" height="{cls.HEIGHT}">{points}</svg>'
            "</section>"
        )

    @classmethod
    def _spend_by_role(cls, role_spend: tuple[RoleSpend, ...]) -> str:
        if not role_spend:
            return "<section><h2>spend by role</h2><p>no call was traced in this window</p></section>"

        costliest = max(entry.spend.cost_usd for entry in role_spend) or 1
        bar_width = cls.WIDTH / len(role_spend)
        bars = "".join(
            f'<rect data-step="{entry.step}" data-cost-usd="{entry.spend.cost_usd}" '
            f'x="{index * bar_width}" y="{cls.HEIGHT - cls._scaled(entry.spend.cost_usd, costliest, cls.HEIGHT)}" '
            f'width="{bar_width * 0.8}" height="{cls._scaled(entry.spend.cost_usd, costliest, cls.HEIGHT)}"/>'
            for index, entry in enumerate(role_spend)
        )
        return (
            "<section><h2>spend by role</h2>"
            f'<svg viewBox="0 0 {cls.WIDTH} {cls.HEIGHT}" width="{cls.WIDTH}" height="{cls.HEIGHT}">{bars}</svg>'
            "</section>"
        )

    @classmethod
    def _rounds_over_time(cls, records: tuple[ClosedSliceRecord, ...]) -> str:
        if not records:
            return "<section><h2>rounds over time</h2><p>no slice was closed in this window</p></section>"

        ordered = sorted(records, key=lambda record: record.ts)
        widest = (ordered[-1].ts - ordered[0].ts).total_seconds() or 1
        tallest = max(record.implement_retries for record in ordered) or 1
        points = "".join(
            f'<circle data-slice-id="{record.slice_id}" data-ts="{record.ts.isoformat()}" '
            f'data-rounds="{record.implement_retries}" '
            f'cx="{cls._scaled((record.ts - ordered[0].ts).total_seconds(), widest, cls.WIDTH)}" '
            f'cy="{cls.HEIGHT - cls._scaled(record.implement_retries, tallest, cls.HEIGHT)}" r="4"/>'
            for record in ordered
        )
        return (
            "<section><h2>rounds over time</h2>"
            f'<svg viewBox="0 0 {cls.WIDTH} {cls.HEIGHT}" width="{cls.WIDTH}" height="{cls.HEIGHT}">{points}</svg>'
            "</section>"
        )

    @staticmethod
    def _scaled(value: float, widest: float, span: int) -> float:
        return round((value / widest) * span, 2)

    @classmethod
    def _rates_section(cls, metrics: ClosedSliceMetrics) -> str:
        return (
            "<section><h2>rates</h2>"
            f"<ul>{cls._rate_rows(metrics.rates)}</ul>"
            f"<ul>{cls._spend_rows(metrics.spend)}</ul>"
            f"<ul>{cls._discard_rows(metrics)}</ul>"
            f"{cls._grouped_section('by model', 'model', metrics.by_model)}"
            f"{cls._grouped_section('by variant', 'variant', metrics.by_variant)}"
            "</section>"
        )

    @classmethod
    def _rate_rows(cls, rates: SliceRates) -> str:
        named = (
            ("verifier_fail", rates.verifier_fail),
            ("blocked_by_controls", rates.blocked_by_controls),
            ("first_attempt", rates.first_attempt),
            ("implement_retries", rates.implement_retries),
            ("verify_discards", rates.verify_discards),
            ("ci_red", rates.ci_red),
        )
        return "".join(
            f'<li data-rate="{name}" data-samples="{measurement.samples}">{name}: {cls._measurement(measurement)}</li>'
            for name, measurement in named
        )

    @classmethod
    def _spend_rows(cls, spend: SpendAverages) -> str:
        named = (
            ("cost_usd", spend.cost_usd),
            ("turns", spend.turns),
            ("duration_ms", spend.duration_ms),
            ("cache_read_tokens", spend.cache_read_tokens),
            ("input_tokens", spend.input_tokens),
            ("output_tokens", spend.output_tokens),
        )
        return "".join(
            f'<li data-spend="{name}" data-samples="{measurement.samples}">{name}: {cls._measurement(measurement)}</li>'
            for name, measurement in named
        )

    @staticmethod
    def _discard_rows(metrics: ClosedSliceMetrics) -> str:
        return "".join(
            f'<li data-cause="{tally.label}" data-count="{tally.count}" data-samples="{tally.samples}">'
            f"{tally.label}: {tally.count}</li>"
            for tally in metrics.discards.tallies
        )

    @classmethod
    def _grouped_section(cls, title: str, group_kind: str, groups: tuple[GroupedMetrics, ...]) -> str:
        rows = "".join(
            f'<li data-group="{group_kind}" data-label="{group.label}">'
            f"{group.label}: first attempt {cls._measurement(group.rates.first_attempt)}, "
            f"cost {cls._measurement(group.spend.cost_usd)}</li>"
            for group in groups
        )
        return f"<h3>{title}</h3><ul>{rows}</ul>"

    @staticmethod
    def _measurement(measurement: Measurement) -> str:
        if measurement.value is None:
            return f"no data ({measurement.samples} samples)"

        return f"{measurement.value} ({measurement.samples} samples)"
