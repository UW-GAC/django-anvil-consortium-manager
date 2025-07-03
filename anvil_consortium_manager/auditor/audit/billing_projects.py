from anvil_consortium_manager.models import BillingProject

from .base import AnVILAudit, ModelInstanceResult


class BillingProjectAudit(AnVILAudit):
    """Class that runs an audit for BillingProject instances."""

    ERROR_NOT_IN_ANVIL = "Not in AnVIL"
    """Error when a BillingProject in the app does not exist in AnVIL."""

    cache_key = "billing_project_audit_results"

    def run_audit(self):
        # Check that all billing projects exist.
        for billing_project in BillingProject.objects.filter(has_app_as_user=True).all():
            model_instance_result = ModelInstanceResult(billing_project)
            if not billing_project.anvil_exists():
                model_instance_result.add_error(self.ERROR_NOT_IN_ANVIL)
            self.add_result(model_instance_result)
