"""Contains base adapter for accounts."""

from abc import ABC, abstractproperty

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.module_loading import import_string
from django_filters import FilterSet

from .. import app_settings, models


class BaseAccountAdapter(ABC):
    """Base class to inherit when customizing the account adapter."""

    """Message to display after a user has successfully linked their AnVIL account."""
    account_link_verify_message = "Thank you for linking your AnVIL account."

    """The URL for AccountLinkVerify view redirect"""
    account_link_redirect = settings.LOGIN_REDIRECT_URL

    """Subject line for AnVIL account verification emails."""
    account_link_email_subject = "Verify your AnVIL account email"

    """path to account verification email template"""
    account_link_email_template = "anvil_consortium_manager/account_verification_email.html"

    """If desired, specify the email address to send an email to after a user verifies an account."""
    account_verification_notification_email = None

    """Template to use for the account verification notification email."""
    account_verification_notification_template = "anvil_consortium_manager/account_notification_email.html"

    def __init__(self, *args, **kwargs):
        """Check for deprecations."""
        if hasattr(self, "account_verify_notification_email"):
            msg = (
                "account_verify_notification_email is deprecated. "
                "Please use account_verification_notification_email instead."
            )
            raise DeprecationWarning(msg)
        if hasattr(self, "after_account_link_verify"):
            msg = "after_account_link_verify is deprecated. Please use after_account_verification instead."
            raise DeprecationWarning(msg)
        if hasattr(self, "account_verification_email_template"):
            msg = "account_verification_email_template is deprecated. Please use account_link_email_template instead."
            raise DeprecationWarning(msg)
        if hasattr(self, "account_verification_notify_email_template"):
            msg = (
                "account_verification_notify_email_template is deprecated. "
                "Please use account_verification_notification_template instead."
            )
            raise DeprecationWarning(msg)

    @abstractproperty
    def list_table_class(self):
        """Table class to use in a list of Accounts."""
        ...

    @abstractproperty
    def list_filterset_class(self):
        """FilterSet subclass to use for Account filtering in the AccountList view."""
        ...

    def get_list_table_class(self):
        """Return the table class to use for the AccountList view."""
        if not self.list_table_class:
            raise ImproperlyConfigured("Set `list_table_class` in `{}`.".format(type(self)))
        if self.list_table_class.Meta.model != models.Account:
            raise ImproperlyConfigured(
                "list_table_class Meta model field must be anvil_consortium_manager.models.Account."
            )
        return self.list_table_class

    def get_list_filterset_class(self):
        """Return the FilterSet subclass to use for Account filtering in the AccountList view."""
        if not self.list_filterset_class:
            raise ImproperlyConfigured("Set `list_filterset_class` in `{}`.".format(type(self)))
        if not issubclass(self.list_filterset_class, FilterSet):
            raise ImproperlyConfigured("list_filterset_class must be a subclass of FilterSet.")
        # Make sure it has the correct model set.
        if self.list_filterset_class.Meta.model != models.Account:
            raise ImproperlyConfigured(
                "list_filterset_class Meta model field must be anvil_consortium_manager.models.Account."
            )
        return self.list_filterset_class

    def get_autocomplete_queryset(self, queryset, q):
        """Filter the Account `queryset` using the query `q` for use in the autocomplete."""
        queryset = queryset.filter(email__icontains=q)
        return queryset

    def get_autocomplete_label(self, account):
        """Adapter to provide a label for an account in autocomplete views."""
        return str(account)

    def after_account_verification(self, account):
        """Custom actions to take for an account after it has been verified by a user."""
        # Check that account is an instance of Account.
        if not isinstance(account, models.Account):
            raise TypeError("account must be an instance of anvil_consortium_manager.models.Account.")
        # Check that account is verified by a user.
        if not (hasattr(account, "user") and account.user):
            raise ValueError("account must be linked to a user.")

    def get_account_verification_notification_context(self, account):
        """Return the context for the account link verify notification email."""
        return {
            "email": account.email,
            "user": account.user,
        }

    def send_account_verification_notification_email(self, account):
        """Send an email to the account_verification_notification_email address after an account is linked."""
        mail_subject = "User verified AnVIL account"
        message = render_to_string(
            self.account_verification_notification_template,
            self.get_account_verification_notification_context(account),
        )
        # Send the message.
        # Current django behavior: If self.account_verification_notification_email is None, no emails are sent.
        send_mail(
            mail_subject,
            message,
            None,
            [self.account_verification_notification_email],
            fail_silently=False,
        )


def get_account_adapter():
    adapter = import_string(app_settings.ACCOUNT_ADAPTER)
    return adapter
