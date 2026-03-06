from django.db import migrations

IMMUTABLE_FN = """
CREATE OR REPLACE FUNCTION auditlog_immutable()
RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'AuditLog is append-only. UPDATE/DELETE is not allowed.';
END;
$$ LANGUAGE plpgsql;
"""

CREATE_TRIGGERS = """
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgname = 'auditlog_no_update'
  ) THEN
    CREATE TRIGGER auditlog_no_update
    BEFORE UPDATE ON audit_auditlog
    FOR EACH ROW EXECUTE FUNCTION auditlog_immutable();
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgname = 'auditlog_no_delete'
  ) THEN
    CREATE TRIGGER auditlog_no_delete
    BEFORE DELETE ON audit_auditlog
    FOR EACH ROW EXECUTE FUNCTION auditlog_immutable();
  END IF;
END $$;
"""

DROP_TRIGGERS = """
DROP TRIGGER IF EXISTS auditlog_no_update ON audit_auditlog;
DROP TRIGGER IF EXISTS auditlog_no_delete ON audit_auditlog;
DROP FUNCTION IF EXISTS auditlog_immutable();
"""


class Migration(migrations.Migration):
    dependencies = [
        ("audit", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(IMMUTABLE_FN),
        migrations.RunSQL(CREATE_TRIGGERS, reverse_sql=DROP_TRIGGERS),
    ]