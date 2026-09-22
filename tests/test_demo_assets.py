from pathlib import Path

SHOTS = Path("docs/screenshots")
NAMES = (
    "health.png",
    "ticket-create.png",
    "tool-trace.png",
    "handoff-ui.png",
    "n8n-canvas.png",
)


def test_screenshot_files_are_png():
    readme = (SHOTS / "README.md").read_text(encoding="utf-8")
    for name in NAMES:
        data = (SHOTS / name).read_bytes()
        assert data.startswith(b"\x89PNG\r\n\x1a\n")
        assert len(data) > 5000
        assert name in readme


def test_status_marks_days_22_through_25_done_and_keeps_26_plus_next():
    status = Path("docs/status.md").read_text(encoding="utf-8")
    for day in ("22", "23", "24", "25"):
        line = next(line for line in status.splitlines() if line.startswith(f"| {day} |"))
        assert "**Done**" in line
    for day in ("26", "27", "28", "29", "30"):
        line = next(line for line in status.splitlines() if line.startswith(f"| {day} |"))
        assert "not started" in line
    readme = Path("README.md").read_text(encoding="utf-8")
    assert "docs/n8n.md" in readme
    assert "/handoff" in readme
    demo = Path("docs/demo.md").read_text(encoding="utf-8")
    assert "10–15 minutes" in demo
    assert "scripts/post_n8n_demo.py" in demo
