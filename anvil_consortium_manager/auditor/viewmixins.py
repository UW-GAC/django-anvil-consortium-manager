from django.core.exceptions import ImproperlyConfigured


class AnVILAuditMixin:
    """Mixin to display AnVIL audit results."""

    audit_class = None

    def get_audit_instance(self):
        if not self.audit_class:
            raise ImproperlyConfigured(
                "%(cls)s is missing an audit class. Define %(cls)s.audit_class or override "
                "%(cls)s.get_audit_instance()." % {"cls": self.__class__.__name__}
            )
        else:
            return self.audit_class()

    def run_audit(self):
        self.audit_results = self.get_audit_instance()
        self.audit_results.run_audit()

    def get(self, request, *args, **kwargs):
        self.run_audit()
        return super().get(request, *args, **kwargs)

    def get_context_data(self, *args, **kwargs):
        """Add audit results to the context data."""
        context = super().get_context_data(*args, **kwargs)
        context["audit_timestamp"] = self.audit_results.timestamp
        context["audit_ok"] = self.audit_results.ok()
        context["verified_table"] = self.audit_results.get_verified_table()
        context["error_table"] = self.audit_results.get_error_table()
        context["not_in_app_table"] = self.audit_results.get_not_in_app_table()
        context["ignored_table"] = self.audit_results.get_ignored_table()
        return context
