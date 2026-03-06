from __future__ import annotations

import json

from textual.widgets import Static


class ConfigPanel(Static):
    def on_mount(self) -> None:
        self.border_title = "Runtime Config"

    def set_config(self, data: dict) -> None:
        sanitized = data.copy()
        connection = sanitized.get("connection", {}).copy()
        if connection.get("password"):
            connection["password"] = "********"
        sanitized["connection"] = connection

        self.update(json.dumps(sanitized, indent=2))
