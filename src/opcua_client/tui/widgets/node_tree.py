from __future__ import annotations

from typing import Any

from textual.widgets import Tree


class NodeTreeWidget(Tree[dict[str, Any]]):
    PLACEHOLDER_LABEL = "⏳ Loading..."

    def __init__(self, *args, **kwargs):
        super().__init__("OPC UA Objects", *args, **kwargs)
        self._selected_node_ids: set[str] = set()

    def on_mount(self) -> None:
        self.border_title = "Node Tree"

    def set_tree_data(self, tree_data: dict[str, Any]) -> None:
        self._selected_node_ids.clear()
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
            node = parent.add(
                self._fmt_label(child, selected=self._is_selected(child)), data=child, allow_expand=allow_expand
            )
            self.add_children(node, child_items)
            if allow_expand and not child_items:
                node.add(self.PLACEHOLDER_LABEL, data={"_placeholder": True}, allow_expand=False)

    def toggle_cursor_selection(self) -> tuple[str | None, bool]:
        """Toggle selection state for the currently focused tree node.

        Returns:
            Tuple of `(node_id, is_selected_after_toggle)`. If no valid node is
            focused, returns `(None, False)`.
        """
        node = self.cursor_node
        if node is None:
            return None, False
        return self.toggle_node_selection(node)

    def toggle_node_selection(self, tree_node) -> tuple[str | None, bool]:
        """Toggle selection state for a concrete tree node.

        Args:
            tree_node: A `TreeNode` instance from this tree.

        Returns:
            Tuple of `(node_id, is_selected_after_toggle)`. If the node is not
            selectable or has no OPC UA Node ID, returns `(None, False)`.
        """
        if not self.is_selectable_node(tree_node):
            return None, False

        data = getattr(tree_node, "data", None)
        if not isinstance(data, dict):
            return None, False

        node_id = str(data.get("id", ""))
        if not node_id:
            return None, False

        if node_id in self._selected_node_ids:
            self._selected_node_ids.remove(node_id)
            is_selected = False
        else:
            self._selected_node_ids.add(node_id)
            is_selected = True

        tree_node.set_label(self._fmt_label(data, selected=is_selected))
        return node_id, is_selected

    def clear_selected_nodes(self) -> int:
        """Clear all selected nodes and refresh their labels.

        Returns:
            Number of selections cleared.
        """
        cleared_count = len(self._selected_node_ids)
        if cleared_count == 0:
            return 0

        self._selected_node_ids.clear()
        self.refresh_labels()
        return cleared_count

    def get_selected_node_ids(self) -> list[str]:
        """Return selected OPC UA Node IDs in visible tree order."""
        selected_in_order: list[str] = []
        for tree_node in self._iter_nodes(self.root):
            data = getattr(tree_node, "data", None)
            if not isinstance(data, dict):
                continue
            node_id = str(data.get("id", ""))
            if node_id and node_id in self._selected_node_ids:
                selected_in_order.append(node_id)
        return selected_in_order

    def refresh_labels(self) -> None:
        """Re-render labels for all non-placeholder nodes."""
        for tree_node in self._iter_nodes(self.root):
            if not self.is_selectable_node(tree_node):
                continue
            data = getattr(tree_node, "data", None)
            if not isinstance(data, dict):
                continue
            tree_node.set_label(self._fmt_label(data, selected=self._is_selected(data)))

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

    def is_selectable_node(self, tree_node) -> bool:
        """Return `True` when the tree node can participate in bulk selection."""
        data = getattr(tree_node, "data", None)
        if not isinstance(data, dict):
            return False
        if data.get("_placeholder") or data.get("_load_error"):
            return False
        return bool(str(data.get("id", "")))

    def _iter_nodes(self, tree_node):
        yield tree_node
        for child in tree_node.children:
            yield from self._iter_nodes(child)

    def _is_selected(self, item: dict[str, Any]) -> bool:
        node_id = str(item.get("id", ""))
        return bool(node_id) and node_id in self._selected_node_ids

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
    def _fmt_label(item: dict[str, Any], *, selected: bool = False) -> str:
        name = item.get("name", "?")
        node_id = item.get("id", "?")
        node_class = item.get("cls", "?")
        var_type = item.get("type")

        icon = "📁"
        if node_class == "Variable":
            icon = "📊"
        elif node_class == "Method":
            icon = "⚙"

        selection_prefix = "☑ " if selected else ""
        label = f"{selection_prefix}{icon} {name} [{node_id}] ({node_class})"
        if var_type:
            label += f" <{var_type}>"
        return label
