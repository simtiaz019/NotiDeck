"""Bundled operational templates, installed without overwriting user edits."""

import json
from importlib.resources import files

from sqlalchemy import select

from notideck.database.models import Template
from notideck.services import audit


def database_templates():
    return json.loads(files("notideck").joinpath("templates/database-alerts.json").read_text())


def install_database_templates(db, actor):
    """Add missing names in the caller's transaction; leave routes and existing templates intact."""
    existing = set(db.scalars(select(Template.name)))
    created = []
    for values in database_templates():
        if values["name"] in existing:
            continue
        row = Template(**values)
        db.add(row)
        db.flush()
        audit(db, actor, "templates.created", {"id": row.id, "name": row.name, "library": "database-alerts"})
        created.append(row)
        existing.add(row.name)
    return created
