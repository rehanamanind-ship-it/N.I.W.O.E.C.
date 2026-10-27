"""Example behavioral tests referenced by the FRS."""

from examples.src.app import add, save_message


def test_add() -> None:
    """Verify the add requirement."""
    assert add(2, 3) == 5  # add


def test_save_message() -> None:
    """Verify the save_message requirement."""
    assert save_message(" hello ") == "hello"  # save_message
