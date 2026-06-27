import re
from pathlib import Path
from langchain_core.runnables.graph import NodeStyles
from langgraph.checkpoint.memory import MemorySaver
from app.config import settings
from app.graph.adapters.mock_soc import MockSocAdapter
from app.graph.build import build_graph
from app.graph import executor as executor_mod

BEGIN = "<!-- BEGIN GENERATED MERMAID: regenerate with `make mermaid`; do not edit by hand -->"
END = "<!-- END GENERATED MERMAID -->"

# Explicit fill, text color, and stroke on every node class so the diagram
# stays legible in both GitHub light and dark themes. Without an explicit
# color: GitHub picks the text color from the active theme, which renders
# light text on these light fills in dark mode.
NODE_STYLES = NodeStyles(
    default="fill:#eef2ff,color:#111827,stroke:#818cf8,stroke-width:1px,line-height:1.2",
    first="fill:#bbf7d0,color:#064e3b,stroke:#16a34a,stroke-width:1px",
    last="fill:#ddd6fe,color:#3b0764,stroke:#7c3aed,stroke-width:1px",
)


def render() -> str:
    graph = build_graph(MemorySaver(), executor_mod=executor_mod,
                        adapter=MockSocAdapter(base_url=settings.console_base_url),
                        settings=settings)
    return graph.get_graph().draw_mermaid(node_colors=NODE_STYLES)


def sync_readme(mermaid: str, readme: Path) -> None:
    text = readme.read_text()
    block = f"{BEGIN}\n```mermaid\n{mermaid}```\n{END}"
    pattern = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END), re.DOTALL)
    new_text, n = pattern.subn(block, text)
    if n != 1:
        raise SystemExit(f"expected one mermaid marker block in {readme}, found {n}")
    readme.write_text(new_text)


if __name__ == "__main__":
    mermaid = render()
    Path("docs/architecture.mmd").write_text(mermaid)
    sync_readme(mermaid, Path("README.md"))
    print("Wrote docs/architecture.mmd and synced the README diagram")
