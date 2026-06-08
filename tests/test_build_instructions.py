"""Build-time instruction parsing."""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "site"))

from build import parse_instruction_sections  # noqa: E402


def test_each_line_under_heading_is_one_step():
    md = """## Cream butter
Combine butter and sugar.
Mix until fluffy, about 5 minutes.

## Bake
Preheat oven to 350 °F.
Bake 12 minutes.
"""
    sections = parse_instruction_sections(md)
    assert len(sections) == 2
    assert sections[0]["name"] == "Cream butter"
    assert len(sections[0]["steps"]) == 2
    assert "fluffy" in sections[0]["steps"][1]
    assert sections[1]["steps"][0].startswith("Preheat")


def test_blank_lines_ignored():
    md = """Step one.

Step two.
"""
    sections = parse_instruction_sections(md)
    assert sections[0]["steps"] == ["Step one.", "Step two."]