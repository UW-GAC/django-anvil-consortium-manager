from django.contrib import messages
from django.core.cache import caches
from django.core.exceptions import ImproperlyConfigured
from django.forms import Form
from django.http import HttpResponseRedirect

from .. import app_settings
from ..anvil_api import AnVILAPIError


class AnVILAuditRunMixin:
    """Mixin to display AnVIL audit results."""

    audit_class = None
    form_class = Form

    def get_audit_instance(self):
        if not self.audit_class:
            raise ImproperlyConfigured(
                "%(cls)s is missing an audit class. Define %(cls)s.audit_class or override "
                "%(cls)s.get_audit_instance()." % {"cls": self.__class__.__name__}
            )
        else:
            return self.audit_class()

    def form_valid(self, form):
        self.audit_results = self.get_audit_instance()
        try:
            self.audit_results.run_audit(cache=True)
        except AnVILAPIError as e:
            messages.error(self.request, f"AnVIL API Error: {e}")
            return self.render_to_response(self.get_context_data(form=form))
        return super().form_valid(form)


class AnVILAuditReviewMixin:
    """Mixin to display AnVIL audit results."""

    audit_result_not_found_redirect_url = None
    cache_key = None
    error_no_cached_result = "No audit results found. Please run the audit first."

    def get_cache_key(self):
        if not self.cache_key:
            raise ImproperlyConfigured(
                "%(cls)s is missing a cache key. Define %(cls)s.cache_name or override "
                "%(cls)s.get_cache_key()." % {"cls": self.__class__.__name__}
            )
        return self.cache_key

    def get_audit_result_not_found_redirect_url(self):
        if self.audit_result_not_found_redirect_url is None:
            raise ImproperlyConfigured(
                "%(cls)s is missing a audit_result_not_found_redirect_url. "
                "Define %(cls)s.audit_result_not_found_redirect_url or override "
                "%(cls)s.get_audit_result_not_found_redirect_url()." % {"cls": self.__class__.__name__}
            )
        return self.audit_result_not_found_redirect_url

    def get_audit_results(self):
        cache = caches[app_settings.AUDIT_CACHE]
        return cache.get(self.get_cache_key())

    def get(self, request, *args, **kwargs):
        audit_results = self.get_audit_results()
        if audit_results is None:
            messages.error(self.request, self.error_no_cached_result)
            return HttpResponseRedirect(self.get_audit_result_not_found_redirect_url())
        self.audit_results = self.get_audit_results()
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
