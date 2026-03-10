from __future__ import annotations

from typing import Any

from textual.widgets import Static


class NodeInfoPanelWidget(Static):
    def on_mount(self) -> None:
        self.border_title = "Node Details"
        self.update("[dim]No node selected — click a node in the tree[/dim]")

    def display_node(
        self,
        node_data: dict[str, Any],
        *,
        value_text: str | None = None,
        value_status: str | None = None,
    ) -> None:
        name = node_data.get("name", "?")
        node_id = node_data.get("id", "?")
        node_class = node_data.get("cls", "?")
        var_type = node_data.get("type")
        children = node_data.get("children", [])

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

        self.update("\n".join(lines))
