from __future__ import annotations

from typing import Any

from textual.widgets import Tree


class NodeTreeWidget(Tree[dict[str, Any]]):
    def __init__(self, *args, **kwargs):
        super().__init__("OPC UA Objects", *args, **kwargs)

    def on_mount(self) -> None:
        self.border_title = "Node Tree"

    def set_tree_data(self, tree_data: dict[str, Any]) -> None:
        self.clear()
        self.root.label = self._fmt_label(tree_data)
        self.root.data = tree_data
        self._add_children(self.root, tree_data.get("children", []))
        self.root.expand()

    def _add_children(self, parent, children: list[dict[str, Any]]) -> None:
        for child in children:
            node = parent.add(self._fmt_label(child), data=child)
            self._add_children(node, child.get("children", []))

    @staticmethod
    def _fmt_label(item: dict[str, Any]) -> str:
        name = item.get("name", "?")
        node_id = item.get("id", "?")
        node_class = item.get("cls", "?")
        var_type = item.get("type")

        icon = "📁"
        if node_class == "Variable":
            icon = "📊"

        label = f"{icon} {name} [{node_id}] ({node_class})"
        if var_type:
            label += f" <{var_type}>"
        return label
