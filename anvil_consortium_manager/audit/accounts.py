from .. import models
from .base import AnVILAudit, ModelInstanceResult


class AccountAudit(AnVILAudit):
    """Class that runs an audit for Account instances."""

    ERROR_NOT_IN_ANVIL = "Not in AnVIL"
    """Error when the Account does not exist in AnVIL."""

    def run_audit(self):
        # Only checks active accounts.
        for account in models.Account.objects.active():
            model_instance_result = ModelInstanceResult(account)
            if not account.anvil_exists():
                model_instance_result.add_error(self.ERROR_NOT_IN_ANVIL)
            self.add_result(model_instance_result)
