import json
from pathlib import Path

import pytest
from sqlalchemy import select

from notideck.database.models import Template
from notideck.routing import render
from notideck.template_library import database_templates, install_database_templates


@pytest.mark.parametrize("template", database_templates(), ids=lambda t: t["name"])
def test_database_templates_render_with_optional_metadata_missing(template):
    event = {
        "title": "Test event",
        "message": "<script>secret</script>",
        "severity": "WARNING",
        "source": "test",
        "metadata": {},
    }
    assert render(template["title"], event)
    assert "Level:" in render(template["text"], event)
    html = render(template["html"], event, html=True)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_audit_template_matches_supplied_event():
    event = json.loads((Path(__file__).parents[1] / "examples/postgres_audit_event.json").read_text())
    template = database_templates()[0]
    assert render(template["title"], event) == "🟡 ❗ [Postgres Audit Alert] lenden-prod-db-dr-01"
    output = render(template["text"], event)
    assert "Source: postgres-audit-monitor" in output
    assert "Level: 🟡 ❗ WARNING" in output
    assert "SEVERITY=ERROR" in output
    assert "CLIENT=172.24.3.43(53378)" in output
    assert "Created: 2026-10-26T04:45:02.943175+00:00" in output
    assert output.endswith("cannot execute UPDATE in a read-only transaction")


def test_library_installed_on_setup_and_preserves_edits(client, app):
    with app.state.factory() as db:
        template = db.scalar(select(Template).where(Template.name == "PostgreSQL audit alert"))
        assert template is not None
        template.text = "My custom template"
        db.commit()
        assert install_database_templates(db, "test") == []
        db.commit()
        assert db.get(Template, template.id).text == "My custom template"
    assert client.get("/api/v1/resources/templates").json()["total"] == 6


def test_library_templates_edit_and_preview_in_console_api(client):
    for template in database_templates():
        response = client.post(
            "/api/v1/resources/templates", json={**template, "name": template["name"] + " custom"}
        )
        assert response.status_code == 201, response.text
        preview = client.post(
            "/api/v1/templates/preview",
            json={
                "template": template["text"],
                "event": {"title": "Test", "message": "Sample", "severity": "WARNING"},
            },
        )
        assert preview.status_code == 200, preview.text
