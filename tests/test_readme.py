from pathlib import Path


def test_readme_has_portfolio_sections():
    text = Path("README.md").read_text()
    for section in ("## Demo", "## Why a graph", "## Architecture",
                    "## Quickstart", "## Safety gate", "## Observability"):
        assert section in text
