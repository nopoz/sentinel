from app.scripts.export_mermaid import render

def test_render_contains_nodes():
    m = render()
    for node in ("plan", "act", "reflect", "approval", "execute", "finish"):
        assert node in m
