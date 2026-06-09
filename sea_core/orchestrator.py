from __future__ import annotations

import asyncio

from sea_core.models import EvalReport, EvaluationTask, PluginHealth, PluginManifest
from sea_core.plugin_client import AdapterPluginClient, HttpPluginClient, MockPluginClient, timeout_result
from sea_core.registry import PluginRegistry
from sea_core.report import build_report


class Orchestrator:
    def __init__(self, registry: PluginRegistry | None = None) -> None:
        self.registry = registry or PluginRegistry()
        self._mock_client = MockPluginClient()
        self._http_client = HttpPluginClient()
        self._adapter_client = AdapterPluginClient()

    async def evaluate(self, task: EvaluationTask) -> EvalReport:
        manifests = self.registry.select_for_task(task)
        results = await asyncio.gather(*(self._evaluate_one(manifest, task) for manifest in manifests))
        return build_report(task, results, manifests)

    async def health(self) -> list[PluginHealth]:
        manifests = self.registry.list_plugins()
        return await asyncio.gather(*(self._client_for(manifest).health(manifest) for manifest in manifests))

    def list_plugins(self) -> list[PluginManifest]:
        return self.registry.list_plugins()

    async def _evaluate_one(self, manifest: PluginManifest, task: EvaluationTask):
        client = self._client_for(manifest)
        try:
            return await asyncio.wait_for(
                client.evaluate(manifest, task),
                timeout=manifest.timeout_seconds,
            )
        except TimeoutError:
            return timeout_result(manifest, task, int(manifest.timeout_seconds * 1000))

    def _client_for(self, manifest: PluginManifest):
        if manifest.transport == "http":
            return self._http_client
        if manifest.transport == "adapter":
            return self._adapter_client
        return self._mock_client
