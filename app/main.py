import re
from pathlib import Path

from fasthtml.common import *

static_path = Path(__file__).resolve().parent / "static"
app, rt = fast_app(static_path=str(static_path))


def parse_quality_from_filename(filename: str) -> float:
    """Extract quality score from filename like 'brass_rail_21.98_0.jpg'."""
    raise NotImplementedError("TDD: implement parse_quality_from_filename")


@rt("/")
def get():
    raise NotImplementedError("TDD: implement gallery route")


if __name__ == "__main__":
    serve()
