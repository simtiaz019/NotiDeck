"""Install missing bundled templates in an initialized local NotiDeck installation.

Run with the same NOTIDECK_CONFIG_DIR as the server. No notifications are sent.
"""

from notideck.config import Config
from notideck.database import engine_for, sessions
from notideck.database.models import Setting
from notideck.template_library import install_database_templates


def main():
    config = Config()
    if not config.database_url:
        raise SystemExit("Complete setup first.")
    engine = engine_for(config.database_url)
    try:
        with config.lock, sessions(engine)() as db:
            if not db.get(Setting, "initialized"):
                raise SystemExit("Complete setup first.")
            created = install_database_templates(db, "local:template-library")
            db.commit()
            for row in created:
                print(row.name)
            print(f"Added {len(created)} templates; existing templates and routes preserved.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
