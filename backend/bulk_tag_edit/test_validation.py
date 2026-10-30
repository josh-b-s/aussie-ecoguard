import ast
from pathlib import Path

source = Path(__file__).with_name("handler.py").read_text(
    encoding="utf-8"
)

tree = ast.parse(source)

assert any(
    isinstance(node, ast.Compare)
    and any(
        isinstance(comparator, ast.Constant)
        and comparator.value == 50
        for comparator in node.comparators
    )
    for node in ast.walk(tree)
), "Missing limit of 50"

assert any(
    isinstance(node, ast.Compare)
    and any(
        isinstance(comparator, ast.Constant)
        and comparator.value == 20
        for comparator in node.comparators
    )
    for node in ast.walk(tree)
), "Missing limit of 20"

assert any(
    isinstance(node, ast.Call)
    and isinstance(node.func, ast.Attribute)
    and node.func.attr == "lower"
    for node in ast.walk(tree)
), "Missing lowercase normalisation"

print("Validation checks found.")