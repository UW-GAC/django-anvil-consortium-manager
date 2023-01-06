from dal import autocomplete
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.sites.shortcuts import get_current_site
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.db.models import ProtectedError, RestrictedError
from django.forms import Form, HiddenInput, inlineformset_factory
from django.http import Http404, HttpResponseRedirect
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    FormView,
    RedirectView,
    TemplateView,
    UpdateView,
)
from django.views.generic.detail import SingleObjectMixin
from django_tables2 import SingleTableMixin, SingleTableView

from . import __version__, anvil_api, auth, exceptions, forms, models, tables
from .adapters.account import get_account_adapter
from .adapters.workspace import workspace_adapter_registry
from .anvil_api import AnVILAPIClient, AnVILAPIError
from .tokens import account_verification_token


class SuccessMessageMixin:
    """Mixin to add a success message to views."""

    @property
    def success_msg(self):
        return NotImplemented

    def add_success_message(self):
        """Add a success message to the request."""
        messages.success(self.request, self.success_msg)

    def form_valid(self, form):
        """Automatically add a success message when the form is valid."""
        self.add_success_message()
        return super().form_valid(form)

    def delete(self, request, *args, **kwargs):
        """Add a success message to the request when deleting an object."""
        # Should this be self.request or request?
        self.add_success_message()
        return super().delete(request, *args, **kwargs)


class AnVILAuditMixin:
    """Mixin to display AnVIL audit results."""

    def run_audit(self):
        raise ImproperlyConfigured("The 'run_audit' method must be implemented.")

    def get(self, request, *args, **kwargs):
        self.run_audit()
        return super().get(request, *args, **kwargs)

    def get_context_data(self, *args, **kwargs):
        """Add audit results to the context data."""
        # Catchall
        if "audit_timestamp" not in kwargs:
            kwargs["audit_timestamp"] = timezone.now()
        if "audit_ok" not in kwargs:
            kwargs["audit_ok"] = self.audit_results.ok()
        if "audit_verified" not in kwargs:
            kwargs["audit_verified"] = self.audit_results.get_verified()
        if "audit_errors" not in kwargs:
            kwargs["audit_errors"] = self.audit_results.get_errors()
        if "audit_not_in_app" not in kwargs:
            kwargs["audit_not_in_app"] = self.audit_results.get_not_in_app()

        return super().get_context_data(*args, **kwargs)


class Index(auth.AnVILConsortiumManagerViewRequired, TemplateView):
    template_name = "anvil_consortium_manager/index.html"

    def get_context_data(self, *args, **kwargs):
        """Add ACM version to the context data."""
        if "app_version" not in kwargs:
            kwargs["app_version"] = __version__
        return super().get_context_data(**kwargs)


class AnVILStatus(auth.AnVILConsortiumManagerViewRequired, TemplateView):
    template_name = "anvil_consortium_manager/status.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        client = AnVILAPIClient()
        try:
            response = client.status()
            json_response = response.json()
            context["anvil_systems_status"] = json_response.pop("systems")
            context["anvil_status"] = json_response
        except AnVILAPIError:
            # If the API call failed, rerender the page with the responses and show a message.
            messages.add_message(
                self.request,
                messages.ERROR,
                "AnVIL API Error: error checking API status",
            )
            context["anvil_systems_status"] = None
            context["anvil_status"] = None

        try:
            response = client.me()
            json_response = response.json()
            context["anvil_user"] = response.json()["userEmail"]
        except AnVILAPIError:
            # If the API call failed, rerender the page with the responses and show a message.
            messages.add_message(
                self.request, messages.ERROR, "AnVIL API Error: error checking API user"
            )
            context["anvil_user"] = None
        return context


class BillingProjectImport(
    auth.AnVILConsortiumManagerEditRequired, SuccessMessageMixin, CreateView
):
    model = models.BillingProject
    form_class = forms.BillingProjectImportForm
    template_name = "anvil_consortium_manager/billingproject_import.html"
    message_not_users_of_billing_project = (
        "Not a user of requested billing project or it doesn't exist on AnVIL."
    )
    success_msg = "Successfully imported Billing Project from AnVIL."

    def form_valid(self, form):
        """If the form is valid, check that we can access the BillingProject on AnVIL and save the associated model."""
        try:
            self.object = models.BillingProject.anvil_import(
                form.cleaned_data["name"],
                note=form.cleaned_data["note"],
            )
        except anvil_api.AnVILAPIError404:
            # Either the workspace doesn't exist or we don't have permission for it.
            messages.add_message(
                self.request, messages.ERROR, self.message_not_users_of_billing_project
            )
            return self.render_to_response(self.get_context_data(form=form))
        except anvil_api.AnVILAPIError as e:
            # If the API call failed for some other reason, rerender the page with the responses and show a message.
            messages.add_message(
                self.request, messages.ERROR, "AnVIL API Error: " + str(e)
            )
            return self.render_to_response(self.get_context_data(form=form))

        messages.add_message(self.request, messages.SUCCESS, self.success_msg)
        return HttpResponseRedirect(self.get_success_url())


class BillingProjectUpdate(
    auth.AnVILConsortiumManagerEditRequired, SuccessMessageMixin, UpdateView
):
    """View to update information about a Billing Project."""

    model = models.BillingProject
    slug_field = "name"
    form_class = forms.BillingProjectUpdateForm
    template_name = "anvil_consortium_manager/billingproject_update.html"
    success_msg = "Successfully updated Billing Project."


class BillingProjectDetail(
    auth.AnVILConsortiumManagerViewRequired, SingleTableMixin, DetailView
):
    model = models.BillingProject
    slug_field = "name"
    context_table_name = "workspace_table"

    def get_table(self):
        return tables.WorkspaceTable(
            self.object.workspace_set.all(), exclude="billing_project"
        )

    def get_context_data(self, **kwargs):
        """Add show_edit_links to context data."""
        context = super().get_context_data(**kwargs)
        edit_permission_codename = (
            models.AnVILProjectManagerAccess.EDIT_PERMISSION_CODENAME
        )
        context["show_edit_links"] = self.request.user.has_perm(
            "anvil_consortium_manager." + edit_permission_codename
        )
        return context


class BillingProjectList(auth.AnVILConsortiumManagerViewRequired, SingleTableView):
    model = models.BillingProject
    table_class = tables.BillingProjectTable


class BillingProjectAutocomplete(
    auth.AnVILConsortiumManagerViewRequired, autocomplete.Select2QuerySetView
):
    """View to provide autocompletion for BillingProjects. Only billing project where the app is a user are included."""

    def get_queryset(self):
        # Only active accounts.
        qs = models.BillingProject.objects.filter(has_app_as_user=True).order_by("name")

        if self.q:
            qs = qs.filter(name__icontains=self.q)

        return qs


class BillingProjectAudit(
    auth.AnVILConsortiumManagerViewRequired, AnVILAuditMixin, TemplateView
):
    """View to run an audit on Workspaces and display the results."""

    template_name = "anvil_consortium_manager/billing_project_audit.html"

    def run_audit(self):
        self.audit_results = models.BillingProject.anvil_audit()


class SingleAccountMixin(object):
    """Retrieve an account using the uuid field."""

    model = models.Account

    def get_object(self, queryset=None):
        """Return the object the view is displaying."""
        # Use a custom queryset if provided; this is required for subclasses
        # like DateDetailView
        if queryset is None:
            queryset = self.get_queryset()
        # Filter the queryset based on kwargs.
        uuid = self.kwargs.get("uuid", None)
        queryset = queryset.filter(uuid=uuid)
        try:
            # Get the single item from the filtered queryset
            obj = queryset.get()
        except queryset.model.DoesNotExist:
            raise Http404(
                _("No %(verbose_name)s found matching the query")
                % {"verbose_name": queryset.model._meta.verbose_name}
            )
        return obj


class AccountDetail(
    auth.AnVILConsortiumManagerViewRequired,
    SingleTableMixin,
    SingleAccountMixin,
    DetailView,
):
    """Render detail page for an :class:`anvil_consortium_manager.models.Account`."""

    context_table_name = "group_table"

    def get_table(self):
        """Get a table of :class:`anvil_consortium_manager.models.ManagedGroup` s that this account is a member of."""
        return tables.GroupAccountMembershipTable(
            self.object.groupaccountmembership_set.all(),
            exclude=["account", "is_service_account"],
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add an indicator of whether the account is inactive.
        context["is_inactive"] = self.object.status == models.Account.INACTIVE_STATUS
        edit_permission_codename = (
            models.AnVILProjectManagerAccess.EDIT_PERMISSION_CODENAME
        )
        context["show_edit_links"] = self.request.user.has_perm(
            "anvil_consortium_manager." + edit_permission_codename
        )
        context["show_deactivate_button"] = not context["is_inactive"]
        context["show_reactivate_button"] = context["is_inactive"]
        return context


class AccountImport(
    auth.AnVILConsortiumManagerEditRequired, SuccessMessageMixin, CreateView
):
    """Import an account from AnVIL.

    This view checks that the specified email has a valid AnVIL account. If so, it saves a record in the database.
    """

    model = models.Account
    template_name = "anvil_consortium_manager/account_import.html"

    message_account_does_not_exist = "This account does not exist on AnVIL."
    """A string that can be displayed if the account does not exist on AnVIL."""

    form_class = forms.AccountImportForm
    """A string that can be displayed if the account does not exist on AnVIL."""

    success_msg = "Successfully imported Account from AnVIL."
    """A string that can be displayed if the account was imported successfully."""

    def form_valid(self, form):
        """If the form is valid, check that the account exists on AnVIL and save the associated model."""
        object = form.save(commit=False)
        try:
            account_exists = object.anvil_exists()
        except AnVILAPIError as e:
            # If the API call failed for some other reason, rerender the page with the responses and show a message.
            messages.add_message(
                self.request, messages.ERROR, "AnVIL API Error: " + str(e)
            )
            return self.render_to_response(self.get_context_data(form=form))
        if not account_exists:
            messages.add_message(
                self.request, messages.ERROR, self.message_account_does_not_exist
            )
            # Re-render the page with a message.
            return self.render_to_response(self.get_context_data(form=form))

        return super().form_valid(form)


class AccountUpdate(
    auth.AnVILConsortiumManagerEditRequired,
    SuccessMessageMixin,
    SingleAccountMixin,
    UpdateView,
):
    """View to update information about an Account."""

    model = models.Account
    form_class = forms.AccountUpdateForm
    template_name = "anvil_consortium_manager/account_update.html"
    success_msg = "Successfully updated Account."


class AccountLink(LoginRequiredMixin, SuccessMessageMixin, FormView):
    """View where a user enter their AnVIL email to get an email verification link."""

    login_url = settings.LOGIN_URL
    template_name = "anvil_consortium_manager/account_link.html"
    model = models.UserEmailEntry
    message_account_does_not_exist = "This account does not exist on AnVIL."
    message_user_already_linked = "You have already linked an AnVIL account."
    message_account_already_exists = (
        "An AnVIL Account with this email already exists in this app."
    )
    form_class = forms.UserEmailEntryForm
    success_msg = (
        "To complete linking the account, check your email for a verification link."
    )

    def get(self, request, *args, **kwargs):
        """Check if the user already has an account linked and redirect."""
        try:
            request.user.account
        except models.Account.DoesNotExist:
            return super().get(request, *args, **kwargs)
        else:
            # The user already has a linked account, so redirect with a message.
            messages.add_message(
                self.request, messages.ERROR, self.message_user_already_linked
            )
            return HttpResponseRedirect(reverse(settings.ANVIL_ACCOUNT_LINK_REDIRECT))

    def post(self, request, *args, **kwargs):
        """Check if the user already has an account linked and redirect."""
        try:
            request.user.account
        except models.Account.DoesNotExist:
            return super().post(request, *args, **kwargs)
        else:
            # The user already has a linked account, so redirect with a message.
            messages.add_message(
                self.request, messages.ERROR, self.message_user_already_linked
            )
            return HttpResponseRedirect(reverse(settings.ANVIL_ACCOUNT_LINK_REDIRECT))

    def get_success_url(self):
        return reverse(settings.ANVIL_ACCOUNT_LINK_REDIRECT)

    def form_valid(self, form):
        """If the form is valid, check that the email exists on AnVIL and send verification email."""
        email = form.cleaned_data.get("email")

        try:
            email_entry = models.UserEmailEntry.objects.get(
                email__iexact=email, user=self.request.user
            )
        except models.UserEmailEntry.DoesNotExist:
            email_entry = models.UserEmailEntry(email=email, user=self.request.user)

        # Check if this email has an account already linked to a different user.
        # Don't need to check the user, because a user who has already linked their account shouldn't get here.
        if models.Account.objects.filter(email=email).count():
            # The user already has a linked account, so redirect with a message.
            messages.add_message(
                self.request, messages.ERROR, self.message_account_already_exists
            )
            return HttpResponseRedirect(reverse(settings.ANVIL_ACCOUNT_LINK_REDIRECT))

        # Check if it exists on AnVIL.
        try:
            anvil_account_exists = email_entry.anvil_account_exists()
        except AnVILAPIError as e:
            messages.add_message(
                self.request, messages.ERROR, "AnVIL API Error: " + str(e)
            )
            return self.render_to_response(self.get_context_data(form=form))

        if not anvil_account_exists:
            messages.add_message(
                self.request, messages.ERROR, self.message_account_does_not_exist
            )
            # Re-render the page with a message.
            return self.render_to_response(self.get_context_data(form=form))

        email_entry.date_verification_email_sent = timezone.now()
        email_entry.save()
        email_entry.send_verification_email(get_current_site(self.request).domain)

        return super().form_valid(form)


class AccountLinkVerify(LoginRequiredMixin, RedirectView):
    """View where a user can verify their email and create an Account object."""

    message_already_linked = "You have already linked an AnVIL account."
    message_link_invalid = "AnVIL account verification link is invalid."
    message_account_already_exists = (
        "An AnVIL Account with this email already exists in this app."
    )
    message_account_does_not_exist = "This account does not exist on AnVIL."
    message_success = "Thank you for verifying your email."

    def get_redirect_url(self, *args, **kwargs):
        return reverse(settings.ANVIL_ACCOUNT_LINK_REDIRECT)

    def get(self, request, *args, **kwargs):
        # Check if this user already has an account linked.
        if models.Account.objects.filter(user=request.user).count():
            messages.add_message(
                self.request, messages.ERROR, self.message_already_linked
            )
            return super().get(request, *args, **kwargs)

        uuid = kwargs.get("uuid")
        token = kwargs.get("token")

        try:
            email_entry = models.UserEmailEntry.objects.get(uuid=uuid)
        except models.UserEmailEntry.DoesNotExist:
            messages.add_message(
                self.request, messages.ERROR, self.message_link_invalid
            )
            return super().get(request, *args, **kwargs)

        # Check if the email is already linked to an account.
        if models.Account.objects.filter(email=email_entry.email).count():
            messages.add_message(
                self.request, messages.ERROR, self.message_account_already_exists
            )
            return super().get(request, *args, **kwargs)

        # Check that the token maches.
        if not account_verification_token.check_token(email_entry, token):
            messages.add_message(
                self.request, messages.ERROR, self.message_link_invalid
            )
            return super().get(request, *args, **kwargs)

        # Create an account for this user from this email.
        account = models.Account(
            user=self.request.user,
            email=email_entry.email,
            status=models.Account.ACTIVE_STATUS,
            is_service_account=False,
            verified_email_entry=email_entry,
        )
        # Make sure an AnVIL account still exists.
        try:
            anvil_account_exists = account.anvil_exists()
        except AnVILAPIError as e:
            messages.add_message(
                self.request, messages.ERROR, "AnVIL API Error: " + str(e)
            )
            return super().get(request, *args, **kwargs)

        if not anvil_account_exists:
            messages.add_message(
                self.request, messages.ERROR, self.message_account_does_not_exist
            )
            return super().get(request, *args, **kwargs)

        # Mark the entry as verified.
        email_entry.date_verified = timezone.now()
        email_entry.save()
        email_entry.send_notification_email()

        # Save the account
        account.full_clean()
        account.save()

        # Add a success message.
        messages.add_message(self.request, messages.SUCCESS, self.message_success)

        return super().get(request, *args, **kwargs)


class AccountList(auth.AnVILConsortiumManagerViewRequired, SingleTableView):
    """View to display a list of Accounts.

    The table class can be customized using in a custom Account adapter."""

    model = models.Account

    def get_table_class(self):
        adapter = get_account_adapter()
        return adapter().get_list_table_class()


class AccountActiveList(auth.AnVILConsortiumManagerViewRequired, SingleTableView):
    model = models.Account
    table_class = tables.AccountTable

    def get_queryset(self):
        return self.model.objects.active()


class AccountInactiveList(auth.AnVILConsortiumManagerViewRequired, SingleTableView):
    model = models.Account
    table_class = tables.AccountTable

    def get_queryset(self):
        return self.model.objects.inactive()


class AccountDeactivate(
    auth.AnVILConsortiumManagerEditRequired,
    SuccessMessageMixin,
    SingleTableMixin,
    SingleAccountMixin,
    DeleteView,
):
    """Deactivate an account and remove it from all groups on AnVIL."""

    template_name = "anvil_consortium_manager/account_confirm_deactivate.html"
    context_table_name = "group_table"
    message_error_removing_from_groups = "Error removing account from groups; manually verify group memberships on AnVIL. (AnVIL API Error: {})"  # noqa
    message_already_inactive = "This Account is already inactive."
    success_msg = "Successfully deactivated Account in app."

    def get_table(self):
        return tables.GroupAccountMembershipTable(
            self.object.groupaccountmembership_set.all(),
            exclude=["account", "is_service_account"],
        )

    def get_success_url(self):
        return self.object.get_absolute_url()
        # exceptions.AnVILRemoveAccountFromGroupError

    def get(self, *args, **kwargs):
        response = super().get(self, *args, **kwargs)
        # Check if account is inactive.
        if self.object.status == self.object.INACTIVE_STATUS:
            messages.add_message(
                self.request, messages.ERROR, self.message_already_inactive
            )
            # Redirect to the object detail page.
            return HttpResponseRedirect(self.object.get_absolute_url())
        return response

    def delete(self, request, *args, **kwargs):
        """
        Make an API call to AnVIL to remove the account from all groups and then set status to inactive.
        """
        self.object = self.get_object()

        if self.object.status == self.object.INACTIVE_STATUS:
            messages.add_message(
                self.request, messages.ERROR, self.message_already_inactive
            )
            # Redirect to the object detail page.
            return HttpResponseRedirect(self.object.get_absolute_url())

        try:
            self.object.deactivate()
        except AnVILAPIError as e:
            msg = self.message_error_removing_from_groups.format(e)
            messages.add_message(request, messages.ERROR, msg)
            # Rerender the same page with an error message.
            return HttpResponseRedirect(self.object.get_absolute_url())
        else:
            # Need to add the message because we're not calling the super method.
            messages.success(self.request, self.success_msg)
            return HttpResponseRedirect(self.get_success_url())


class AccountReactivate(
    auth.AnVILConsortiumManagerEditRequired,
    SuccessMessageMixin,
    SingleTableMixin,
    SingleAccountMixin,
    SingleObjectMixin,
    FormView,
):
    """Reactivate an account and re-add it to all groups on AnVIL."""

    context_table_name = "group_table"
    form_class = Form
    template_name = "anvil_consortium_manager/account_confirm_reactivate.html"
    message_error_adding_to_groups = "Error adding account to groups; manually verify group memberships on AnVIL. (AnVIL API Error: {})"  # noqa
    message_already_active = "This Account is already active."
    success_msg = "Successfully reactivated Account in app."

    def get_success_url(self):
        return self.object.get_absolute_url()
        # exceptions.AnVILRemoveAccountFromGroupError

    def get_table(self):
        return tables.GroupAccountMembershipTable(
            self.object.groupaccountmembership_set.all(),
            exclude=["account", "is_service_account"],
        )

    def get(self, *args, **kwargs):
        self.object = self.get_object()
        # Check if account is inactive.
        if self.object.status == self.object.ACTIVE_STATUS:
            messages.add_message(
                self.request, messages.ERROR, self.message_already_active
            )
            # Redirect to the object detail page.
            return HttpResponseRedirect(self.object.get_absolute_url())
        return super().get(self, *args, **kwargs)

    def form_valid(self, form):
        """Set the object status to active and add it to all groups on AnVIL."""
        # Set the status to active.
        self.object = self.get_object()
        if self.object.status == self.object.ACTIVE_STATUS:
            messages.add_message(
                self.request, messages.ERROR, self.message_already_active
            )
            # Redirect to the object detail page.
            return HttpResponseRedirect(self.object.get_absolute_url())

        self.object.status = self.object.ACTIVE_STATUS
        self.object.save()
        # Re-add to all groups
        group_memberships = self.object.groupaccountmembership_set.all()
        try:
            for membership in group_memberships:
                membership.anvil_create()
        except AnVILAPIError as e:
            msg = self.message_error_adding_to_groups.format(e)
            messages.add_message(self.request, messages.ERROR, msg)
            # Rerender the same page with an error message.
            return HttpResponseRedirect(self.object.get_absolute_url())
        return super().form_valid(form)


class AccountDelete(
    auth.AnVILConsortiumManagerEditRequired,
    SuccessMessageMixin,
    SingleAccountMixin,
    DeleteView,
):
    model = models.Account
    message_error_removing_from_groups = "Error removing account from groups; manually verify group memberships on AnVIL. (AnVIL API Error: {})"  # noqa
    success_msg = "Successfully deleted Account from app."

    def get_success_url(self):
        return reverse("anvil_consortium_manager:accounts:list")

    def delete(self, request, *args, **kwargs):
        """
        Make an API call to AnVIL to remove the account from all groups and then delete it from the app.
        """
        self.object = self.get_object()
        try:
            self.object.anvil_remove_from_groups()
        except AnVILAPIError as e:
            msg = self.message_error_removing_from_groups.format(e)
            messages.add_message(request, messages.ERROR, msg)
            # Rerender the same page with an error message.
            return HttpResponseRedirect(self.object.get_absolute_url())
        else:
            return super().delete(request, *args, **kwargs)


class AccountAutocomplete(
    auth.AnVILConsortiumManagerViewRequired, autocomplete.Select2QuerySetView
):
    """View to provide autocompletion for Accounts. Only active accounts are included."""

    def get_result_label(self, item):
        adapter = get_account_adapter()
        return adapter().get_autocomplete_label(item)

    def get_selected_result_label(self, item):
        adapter = get_account_adapter()
        return adapter().get_autocomplete_label(item)

    def get_queryset(self):
        # Only active accounts.
        qs = models.Account.objects.filter(
            status=models.Account.ACTIVE_STATUS
        ).order_by("email")

        if self.q:
            # Use the account adapter to process the query.
            adapter = get_account_adapter()
            qs = adapter().get_autocomplete_queryset(qs, self.q)

        return qs


class AccountAudit(
    auth.AnVILConsortiumManagerViewRequired, AnVILAuditMixin, TemplateView
):
    """View to run an audit on Accounts and display the results."""

    template_name = "anvil_consortium_manager/account_audit.html"

    def run_audit(self):
        self.audit_results = models.Account.anvil_audit()


class ManagedGroupDetail(auth.AnVILConsortiumManagerViewRequired, DetailView):
    model = models.ManagedGroup
    slug_field = "name"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["workspace_authorization_domain_table"] = tables.WorkspaceTable(
            self.object.workspace_set.all(),
            exclude=(
                "number_groups",
                "has_authorization_domains",
                "billing_project",
            ),
        )
        context["workspace_table"] = tables.WorkspaceGroupSharingTable(
            self.object.workspacegroupsharing_set.all(), exclude="group"
        )
        context["active_account_table"] = tables.GroupAccountMembershipTable(
            self.object.groupaccountmembership_set.filter(
                account__status=models.Account.ACTIVE_STATUS
            ),
            exclude="group",
        )
        context["inactive_account_table"] = tables.GroupAccountMembershipTable(
            self.object.groupaccountmembership_set.filter(
                account__status=models.Account.INACTIVE_STATUS
            ),
            exclude="group",
        )
        context["group_table"] = tables.GroupGroupMembershipTable(
            self.object.child_memberships.all(), exclude="parent_group"
        )
        context["parent_table"] = tables.GroupGroupMembershipTable(
            self.object.parent_memberships.all(), exclude="child_group"
        )
        edit_permission_codename = (
            models.AnVILProjectManagerAccess.EDIT_PERMISSION_CODENAME
        )
        context["show_edit_links"] = self.request.user.has_perm(
            "anvil_consortium_manager." + edit_permission_codename
        )
        return context


class ManagedGroupCreate(
    auth.AnVILConsortiumManagerEditRequired, SuccessMessageMixin, CreateView
):
    model = models.ManagedGroup
    form_class = forms.ManagedGroupCreateForm
    template_name = "anvil_consortium_manager/managedgroup_create.html"
    success_msg = "Successfully created Managed Group on AnVIL."

    def form_valid(self, form):
        """If the form is valid, save the associated model and create it on AnVIL."""
        # Create but don't save the new group.
        self.object = form.save(commit=False)
        # Make an API call to AnVIL to create the group.
        try:
            self.object.anvil_create()
        except AnVILAPIError as e:
            # If the API call failed, rerender the page with the responses and show a message.
            messages.add_message(
                self.request, messages.ERROR, "AnVIL API Error: " + str(e)
            )
            return self.render_to_response(self.get_context_data(form=form))
        # The object is saved by the super's form_valid method.
        return super().form_valid(form)


class ManagedGroupUpdate(
    auth.AnVILConsortiumManagerEditRequired,
    SuccessMessageMixin,
    UpdateView,
):
    """View to update information about an Account."""

    model = models.ManagedGroup
    form_class = forms.ManagedGroupUpdateForm
    slug_field = "name"
    template_name = "anvil_consortium_manager/managedgroup_update.html"
    success_msg = "Successfully updated ManagedGroup."


class ManagedGroupList(auth.AnVILConsortiumManagerViewRequired, SingleTableView):
    model = models.ManagedGroup
    table_class = tables.ManagedGroupTable


class ManagedGroupDelete(
    auth.AnVILConsortiumManagerEditRequired, SuccessMessageMixin, DeleteView
):
    model = models.ManagedGroup
    slug_field = "name"
    message_not_managed_by_app = (
        "Cannot delete group because it is not managed by this app."
    )
    message_is_auth_domain = (
        "Cannot delete group since it is an authorization domain for a workspace."
    )
    message_is_member_of_another_group = (
        "Cannot delete group since it is a member of another group."
    )
    message_has_access_to_workspace = (
        "Cannot delete group because it has access to at least one workspace."
    )
    # In some cases the AnVIL API returns a successful code but the group is not deleted.
    message_could_not_delete_group_from_app = (
        "Cannot delete group from app due to foreign key restrictions."
    )
    message_could_not_delete_group_from_anvil = (
        "Cannot not delete group from AnVIL - unknown reason."
    )
    success_msg = "Successfully deleted Group on AnVIL."

    def get_success_url(self):
        return reverse("anvil_consortium_manager:managed_groups:list")

    def get(self, *args, **kwargs):
        response = super().get(self, *args, **kwargs)
        # Check if managed by the app.
        if not self.object.is_managed_by_app:
            messages.add_message(
                self.request, messages.ERROR, self.message_not_managed_by_app
            )
            # Redirect to the object detail page.
            return HttpResponseRedirect(self.object.get_absolute_url())
        # Check authorization domains
        if self.object.workspaceauthorizationdomain_set.count() > 0:
            # Add a message and redirect.
            messages.add_message(
                self.request, messages.ERROR, self.message_is_auth_domain
            )
            # Redirect to the object detail page.
            return HttpResponseRedirect(self.object.get_absolute_url())
        # Check that it is not a member of other groups.
        # This is enforced by AnVIL.
        if self.object.parent_memberships.count() > 0:
            messages.add_message(
                self.request, messages.ERROR, self.message_is_member_of_another_group
            )
            return HttpResponseRedirect(self.object.get_absolute_url())
        if self.object.workspacegroupsharing_set.count() > 0:
            messages.add_message(
                self.request, messages.ERROR, self.message_has_access_to_workspace
            )
            return HttpResponseRedirect(self.object.get_absolute_url())
        # Otherwise, return the response.
        return response

    def delete(self, request, *args, **kwargs):
        """
        Make an API call to AnVIL and then call the delete method on the object.
        """
        self.object = self.get_object()
        # Check that the group is managed by the app.
        if not self.object.is_managed_by_app:
            messages.add_message(
                self.request, messages.ERROR, self.message_not_managed_by_app
            )
            # Redirect to the object detail page.
            return HttpResponseRedirect(self.object.get_absolute_url())
        # Check if it's an auth domain for any workspaces.
        if self.object.workspaceauthorizationdomain_set.count() > 0:
            # Add a message and redirect.
            messages.add_message(
                self.request, messages.ERROR, self.message_is_auth_domain
            )
            # Redirect to the object detail page.
            return HttpResponseRedirect(self.object.get_absolute_url())
        # Check that it is not a member of other groups.
        # This is enforced by AnVIL.
        if self.object.parent_memberships.count() > 0:
            messages.add_message(
                self.request, messages.ERROR, self.message_is_member_of_another_group
            )
            return HttpResponseRedirect(self.object.get_absolute_url())
        if self.object.workspacegroupsharing_set.count() > 0:
            messages.add_message(
                self.request, messages.ERROR, self.message_has_access_to_workspace
            )
            return HttpResponseRedirect(self.object.get_absolute_url())

        try:
            with transaction.atomic():
                self.object.delete()
                self.object.anvil_delete()
                self.add_success_message()
                response = HttpResponseRedirect(self.get_success_url())
        except (ProtectedError, RestrictedError):
            messages.add_message(
                self.request,
                messages.ERROR,
                self.message_could_not_delete_group_from_app,
            )
            response = HttpResponseRedirect(self.object.get_absolute_url())
        except exceptions.AnVILGroupDeletionError:
            messages.add_message(
                self.request,
                messages.ERROR,
                self.message_could_not_delete_group_from_anvil,
            )
            response = HttpResponseRedirect(self.object.get_absolute_url())
        except AnVILAPIError as e:
            # The AnVIL call has failed for some reason.
            messages.add_message(
                self.request, messages.ERROR, "AnVIL API Error: " + str(e)
            )
            # Rerender the same page with an error message.
            response = self.render_to_response(self.get_context_data())
        return response


class ManagedGroupAutocomplete(
    auth.AnVILConsortiumManagerViewRequired, autocomplete.Select2QuerySetView
):
    """View to provide autocompletion for ManagedGroups."""

    def get_queryset(self):
        # Filter out unathorized users, or does the auth mixin do that?
        qs = models.ManagedGroup.objects.filter(is_managed_by_app=True).order_by("name")

        if self.q:
            qs = qs.filter(name__icontains=self.q)

        return qs


class ManagedGroupAudit(
    auth.AnVILConsortiumManagerViewRequired, AnVILAuditMixin, TemplateView
):
    """View to run an audit on ManagedGroups and display the results."""

    template_name = "anvil_consortium_manager/managedgroup_audit.html"

    def run_audit(self):
        self.audit_results = models.ManagedGroup.anvil_audit()


class ManagedGroupMembershipAudit(
    auth.AnVILConsortiumManagerViewRequired,
    SingleObjectMixin,
    AnVILAuditMixin,
    TemplateView,
):
    """View to run an audit on ManagedGroups and display the results."""

    model = models.ManagedGroup
    slug_field = "name"
    template_name = "anvil_consortium_manager/managedgroup_membership_audit.html"
    message_not_managed_by_app = (
        "Cannot audit membership because group is not managed by this app."
    )

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        # Check if managed by the app.
        if not self.object.is_managed_by_app:
            messages.add_message(
                self.request,
                messages.ERROR,
                self.message_not_managed_by_app,
            )
            # Redirect to the object detail page.
            return HttpResponseRedirect(self.object.get_absolute_url())
        # Otherwise, return the response.
        return super().get(request, *args, **kwargs)

    def run_audit(self):
        self.audit_results = self.object.anvil_audit_membership()


class WorkspaceAdapterMixin:
    """Class for handling workspace adapters."""

    def get_workspace_type(self):
        # Try getting it from the kwargs.
        workspace_type = self.kwargs.get("workspace_type")
        return workspace_type

    def get_adapter(self):
        workspace_type = self.get_workspace_type()
        if workspace_type:
            try:
                adapter = workspace_adapter_registry.get_adapter(workspace_type)
            except KeyError:
                raise Http404("workspace_type is not registered.")
        else:
            raise AttributeError(
                "`workspace_type` must be specified." % self.__class__.__name__
            )
        return adapter

    def get(self, request, *args, **kwargs):
        self.adapter = self.get_adapter()
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.adapter = self.get_adapter()
        return super().post(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        if "workspace_type_display_name" not in kwargs:
            kwargs["workspace_type_display_name"] = self.adapter.get_name()
        return super().get_context_data(**kwargs)


class WorkspaceDetail(
    auth.AnVILConsortiumManagerViewRequired, WorkspaceAdapterMixin, DetailView
):
    model = models.Workspace

    def get_object(self, queryset=None):
        """Return the object the view is displaying."""

        # Use a custom queryset if provided; this is required for subclasses
        # like DateDetailView
        if queryset is None:
            queryset = self.get_queryset()
        # Filter the queryset based on kwargs.
        billing_project_slug = self.kwargs.get("billing_project_slug", None)
        workspace_slug = self.kwargs.get("workspace_slug", None)
        queryset = queryset.filter(
            billing_project__name=billing_project_slug, name=workspace_slug
        )
        try:
            # Get the single item from the filtered queryset
            obj = queryset.get()
        except queryset.model.DoesNotExist:
            raise Http404(
                _("No %(verbose_name)s found matching the query")
                % {"verbose_name": queryset.model._meta.verbose_name}
            )
        return obj

    def get_workspace_type(self):
        """Return the workspace type of this workspace."""
        object = self.get_object()
        return object.workspace_type

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["group_sharing_table"] = tables.WorkspaceGroupSharingTable(
            self.object.workspacegroupsharing_set.all(), exclude="workspace"
        )
        context["authorization_domain_table"] = tables.ManagedGroupTable(
            self.object.authorization_domains.all(),
            exclude=["workspace", "number_groups", "number_accounts"],
        )
        edit_permission_codename = (
            models.AnVILProjectManagerAccess.EDIT_PERMISSION_CODENAME
        )
        context["show_edit_links"] = self.request.user.has_perm(
            "anvil_consortium_manager." + edit_permission_codename
        )
        return context

    def get_template_names(self):
        """Return the workspace detail template name specified in the adapter."""
        adapter = workspace_adapter_registry.get_adapter(self.object.workspace_type)
        template_name = adapter.get_workspace_detail_template_name()
        return [template_name]


class WorkspaceCreate(
    auth.AnVILConsortiumManagerEditRequired,
    SuccessMessageMixin,
    WorkspaceAdapterMixin,
    FormView,
):
    form_class = forms.WorkspaceCreateForm
    success_msg = "Successfully created Workspace on AnVIL."
    template_name = "anvil_consortium_manager/workspace_create.html"

    def get_workspace_data_formset(self):
        """Return an instance of the workspace data form to be used in this view."""
        formset_prefix = "workspacedata"
        form_class = self.adapter.get_workspace_data_form_class()
        model = self.adapter.get_workspace_data_model()
        formset_factory = inlineformset_factory(
            models.Workspace,
            model,
            form=form_class,
            can_delete=False,
            can_delete_extra=False,
            absolute_max=1,
            max_num=1,
            min_num=1,
        )
        if self.request.method in ("POST"):
            formset = formset_factory(
                self.request.POST,
                instance=self.workspace,
                prefix=formset_prefix,
                initial=[{"workspace": self.workspace}],
            )
        else:
            formset = formset_factory(prefix=formset_prefix, initial=[{}])
        return formset

    def get_context_data(self, **kwargs):
        """Insert the workspace data formset into the context dict."""
        if "workspace_data_formset" not in kwargs:
            kwargs["workspace_data_formset"] = self.get_workspace_data_formset()
        return super().get_context_data(**kwargs)

    def post(self, request, *args, **kwargs):
        """
        Handle POST requests: instantiate the forms instances with the passed
        POST variables and then check if they are valid.
        """
        self.adapter = self.get_adapter()
        self.workspace = None
        form = self.get_form()
        # First, check if the workspace form is valid.
        # If it is, we'll save the model and then check the workspace data formset in the post method.
        if form.is_valid():
            return self.form_valid(form)
        else:
            workspace_data_formset = self.get_workspace_data_formset()
            return self.forms_invalid(form, workspace_data_formset)

    def form_valid(self, form):
        """If the form(s) are valid, save the associated model(s) and create the workspace on AnVIL."""
        # Need to use a transaction because the object needs to be saved to access the many-to-many field.
        try:
            with transaction.atomic():
                # Calling form.save() does not create the history for the authorization domain many to many field.
                # Instead, save the workspace first and then create the auth domain relationships one by one.
                # Add the workspace data type from the adapter to the instance.
                form.instance.workspace_type = self.adapter.get_type()
                self.workspace = form.save(commit=False)
                self.workspace.save()
                # Now check the workspace_data_formset.
                workspace_data_formset = self.get_workspace_data_formset()
                if not workspace_data_formset.is_valid():
                    # Tell the transaction to roll back, since we are not raising an exception.
                    transaction.set_rollback(True)
                    return self.forms_invalid(form, workspace_data_formset)
                # Now save the auth domains and the workspace_data_form.
                for auth_domain in form.cleaned_data["authorization_domains"]:
                    models.WorkspaceAuthorizationDomain.objects.create(
                        workspace=self.workspace, group=auth_domain
                    )
                workspace_data_formset.forms[0].save()
                # Then create the workspace on AnVIL.
                self.workspace.anvil_create()
        except AnVILAPIError as e:
            # If the API call failed, rerender the page with the responses and show a message.
            messages.add_message(
                self.request, messages.ERROR, "AnVIL API Error: " + str(e)
            )
            return self.render_to_response(
                self.get_context_data(
                    form=form, workspace_data_formset=workspace_data_formset
                )
            )
        return super().form_valid(form)

    def forms_invalid(self, form, workspace_data_formset):
        """If the form(s) are invalid, render the invalid form."""
        return self.render_to_response(
            self.get_context_data(
                form=form, workspace_data_formset=workspace_data_formset
            )
        )

    def get_success_url(self):
        return self.workspace.get_absolute_url()


class WorkspaceImport(
    auth.AnVILConsortiumManagerEditRequired,
    SuccessMessageMixin,
    WorkspaceAdapterMixin,
    FormView,
):
    template_name = "anvil_consortium_manager/workspace_import.html"
    message_anvil_no_access_to_workspace = (
        "Requested workspace doesn't exist or you don't have permission to see it."
    )
    message_anvil_not_owner = "Not an owner of this workspace."
    message_workspace_exists = "This workspace already exists in the web app."
    message_error_fetching_workspaces = "Unable to fetch workspaces from AnVIL."
    message_no_available_workspaces = "No workspaces available for import from AnVIL."
    success_msg = "Successfully imported Workspace from AnVIL."
    # Set in a method.
    workspace_choices = None

    def get_form(self):
        """Return the form instance with the list of available workspaces to import."""
        try:
            all_workspaces = (
                AnVILAPIClient()
                .list_workspaces(
                    fields="workspace.namespace,workspace.name,accessLevel"
                )
                .json()
            )
            # Filter workspaces to only owners and not imported.
            workspaces = [
                w["workspace"]["namespace"] + "/" + w["workspace"]["name"]
                for w in all_workspaces
                if (w["accessLevel"] == "OWNER")
                and not models.Workspace.objects.filter(
                    billing_project__name=w["workspace"]["namespace"],
                    name=w["workspace"]["name"],
                ).exists()
            ]
            workspace_choices = [(x, x) for x in workspaces]

            if not len(workspace_choices):
                messages.add_message(
                    self.request, messages.INFO, self.message_no_available_workspaces
                )

        except AnVILAPIError:
            workspace_choices = []
            messages.add_message(
                self.request, messages.ERROR, self.message_error_fetching_workspaces
            )

        return forms.WorkspaceImportForm(
            workspace_choices=workspace_choices, **self.get_form_kwargs()
        )

    def get_workspace_data_formset(self):
        """Return an instance of the workspace data form to be used in this view."""
        formset_prefix = "workspacedata"
        form_class = self.adapter.get_workspace_data_form_class()
        model = self.adapter.get_workspace_data_model()
        formset_factory = inlineformset_factory(
            models.Workspace,
            model,
            form=form_class,
            can_delete=False,
            can_delete_extra=False,
            absolute_max=1,
            max_num=1,
            min_num=1,
        )
        if self.request.method in ("POST"):
            formset = formset_factory(
                self.request.POST,
                instance=self.workspace,
                prefix=formset_prefix,
                initial=[{"workspace": self.workspace}],
            )
        else:
            formset = formset_factory(prefix=formset_prefix, initial=[{}])
        return formset

    def get_context_data(self, **kwargs):
        """Insert the workspace data form into the context dict."""
        if "workspace_data_formset" not in kwargs:
            kwargs["workspace_data_formset"] = self.get_workspace_data_formset()
        return super().get_context_data(**kwargs)

    def post(self, request, *args, **kwargs):
        """
        Handle POST requests: instantiate the forms instances with the passed
        POST variables and then check if they are valid.
        """
        self.adapter = self.get_adapter()
        self.workspace = None
        form = self.get_form()
        # First, check if the workspace form is valid.
        # If it is, we'll save the model and then check the workspace data form.
        if form.is_valid():
            return self.form_valid(form)
        else:
            workspace_data_formset = self.get_workspace_data_formset()
            return self.forms_invalid(form, workspace_data_formset)

    def get_success_url(self):
        return self.workspace.get_absolute_url()

    @transaction.atomic
    def form_valid(self, form):
        """If the form is valid, check that the workspace exists on AnVIL and save the associated model.
        Then check if the workspace_data_form is valid."""
        # Separate the billing project and workspace name.
        billing_project_name, workspace_name = form.cleaned_data["workspace"].split("/")

        try:
            workspace_type = self.adapter.get_type()
            # This is not ideal because we attempt to import the workspace before validating the workspace_data_Form.
            # However, we need to add the workspace to the form before validating it.
            self.workspace = models.Workspace.anvil_import(
                billing_project_name,
                workspace_name,
                workspace_type=workspace_type,
                note=form.cleaned_data["note"],
            )
            workspace_data_formset = self.get_workspace_data_formset()
            if not workspace_data_formset.is_valid():
                # Delete the workspace, since we are not raising an exception.
                # self.workspace.delete()
                transaction.set_rollback(True)
                return self.forms_invalid(form, workspace_data_formset)
            workspace_data_formset.forms[0].save()
        except anvil_api.AnVILAPIError as e:
            messages.add_message(
                self.request, messages.ERROR, "AnVIL API Error: " + str(e)
            )
            return self.render_to_response(self.get_context_data(form=form))
        return super().form_valid(form)

    def forms_invalid(self, form, workspace_data_formset):
        """If the form is invalid, render the invalid form."""
        return self.render_to_response(
            self.get_context_data(
                form=form, workspace_data_formset=workspace_data_formset
            )
        )


class WorkspaceClone(
    auth.AnVILConsortiumManagerEditRequired,
    SuccessMessageMixin,
    WorkspaceAdapterMixin,
    SingleObjectMixin,
    FormView,
):
    model = models.Workspace
    form_class = forms.WorkspaceCloneForm
    success_msg = "Successfully created Workspace on AnVIL."
    template_name = "anvil_consortium_manager/workspace_clone.html"

    def get_object(self, queryset=None):
        """Return the workspace to clone."""
        if queryset is None:
            queryset = self.get_queryset()
        # Filter the queryset based on kwargs.
        billing_project_slug = self.kwargs.get("billing_project_slug")
        workspace_slug = self.kwargs.get("workspace_slug")
        queryset = queryset.filter(
            billing_project__name=billing_project_slug, name=workspace_slug
        )
        try:
            # Get the single item from the filtered queryset
            obj = queryset.get()
        except queryset.model.DoesNotExist:
            raise Http404(
                _("No %(verbose_name)s found matching the query")
                % {"verbose_name": queryset.model._meta.verbose_name}
            )
        return obj

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        return super().get(request, *args, **kwargs)

    def get_initial(self):
        """Add the authorization domains of the workspace to be cloned to the form."""
        initial = super().get_initial()
        initial["authorization_domains"] = self.object.authorization_domains.all()
        return initial

    def get_form(self, form_class=None):
        """Return an instance of the form to be used in this view."""
        if form_class is None:
            form_class = self.get_form_class()
        return form_class(self.object, **self.get_form_kwargs())

    def get_workspace_data_formset(self):
        """Return an instance of the workspace data form to be used in this view."""
        formset_prefix = "workspacedata"
        form_class = self.adapter.get_workspace_data_form_class()
        model = self.adapter.get_workspace_data_model()
        formset_factory = inlineformset_factory(
            models.Workspace,
            model,
            form=form_class,
            can_delete=False,
            can_delete_extra=False,
            absolute_max=1,
            max_num=1,
            min_num=1,
        )
        if self.request.method in ("POST"):
            formset = formset_factory(
                self.request.POST,
                instance=self.new_workspace,
                prefix=formset_prefix,
                initial=[{"workspace": self.new_workspace}],
            )
        else:
            formset = formset_factory(prefix=formset_prefix, initial=[{}])
        return formset

    def get_context_data(self, **kwargs):
        """Insert the workspace data formset into the context dict."""
        if "workspace_data_formset" not in kwargs:
            kwargs["workspace_data_formset"] = self.get_workspace_data_formset()
        return super().get_context_data(**kwargs)

    def post(self, request, *args, **kwargs):
        """
        Handle POST requests: instantiate the forms instances with the passed
        POST variables and then check if they are valid.
        """
        self.adapter = self.get_adapter()
        self.object = self.get_object()
        self.new_workspace = None
        form = self.get_form()
        # First, check if the workspace form is valid.
        # If it is, we'll save the model and then check the workspace data formset in the post method.
        if form.is_valid():
            return self.form_valid(form)
        else:
            workspace_data_formset = self.get_workspace_data_formset()
            return self.forms_invalid(form, workspace_data_formset)

    def form_valid(self, form):
        """If the form(s) are valid, save the associated model(s) and create the workspace on AnVIL."""
        # Need to use a transaction because the object needs to be saved to access the many-to-many field.
        try:
            with transaction.atomic():
                # Calling form.save() does not create the history for the authorization domain many to many field.
                # Instead, save the workspace first and then create the auth domain relationships one by one.
                # Add the workspace data type from the adapter to the instance.
                form.instance.workspace_type = self.adapter.get_type()
                self.new_workspace = form.save(commit=False)
                self.new_workspace.save()
                # Now check the workspace_data_formset.
                workspace_data_formset = self.get_workspace_data_formset()
                if not workspace_data_formset.is_valid():
                    # Tell the transaction to roll back, since we are not raising an exception.
                    transaction.set_rollback(True)
                    return self.forms_invalid(form, workspace_data_formset)
                # Now save the auth domains and the workspace_data_form.
                for auth_domain in form.cleaned_data["authorization_domains"]:
                    models.WorkspaceAuthorizationDomain.objects.create(
                        workspace=self.new_workspace, group=auth_domain
                    )
                workspace_data_formset.forms[0].save()
                # Then create the workspace on AnVIL.
                authorization_domains = self.new_workspace.authorization_domains.all()
                print(authorization_domains)
                self.object.anvil_clone(
                    self.new_workspace.billing_project,
                    self.new_workspace.name,
                    authorization_domains=authorization_domains,
                )
        except AnVILAPIError as e:
            # If the API call failed, rerender the page with the responses and show a message.
            messages.add_message(
                self.request, messages.ERROR, "AnVIL API Error: " + str(e)
            )
            return self.render_to_response(
                self.get_context_data(
                    form=form, workspace_data_formset=workspace_data_formset
                )
            )
        return super().form_valid(form)

    def forms_invalid(self, form, workspace_data_formset):
        """If the form(s) are invalid, render the invalid form."""
        return self.render_to_response(
            self.get_context_data(
                form=form, workspace_data_formset=workspace_data_formset
            )
        )

    def get_success_url(self):
        return self.new_workspace.get_absolute_url()


class WorkspaceUpdate(
    auth.AnVILConsortiumManagerEditRequired,
    SuccessMessageMixin,
    WorkspaceAdapterMixin,
    UpdateView,
):
    """View to update information about an Account."""

    model = models.Workspace
    form_class = forms.WorkspaceUpdateForm
    slug_field = "name"
    template_name = "anvil_consortium_manager/workspace_update.html"
    success_msg = "Successfully updated Workspace."

    def get_object(self, queryset=None):
        """Return the object the view is displaying."""

        # Use a custom queryset if provided; this is required for subclasses
        # like DateDetailView
        if queryset is None:
            queryset = self.get_queryset()
        # Filter the queryset based on kwargs.
        billing_project_slug = self.kwargs.get("billing_project_slug", None)
        workspace_slug = self.kwargs.get("workspace_slug", None)
        queryset = queryset.filter(
            billing_project__name=billing_project_slug, name=workspace_slug
        )
        try:
            # Get the single item from the filtered queryset
            obj = queryset.get()
        except queryset.model.DoesNotExist:
            raise Http404(
                _("No %(verbose_name)s found matching the query")
                % {"verbose_name": queryset.model._meta.verbose_name}
            )
        return obj

    def get_workspace_type(self):
        """Return the workspace type of this workspace."""
        object = self.get_object()
        return object.workspace_type

    def get_workspace_data_formset(self):
        """Return an instance of the workspace data form to be used in this view."""
        formset_prefix = "workspacedata"
        form_class = self.adapter.get_workspace_data_form_class()
        model = self.adapter.get_workspace_data_model()
        formset_factory = inlineformset_factory(
            models.Workspace,
            model,
            form=form_class,
            # exclude=("workspace",),
            can_delete=False,
            can_delete_extra=False,
            absolute_max=1,
            max_num=1,
            min_num=1,
        )
        if self.request.method in ("POST"):
            formset = formset_factory(
                self.request.POST,
                instance=self.object,
                prefix=formset_prefix,
                initial=[{"workspace": self.object}],
            )
        else:
            formset = formset_factory(
                prefix=formset_prefix, initial=[{}], instance=self.object
            )
        return formset

    def get_context_data(self, **kwargs):
        """Insert the workspace data formset into the context dict."""
        if "workspace_data_formset" not in kwargs:
            kwargs["workspace_data_formset"] = self.get_workspace_data_formset()
        return super().get_context_data(**kwargs)

    def post(self, request, *args, **kwargs):
        """
        Handle POST requests: instantiate the forms instances with the passed
        POST variables and then check if they are valid.
        """
        self.object = self.get_object()
        self.adapter = self.get_adapter()
        form = self.get_form()
        workspace_data_formset = self.get_workspace_data_formset()
        if form.is_valid() and workspace_data_formset.is_valid():
            return self.form_valid(form, workspace_data_formset)
        else:
            return self.forms_invalid(form, workspace_data_formset)

    @transaction.atomic
    def form_valid(self, form, workspace_data_formset):
        """If the form(s) are valid, save the associated model(s) and create the workspace on AnVIL."""
        workspace_data_formset.save()
        return super().form_valid(form)

    def forms_invalid(self, form, workspace_data_formset):
        """If the form(s) are invalid, render the invalid form."""
        return self.render_to_response(
            self.get_context_data(
                form=form, workspace_data_formset=workspace_data_formset
            )
        )

    def get_success_url(self):
        return self.object.get_absolute_url()


class WorkspaceList(auth.AnVILConsortiumManagerViewRequired, SingleTableView):
    """Display a list of all workspaces using the default table."""

    model = models.Workspace
    table_class = tables.WorkspaceTable


class WorkspaceListByType(
    auth.AnVILConsortiumManagerViewRequired, WorkspaceAdapterMixin, SingleTableView
):
    """Display a list of workspaces of the given ``workspace_type``."""

    model = models.Workspace

    def get_queryset(self):
        return self.model.objects.filter(workspace_type=self.adapter.get_type())

    def get_table_class(self):
        """Use the adapter to get the table class."""
        table_class = self.adapter.get_list_table_class()
        return table_class


class WorkspaceDelete(
    auth.AnVILConsortiumManagerEditRequired, SuccessMessageMixin, DeleteView
):
    model = models.Workspace
    success_msg = "Successfully deleted Workspace on AnVIL."
    message_could_not_delete_workspace_from_app = (
        "Cannot delete workspace from app due to foreign key restrictions."
    )

    def get_object(self, queryset=None):
        """Return the object the view is displaying."""

        # Use a custom queryset if provided; this is required for subclasses
        # like DateDetailView
        if queryset is None:
            queryset = self.get_queryset()
        # Filter the queryset based on kwargs.
        billing_project_slug = self.kwargs.get("billing_project_slug", None)
        workspace_slug = self.kwargs.get("workspace_slug", None)
        queryset = queryset.filter(
            billing_project__name=billing_project_slug, name=workspace_slug
        )
        try:
            # Get the single item from the filtered queryset
            obj = queryset.get()
        except queryset.model.DoesNotExist:
            raise Http404(
                _("No %(verbose_name)s found matching the query")
                % {"verbose_name": queryset.model._meta.verbose_name}
            )
        return obj

    def get_success_url(self):
        return reverse(
            "anvil_consortium_manager:workspaces:list",
            args=[self.object.workspace_type],
        )

    def delete(self, request, *args, **kwargs):
        """
        Make an API call to AnVIL and then call the delete method on the object.
        """
        self.object = self.get_object()
        try:
            with transaction.atomic():
                self.object.delete()
                self.object.anvil_delete()
                self.add_success_message()
                response = HttpResponseRedirect(self.get_success_url())
        except (ProtectedError, RestrictedError):
            messages.add_message(
                self.request,
                messages.ERROR,
                self.message_could_not_delete_workspace_from_app,
            )
            response = HttpResponseRedirect(self.object.get_absolute_url())
        except AnVILAPIError as e:
            # The AnVIL call has failed for some reason.
            messages.add_message(
                self.request, messages.ERROR, "AnVIL API Error: " + str(e)
            )
            # Rerender the same page with an error message.
            response = self.render_to_response(self.get_context_data())
        return response


class WorkspaceAudit(
    auth.AnVILConsortiumManagerViewRequired, AnVILAuditMixin, TemplateView
):
    """View to run an audit on Workspaces and display the results."""

    template_name = "anvil_consortium_manager/workspace_audit.html"

    def run_audit(self):
        self.audit_results = models.Workspace.anvil_audit()


class WorkspaceSharingAudit(
    auth.AnVILConsortiumManagerViewRequired,
    SingleObjectMixin,
    AnVILAuditMixin,
    TemplateView,
):
    """View to run an audit on access to a specific Workspace and display the results."""

    model = models.Workspace
    template_name = "anvil_consortium_manager/workspace_sharing_audit.html"

    def get_object(self, queryset=None):
        """Return the object the view is displaying."""

        # Use a custom queryset if provided; this is required for subclasses
        # like DateDetailView
        if queryset is None:
            queryset = self.get_queryset()
        # Filter the queryset based on kwargs.
        billing_project_slug = self.kwargs.get("billing_project_slug", None)
        workspace_slug = self.kwargs.get("workspace_slug", None)
        queryset = queryset.filter(
            billing_project__name=billing_project_slug, name=workspace_slug
        )
        try:
            # Get the single item from the filtered queryset
            obj = queryset.get()
        except queryset.model.DoesNotExist:
            raise Http404(
                _("No %(verbose_name)s found matching the query")
                % {"verbose_name": queryset.model._meta.verbose_name}
            )
        return obj

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        # Otherwise, return the response.
        return super().get(request, *args, **kwargs)

    def run_audit(self):
        self.audit_results = self.object.anvil_audit_sharing()


class WorkspaceAutocomplete(
    auth.AnVILConsortiumManagerViewRequired, autocomplete.Select2QuerySetView
):
    """View to provide autocompletion for Workspaces.

    Right now this only matches Workspace name, not billing project."""

    def get_queryset(self):
        # Filter out unathorized users, or does the auth mixin do that?
        qs = models.Workspace.objects.filter().order_by("billing_project__name", "name")

        if self.q:
            qs = qs.filter(name__icontains=self.q)

        return qs


class GroupGroupMembershipDetail(auth.AnVILConsortiumManagerViewRequired, DetailView):
    model = models.GroupGroupMembership

    def get_object(self, queryset=None):
        """Return the object the view is displaying."""

        # Use a custom queryset if provided; this is required for subclasses
        # like DateDetailView
        if queryset is None:
            queryset = self.get_queryset()
        # Filter the queryset based on kwargs.
        parent_group_slug = self.kwargs.get("parent_group_slug", None)
        child_group_slug = self.kwargs.get("child_group_slug", None)
        queryset = queryset.filter(
            parent_group__name=parent_group_slug, child_group__name=child_group_slug
        )
        try:
            # Get the single item from the filtered queryset
            obj = queryset.get()
        except queryset.model.DoesNotExist:
            raise Http404(
                _("No %(verbose_name)s found matching the query")
                % {"verbose_name": queryset.model._meta.verbose_name}
            )
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        edit_permission_codename = (
            models.AnVILProjectManagerAccess.EDIT_PERMISSION_CODENAME
        )
        context["show_edit_links"] = self.request.user.has_perm(
            "anvil_consortium_manager." + edit_permission_codename
        )
        return context


class GroupGroupMembershipCreate(
    auth.AnVILConsortiumManagerEditRequired, SuccessMessageMixin, CreateView
):
    model = models.GroupGroupMembership
    form_class = forms.GroupGroupMembershipForm
    success_msg = "Successfully created group membership."

    def get_success_url(self):
        return reverse("anvil_consortium_manager:group_group_membership:list")

    def form_valid(self, form):
        """If the form is valid, save the associated model and create it on AnVIL."""
        # Create but don't save the new group.
        self.object = form.save(commit=False)
        # Make an API call to AnVIL to create the group.
        try:
            self.object.anvil_create()
        except AnVILAPIError as e:
            # If the API call failed, rerender the page with the responses and show a message.
            messages.add_message(
                self.request, messages.ERROR, "AnVIL API Error: " + str(e)
            )
            return self.render_to_response(self.get_context_data(form=form))
        # The object is saved by the super's form_valid method.
        return super().form_valid(form)


class GroupGroupMembershipCreateByParent(GroupGroupMembershipCreate):
    """View to create a new GroupGroupMembership object for the parent group specified in the url."""

    template_name = "anvil_consortium_manager/groupgroupmembership_form_byparent.html"
    message_not_managed_by_app = "Parent group is not managed by this app."

    def get_parent_group(self):
        try:
            name = self.kwargs["parent_group_slug"]
            group = models.ManagedGroup.objects.get(name=name)
        except models.ManagedGroup.DoesNotExist:
            raise Http404("ManagedGroup not found.")
        return group

    def check_group_errors(self):
        """Check parent and child groups and return an error message upon error."""
        if not self.parent_group.is_managed_by_app:
            return self.message_not_managed_by_app

    def get(self, request, *args, **kwargs):
        self.parent_group = self.get_parent_group()
        error = self.check_group_errors()
        if error:
            messages.error(self.request, error)
            return HttpResponseRedirect(self.parent_group.get_absolute_url())
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.parent_group = self.get_parent_group()
        error = self.check_group_errors()
        if error:
            messages.error(self.request, error)
            return HttpResponseRedirect(self.parent_group.get_absolute_url())
        return super().post(request, *args, **kwargs)

    def get_initial(self):
        initial = super().get_initial()
        initial["parent_group"] = self.parent_group
        return initial

    def get_form(self, **kwargs):
        """Get the form and set the inputs to use a hidden widget."""
        form = super().get_form(**kwargs)
        form.fields["parent_group"].widget = HiddenInput()
        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["parent_group"] = self.parent_group
        return context

    def get_success_url(self):
        return self.object.get_absolute_url()


class GroupGroupMembershipCreateByChild(GroupGroupMembershipCreate):
    """View to create a new GroupGroupMembership object for the child group specified in the url."""

    template_name = "anvil_consortium_manager/groupgroupmembership_form_bychild.html"

    def get_child_group(self):
        try:
            name = self.kwargs["group_slug"]
            group = models.ManagedGroup.objects.get(name=name)
        except models.ManagedGroup.DoesNotExist:
            raise Http404("ManagedGroup not found.")
        return group

    def get(self, request, *args, **kwargs):
        self.child_group = self.get_child_group()
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.child_group = self.get_child_group()
        return super().post(request, *args, **kwargs)

    def get_initial(self):
        initial = super().get_initial()
        initial["child_group"] = self.child_group
        return initial

    def get_form(self, **kwargs):
        """Get the form and set the inputs to use a hidden widget."""
        form = super().get_form(**kwargs)
        form.fields["child_group"].widget = HiddenInput()
        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["child_group"] = self.child_group
        return context

    def get_success_url(self):
        return self.object.get_absolute_url()


class GroupGroupMembershipCreateByParentChild(GroupGroupMembershipCreate):
    """View to create a new GroupGroupMembership object for the parent and child groups specified in the url."""

    template_name = (
        "anvil_consortium_manager/groupgroupmembership_form_byparentchild.html"
    )

    message_already_exists = (
        "Child group is already a member of the parent Managed Group."
    )
    message_cannot_add_group_to_itself = "Cannot add a group to itself as a member."
    message_circular_relationship = "Cannot add a circular group relationship."
    message_not_managed_by_app = "Parent group is not managed by this app."

    def get_parent_group(self):
        try:
            name = self.kwargs["parent_group_slug"]
            group = models.ManagedGroup.objects.get(name=name)
        except models.ManagedGroup.DoesNotExist:
            raise Http404("ManagedGroup not found.")
        return group

    def get_child_group(self):
        try:
            name = self.kwargs["child_group_slug"]
            group = models.ManagedGroup.objects.get(name=name)
        except models.ManagedGroup.DoesNotExist:
            raise Http404("ManagedGroup not found.")
        return group

    def check_group_errors(self):
        """Check parent and child groups and return an error message upon error."""
        if not self.parent_group.is_managed_by_app:
            return self.message_not_managed_by_app
        if self.parent_group == self.child_group:
            return self.message_cannot_add_group_to_itself
        if self.parent_group in self.child_group.get_all_children():
            return self.message_circular_relationship

    def get(self, request, *args, **kwargs):
        self.parent_group = self.get_parent_group()
        self.child_group = self.get_child_group()
        error = self.check_group_errors()
        if error:
            messages.error(self.request, error)
            return HttpResponseRedirect(self.parent_group.get_absolute_url())
        try:
            obj = models.GroupGroupMembership.objects.get(
                parent_group=self.parent_group, child_group=self.child_group
            )
            messages.error(self.request, self.message_already_exists)
            return HttpResponseRedirect(obj.get_absolute_url())
        except models.GroupGroupMembership.DoesNotExist:
            return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.parent_group = self.get_parent_group()
        self.child_group = self.get_child_group()
        error = self.check_group_errors()
        if error:
            messages.error(self.request, error)
            return HttpResponseRedirect(self.parent_group.get_absolute_url())
        try:
            obj = models.GroupGroupMembership.objects.get(
                parent_group=self.parent_group, child_group=self.child_group
            )
            messages.error(self.request, self.message_already_exists)
            return HttpResponseRedirect(obj.get_absolute_url())
        except models.GroupGroupMembership.DoesNotExist:
            return super().post(request, *args, **kwargs)

    def get_initial(self):
        initial = super().get_initial()
        initial["parent_group"] = self.parent_group
        initial["child_group"] = self.child_group
        return initial

    def get_form(self, **kwargs):
        """Get the form and set the inputs to use a hidden widget."""
        form = super().get_form(**kwargs)
        form.fields["parent_group"].widget = HiddenInput()
        form.fields["child_group"].widget = HiddenInput()
        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["parent_group"] = self.parent_group
        context["child_group"] = self.child_group
        return context

    def get_success_url(self):
        return self.object.get_absolute_url()


class GroupGroupMembershipList(
    auth.AnVILConsortiumManagerViewRequired, SingleTableView
):
    model = models.GroupGroupMembership
    table_class = tables.GroupGroupMembershipTable


class GroupGroupMembershipDelete(
    auth.AnVILConsortiumManagerEditRequired, SuccessMessageMixin, DeleteView
):
    model = models.GroupGroupMembership
    success_msg = "Successfully deleted group membership on AnVIL."

    message_parent_group_not_managed_by_app = (
        "Cannot remove members from parent group because it is not managed by this app."
    )

    def get_object(self, queryset=None):
        """Return the object the view is displaying."""

        # Use a custom queryset if provided; this is required for subclasses
        # like DateDetailView
        if queryset is None:
            queryset = self.get_queryset()
        # Filter the queryset based on kwargs.
        parent_group_slug = self.kwargs.get("parent_group_slug", None)
        child_group_slug = self.kwargs.get("child_group_slug", None)
        queryset = queryset.filter(
            parent_group__name=parent_group_slug, child_group__name=child_group_slug
        )
        try:
            # Get the single item from the filtered queryset
            obj = queryset.get()
        except queryset.model.DoesNotExist:
            raise Http404(
                _("No %(verbose_name)s found matching the query")
                % {"verbose_name": queryset.model._meta.verbose_name}
            )
        return obj

    def get_success_url(self):
        return self.parent_group.get_absolute_url()

    def get(self, request, *args, **kwargs):
        response = super().get(self, *args, **kwargs)
        # Check if managed by the app.
        if not self.object.parent_group.is_managed_by_app:
            messages.add_message(
                self.request,
                messages.ERROR,
                self.message_parent_group_not_managed_by_app,
            )
            # Redirect to the object detail page.
            return HttpResponseRedirect(self.object.get_absolute_url())
        # Otherwise, return the response.
        return response

    def delete(self, request, *args, **kwargs):
        """
        Make an API call to AnVIL and then call the delete method on the object.
        """
        self.object = self.get_object()
        self.parent_group = self.object.parent_group
        # Check if managed by the app.
        if not self.object.parent_group.is_managed_by_app:
            messages.add_message(
                self.request,
                messages.ERROR,
                self.message_parent_group_not_managed_by_app,
            )
            # Redirect to the object detail page.
            return HttpResponseRedirect(self.object.get_absolute_url())
        # Try to delete it on AnVIL.
        try:
            self.object.anvil_delete()
        except AnVILAPIError as e:
            # The AnVIL call has failed for some reason.
            messages.add_message(
                self.request, messages.ERROR, "AnVIL API Error: " + str(e)
            )
            # Rerender the same page with an error message.
            return self.render_to_response(self.get_context_data())
        return super().delete(request, *args, **kwargs)


class GroupAccountMembershipDetail(auth.AnVILConsortiumManagerViewRequired, DetailView):
    model = models.GroupAccountMembership

    def get_object(self, queryset=None):
        """Return the object the view is displaying."""

        # Use a custom queryset if provided; this is required for subclasses
        # like DateDetailView
        if queryset is None:
            queryset = self.get_queryset()
        # Filter the queryset based on kwargs.
        group_slug = self.kwargs.get("group_slug", None)
        account_uuid = self.kwargs.get("account_uuid", None)
        queryset = queryset.filter(group__name=group_slug, account__uuid=account_uuid)
        try:
            # Get the single item from the filtered queryset
            obj = queryset.get()
        except queryset.model.DoesNotExist:
            raise Http404(
                _("No %(verbose_name)s found matching the query")
                % {"verbose_name": queryset.model._meta.verbose_name}
            )
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        edit_permission_codename = (
            models.AnVILProjectManagerAccess.EDIT_PERMISSION_CODENAME
        )
        context["show_edit_links"] = self.request.user.has_perm(
            "anvil_consortium_manager." + edit_permission_codename
        )
        return context


class GroupAccountMembershipCreate(
    auth.AnVILConsortiumManagerEditRequired, SuccessMessageMixin, CreateView
):
    model = models.GroupAccountMembership
    form_class = forms.GroupAccountMembershipForm
    success_msg = "Successfully added account membership."

    def get_success_url(self):
        return reverse("anvil_consortium_manager:group_account_membership:list")

    def form_valid(self, form):
        """If the form is valid, save the associated model and create it on AnVIL."""
        # Create but don't save the new group.
        self.object = form.save(commit=False)
        # Make an API call to AnVIL to create the group.
        try:
            self.object.anvil_create()
        except AnVILAPIError as e:
            # If the API call failed, rerender the page with the responses and show a message.
            messages.add_message(
                self.request, messages.ERROR, "AnVIL API Error: " + str(e)
            )
            return self.render_to_response(self.get_context_data(form=form))
        # The object is saved by the super's form_valid method.
        return super().form_valid(form)


class GroupAccountMembershipCreateByGroup(GroupAccountMembershipCreate):
    """View to create a new GroupAccountMembership for the group specified in the url."""

    template_name = "anvil_consortium_manager/groupaccountmembership_form_bygroup.html"

    message_not_managed_by_app = (
        "Cannot add Account because this group is not managed by the app."
    )
    message_group_not_found = "Managed Group not found on AnVIL."
    """Message to display when the ManagedGroup was not found on AnVIL."""

    message_already_exists = "This Account is already a member of this Managed Group."

    def get_group(self):
        try:
            group_slug = self.kwargs["group_slug"]
            group = models.ManagedGroup.objects.get(name=group_slug)
        except models.ManagedGroup.DoesNotExist:
            raise Http404("Workspace or ManagedGroup not found.")
        return group

    def get(self, request, *args, **kwargs):
        self.group = self.get_group()
        if not self.group.is_managed_by_app:
            messages.error(self.request, self.message_not_managed_by_app)
            return HttpResponseRedirect(self.group.get_absolute_url())
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.group = self.get_group()
        if not self.group.is_managed_by_app:
            messages.error(self.request, self.message_not_managed_by_app)
            return HttpResponseRedirect(self.group.get_absolute_url())
        return super().post(request, *args, **kwargs)

    def get_initial(self):
        initial = super().get_initial()
        initial["group"] = self.group
        return initial

    def get_form(self, **kwargs):
        """Get the form and set the inputs to use a hidden widget."""
        form = super().get_form(**kwargs)
        form.fields["group"].widget = HiddenInput()
        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["group"] = self.group
        return context

    def get_success_url(self):
        return self.object.get_absolute_url()


class GroupAccountMembershipCreateByAccount(GroupAccountMembershipCreate):
    """View to create a new GroupAccountMembership for the account specified in the url."""

    template_name = (
        "anvil_consortium_manager/groupaccountmembership_form_byaccount.html"
    )

    message_not_managed_by_app = (
        "Cannot add Account because this group is not managed by the app."
    )
    message_group_not_found = "Managed Group not found on AnVIL."
    """Message to display when the ManagedGroup was not found on AnVIL."""

    message_already_exists = "This Account is already a member of this Managed Group."

    def get_account(self):
        try:
            account_uuid = self.kwargs["uuid"]
            account = models.Account.objects.get(uuid=account_uuid)
        except models.Account.DoesNotExist:
            raise Http404("Account not found.")
        return account

    def get(self, request, *args, **kwargs):
        self.account = self.get_account()
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.account = self.get_account()
        return super().post(request, *args, **kwargs)

    def get_initial(self):
        initial = super().get_initial()
        initial["account"] = self.account
        return initial

    def get_form(self, **kwargs):
        """Get the form and set the inputs to use a hidden widget."""
        form = super().get_form(**kwargs)
        form.fields["account"].widget = HiddenInput()
        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["account"] = self.account
        return context

    def get_success_url(self):
        return self.object.get_absolute_url()


class GroupAccountMembershipCreateByGroupAccount(GroupAccountMembershipCreate):
    """View to create a new GroupAccountMembership object for the group and account specified in the url."""

    template_name = (
        "anvil_consortium_manager/groupaccountmembership_form_bygroupaccount.html"
    )

    message_group_not_found = "Managed Group not found on AnVIL."
    """Message to display when the ManagedGroup was not found on AnVIL."""

    message_already_exists = "This Account is already a member of this Managed Group."

    def get_account(self):
        try:
            uuid = self.kwargs["account_uuid"]
            account = models.Account.objects.get(uuid=uuid)
        except models.Account.DoesNotExist:
            raise Http404("Account not found.")
        return account

    def get_group(self):
        try:
            group_slug = self.kwargs["group_slug"]
            group = models.ManagedGroup.objects.get(name=group_slug)
        except models.ManagedGroup.DoesNotExist:
            raise Http404("Workspace or ManagedGroup not found.")
        return group

    def get(self, request, *args, **kwargs):
        self.account = self.get_account()
        self.group = self.get_group()
        try:
            obj = models.GroupAccountMembership.objects.get(
                account=self.account, group=self.group
            )
            messages.error(self.request, self.message_already_exists)
            return HttpResponseRedirect(obj.get_absolute_url())
        except models.GroupAccountMembership.DoesNotExist:
            return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.account = self.get_account()
        self.group = self.get_group()
        try:
            obj = models.GroupAccountMembership.objects.get(
                account=self.account, group=self.group
            )
            messages.error(self.request, self.message_already_exists)
            return HttpResponseRedirect(obj.get_absolute_url())
        except models.GroupAccountMembership.DoesNotExist:
            return super().post(request, *args, **kwargs)

    def get_initial(self):
        initial = super().get_initial()
        initial["account"] = self.account
        initial["group"] = self.group
        return initial

    def get_form(self, **kwargs):
        """Get the form and set the inputs to use a hidden widget."""
        form = super().get_form(**kwargs)
        form.fields["account"].widget = HiddenInput()
        form.fields["group"].widget = HiddenInput()
        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["account"] = self.account
        context["group"] = self.group
        return context

    def get_success_url(self):
        return self.object.get_absolute_url()


class GroupAccountMembershipList(
    auth.AnVILConsortiumManagerViewRequired, SingleTableView
):
    """Show a list of all group memberships regardless of account active/inactive status."""

    model = models.GroupAccountMembership
    table_class = tables.GroupAccountMembershipTable


class GroupAccountMembershipActiveList(
    auth.AnVILConsortiumManagerViewRequired, SingleTableView
):
    """Show a list of all group memberships for active accounts."""

    model = models.GroupAccountMembership
    table_class = tables.GroupAccountMembershipTable

    def get_queryset(self):
        return self.model.objects.filter(account__status=models.Account.ACTIVE_STATUS)


class GroupAccountMembershipInactiveList(
    auth.AnVILConsortiumManagerViewRequired, SingleTableView
):
    """Show a list of all group memberships for inactive accounts."""

    model = models.GroupAccountMembership
    table_class = tables.GroupAccountMembershipTable

    def get_queryset(self):
        return self.model.objects.filter(account__status=models.Account.INACTIVE_STATUS)


class GroupAccountMembershipDelete(
    auth.AnVILConsortiumManagerEditRequired, SuccessMessageMixin, DeleteView
):
    model = models.GroupAccountMembership
    success_msg = "Successfully deleted account membership on AnVIL."

    message_group_not_managed_by_app = (
        "Cannot remove members from group because it is not managed by this app."
    )

    def get_object(self, queryset=None):
        """Return the object the view is displaying."""

        # Use a custom queryset if provided; this is required for subclasses
        # like DateDetailView
        if queryset is None:
            queryset = self.get_queryset()
        # Filter the queryset based on kwargs.
        group_slug = self.kwargs.get("group_slug", None)
        account_uuid = self.kwargs.get("account_uuid", None)
        queryset = queryset.filter(group__name=group_slug, account__uuid=account_uuid)
        try:
            # Get the single item from the filtered queryset
            obj = queryset.get()
        except queryset.model.DoesNotExist:
            raise Http404(
                _("No %(verbose_name)s found matching the query")
                % {"verbose_name": queryset.model._meta.verbose_name}
            )
        return obj

    def get_success_url(self):
        return self.group.get_absolute_url()

    def get(self, request, *args, **kwargs):
        response = super().get(self, *args, **kwargs)
        # Check if managed by the app.
        if not self.object.group.is_managed_by_app:
            messages.add_message(
                self.request, messages.ERROR, self.message_group_not_managed_by_app
            )
            # Redirect to the object detail page.
            return HttpResponseRedirect(self.object.get_absolute_url())
        # Otherwise, return the response.
        return response

    def delete(self, request, *args, **kwargs):
        """
        Make an API call to AnVIL and then call the delete method on the object.
        """
        self.object = self.get_object()
        self.group = self.object.group
        # Check if managed by the app.
        if not self.object.group.is_managed_by_app:
            messages.add_message(
                self.request, messages.ERROR, self.message_group_not_managed_by_app
            )
            # Redirect to the object detail page.
            return HttpResponseRedirect(self.object.get_absolute_url())
        # Try to delete from AnVIL.
        try:
            self.object.anvil_delete()
        except AnVILAPIError as e:
            # The AnVIL call has failed for some reason.
            messages.add_message(
                self.request, messages.ERROR, "AnVIL API Error: " + str(e)
            )
            # Rerender the same page with an error message.
            return self.render_to_response(self.get_context_data())
        return super().delete(request, *args, **kwargs)


class WorkspaceGroupSharingDetail(auth.AnVILConsortiumManagerViewRequired, DetailView):
    model = models.WorkspaceGroupSharing

    def get_object(self, queryset=None):
        """Return the object the view is displaying."""

        # Use a custom queryset if provided; this is required for subclasses
        # like DateDetailView
        if queryset is None:
            queryset = self.get_queryset()
        # Filter the queryset based on kwargs.
        billing_project_slug = self.kwargs.get("billing_project_slug", None)
        workspace_slug = self.kwargs.get("workspace_slug", None)
        group_slug = self.kwargs.get("group_slug", None)
        queryset = queryset.filter(
            workspace__billing_project__name=billing_project_slug,
            workspace__name=workspace_slug,
            group__name=group_slug,
        )
        try:
            # Get the single item from the filtered queryset
            obj = queryset.get()
        except queryset.model.DoesNotExist:
            raise Http404(
                _("No %(verbose_name)s found matching the query")
                % {"verbose_name": queryset.model._meta.verbose_name}
            )
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        edit_permission_codename = (
            models.AnVILProjectManagerAccess.EDIT_PERMISSION_CODENAME
        )
        context["show_edit_links"] = self.request.user.has_perm(
            "anvil_consortium_manager." + edit_permission_codename
        )
        return context


class WorkspaceGroupSharingCreate(
    auth.AnVILConsortiumManagerEditRequired, SuccessMessageMixin, CreateView
):
    """View to create a new WorkspaceGroupSharing object and share the Workspace with a Group on AnVIL."""

    model = models.WorkspaceGroupSharing
    form_class = forms.WorkspaceGroupSharingForm
    success_msg = "Successfully shared Workspace with Group."
    """Message to display when the WorkspaceGroupSharing object was successfully created in the app and on AnVIL."""

    message_group_not_found = "Managed Group not found on AnVIL."
    """Message to display when the ManagedGroup was not found on AnVIL."""

    def get_success_url(self):
        """URL to redirect to upon success."""
        return reverse("anvil_consortium_manager:workspace_group_sharing:list")

    def form_valid(self, form):
        """If the form is valid, save the associated model and create it on AnVIL."""
        # Create but don't save the new group.
        self.object = form.save(commit=False)
        # Make an API call to AnVIL to create the group.
        try:
            self.object.anvil_create_or_update()
        except exceptions.AnVILGroupNotFound:
            messages.add_message(
                self.request, messages.ERROR, self.message_group_not_found
            )
            return self.render_to_response(self.get_context_data(form=form))
        except AnVILAPIError as e:
            # If the API call failed, rerender the page with the responses and show a message.
            messages.add_message(
                self.request, messages.ERROR, "AnVIL API Error: " + str(e)
            )
            return self.render_to_response(self.get_context_data(form=form))
        # The object is saved by the super's form_valid method.
        return super().form_valid(form)


class WorkspaceGroupSharingCreateByWorkspace(WorkspaceGroupSharingCreate):
    """View to create a new WorkspaceGroupSharing object for the workspace specified in the url."""

    model = models.WorkspaceGroupSharing
    form_class = forms.WorkspaceGroupSharingForm
    template_name = (
        "anvil_consortium_manager/workspacegroupsharing_form_byworkspace.html"
    )
    success_msg = "Successfully shared Workspace with Group."
    """Message to display when the WorkspaceGroupSharing object was successfully created in the app and on AnVIL."""

    message_group_not_found = "Managed Group not found on AnVIL."
    """Message to display when the ManagedGroup was not found on AnVIL."""

    message_already_exists = (
        "This workspace has already been shared with this managed group."
    )

    def get_workspace(self):
        try:
            billing_project_slug = self.kwargs["billing_project_slug"]
            workspace_slug = self.kwargs["workspace_slug"]
            workspace = models.Workspace.objects.get(
                billing_project__name=billing_project_slug, name=workspace_slug
            )
        except models.Workspace.DoesNotExist:
            raise Http404("Workspace not found.")
        return workspace

    def get(self, request, *args, **kwargs):
        self.workspace = self.get_workspace()
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.workspace = self.get_workspace()
        return super().post(request, *args, **kwargs)

    def get_initial(self):
        initial = super().get_initial()
        initial["workspace"] = self.workspace
        return initial

    def get_form(self, **kwargs):
        """Get the form and set the inputs to use a hidden widget."""
        form = super().get_form(**kwargs)
        form.fields["workspace"].widget = HiddenInput()
        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["workspace"] = self.workspace
        return context

    def get_success_url(self):
        return self.object.get_absolute_url()


class WorkspaceGroupSharingCreateByGroup(WorkspaceGroupSharingCreate):
    """View to create a new WorkspaceGroupSharing object for the group specified in the url."""

    model = models.WorkspaceGroupSharing
    form_class = forms.WorkspaceGroupSharingForm
    template_name = "anvil_consortium_manager/workspacegroupsharing_form_bygroup.html"
    success_msg = "Successfully shared Workspace with Group."
    """Message to display when the WorkspaceGroupSharing object was successfully created in the app and on AnVIL."""

    message_group_not_found = "Managed Group not found on AnVIL."
    """Message to display when the ManagedGroup was not found on AnVIL."""

    message_already_exists = (
        "This workspace has already been shared with this managed group."
    )

    def get_group(self):
        try:
            group_slug = self.kwargs["group_slug"]
            group = models.ManagedGroup.objects.get(name=group_slug)
        except models.ManagedGroup.DoesNotExist:
            raise Http404("Workspace or ManagedGroup not found.")
        return group

    def get(self, request, *args, **kwargs):
        self.group = self.get_group()
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.group = self.get_group()
        return super().post(request, *args, **kwargs)

    def get_initial(self):
        initial = super().get_initial()
        initial["group"] = self.group
        return initial

    def get_form(self, **kwargs):
        """Get the form and set the inputs to use a hidden widget."""
        form = super().get_form(**kwargs)
        form.fields["group"].widget = HiddenInput()
        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["group"] = self.group
        return context

    def get_success_url(self):
        return self.object.get_absolute_url()


class WorkspaceGroupSharingCreateByWorkspaceGroup(WorkspaceGroupSharingCreate):
    """View to create a new WorkspaceGroupSharing object for the workspace and group specified in the url."""

    model = models.WorkspaceGroupSharing
    form_class = forms.WorkspaceGroupSharingForm
    template_name = (
        "anvil_consortium_manager/workspacegroupsharing_form_byworkspacegroup.html"
    )
    success_msg = "Successfully shared Workspace with Group."
    """Message to display when the WorkspaceGroupSharing object was successfully created in the app and on AnVIL."""

    message_group_not_found = "Managed Group not found on AnVIL."
    """Message to display when the ManagedGroup was not found on AnVIL."""

    message_already_exists = (
        "This workspace has already been shared with this managed group."
    )

    def get_workspace(self):
        try:
            billing_project_slug = self.kwargs["billing_project_slug"]
            workspace_slug = self.kwargs["workspace_slug"]
            workspace = models.Workspace.objects.get(
                billing_project__name=billing_project_slug, name=workspace_slug
            )
        except models.Workspace.DoesNotExist:
            raise Http404("Workspace not found.")
        return workspace

    def get_group(self):
        try:
            group_slug = self.kwargs["group_slug"]
            group = models.ManagedGroup.objects.get(name=group_slug)
        except models.ManagedGroup.DoesNotExist:
            raise Http404("Workspace or ManagedGroup not found.")
        return group

    def get(self, request, *args, **kwargs):
        self.workspace = self.get_workspace()
        self.group = self.get_group()
        try:
            obj = models.WorkspaceGroupSharing.objects.get(
                workspace=self.workspace, group=self.group
            )
            messages.error(self.request, self.message_already_exists)
            return HttpResponseRedirect(obj.get_absolute_url())
        except models.WorkspaceGroupSharing.DoesNotExist:
            return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.workspace = self.get_workspace()
        self.group = self.get_group()
        try:
            obj = models.WorkspaceGroupSharing.objects.get(
                workspace=self.workspace, group=self.group
            )
            messages.error(self.request, self.message_already_exists)
            return HttpResponseRedirect(obj.get_absolute_url())
        except models.WorkspaceGroupSharing.DoesNotExist:
            return super().post(request, *args, **kwargs)

    def get_initial(self):
        initial = super().get_initial()
        initial["workspace"] = self.workspace
        initial["group"] = self.group
        return initial

    def get_form(self, **kwargs):
        """Get the form and set the inputs to use a hidden widget."""
        form = super().get_form(**kwargs)
        form.fields["workspace"].widget = HiddenInput()
        form.fields["group"].widget = HiddenInput()
        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["workspace"] = self.workspace
        context["group"] = self.group
        return context

    def get_success_url(self):
        return self.object.get_absolute_url()


class WorkspaceGroupSharingUpdate(
    auth.AnVILConsortiumManagerEditRequired, SuccessMessageMixin, UpdateView
):
    """View to update a WorkspaceGroupSharing object and on AnVIL."""

    model = models.WorkspaceGroupSharing
    fields = (
        "access",
        "can_compute",
    )
    template_name = "anvil_consortium_manager/workspacegroupsharing_update.html"
    success_msg = "Successfully updated Workspace sharing."
    """Message to display when the WorkspaceGroupSharing object was successfully updated."""

    def get_object(self, queryset=None):
        """Return the object the view is displaying."""

        # Use a custom queryset if provided; this is required for subclasses
        # like DateDetailView
        if queryset is None:
            queryset = self.get_queryset()
        # Filter the queryset based on kwargs.
        billing_project_slug = self.kwargs.get("billing_project_slug", None)
        workspace_slug = self.kwargs.get("workspace_slug", None)
        group_slug = self.kwargs.get("group_slug", None)
        queryset = queryset.filter(
            workspace__billing_project__name=billing_project_slug,
            workspace__name=workspace_slug,
            group__name=group_slug,
        )
        try:
            # Get the single item from the filtered queryset
            obj = queryset.get()
        except queryset.model.DoesNotExist:
            raise Http404(
                _("No %(verbose_name)s found matching the query")
                % {"verbose_name": queryset.model._meta.verbose_name}
            )
        return obj

    def form_valid(self, form):
        """If the form is valid, save the associated model and create it on AnVIL."""
        # Create but don't save the new group.
        self.object = form.save(commit=False)
        # Make an API call to AnVIL to create the group.
        try:
            self.object.anvil_create_or_update()
        except AnVILAPIError as e:
            # If the API call failed, rerender the page with the responses and show a message.
            messages.add_message(
                self.request, messages.ERROR, "AnVIL API Error: " + str(e)
            )
            return self.render_to_response(self.get_context_data(form=form))
        # The object is saved by the super's form_valid method.
        return super().form_valid(form)


class WorkspaceGroupSharingList(
    auth.AnVILConsortiumManagerViewRequired, SingleTableView
):
    model = models.WorkspaceGroupSharing
    table_class = tables.WorkspaceGroupSharingTable


class WorkspaceGroupSharingDelete(
    auth.AnVILConsortiumManagerEditRequired, SuccessMessageMixin, DeleteView
):
    model = models.WorkspaceGroupSharing
    success_msg = "Successfully removed workspace sharing on AnVIL."

    def get_object(self, queryset=None):
        """Return the object the view is displaying."""

        # Use a custom queryset if provided; this is required for subclasses
        # like DateDetailView
        if queryset is None:
            queryset = self.get_queryset()
        # Filter the queryset based on kwargs.
        billing_project_slug = self.kwargs.get("billing_project_slug", None)
        workspace_slug = self.kwargs.get("workspace_slug", None)
        group_slug = self.kwargs.get("group_slug", None)
        queryset = queryset.filter(
            workspace__billing_project__name=billing_project_slug,
            workspace__name=workspace_slug,
            group__name=group_slug,
        )
        try:
            # Get the single item from the filtered queryset
            obj = queryset.get()
        except queryset.model.DoesNotExist:
            raise Http404(
                _("No %(verbose_name)s found matching the query")
                % {"verbose_name": queryset.model._meta.verbose_name}
            )
        return obj

    def get_success_url(self):
        return reverse("anvil_consortium_manager:workspace_group_sharing:list")

    def delete(self, request, *args, **kwargs):
        """
        Make an API call to AnVIL and then call the delete method on the object.
        """
        self.object = self.get_object()
        try:
            self.object.anvil_delete()
        except AnVILAPIError as e:
            # The AnVIL call has failed for some reason.
            messages.add_message(
                self.request, messages.ERROR, "AnVIL API Error: " + str(e)
            )
            # Rerender the same page with an error message.
            return self.render_to_response(self.get_context_data())
        return super().delete(request, *args, **kwargs)
