import logging
from dataclasses import dataclass

from django.contrib import messages
from django.core.cache import caches
from django.core.mail import mail_admins
from django.urls import reverse
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe

from .. import app_settings
from .audit.accounts import AccountAudit
from .audit.billing_projects import BillingProjectAudit
from .audit.managed_groups import ManagedGroupAudit
from .audit.workspaces import WorkspaceAudit

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AuditCheckConfig:
    audit_class: type
    audit_review_url: str


AUDITS_TO_CHECK = [
    AuditCheckConfig(AccountAudit, "anvil_consortium_manager:auditor:accounts:review"),
    AuditCheckConfig(BillingProjectAudit, "anvil_consortium_manager:auditor:billing_projects:review"),
    AuditCheckConfig(ManagedGroupAudit, "anvil_consortium_manager:auditor:managed_groups:review"),
    AuditCheckConfig(WorkspaceAudit, "anvil_consortium_manager:auditor:workspaces:review"),
]


def check_cached_anvil_audits(request):
    try:
        cache = caches[app_settings.AUDIT_CACHE]

        issues = []

        for config in AUDITS_TO_CHECK:
            audit_review_url = reverse(config.audit_review_url)
            cached_result = cache.get(config.audit_class.cache_key)
            if cached_result is None:
                issues.append(
                    format_html(
                        "No cached audit results found for {} - <a href='{}'>Please review this audit</a>",
                        config.audit_class.__name__,
                        audit_review_url,
                    )
                )
            elif not cached_result.ok():
                issues.append(
                    format_html(
                        "Audit {} contains errors - <a href='{}'>Please review this audit</a>",
                        config.audit_class.__name__,
                        audit_review_url,
                    )
                )

        if issues:
            combined = format_html_join(mark_safe("<br>"), "{}", ((msg,) for msg in issues))
            # Since this happens on login we do not want to fail
            # this also protects against tests where the messages framework
            # may not be setup
            try:
                messages.add_message(request, messages.ERROR, combined)
            except Exception as e:
                logger.error(
                    f"[check_cached_anvil_audits] Could not notify user as messages not configured correctly {e}"
                )

    except Exception as e:
        logger.exception(f"[check_anvil_audits] Encountered exception {e}")
        mail_admins(
            subject="check_anvil_audits failed.",
            message=f"[check_anvil_audits] Encountered exception {e}",
            fail_silently=True,
        )
