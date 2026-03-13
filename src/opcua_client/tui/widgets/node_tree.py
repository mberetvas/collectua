from __future__ import annotations

from typing import Any

from textual.widgets import Tree


class NodeTreeWidget(Tree[dict[str, Any]]):
    PLACEHOLDER_LABEL = "⏳ Loading..."

    def __init__(self, *args, **kwargs):
        super().__init__("OPC UA Objects", *args, **kwargs)

    def on_mount(self) -> None:
        self.border_title = "Node Tree"

    def set_tree_data(self, tree_data: dict[str, Any]) -> None:
        self.clear()
        self.root.label = self._fmt_label(tree_data)
        self.root.data = tree_data
        self.add_children(self.root, tree_data.get("children", []))
        self.root.expand()

    def add_children(self, parent, children: list[dict[str, Any]]) -> None:
        for child in children:
            child_items = child.get("children", [])
            expandable = bool(child_items) or bool(child.get("expandable"))
            allow_expand = child.get("cls") == "Object" and expandable
            node = parent.add(self._fmt_label(child), data=child, allow_expand=allow_expand)
            self.add_children(node, child_items)
            if allow_expand and not child_items:
                node.add(self.PLACEHOLDER_LABEL, data={"_placeholder": True}, allow_expand=False)

    def remove_placeholder(self, tree_node) -> bool:
        removed = False
        for child in list(tree_node.children):
            data = getattr(child, "data", None)
            if isinstance(data, dict) and data.get("_placeholder"):
                child.remove()
                removed = True
        return removed

    def has_placeholder(self, tree_node) -> bool:
        for child in tree_node.children:
            data = getattr(child, "data", None)
            if isinstance(data, dict) and data.get("_placeholder"):
                return True
        return False

    def is_placeholder_node(self, tree_node) -> bool:
        data = getattr(tree_node, "data", None)
        return isinstance(data, dict) and data.get("_placeholder") is True

    def focus_node(self, tree_node) -> bool:
        if tree_node is None:
            return False
        self.move_cursor(tree_node)
        self.select_node(tree_node)
        return True

    def _first_navigable_child(self, tree_node):
        for child in tree_node.children:
            if not self.is_placeholder_node(child):
                return child
        return None

    def focus_first_child(self, tree_node) -> bool:
        child = self._first_navigable_child(tree_node)
        return self.focus_node(child)

    def focus_parent(self, tree_node) -> bool:
        parent = getattr(tree_node, "parent", None)
        if parent is None:
            return False
        return self.focus_node(parent)

    def focus_previous_sibling(self, tree_node) -> bool:
        parent = getattr(tree_node, "parent", None)
        if parent is None:
            return False

        siblings = [child for child in parent.children if not self.is_placeholder_node(child)]
        try:
            index = siblings.index(tree_node)
        except ValueError:
            return False

        if index <= 0:
            return False
        return self.focus_node(siblings[index - 1])

    def focus_next_sibling(self, tree_node) -> bool:
        parent = getattr(tree_node, "parent", None)
        if parent is None:
            return False

        siblings = [child for child in parent.children if not self.is_placeholder_node(child)]
        try:
            index = siblings.index(tree_node)
        except ValueError:
            return False

        if index >= len(siblings) - 1:
            return False
        return self.focus_node(siblings[index + 1])

    @staticmethod
    def _fmt_label(item: dict[str, Any]) -> str:
        name = item.get("name", "?")
        node_id = item.get("id", "?")
        node_class = item.get("cls", "?")
        var_type = item.get("type")

        icon = "📁"
        if node_class == "Variable":
            icon = "📊"
        elif node_class == "Method":
            icon = "⚙"

        label = f"{icon} {name} [{node_id}] ({node_class})"
        if var_type:
            label += f" <{var_type}>"
        return label
