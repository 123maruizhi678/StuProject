"""Prepare explicitly authorized local MySQL tests without replacing existing rows."""
import json
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from cryptography.fernet import Fernet
from sqlalchemy import inspect, text
from sqlalchemy.schema import CreateColumn
from app.config import settings
from app.database import engine, SessionLocal
from app.models import common, enterprise, customer


def main():
    if settings.DB_HOST not in ("localhost", "127.0.0.1", "::1") or settings.DB_NAME != "education_agent":
        raise RuntimeError("This preparation is restricted to local education_agent")
    runtime = ROOT / ".runtime"
    runtime.mkdir(exist_ok=True)
    additions = {
        "service_ticket_record": {"sla_snapshot"},
        "student_application_progress": {"row_version"},
        "customer_followup": {"schedule_operation_id", "schedule_base_at"},
        "customer_source": {"row_version", "current_parse_batch_id"},
        "customer_info": {"parse_batch_id", "source_row_key"},
        "research_rule": {"active_slot"},
        "research_result": {"input_snapshot"},
    }
    changes = []
    with engine.connect() as conn:
        inspector = inspect(conn)
        tables = list(additions) + ["enterprise_course", "enterprise_student_course", "student_academic_event", "student_academic_reminder"]
        before = {name: conn.execute(text(f"SHOW CREATE TABLE `{name}`")).first()[1]
                  for name in tables if inspector.has_table(name)}
        (runtime / "backend-schema-before.json").write_text(json.dumps(before, ensure_ascii=False, indent=2), encoding="utf-8")
        for name, columns in additions.items():
            table = common.UserAccount.metadata.tables[name]
            existing = {c["name"] for c in inspector.get_columns(name)}
            for name_column in sorted(columns - existing):
                column = table.c[name_column]
                definition = str(CreateColumn(column).compile(dialect=engine.dialect))
                if not column.nullable and column.server_default is None:
                    definition += " DEFAULT 1"
                conn.execute(text(f"ALTER TABLE `{name}` ADD COLUMN {definition}"))
                changes.append(f"add {name}.{name_column}")
        for table in (enterprise.enterprise_course, enterprise.enterprise_student_course):
            if not inspector.has_table(table.name):
                table.create(conn)
                changes.append(f"create {table.name}")
        for name in ("student_academic_event", "student_application_progress"):
            if not next(c for c in inspector.get_columns(name) if c['name'] == 'synced_at')['nullable']:
                conn.execute(text(f"ALTER TABLE `{name}` MODIFY synced_at DATETIME(6) NULL"))
                changes.append(f"nullable {name}.synced_at")
        col = next(c for c in inspector.get_columns('student_academic_reminder') if c['name'] == 'updated_at')
        if getattr(col['type'], 'fsp', None) != 6 or 'ON UPDATE' in str(col.get('default', '')).upper():
            conn.execute(text("ALTER TABLE student_academic_reminder MODIFY updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)"))
            changes.append('microseconds student_academic_reminder.updated_at')
        conn.commit()
    # These are local application secrets, generated once and retained across restarts.
    env_path = ROOT / ".env"
    env_text = env_path.read_text(encoding="utf-8")
    configured = []
    for key, value in {
        "ENTERPRISE_CONFIRM_SECRET": secrets.token_urlsafe(48),
        "ENTERPRISE_PHONE_ENCRYPTION_KEY": Fernet.generate_key().decode(),
        "ENTERPRISE_PHONE_LOOKUP_SECRET": secrets.token_urlsafe(48),
    }.items():
        if getattr(settings, key):
            continue
        lines = env_text.splitlines()
        found = False
        for i, line in enumerate(lines):
            if line.partition('=')[0].strip() == key:
                lines[i] = f"{key}={value}"
                found = True
        if not found:
            lines.append(f"{key}={value}")
        env_text = '\n'.join(lines) + '\n'
        configured.append(key)
    env_path.write_text(env_text, encoding="utf-8")
    from scripts.report.init_report_tables import apply as prepare_report
    prepare_report()
    from app.services.common.auth_service import hash_password
    from app.core.common.system_admin import ensure_admin_actor
    from sqlalchemy import select
    with SessionLocal() as db:
        account = db.scalar(select(common.UserAccount).where(common.UserAccount.username == 'root'))
        if account is None:
            account = common.UserAccount(username='root', password_hash=hash_password('root'), identity_type='admin')
            db.add(account)
            db.flush()
            ensure_admin_actor(db, account)
            db.commit()
            changes.append('create authorized local root admin')
    result = {"schema_changes": changes, "generated_local_secret_names": configured}
    (runtime / "backend-preparation.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))


if __name__ == '__main__':
    main()
