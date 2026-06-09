from __future__ import annotations

from sea_core.models import Direction, EvalReport, EvaluationTask, PluginManifest, PluginResult, PluginStatus


def build_report(
    task: EvaluationTask,
    results: list[PluginResult],
    manifests: list[PluginManifest],
) -> EvalReport:
    manifest_by_id = {manifest.plugin_id: manifest for manifest in manifests}
    successful = [result for result in results if result.status == PluginStatus.SUCCESS]
    failed = [result for result in results if result.status != PluginStatus.SUCCESS]

    direction_counts = {direction.value: 0 for direction in Direction}
    for result in successful:
        direction_counts[result.direction.value] += 1

    weighted_score = _weighted_score(successful, manifest_by_id)
    consensus_level = _consensus_level(successful)
    divergence_notes = _divergence_notes(successful, failed)

    return EvalReport(
        ticker=task.ticker,
        eval_date=task.eval_date,
        market=task.resolved_market,
        results=results,
        success_count=len(successful),
        failed_count=len(failed),
        direction_counts=direction_counts,
        consensus_level=consensus_level,
        weighted_score=weighted_score,
        divergence_notes=divergence_notes,
    )


def _weighted_score(results: list[PluginResult], manifests: dict[str, PluginManifest]) -> float | None:
    numerator = 0.0
    denominator = 0.0
    for result in results:
        if result.direction == Direction.UNKNOWN:
            continue
        weight = manifests.get(result.plugin_id).weight if manifests.get(result.plugin_id) else 1.0
        numerator += result.direction.score_value * result.confidence * weight
        denominator += weight
    if denominator == 0:
        return None
    return max(-1.0, min(1.0, numerator / denominator))


def _consensus_level(results: list[PluginResult]) -> str:
    directions = [result.direction for result in results if result.direction != Direction.UNKNOWN]
    if not directions:
        return "none"
    if len(set(directions)) == 1:
        return "strong"
    majority = max(directions.count(direction) for direction in set(directions))
    if majority / len(directions) > 0.6:
        return "moderate"
    return "diverged"


def _divergence_notes(successful: list[PluginResult], failed: list[PluginResult]) -> list[str]:
    notes: list[str] = []
    directions = {result.direction for result in successful if result.direction != Direction.UNKNOWN}
    if len(directions) > 1:
        notes.append("Successful plugins returned different directions.")
    if failed:
        notes.append(f"{len(failed)} plugin(s) did not return a successful result.")
    return notes

