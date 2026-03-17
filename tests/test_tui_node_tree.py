from __future__ import annotations

from opcua_client.tui.widgets.node_tree import NodeTreeWidget


def _tree_fixture() -> dict[str, object]:
    return {
        "id": "ns=0;i=85",
        "name": "Objects",
        "cls": "Object",
        "children": [
            {
                "id": 'ns=3;s="_707ZMA"."CounterCMA"',
                "name": "CounterCMA",
                "cls": "Variable",
                "children": [],
            },
            {
                "id": 'ns=3;s="_707ZMA"."CounterSPA"',
                "name": "CounterSPA",
                "cls": "Variable",
                "children": [],
            },
        ],
    }


def test_selected_node_ids_are_returned_in_tree_order() -> None:
    tree = NodeTreeWidget()
    tree.set_tree_data(_tree_fixture())

    second = tree.root.children[1]
    first = tree.root.children[0]

    tree.toggle_node_selection(second)
    tree.toggle_node_selection(first)

    assert tree.get_selected_node_ids() == [
        'ns=3;s="_707ZMA"."CounterCMA"',
        'ns=3;s="_707ZMA"."CounterSPA"',
    ]


def test_placeholder_nodes_are_not_selectable() -> None:
    tree = NodeTreeWidget()
    tree.set_tree_data(
        {
            "id": "ns=0;i=85",
            "name": "Objects",
            "cls": "Object",
            "children": [
                {
                    "id": 'ns=3;s="_707ZMA"',
                    "name": "_707ZMA",
                    "cls": "Object",
                    "children": [],
                    "expandable": True,
                }
            ],
        }
    )

    obj = tree.root.children[0]
    placeholder = obj.children[0]

    node_id, is_selected = tree.toggle_node_selection(placeholder)

    assert node_id is None
    assert is_selected is False
    assert tree.get_selected_node_ids() == []


def test_clear_selected_nodes_returns_cleared_count() -> None:
    tree = NodeTreeWidget()
    tree.set_tree_data(_tree_fixture())

    first = tree.root.children[0]
    second = tree.root.children[1]
    tree.toggle_node_selection(first)
    tree.toggle_node_selection(second)

    cleared = tree.clear_selected_nodes()

    assert cleared == 2
    assert tree.get_selected_node_ids() == []
