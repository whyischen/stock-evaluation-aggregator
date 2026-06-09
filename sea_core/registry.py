from __future__ import annotations

from sea_core.config import DEFAULT_PLUGINS
from sea_core.models import EvaluationTask, PluginManifest


class PluginRegistry:
    def __init__(self, manifests: list[PluginManifest] | None = None) -> None:
        self._plugins = {plugin.plugin_id: plugin for plugin in (manifests or DEFAULT_PLUGINS)}

    def list_plugins(self) -> list[PluginManifest]:
        return list(self._plugins.values())

    def get(self, plugin_id: str) -> PluginManifest | None:
        return self._plugins.get(plugin_id)

    def select_for_task(self, task: EvaluationTask) -> list[PluginManifest]:
        selected_ids = set(task.plugin_ids or [])
        plugins = []
        for plugin in self._plugins.values():
            if not plugin.enabled:
                continue
            if selected_ids and plugin.plugin_id not in selected_ids:
                continue
            if not plugin.supports_market(task.resolved_market):
                continue
            plugins.append(plugin)
        return plugins

