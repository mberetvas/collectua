from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Button, Static


class NodeInfoPanelWidget(Vertical):
    class CopyNodeIdRequested(Message):
        def __init__(self, node_id: str | None) -> None:
            super().__init__()
            self.node_id = node_id

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._current_node_id: str | None = None
        self._copy_feedback: str | None = None
        self._last_node_data: dict[str, Any] | None = None
        self._last_value_text: str | None = None
        self._last_value_status: str | None = None

    def compose(self) -> ComposeResult:
        yield Static("", id="node-info-details")
        with Horizontal(id="node-info-actions"):
            yield Button("Copy Node ID", id="copy-node-id-btn", variant="primary")

    def on_mount(self) -> None:
        self.border_title = "Node Details"
        self.query_one("#node-info-details", Static).update("[dim]No node selected — click a node in the tree[/dim]")
        self.query_one("#copy-node-id-btn", Button).disabled = True

    def set_copy_feedback(self, message: str) -> None:
        self._copy_feedback = message
        if self._last_node_data is not None:
            self._render_node(
                self._last_node_data, value_text=self._last_value_text, value_status=self._last_value_status
            )

    def display_node(
        self,
        node_data: dict[str, Any],
        *,
        value_text: str | None = None,
        value_status: str | None = None,
    ) -> None:
        self._last_node_data = node_data
        self._last_value_text = value_text
        self._last_value_status = value_status
        self._render_node(node_data, value_text=value_text, value_status=value_status)

    def _render_node(
        self,
        node_data: dict[str, Any],
        *,
        value_text: str | None = None,
        value_status: str | None = None,
    ) -> None:
        name = node_data.get("name", "?")
        node_id = str(node_data.get("id", "?"))
        node_class = node_data.get("cls", "?")
        var_type = node_data.get("type")
        children = node_data.get("children", [])

        self._current_node_id = node_id if node_id and node_id != "?" else None
        self.query_one("#copy-node-id-btn", Button).disabled = self._current_node_id is None

        icon = "📊" if node_class == "Variable" else "📁"

        lines = [
            f"{icon} [bold #8aff80]Name:[/]       {name}",
            f"   [bold #8aff80]Node ID:[/]    {node_id}",
            f"   [bold #8aff80]Class:[/]      {node_class}",
        ]

        if var_type:
            lines.append(f"   [bold #8aff80]Value Type:[/] {var_type}")

        if value_text is not None:
            lines.append(f"   [bold #8aff80]Value:[/]      {value_text}")
        if value_status:
            lines.append(f"   [dim]{value_status}[/dim]")
        if self._copy_feedback:
            lines.append(f"   [bold #ffbf4d]{self._copy_feedback}[/bold #ffbf4d]")

        if children:
            lines.append("")
            lines.append(f"   [bold #ffbf4d]Children ({len(children)}):[/]")
            for child in children:
                child_name = child.get("name", "?")
                child_cls = child.get("cls", "?")
                child_type = child.get("type")
                child_icon = "📊" if child_cls == "Variable" else "📁"
                entry = f"     {child_icon} [#8aff80]{child_name}[/] [dim]({child_cls})"
                if child_type:
                    entry += f" <{child_type}>"
                entry += "[/dim]"
                lines.append(entry)
        else:
            lines.append("")
            lines.append("   [dim]No children[/dim]")

        self.query_one("#node-info-details", Static).update("\n".join(lines))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "copy-node-id-btn":
            self.post_message(self.CopyNodeIdRequested(self._current_node_id))
