from django.test import TestCase
from .models import AuditLog


class AuditLogTests(TestCase):
    def test_audit_log_is_append_only(self):
        log = AuditLog.objects.create(action="test")
        with self.assertRaises(ValueError):
            log.save()
        with self.assertRaises(ValueError):
            log.delete()
