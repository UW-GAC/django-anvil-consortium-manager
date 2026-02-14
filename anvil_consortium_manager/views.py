import logging

from dal import autocomplete
from django.conf import settings
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import mail_admins
from django.db import transaction
from django.db.models import ProtectedError, Q, RestrictedError
from django.forms import Form, HiddenInput, inlineformset_factory
from django.http import Http404, HttpResponseRedirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, DeleteView, DetailView, FormView, RedirectView, TemplateView, UpdateView
from django.views.generic.detail import SingleObjectMixin
from django_filters.views import FilterView
from django_tables2 import SingleTableMixin, SingleTableView

from . import __version__, anvil_api, auth, exceptions, filters, forms, models, tables, viewmixins
from .adapters.account import get_account_adapter
from .adapters.workspace import workspace_adapter_registry
from .anvil_api import AnVILAPIClient, AnVILAPIError
from .tokens import account_verification_token

logger = logging.getLogger(__name__)


class Index(auth.AnVILConsortiumManagerStaffViewRequired, TemplateView):
    template_name = "anvil_consortium_manager/index.html"

    def get_context_data(self, *args, **kwargs):
        """Add ACM version to the context data."""
        if "app_version" not in kwargs:
            kwargs["app_version"] = __version__
        return super().get_context_data(**kwargs)


class AnVILStatus(auth.AnVILConsortiumManagerStaffViewRequired, TemplateView):
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
            messages.add_message(self.request, messages.ERROR, "AnVIL API Error: error checking API user")
            context["anvil_user"] = None
        return context


class BillingProjectImport(auth.AnVILConsortiumManagerStaffEditRequired, SuccessMessageMixin, CreateView):
    model = models.BillingProject
    form_class = forms.BillingProjectImportForm
    template_name = "anvil_consortium_manager/billingproject_import.html"
    message_not_users_of_billing_project = "Not a user of requested billing project or it doesn't exist on AnVIL."
    success_message = "Successfully imported Billing Project from AnVIL."
    message_error_fetching_billing_projects = "Unable to fetch billing projects from AnVIL."
    message_no_available_billing_projects = "No unimported billing projects available for import from AnVIL."

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()

        try:
            all_billing_projects = AnVILAPIClient().get_billing_projects().json()

            unimported_billing_project_names = []

            for billing_project in all_billing_projects:
                billing_project_name = billing_project["projectName"]
                if not models.BillingProject.objects.filter(name__iexact=billing_project_name).exists():
                    unimported_billing_project_names.append(billing_project_name)

            if not unimported_billing_project_names:
                messages.add_message(self.request, messages.INFO, self.message_no_available_billing_projects)

            billing_project_choices = [(x, x) for x in sorted(unimported_billing_project_names)]
            kwargs["billing_project_choices"] = billing_project_choices

        except AnVILAPIError:
            messages.add_message(self.request, messages.ERROR, self.message_error_fetching_billing_projects)

        return kwargs

    def form_valid(self, form):
        """If the form is valid, check that we can access the BillingProject on AnVIL and save the associated model."""
        try:
            self.object = models.BillingProject.anvil_import(
                form.cleaned_data["name"],
                note=form.cleaned_data["note"],
            )
        except anvil_api.AnVILAPIError404:
            # Either the workspace doesn't exist or we don't have permission for it.
            messages.add_message(self.request, messages.ERROR, self.message_not_users_of_billing_project)
            return self.render_to_response(self.get_context_data(form=form))
        except anvil_api.AnVILAPIError as e:
            # If the API call failed for some other reason, rerender the page with the responses and show a message.
            messages.add_message(self.request, messages.ERROR, "AnVIL API Error: " + str(e))
            return self.render_to_response(self.get_context_data(form=form))

        messages.add_message(self.request, messages.SUCCESS, self.success_message)
        return HttpResponseRedirect(self.get_success_url())


class BillingProjectUpdate(auth.AnVILConsortiumManagerStaffEditRequired, SuccessMessageMixin, UpdateView):
    """View to update information about a Billing Project."""

    model = models.BillingProject
    slug_field = "name"
    form_class = forms.BillingProjectUpdateForm
    template_name = "anvil_consortium_manager/billingproject_update.html"
    success_message = "Successfully updated Billing Project."


class BillingProjectDetail(auth.AnVILConsortiumManagerStaffViewRequired, SingleTableMixin, DetailView):
    model = models.BillingProject
    slug_field = "name"
    context_table_name = "workspace_table"

    def get_table(self):
        return tables.WorkspaceStaffTable(self.object.workspace_set.all(), exclude="billing_project")

    def get_context_data(self, **kwargs):
        """Add show_edit_links to context data."""
        context = super().get_context_data(**kwargs)
        edit_permission_codename = models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME
        context["show_edit_links"] = self.request.user.has_perm("anvil_consortium_manager." + edit_permission_codename)
        return context


class BillingProjectList(auth.AnVILConsortiumManagerStaffViewRequired, SingleTableMixin, FilterView):
    model = models.BillingProject
    table_class = tables.BillingProjectStaffTable
    ordering = ("name",)
    template_name = "anvil_consortium_manager/billingproject_list.html"

    filterset_class = filters.BillingProjectListFilter


class BillingProjectAutocomplete(auth.AnVILConsortiumManagerStaffViewRequired, autocomplete.Select2QuerySetView):
    """View to provide autocompletion for BillingProjects. Only billing project where the app is a user are included."""

    def get_queryset(self):
        # Only active accounts.
        qs = models.BillingProject.objects.filter(has_app_as_user=True).order_by("name")

        if self.q:
            qs = qs.filter(name__icontains=self.q)

        return qs


class AccountDetail(
    auth.AnVILConsortiumManagerStaffViewRequired,
    viewmixins.SingleAccountMixin,
    DetailView,
):
    """Render detail page for an :class:`anvil_consortium_manager.models.Account`."""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add an indicator of whether the account is inactive.
        context["is_inactive"] = self.object.status == models.Account.INACTIVE_STATUS
        edit_permission_codename = models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME
        context["show_edit_links"] = self.request.user.has_perm("anvil_consortium_manager." + edit_permission_codename)
        context["show_deactivate_button"] = not context["is_inactive"]
        context["show_reactivate_button"] = context["is_inactive"]
        context["show_unlink_button"] = self.object.user is not None
        context["unlinked_users"] = self.object.unlinked_users.all()
        try:
            context["user_detail_link"] = self.object.user.get_absolute_url()
        except AttributeError:
            context["user_detail_link"] = None
        context["group_table"] = tables.GroupAccountMembershipStaffTable(
            self.object.groupaccountmembership_set.all(),
            exclude=["account", "is_service_account"],
        )

        all_account_groups = self.object.get_all_groups()

        # Get a list of all workspaces.
        # For each workspace, check if it's accessible to the account.
        # Put unknown workspaces into their own array.
        accessible_workspaces = []
        unknown_workspaces = []
        for workspace in models.Workspace.objects.filter(
            Q(workspacegroupsharing__group__in=all_account_groups)
            | Q(workspacegroupsharing__group__is_managed_by_app=False)
        ):
            try:
                if workspace.is_accessible_by_account(self.object, all_account_groups=all_account_groups):
                    accessible_workspaces.append(workspace)
                else:
                    pass
            # Determine why access is not known, and add fields to be used in the table later.
            except exceptions.AnVILNotWorkspaceOwnerError:
                # This means that the app can't determine workspace access because the account is not the owner.
                workspace.sharing_known = None
                workspace.auth_domain_known = None
                workspace.owned_by_app = False
                unknown_workspaces.append(workspace)
            except exceptions.WorkspaceAccessSharingUnknownError:
                # This means that the app can't determine workspace access due to sharing.
                workspace.sharing_known = False
                workspace.auth_domain_known = True
                workspace.owned_by_app = True
                unknown_workspaces.append(workspace)
            except exceptions.WorkspaceAccessAuthorizationDomainUnknownError:
                # This means that the app can't determine workspace access due to auth domain membership.
                workspace.sharing_known = True
                workspace.auth_domain_known = False
                workspace.owned_by_app = True
                unknown_workspaces.append(workspace)
            except exceptions.WorkspaceAccessUnknownError:
                workspace.sharing_known = False
                workspace.auth_domain_known = False
                workspace.owned_by_app = True
                unknown_workspaces.append(workspace)
        # Accessible
        accessible_sharing = models.WorkspaceGroupSharing.objects.filter(
            workspace__in=accessible_workspaces,
            group__in=all_account_groups,
        ).order_by("workspace", "group")
        context["accessible_workspace_table"] = tables.WorkspaceGroupSharingStaffTable(accessible_sharing)

        # List of workspaces with unknown access.
        # We do not show sharing records here because it is too confusing.
        context["unknown_access_workspace_table"] = tables.WorkspaceAccessUnknownStaffTable(unknown_workspaces)
        return context


class AccountImport(auth.AnVILConsortiumManagerStaffEditRequired, SuccessMessageMixin, CreateView):
    """Import an account from AnVIL.

    This view checks that the specified email has a valid AnVIL account. If so, it saves a record in the database.
    """

    model = models.Account
    template_name = "anvil_consortium_manager/account_import.html"

    message_account_does_not_exist = "This account does not exist on AnVIL."
    """A string that can be displayed if the account does not exist on AnVIL."""

    message_email_associated_with_group = "This email is associated with a group, not a user."
    """A string that can be displayed if the account does not exist on AnVIL."""

    form_class = forms.AccountImportForm
    """A string that can be displayed if the account does not exist on AnVIL."""

    success_message = "Successfully imported Account from AnVIL."
    """A string that can be displayed if the account was imported successfully."""

    def form_valid(self, form):
        """If the form is valid, check that the account exists on AnVIL and save the associated model."""
        object = form.save(commit=False)
        try:
            account_exists = object.anvil_exists()
        except AnVILAPIError as e:
            msg = "AnVIL API Error: " + str(e)
            # If the API call failed for some other reason, rerender the page with the responses and show a message.
            messages.add_message(self.request, messages.ERROR, msg)
            return self.render_to_response(self.get_context_data(form=form))
        if not account_exists:
            messages.add_message(self.request, messages.ERROR, self.message_account_does_not_exist)
            # Re-render the page with a message.
            return self.render_to_response(self.get_context_data(form=form))

        return super().form_valid(form)


class AccountUpdate(
    auth.AnVILConsortiumManagerStaffEditRequired,
    SuccessMessageMixin,
    viewmixins.SingleAccountMixin,
    UpdateView,
):
    """View to update information about an Account."""

    model = models.Account
    form_class = forms.AccountUpdateForm
    template_name = "anvil_consortium_manager/account_update.html"
    success_message = "Successfully updated Account."


class AccountLink(auth.AnVILConsortiumManagerAccountLinkRequired, SuccessMessageMixin, FormView):
    """View where a user enter their AnVIL email to get an email verification link."""

    login_url = settings.LOGIN_URL
    template_name = "anvil_consortium_manager/account_link.html"
    model = models.UserEmailEntry
    message_account_does_not_exist = "This account does not exist on AnVIL."
    message_user_already_linked = "You have already linked an AnVIL account."
    message_account_already_exists = "An AnVIL Account with this email already exists in this app."
    form_class = forms.UserEmailEntryForm
    success_message = "To complete linking the account, check your email for a verification link."

    def get_redirect_url(self):
        return reverse(get_account_adapter().account_link_redirect)

    def get(self, request, *args, **kwargs):
        """Check if the user already has an account linked and redirect."""
        try:
            request.user.account
        except models.Account.DoesNotExist:
            return super().get(request, *args, **kwargs)
        else:
            # The user already has a linked account, so redirect with a message.
            messages.add_message(self.request, messages.ERROR, self.message_user_already_linked)
            return HttpResponseRedirect(self.get_redirect_url())

    def post(self, request, *args, **kwargs):
        """Check if the user already has an account linked and redirect."""
        try:
            request.user.account
        except models.Account.DoesNotExist:
            return super().post(request, *args, **kwargs)
        else:
            # The user already has a linked account, so redirect with a message.
            messages.add_message(self.request, messages.ERROR, self.message_user_already_linked)
            return HttpResponseRedirect(self.get_redirect_url())

    def get_success_url(self):
        return self.get_redirect_url()

    def form_valid(self, form):
        """If the form is valid, check that the email exists on AnVIL and send verification email."""
        email = form.cleaned_data.get("email")

        try:
            email_entry = models.UserEmailEntry.objects.get(email__iexact=email, user=self.request.user)
        except models.UserEmailEntry.DoesNotExist:
            email_entry = models.UserEmailEntry(email=email, user=self.request.user)

        # Check if this email has an account already linked to a different user.
        # Don't need to check the user, because a user who has already linked their account shouldn't get here.
        if models.Account.objects.filter(email=email, user__isnull=False).count():
            # The user already has a linked account, so redirect with a message.
            messages.add_message(self.request, messages.ERROR, self.message_account_already_exists)
            return HttpResponseRedirect(self.get_redirect_url())

        if models.AccountUserArchive.objects.filter(account__email=email).exists():
            # The Account was already linked to a previous user, so redirect with a message.
            messages.add_message(self.request, messages.ERROR, self.message_account_already_exists)
            return HttpResponseRedirect(self.get_redirect_url())

        # Check if it exists on AnVIL.
        try:
            anvil_account_exists = email_entry.anvil_account_exists()
        except AnVILAPIError as e:
            messages.add_message(self.request, messages.ERROR, "AnVIL API Error: " + str(e))
            return self.render_to_response(self.get_context_data(form=form))

        if not anvil_account_exists:
            messages.add_message(self.request, messages.ERROR, self.message_account_does_not_exist)
            # Re-render the page with a message.
            return self.render_to_response(self.get_context_data(form=form))

        email_entry.date_verification_email_sent = timezone.now()
        email_entry.save()
        email_entry.send_verification_email(get_current_site(self.request).domain)

        return super().form_valid(form)


class AccountLinkVerify(auth.AnVILConsortiumManagerAccountLinkRequired, RedirectView):
    """View where a user can verify their email and create an Account object."""

    message_already_linked = "You have already linked an AnVIL account."
    message_link_invalid = "AnVIL account verification link is invalid."
    message_account_already_exists = "An AnVIL Account with this email already exists in this app."
    message_account_does_not_exist = "This account does not exist on AnVIL."
    message_service_account = "Account is already marked as a service account."
    message_success = get_account_adapter().account_link_verify_message
    # after_account_verification hook errors
    log_message_after_account_link_failed = "Error in after_account_verification hook"
    mail_subject_after_account_link_failed = "AccountLinkVerify - error encountered in after_account_verification"
    mail_template_after_account_link_failed = "anvil_consortium_manager/account_link_error_email.html"
    # send_account_verification_notification_email hook errors
    log_message_send_account_verification_notification_email_failed = (
        "Error in send_account_verification_notification_email hook"
    )
    mail_subject_send_account_verification_notification_email_failed = (
        "AccountLinkVerify - error encountered in send_account_verification_notification_email"
    )
    mail_template_send_account_verification_notification_email_failed = (
        "anvil_consortium_manager/account_link_error_email.html"
    )

    def get_redirect_url(self, *args, **kwargs):
        return reverse(get_account_adapter().account_link_redirect)

    def get(self, request, *args, **kwargs):
        # Check if this user already has an account linked.
        if models.Account.objects.filter(user=request.user).count():
            messages.add_message(self.request, messages.ERROR, self.message_already_linked)
            return super().get(request, *args, **kwargs)

        uuid = kwargs.get("uuid")
        token = kwargs.get("token")

        try:
            email_entry = models.UserEmailEntry.objects.get(uuid=uuid)
        except models.UserEmailEntry.DoesNotExist:
            messages.add_message(self.request, messages.ERROR, self.message_link_invalid)
            return super().get(request, *args, **kwargs)

        # Check if the email is already linked to an account.
        if models.Account.objects.filter(email=email_entry.email, user__isnull=False).count():
            messages.add_message(self.request, messages.ERROR, self.message_account_already_exists)
            return super().get(request, *args, **kwargs)

        # Check if any user was previously linked to this account.
        if models.AccountUserArchive.objects.filter(account__email=email_entry.email).exists():
            messages.add_message(self.request, messages.ERROR, self.message_account_already_exists)
            return super().get(request, *args, **kwargs)

        # Check if the account is a service account.
        if models.Account.objects.filter(email=email_entry.email, is_service_account=True).count():
            messages.add_message(self.request, messages.ERROR, self.message_service_account)
            return super().get(request, *args, **kwargs)

        # Check that the token matches.
        if not account_verification_token.check_token(email_entry, token):
            messages.add_message(self.request, messages.ERROR, self.message_link_invalid)
            return super().get(request, *args, **kwargs)

        # Create an account for this user from this email.
        try:
            account = models.Account.objects.get(email=email_entry.email)
            account.verified_email_entry = email_entry
            account.user = request.user
        except models.Account.DoesNotExist:
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
            messages.add_message(self.request, messages.ERROR, "AnVIL API Error: " + str(e))
            return super().get(request, *args, **kwargs)

        if not anvil_account_exists:
            messages.add_message(self.request, messages.ERROR, self.message_account_does_not_exist)
            return super().get(request, *args, **kwargs)

        # Mark the entry as verified.
        email_entry.date_verified = timezone.now()
        email_entry.save()

        # Save the account
        account.full_clean()
        account.save()

        # Add a success message.
        messages.add_message(self.request, messages.SUCCESS, self.message_success)

        # Call account adapter after verify hook
        adapter_class = get_account_adapter()
        adapter_instance = adapter_class()

        try:
            adapter_instance.after_account_verification(account)
        except Exception as e:
            # Log but do not stop execution
            logger.exception(f"[AccountLinkVerify] {self.log_message_after_account_link_failed}: {e}")

            # Get the exception type and message
            error_description = f"{type(e).__name__}: {str(e)}"

            # Send a mail about issue to the admins.
            mail_content = render_to_string(
                self.mail_template_after_account_link_failed,
                {
                    "email_entry": email_entry,
                    "account": account,
                    "error_description": error_description,
                    "hook": "after_account_verification",
                },
            )
            mail_admins(
                subject=self.mail_subject_after_account_link_failed,
                message=mail_content,
                fail_silently=False,
            )

        try:
            adapter_instance.send_account_verification_notification_email(account)
        except Exception as e:
            # Log but do not stop execution
            logger.exception(
                f"[AccountLinkVerify] {self.log_message_send_account_verification_notification_email_failed}: {e}"
            )

            # Get the exception type and message
            error_description = f"{type(e).__name__}: {str(e)}"

            # Send a mail about issue to the admins.
            mail_content = render_to_string(
                self.mail_template_send_account_verification_notification_email_failed,
                {
                    "email_entry": email_entry,
                    "account": account,
                    "error_description": error_description,
                    "hook": "send_account_verification_notification_email",
                },
            )
            mail_admins(
                subject=self.mail_subject_send_account_verification_notification_email_failed,
                message=mail_content,
                fail_silently=False,
            )

        return super().get(request, *args, **kwargs)


class AccountList(
    auth.AnVILConsortiumManagerStaffViewRequired,
    viewmixins.AccountAdapterMixin,
    SingleTableMixin,
    FilterView,
):
    """View to display a list of Accounts.

    The table class can be customized using in a custom Account adapter."""

    model = models.Account
    ordering = ("email",)
    template_name = "anvil_consortium_manager/account_list.html"


class AccountActiveList(
    auth.AnVILConsortiumManagerStaffViewRequired,
    viewmixins.AccountAdapterMixin,
    SingleTableMixin,
    FilterView,
):
    model = models.Account
    ordering = ("email",)
    template_name = "anvil_consortium_manager/account_list.html"

    def get_queryset(self):
        return self.model.objects.active()


class AccountInactiveList(
    auth.AnVILConsortiumManagerStaffViewRequired,
    viewmixins.AccountAdapterMixin,
    SingleTableMixin,
    FilterView,
):
    model = models.Account
    ordering = ("email",)
    template_name = "anvil_consortium_manager/account_list.html"

    def get_queryset(self):
        return self.model.objects.inactive()


class AccountDeactivate(
    auth.AnVILConsortiumManagerStaffEditRequired,
    SuccessMessageMixin,
    SingleTableMixin,
    viewmixins.SingleAccountMixin,
    DeleteView,
):
    """Deactivate an account and remove it from all groups on AnVIL."""

    form_class = Form
    template_name = "anvil_consortium_manager/account_confirm_deactivate.html"
    context_table_name = "group_table"
    message_error_removing_from_groups = (
        "Error removing account from groups; manually verify group memberships on AnVIL. (AnVIL API Error: {})"  # noqa
    )
    message_already_inactive = "This Account is already inactive."
    success_message = "Successfully deactivated Account in app."

    def get_table(self):
        return tables.GroupAccountMembershipStaffTable(
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
            messages.add_message(self.request, messages.ERROR, self.message_already_inactive)
            # Redirect to the object detail page.
            return HttpResponseRedirect(self.object.get_absolute_url())
        return response

    def form_valid(self, form):
        """
        Make an API call to AnVIL to remove the account from all groups and then set status to inactive.
        """
        self.object = self.get_object()

        if self.object.status == self.object.INACTIVE_STATUS:
            messages.add_message(self.request, messages.ERROR, self.message_already_inactive)
            # Redirect to the object detail page.
            return HttpResponseRedirect(self.object.get_absolute_url())

        try:
            self.object.deactivate()
        except AnVILAPIError as e:
            msg = self.message_error_removing_from_groups.format(e)
            messages.add_message(self.request, messages.ERROR, msg)
            # Rerender the same page with an error message.
            return HttpResponseRedirect(self.object.get_absolute_url())
        else:
            # Need to add the message because we're not calling the super method.
            messages.success(self.request, self.success_message)
            return HttpResponseRedirect(self.get_success_url())


class AccountReactivate(
    auth.AnVILConsortiumManagerStaffEditRequired,
    SuccessMessageMixin,
    SingleTableMixin,
    viewmixins.SingleAccountMixin,
    SingleObjectMixin,
    FormView,
):
    """Reactivate an account and re-add it to all groups on AnVIL."""

    context_table_name = "group_table"
    form_class = Form
    template_name = "anvil_consortium_manager/account_confirm_reactivate.html"
    message_error_adding_to_groups = (
        "Error adding account to groups; manually verify group memberships on AnVIL. (AnVIL API Error: {})"  # noqa
    )
    message_already_active = "This Account is already active."
    success_message = "Successfully reactivated Account in app."

    def get_success_url(self):
        return self.object.get_absolute_url()
        # exceptions.AnVILRemoveAccountFromGroupError

    def get_table(self):
        return tables.GroupAccountMembershipStaffTable(
            self.object.groupaccountmembership_set.all(),
            exclude=["account", "is_service_account"],
        )

    def get(self, *args, **kwargs):
        self.object = self.get_object()
        # Check if account is inactive.
        if self.object.status == self.object.ACTIVE_STATUS:
            messages.add_message(self.request, messages.ERROR, self.message_already_active)
            # Redirect to the object detail page.
            return HttpResponseRedirect(self.object.get_absolute_url())
        return super().get(self, *args, **kwargs)

    def form_valid(self, form):
        """Set the object status to active and add it to all groups on AnVIL."""
        # Set the status to active.
        self.object = self.get_object()
        if self.object.status == self.object.ACTIVE_STATUS:
            messages.add_message(self.request, messages.ERROR, self.message_already_active)
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
    auth.AnVILConsortiumManagerStaffEditRequired,
    SuccessMessageMixin,
    viewmixins.SingleAccountMixin,
    DeleteView,
):
    model = models.Account
    message_error_removing_from_groups = (
        "Error removing account from groups; manually verify group memberships on AnVIL. (AnVIL API Error: {})"  # noqa
    )
    success_message = "Successfully deleted Account from app."

    def get_success_url(self):
        return reverse("anvil_consortium_manager:accounts:list")

    def form_valid(self, form):
        """
        Make an API call to AnVIL to remove the account from all groups and then delete it from the app.
        """
        self.object = self.get_object()
        try:
            self.object.anvil_remove_from_groups()
        except AnVILAPIError as e:
            msg = self.message_error_removing_from_groups.format(e)
            messages.add_message(self.request, messages.ERROR, msg)
            # Rerender the same page with an error message.
            return HttpResponseRedirect(self.object.get_absolute_url())
        else:
            return super().form_valid(form)


class AccountAutocomplete(auth.AnVILConsortiumManagerStaffViewRequired, autocomplete.Select2QuerySetView):
    """View to provide autocompletion for Accounts. Only active accounts are included."""

    def get_result_label(self, item):
        adapter = get_account_adapter()
        return adapter().get_autocomplete_label(item)

    def get_selected_result_label(self, item):
        adapter = get_account_adapter()
        return adapter().get_autocomplete_label(item)

    def get_queryset(self):
        # Only active accounts.
        qs = models.Account.objects.active().order_by("email")

        # Use the account adapter to process the query.
        adapter = get_account_adapter()
        qs = adapter().get_autocomplete_queryset(qs, self.q)

        return qs


class AccountUnlinkUser(
    auth.AnVILConsortiumManagerStaffEditRequired, viewmixins.SingleAccountMixin, SuccessMessageMixin, FormView
):
    """Unlink an Account from a User."""

    # model = models.Account
    form_class = Form
    template_name = "anvil_consortium_manager/account_confirm_unlink_user.html"
    success_message = "Successfully unlinked user from Account."
    message_no_user = "This Account is not linked to a user."

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self.object.user:
            messages.add_message(self.request, messages.ERROR, self.message_no_user)
            return HttpResponseRedirect(self.object.get_absolute_url())
        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self.object.user:
            messages.add_message(self.request, messages.ERROR, self.message_no_user)
            return HttpResponseRedirect(self.object.get_absolute_url())
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        """Unlink the user from the account."""
        self.object.unlink_user()
        return super().form_valid(form)

    def get_success_url(self):
        return self.object.get_absolute_url()


class ManagedGroupDetail(
    auth.AnVILConsortiumManagerStaffViewRequired,
    viewmixins.ManagedGroupGraphMixin,
    DetailView,
):
    model = models.ManagedGroup
    slug_field = "name"

    def get_graph(self):
        self.graph = self.object.get_graph()

    def plot_graph(self):
        fig = super().plot_graph()
        # Replot this group in a different color.
        # Annotate this group.
        fig.add_annotation(
            x=self.graph_layout[self.object.name][0],
            y=self.graph_layout[self.object.name][1],
            text=self.object.name,
            bgcolor="lightskyblue",
            bordercolor="black",
            showarrow=True,
            arrowhead=1,
        )
        return fig

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["workspace_authorization_domain_table"] = tables.WorkspaceStaffTable(
            self.object.workspace_set.all(),
            exclude=(
                "number_groups",
                "has_authorization_domains",
                "billing_project",
            ),
        )
        context["workspace_table"] = tables.WorkspaceGroupSharingStaffTable(
            self.object.workspacegroupsharing_set.all(), exclude="group"
        )
        context["parent_table"] = tables.GroupGroupMembershipStaffTable(
            self.object.parent_memberships.all(), exclude="child_group"
        )
        if self.object.is_managed_by_app:
            context["account_table"] = tables.GroupAccountMembershipStaffTable(
                self.object.groupaccountmembership_set.all(),
                exclude="group",
            )
            context["group_table"] = tables.GroupGroupMembershipStaffTable(
                self.object.child_memberships.all(), exclude="parent_group"
            )
        edit_permission_codename = models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME
        context["show_edit_links"] = self.request.user.has_perm("anvil_consortium_manager." + edit_permission_codename)
        return context


class ManagedGroupCreate(
    auth.AnVILConsortiumManagerStaffEditRequired,
    viewmixins.ManagedGroupAdapterMixin,
    SuccessMessageMixin,
    FormView,
):
    model = models.ManagedGroup
    form_class = forms.ManagedGroupCreateForm
    template_name = "anvil_consortium_manager/managedgroup_create.html"
    success_message = "Successfully created Managed Group on AnVIL."
    ADAPTER_ERROR_MESSAGE = "[ManagedGroupCreate] after_anvil_create method failed"

    def get_success_url(self):
        return self.object.get_absolute_url()

    def form_valid(self, form):
        """If the form is valid, save the associated model and create it on AnVIL."""
        # Set the email for the new group based on the default.
        form.instance.email = form.instance.name.lower() + "@firecloud.org"
        # Create but don't save the new group.
        # Make an API call to AnVIL to create the group.
        try:
            with transaction.atomic():
                self.object = form.save()
                self.object.anvil_create()
                try:
                    self.adapter.after_anvil_create(self.object)
                except Exception:
                    # Log the error.
                    logger.exception(self.ADAPTER_ERROR_MESSAGE)
                    # Add a message
                    messages.add_message(
                        self.request,
                        messages.WARNING,
                        self.ADAPTER_ERROR_MESSAGE,
                    )
        except AnVILAPIError as e:
            # If the API call failed, rerender the page with the responses and show a message.
            messages.add_message(self.request, messages.ERROR, "AnVIL API Error: " + str(e))
            return self.render_to_response(self.get_context_data(form=form))
        # The object is saved by the super's form_valid method.
        return super().form_valid(form)


class ManagedGroupUpdate(
    auth.AnVILConsortiumManagerStaffEditRequired,
    SuccessMessageMixin,
    UpdateView,
):
    """View to update information about an Account."""

    model = models.ManagedGroup
    form_class = forms.ManagedGroupUpdateForm
    slug_field = "name"
    template_name = "anvil_consortium_manager/managedgroup_update.html"
    success_message = "Successfully updated ManagedGroup."


class ManagedGroupList(
    auth.AnVILConsortiumManagerStaffViewRequired, viewmixins.ManagedGroupAdapterMixin, SingleTableMixin, FilterView
):
    model = models.ManagedGroup
    ordering = ("name",)
    template_name = "anvil_consortium_manager/managedgroup_list.html"

    filterset_class = filters.ManagedGroupListFilter

    def get_table_class(self):
        """Use the adapter to get the table class."""
        return self.adapter.get_list_table_class()


class ManagedGroupVisualization(
    auth.AnVILConsortiumManagerStaffViewRequired,
    viewmixins.ManagedGroupGraphMixin,
    TemplateView,
):
    """Display a visualization of all group relationships."""

    template_name = "anvil_consortium_manager/managedgroup_visualization.html"

    def get_graph(self):
        G = models.ManagedGroup.get_full_graph()
        self.graph = G


class ManagedGroupDelete(auth.AnVILConsortiumManagerStaffEditRequired, SuccessMessageMixin, DeleteView):
    model = models.ManagedGroup
    slug_field = "name"
    message_not_managed_by_app = "Cannot delete group because it is not managed by this app."
    message_is_auth_domain = "Cannot delete group since it is an authorization domain for a workspace."
    message_is_member_of_another_group = "Cannot delete group since it is a member of another group."
    message_has_access_to_workspace = "Cannot delete group because it has access to at least one workspace."
    # In some cases the AnVIL API returns a successful code but the group is not deleted.
    message_could_not_delete_group_from_app = "Cannot delete group from app due to foreign key restrictions."
    message_could_not_delete_group_from_anvil = "Cannot not delete group from AnVIL - unknown reason."
    success_message = "Successfully deleted Group on AnVIL."

    def get_success_url(self):
        return reverse("anvil_consortium_manager:managed_groups:list")

    def get(self, *args, **kwargs):
        response = super().get(self, *args, **kwargs)
        # Check if managed by the app.
        if not self.object.is_managed_by_app:
            messages.add_message(self.request, messages.ERROR, self.message_not_managed_by_app)
            # Redirect to the object detail page.
            return HttpResponseRedirect(self.object.get_absolute_url())
        # Check authorization domains
        if self.object.workspaceauthorizationdomain_set.count() > 0:
            # Add a message and redirect.
            messages.add_message(self.request, messages.ERROR, self.message_is_auth_domain)
            # Redirect to the object detail page.
            return HttpResponseRedirect(self.object.get_absolute_url())
        # Check that it is not a member of other groups.
        # This is enforced by AnVIL.
        if self.object.parent_memberships.count() > 0:
            messages.add_message(self.request, messages.ERROR, self.message_is_member_of_another_group)
            return HttpResponseRedirect(self.object.get_absolute_url())
        if self.object.workspacegroupsharing_set.count() > 0:
            messages.add_message(self.request, messages.ERROR, self.message_has_access_to_workspace)
            return HttpResponseRedirect(self.object.get_absolute_url())
        # Otherwise, return the response.
        return response

    def form_valid(self, form):
        """
        Make an API call to AnVIL and then call the delete method on the object.
        """
        self.object = self.get_object()
        # Check that the group is managed by the app.
        if not self.object.is_managed_by_app:
            messages.add_message(self.request, messages.ERROR, self.message_not_managed_by_app)
            # Redirect to the object detail page.
            return HttpResponseRedirect(self.object.get_absolute_url())
        # Check if it's an auth domain for any workspaces.
        if self.object.workspaceauthorizationdomain_set.count() > 0:
            # Add a message and redirect.
            messages.add_message(self.request, messages.ERROR, self.message_is_auth_domain)
            # Redirect to the object detail page.
            return HttpResponseRedirect(self.object.get_absolute_url())
        # Check that it is not a member of other groups.
        # This is enforced by AnVIL.
        if self.object.parent_memberships.count() > 0:
            messages.add_message(self.request, messages.ERROR, self.message_is_member_of_another_group)
            return HttpResponseRedirect(self.object.get_absolute_url())
        if self.object.workspacegroupsharing_set.count() > 0:
            messages.add_message(self.request, messages.ERROR, self.message_has_access_to_workspace)
            return HttpResponseRedirect(self.object.get_absolute_url())

        try:
            with transaction.atomic():
                self.object.delete()
                self.object.anvil_delete()
                success_message = self.get_success_message(form.cleaned_data)
                if success_message:
                    messages.success(self.request, success_message)
                response = HttpResponseRedirect(self.get_success_url())
        except (ProtectedError, RestrictedError):
            messages.add_message(
                self.request,
                messages.ERROR,
                self.message_could_not_delete_group_from_app,
            )
            response = HttpResponseRedirect(self.object.get_absolute_url())
        except AnVILAPIError as e:
            # The AnVIL call has failed for some reason.
            messages.add_message(self.request, messages.ERROR, "AnVIL API Error: " + str(e))
            # Rerender the same page with an error message.
            response = self.render_to_response(self.get_context_data())
        return response


class ManagedGroupAutocomplete(auth.AnVILConsortiumManagerStaffViewRequired, autocomplete.Select2QuerySetView):
    """View to provide autocompletion for ManagedGroups."""

    def get_queryset(self):
        # Filter out unathorized users, or does the auth mixin do that?
        qs = models.ManagedGroup.objects.order_by("name")

        only_managed_by_app = self.forwarded.get("only_managed_by_app", None)

        if self.q:
            qs = qs.filter(name__icontains=self.q)
        if only_managed_by_app:
            qs = qs.filter(is_managed_by_app=True)

        return qs


class WorkspaceLandingPage(
    auth.AnVILConsortiumManagerViewRequired,
    viewmixins.RegisteredWorkspaceAdaptersMixin,
    TemplateView,
):
    template_name = "anvil_consortium_manager/workspace_landing_page.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        edit_permission_codename = models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME
        context["show_edit_links"] = self.request.user.has_perm("anvil_consortium_manager." + edit_permission_codename)
        return context


class WorkspaceDetail(
    auth.AnVILConsortiumManagerViewRequired,
    viewmixins.RegisteredWorkspaceAdaptersMixin,
    viewmixins.WorkspaceAdapterMixin,
    DetailView,
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
        queryset = queryset.filter(billing_project__name=billing_project_slug, name=workspace_slug)
        try:
            # Get the single item from the filtered queryset
            obj = queryset.get()
        except queryset.model.DoesNotExist:
            raise Http404(
                _("No %(verbose_name)s found matching the query") % {"verbose_name": queryset.model._meta.verbose_name}
            )
        return obj

    def get_workspace_type(self):
        """Return the workspace type of this workspace."""
        object = self.get_object()
        return object.workspace_type

    def get_workspace_data_object(self):
        model = self.adapter.get_workspace_data_model()
        return model.objects.get(workspace=self.object)

    def get_context_data(self, **kwargs):
        # Get info about permissions.
        staff_view_permission_codename = models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME
        has_staff_view_perms = self.request.user.has_perm("anvil_consortium_manager." + staff_view_permission_codename)
        edit_permission_codename = models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME
        has_edit_perms = self.request.user.has_perm("anvil_consortium_manager." + edit_permission_codename)
        # Get the default context data.
        context = super().get_context_data(**kwargs)
        # Add custom variables for this view.
        context["workspace_data_object"] = self.get_workspace_data_object()
        context["show_edit_links"] = has_edit_perms
        context["has_authorization_domain_not_managed_by_app"] = self.object.authorization_domains.filter(
            is_managed_by_app=False
        ).exists()

        try:
            account = self.request.user.account
            try:
                has_access = self.object.is_accessible_by_account(account)
            except exceptions.WorkspaceAccessUnknownError:
                has_access = None
        except models.Account.DoesNotExist:
            has_access = False
        context["has_access"] = has_access
        # Tables.
        table_class = tables.ManagedGroupStaffTable if has_staff_view_perms else tables.ManagedGroupUserTable
        context["authorization_domain_table"] = table_class(
            self.object.authorization_domains.all(),
            exclude=["workspace", "number_groups", "number_accounts"],
        )
        if has_staff_view_perms:
            context["group_sharing_table"] = tables.WorkspaceGroupSharingStaffTable(
                self.object.workspacegroupsharing_set.all(), exclude="workspace"
            )

        context.update(self.adapter.get_extra_detail_context_data(self.object, self.request))
        return context

    def get_template_names(self):
        """Return the workspace detail template name specified in the adapter."""
        adapter = workspace_adapter_registry.get_adapter(self.object.workspace_type)
        template_name = adapter.get_workspace_detail_template_name()
        return [template_name]


class WorkspaceCreate(
    auth.AnVILConsortiumManagerStaffEditRequired,
    SuccessMessageMixin,
    viewmixins.WorkspaceAdapterMixin,
    FormView,
):
    success_message = "Successfully created Workspace on AnVIL."
    template_name = "anvil_consortium_manager/workspace_create.html"
    ADAPTER_ERROR_MESSAGE_BEFORE_ANVIL_CREATE = "[WorkspaceCreate] before_anvil_create method failed"
    ADAPTER_ERROR_MESSAGE_AFTER_ANVIL_CREATE = "[WorkspaceCreate] after_anvil_create method failed"

    def get_form_class(self):
        return self.adapter.get_workspace_form_class()

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
            fk_name="workspace",
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
                for auth_domain in form.cleaned_data.get("authorization_domains", []):
                    models.WorkspaceAuthorizationDomain.objects.create(workspace=self.workspace, group=auth_domain)
                workspace_data_formset.forms[0].save()
                # Then create the workspace on AnVIL, running custom adapter methods as appropriate.
                try:
                    self.adapter.before_anvil_create(self.workspace)
                except Exception:
                    # Log the error.
                    logger.exception(self.ADAPTER_ERROR_MESSAGE_BEFORE_ANVIL_CREATE)
                    # Add a message
                    messages.add_message(
                        self.request,
                        messages.WARNING,
                        self.ADAPTER_ERROR_MESSAGE_BEFORE_ANVIL_CREATE,
                    )
                self.workspace.anvil_create()
                try:
                    self.adapter.after_anvil_create(self.workspace)
                except Exception:
                    # Log the error.
                    logger.exception(self.ADAPTER_ERROR_MESSAGE_AFTER_ANVIL_CREATE)
                    # Add a message
                    messages.add_message(
                        self.request,
                        messages.WARNING,
                        self.ADAPTER_ERROR_MESSAGE_AFTER_ANVIL_CREATE,
                    )
        except AnVILAPIError as e:
            # If the API call failed, rerender the page with the responses and show a message.
            messages.add_message(self.request, messages.ERROR, "AnVIL API Error: " + str(e))
            return self.render_to_response(
                self.get_context_data(form=form, workspace_data_formset=workspace_data_formset)
            )
        return super().form_valid(form)

    def forms_invalid(self, form, workspace_data_formset):
        """If the form(s) are invalid, render the invalid form."""
        return self.render_to_response(self.get_context_data(form=form, workspace_data_formset=workspace_data_formset))

    def get_success_url(self):
        return self.workspace.get_absolute_url()


class WorkspaceImport(
    auth.AnVILConsortiumManagerStaffEditRequired,
    SuccessMessageMixin,
    viewmixins.WorkspaceAdapterMixin,
    FormView,
):
    template_name = "anvil_consortium_manager/workspace_import.html"
    message_anvil_no_access_to_workspace = "Requested workspace doesn't exist or you don't have permission to see it."
    message_anvil_not_owner = "Not an owner of this workspace."
    message_workspace_exists = "This workspace already exists in the web app."
    message_error_fetching_workspaces = "Unable to fetch workspaces from AnVIL."
    message_no_available_workspaces = "No workspaces available for import from AnVIL."
    success_message = "Successfully imported Workspace from AnVIL."
    # Set in a method.
    workspace_choices = None
    ADAPTER_ERROR_MESSAGE = "[WorkspaceImport] after_anvil_import method failed"

    def get_form(self):
        """Return the form instance with the list of available workspaces to import."""
        try:
            all_workspaces = (
                AnVILAPIClient().list_workspaces(fields="workspace.namespace,workspace.name,accessLevel").json()
            )
            # Filter workspaces to only owners and not imported.
            workspaces = [
                w["workspace"]["namespace"] + "/" + w["workspace"]["name"]
                for w in all_workspaces
                if (w["accessLevel"] == "OWNER" or w["accessLevel"] == "NO ACCESS")
                and not models.Workspace.objects.filter(
                    billing_project__name=w["workspace"]["namespace"],
                    name=w["workspace"]["name"],
                ).exists()
            ]
            # Sort workspaces alphabetically.
            workspaces = sorted(workspaces)
            workspace_choices = [(x, x) for x in workspaces]

            if not len(workspace_choices):
                messages.add_message(self.request, messages.INFO, self.message_no_available_workspaces)

        except AnVILAPIError:
            workspace_choices = []
            messages.add_message(self.request, messages.ERROR, self.message_error_fetching_workspaces)

        return forms.WorkspaceImportForm(workspace_choices=workspace_choices, **self.get_form_kwargs())

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
            fk_name="workspace",
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
            try:
                self.adapter.after_anvil_import(self.workspace)
            except Exception:
                # Log the error.
                logger.exception(self.ADAPTER_ERROR_MESSAGE)
                # Add a message
                messages.add_message(
                    self.request,
                    messages.WARNING,
                    self.ADAPTER_ERROR_MESSAGE,
                )
        except anvil_api.AnVILAPIError as e:
            messages.add_message(self.request, messages.ERROR, "AnVIL API Error: " + str(e))
            return self.render_to_response(self.get_context_data(form=form))
        return super().form_valid(form)

    def forms_invalid(self, form, workspace_data_formset):
        """If the form is invalid, render the invalid form."""
        return self.render_to_response(self.get_context_data(form=form, workspace_data_formset=workspace_data_formset))


class WorkspaceClone(
    auth.AnVILConsortiumManagerStaffEditRequired,
    SuccessMessageMixin,
    viewmixins.WorkspaceCheckAccessMixin,
    viewmixins.WorkspaceAdapterMixin,
    SingleObjectMixin,
    FormView,
):
    model = models.Workspace
    success_message = "Successfully created Workspace on AnVIL."
    template_name = "anvil_consortium_manager/workspace_clone.html"
    ADAPTER_ERROR_MESSAGE_BEFORE_ANVIL_CREATE = "[WorkspaceClone] before_anvil_create method failed"
    ADAPTER_ERROR_MESSAGE_AFTER_ANVIL_CREATE = "[WorkspaceClone] after_anvil_create method failed"
    workspace_access = models.Workspace.AppAccessChoices.LIMITED
    workspace_access_error_message = "Cannot clone a workspace to which the app doesn't have access"
    workspace_unlocked = False

    def get_object(self, queryset=None):
        """Return the workspace to clone."""
        if queryset is None:
            queryset = self.get_queryset()
        # Filter the queryset based on kwargs.
        billing_project_slug = self.kwargs.get("billing_project_slug")
        workspace_slug = self.kwargs.get("workspace_slug")
        queryset = queryset.filter(billing_project__name=billing_project_slug, name=workspace_slug)
        try:
            # Get the single item from the filtered queryset
            obj = queryset.get()
        except queryset.model.DoesNotExist:
            raise Http404(
                _("No %(verbose_name)s found matching the query") % {"verbose_name": queryset.model._meta.verbose_name}
            )
        return obj

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        """
        Handle POST requests: instantiate the forms instances with the passed
        POST variables and then check if they are valid.
        """
        self.adapter = self.get_adapter()
        self.object = self.get_object()
        if not self.check_workspace(self.object):
            return HttpResponseRedirect(self.object.get_absolute_url())
        self.new_workspace = None
        form = self.get_form()
        # First, check if the workspace form is valid.
        # If it is, we'll save the model and then check the workspace data formset in the post method.
        if form.is_valid():
            return self.form_valid(form)
        else:
            workspace_data_formset = self.get_workspace_data_formset()
            return self.forms_invalid(form, workspace_data_formset)

    def get_initial(self):
        """Add the authorization domains of the workspace to be cloned to the form."""
        initial = super().get_initial()
        initial["authorization_domains"] = self.object.authorization_domains.all()
        return initial

    def get_form_class(self):
        # Create a custom class from the custom workspace form, and add cleaning
        # methods with the WorkspaceCloneFormMixin
        workspace_form_class = self.adapter.get_workspace_form_class()

        class WorkspaceCloneForm(forms.WorkspaceCloneFormMixin, workspace_form_class):
            # class WorkspaceCloneForm(forms.WorkspaceCloneFormMixin, forms.WorkspaceForm):

            class Meta(workspace_form_class.Meta):
                pass

        return WorkspaceCloneForm

    def get_form(self, form_class=None):
        """Return an instance of the form to be used in this view."""
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
            fk_name="workspace",
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
                for auth_domain in form.cleaned_data.get("authorization_domains", []):
                    models.WorkspaceAuthorizationDomain.objects.create(workspace=self.new_workspace, group=auth_domain)
                workspace_data_formset.forms[0].save()
                # Then create the workspace on AnVIL.
                try:
                    self.adapter.before_anvil_create(self.new_workspace)
                except Exception:
                    # Log the error.
                    logger.exception(self.ADAPTER_ERROR_MESSAGE_BEFORE_ANVIL_CREATE)
                    # Add a message
                    messages.add_message(
                        self.request,
                        messages.WARNING,
                        self.ADAPTER_ERROR_MESSAGE_BEFORE_ANVIL_CREATE,
                    )
                authorization_domains = self.new_workspace.authorization_domains.all()
                self.object.anvil_clone(
                    self.new_workspace.billing_project,
                    self.new_workspace.name,
                    authorization_domains=authorization_domains,
                )
                try:
                    self.adapter.after_anvil_create(self.new_workspace)
                except Exception:
                    # Log the error.
                    logger.exception(self.ADAPTER_ERROR_MESSAGE_AFTER_ANVIL_CREATE)
                    # Add a message
                    messages.add_message(
                        self.request,
                        messages.WARNING,
                        self.ADAPTER_ERROR_MESSAGE_AFTER_ANVIL_CREATE,
                    )
        except AnVILAPIError as e:
            # If the API call failed, rerender the page with the responses and show a message.
            messages.add_message(self.request, messages.ERROR, "AnVIL API Error: " + str(e))
            return self.render_to_response(
                self.get_context_data(form=form, workspace_data_formset=workspace_data_formset)
            )
        return super().form_valid(form)

    def forms_invalid(self, form, workspace_data_formset):
        """If the form(s) are invalid, render the invalid form."""
        return self.render_to_response(self.get_context_data(form=form, workspace_data_formset=workspace_data_formset))

    def get_success_url(self):
        return self.new_workspace.get_absolute_url()


class WorkspaceUpdate(
    auth.AnVILConsortiumManagerStaffEditRequired,
    SuccessMessageMixin,
    viewmixins.WorkspaceAdapterMixin,
    UpdateView,
):
    """View to update information about an Account."""

    model = models.Workspace
    slug_field = "name"
    template_name = "anvil_consortium_manager/workspace_update.html"
    success_message = "Successfully updated Workspace."

    def get_form_class(self):
        form_class = self.adapter.get_workspace_form_class()

        class WorkspaceUpdateForm(form_class):
            class Meta(form_class.Meta):
                exclude = (
                    "billing_project",
                    "name",
                    "authorization_domains",
                )

        return WorkspaceUpdateForm

    def get_object(self, queryset=None):
        """Return the object the view is displaying."""

        # Use a custom queryset if provided; this is required for subclasses
        # like DateDetailView
        if queryset is None:
            queryset = self.get_queryset()
        # Filter the queryset based on kwargs.
        billing_project_slug = self.kwargs.get("billing_project_slug", None)
        workspace_slug = self.kwargs.get("workspace_slug", None)
        queryset = queryset.filter(billing_project__name=billing_project_slug, name=workspace_slug)
        try:
            # Get the single item from the filtered queryset
            obj = queryset.get()
        except queryset.model.DoesNotExist:
            raise Http404(
                _("No %(verbose_name)s found matching the query") % {"verbose_name": queryset.model._meta.verbose_name}
            )
        return obj

    def get_workspace_data_object(self):
        model = self.adapter.get_workspace_data_model()
        return model.objects.get(workspace=self.object)

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
            fk_name="workspace",
        )
        if self.request.method in ("POST"):
            formset = formset_factory(
                self.request.POST,
                instance=self.object,
                prefix=formset_prefix,
                initial=[{"workspace": self.object}],
            )
        else:
            formset = formset_factory(prefix=formset_prefix, initial=[{}], instance=self.object)
        return formset

    def get_context_data(self, **kwargs):
        """Insert the workspace data formset into the context dict."""
        if "workspace_data_formset" not in kwargs:
            kwargs["workspace_data_formset"] = self.get_workspace_data_formset()
        kwargs["workspace_data_object"] = self.get_workspace_data_object()
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
        return self.render_to_response(self.get_context_data(form=form, workspace_data_formset=workspace_data_formset))

    def get_success_url(self):
        return self.object.get_absolute_url()


class WorkspaceUpdateRequesterPays(
    auth.AnVILConsortiumManagerStaffEditRequired,
    viewmixins.WorkspaceCheckAccessMixin,
    SuccessMessageMixin,
    UpdateView,
):
    """Deactivate an account and remove it from all groups on AnVIL."""

    model = models.Workspace
    form_class = forms.WorkspaceRequesterPaysForm
    template_name = "anvil_consortium_manager/workspace_update_requester_pays.html"
    message_api_error = "Error updating requester pays status on AnVIL. (AnVIL API Error: {})"
    workspace_access_error_message = (
        "Cannot update requester pays status for a workspace where the app is not an owner."
    )
    workspace_access = models.Workspace.AppAccessChoices.OWNER
    workspace_unlocked = False
    success_message = "Successfully updated requester pays status."

    def get_object(self, queryset=None):
        """Return the object the view is displaying."""

        # Use a custom queryset if provided; this is required for subclasses
        # like DateDetailView
        if queryset is None:
            queryset = self.get_queryset()
        # Filter the queryset based on kwargs.
        billing_project_slug = self.kwargs.get("billing_project_slug", None)
        workspace_slug = self.kwargs.get("workspace_slug", None)
        queryset = queryset.filter(billing_project__name=billing_project_slug, name=workspace_slug)
        try:
            # Get the single item from the filtered queryset
            obj = queryset.get()
        except queryset.model.DoesNotExist:
            raise Http404(
                _("No %(verbose_name)s found matching the query") % {"verbose_name": queryset.model._meta.verbose_name}
            )
        return obj

    def form_valid(self, form):
        if form.has_changed():
            # Only make an API call if the form has changed data.
            client = AnVILAPIClient()
            try:
                # Make an API call to AnVIL to update the requester pays status.
                client.update_workspace_requester_pays(
                    self.object.billing_project.name, self.object.name, form.cleaned_data["is_requester_pays"]
                )
            except AnVILAPIError as e:
                msg = self.message_api_error.format(e)
                messages.add_message(self.request, messages.ERROR, msg)
                return self.render_to_response(self.get_context_data(form=form))
        return super().form_valid(form)


class WorkspaceList(auth.AnVILConsortiumManagerViewRequired, SingleTableMixin, FilterView):
    """Display a list of all workspaces using the default table."""

    model = models.Workspace
    ordering = (
        "billing_project__name",
        "name",
    )
    template_name = "anvil_consortium_manager/workspace_list.html"
    filterset_class = filters.WorkspaceListFilter

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["workspace_type_display_name"] = "All workspace"
        return context

    def get_table_class(self):
        staff_view_permission_codename = models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME
        if self.request.user.has_perm("anvil_consortium_manager." + staff_view_permission_codename):
            return tables.WorkspaceStaffTable
        else:
            return tables.WorkspaceUserTable


class WorkspaceListByType(
    auth.AnVILConsortiumManagerViewRequired,
    viewmixins.WorkspaceAdapterMixin,
    SingleTableMixin,
    FilterView,
):
    """Display a list of workspaces of the given ``workspace_type``."""

    model = models.Workspace
    ordering = (
        "billing_project__name",
        "name",
    )
    filterset_class = filters.WorkspaceListFilter

    def get_queryset(self):
        return self.model.objects.filter(workspace_type=self.adapter.get_type())

    def get_table_class(self):
        """Use the adapter to get the table class."""
        staff_view_permission_codename = models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME
        if self.request.user.has_perm("anvil_consortium_manager." + staff_view_permission_codename):
            return self.adapter.get_list_table_class_staff_view()
        else:
            return self.adapter.get_list_table_class_view()

    def get_template_names(self):
        """Return the workspace list template name specified in the adapter."""
        return [self.adapter.workspace_list_template_name]


class WorkspaceDelete(
    auth.AnVILConsortiumManagerStaffEditRequired,
    viewmixins.WorkspaceCheckAccessMixin,
    SuccessMessageMixin,
    DeleteView,
):
    model = models.Workspace
    success_message = "Successfully deleted Workspace on AnVIL."
    message_could_not_delete_workspace_from_app = "Cannot delete workspace from app due to foreign key restrictions."
    workspace_access = models.Workspace.AppAccessChoices.OWNER
    workspace_unlocked = True
    workspace_access_error_message = "Cannot delete a workspace where the app is not an owner."
    lock_error_message = "Cannot delete workspace because it is locked."

    def get_object(self, queryset=None):
        """Return the object the view is displaying."""
        # Use a custom queryset if provided; this is required for subclasses
        # like DateDetailView
        if queryset is None:
            queryset = self.get_queryset()
        # Filter the queryset based on kwargs.
        billing_project_slug = self.kwargs.get("billing_project_slug", None)
        workspace_slug = self.kwargs.get("workspace_slug", None)
        queryset = queryset.filter(billing_project__name=billing_project_slug, name=workspace_slug)
        try:
            # Get the single item from the filtered queryset
            obj = queryset.get()
        except queryset.model.DoesNotExist:
            raise Http404(
                _("No %(verbose_name)s found matching the query") % {"verbose_name": queryset.model._meta.verbose_name}
            )
        return obj

    def get_success_url(self):
        return reverse(
            "anvil_consortium_manager:workspaces:list",
            args=[self.object.workspace_type],
        )

    def form_valid(self, form):
        """
        Make an API call to AnVIL and then call the delete method on the object.
        """
        self.object = self.get_object()
        try:
            with transaction.atomic():
                self.object.delete()
                self.object.anvil_delete()
                success_message = self.get_success_message(form.cleaned_data)
                if success_message:
                    messages.success(self.request, success_message)
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
            messages.add_message(self.request, messages.ERROR, "AnVIL API Error: " + str(e))
            # Rerender the same page with an error message.
            response = self.render_to_response(self.get_context_data())
        return response


class WorkspaceAutocomplete(auth.AnVILConsortiumManagerStaffViewRequired, autocomplete.Select2QuerySetView):
    """View to provide autocompletion for Workspaces.

    Right now this only matches Workspace name, not billing project."""

    def get_queryset(self):
        qs = models.Workspace.objects.filter().order_by("billing_project__name", "name")
        app_access_values = self.forwarded.get("app_access_values", [])

        if self.q:
            qs = qs.filter(name__icontains=self.q)
        if app_access_values:
            qs = qs.filter(app_access__in=app_access_values)

        return qs


class WorkspaceAutocompleteByType(
    auth.AnVILConsortiumManagerStaffViewRequired,
    viewmixins.WorkspaceAdapterMixin,
    autocomplete.Select2QuerySetView,
):
    """View to provide autocompletion for Workspace data models by type."""

    def get_queryset(self):
        # Eventually, add a new method to the workspace adapter that can be overridden for custom autocomplete.
        # Filter out unathorized users, or does the auth mixin do that?
        qs = (
            self.adapter.get_workspace_data_model()
            .objects.filter()
            .order_by("workspace__billing_project", "workspace__name")
        )

        # Use the workspace adapter to process the query.
        qs = self.adapter.get_autocomplete_queryset(qs, self.q, forwarded=self.forwarded)

        return qs


class GroupGroupMembershipDetail(auth.AnVILConsortiumManagerStaffViewRequired, DetailView):
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
        queryset = queryset.filter(parent_group__name=parent_group_slug, child_group__name=child_group_slug)
        try:
            # Get the single item from the filtered queryset
            obj = queryset.get()
        except queryset.model.DoesNotExist:
            raise Http404(
                _("No %(verbose_name)s found matching the query") % {"verbose_name": queryset.model._meta.verbose_name}
            )
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        edit_permission_codename = models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME
        context["show_edit_links"] = self.request.user.has_perm("anvil_consortium_manager." + edit_permission_codename)
        return context


class GroupGroupMembershipCreate(auth.AnVILConsortiumManagerStaffEditRequired, SuccessMessageMixin, CreateView):
    model = models.GroupGroupMembership
    form_class = forms.GroupGroupMembershipForm
    success_message = "Successfully created group membership."

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
            messages.add_message(self.request, messages.ERROR, "AnVIL API Error: " + str(e))
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

    template_name = "anvil_consortium_manager/groupgroupmembership_form_byparentchild.html"

    message_already_exists = "Child group is already a member of the parent Managed Group."
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
            obj = models.GroupGroupMembership.objects.get(parent_group=self.parent_group, child_group=self.child_group)
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
            obj = models.GroupGroupMembership.objects.get(parent_group=self.parent_group, child_group=self.child_group)
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


class GroupGroupMembershipList(auth.AnVILConsortiumManagerStaffViewRequired, SingleTableView):
    model = models.GroupGroupMembership
    table_class = tables.GroupGroupMembershipStaffTable


class GroupGroupMembershipDelete(auth.AnVILConsortiumManagerStaffEditRequired, SuccessMessageMixin, DeleteView):
    model = models.GroupGroupMembership
    success_message = "Successfully deleted group membership on AnVIL."

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
        queryset = queryset.filter(parent_group__name=parent_group_slug, child_group__name=child_group_slug)
        try:
            # Get the single item from the filtered queryset
            obj = queryset.get()
        except queryset.model.DoesNotExist:
            raise Http404(
                _("No %(verbose_name)s found matching the query") % {"verbose_name": queryset.model._meta.verbose_name}
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

    def form_valid(self, form):
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
            messages.add_message(self.request, messages.ERROR, "AnVIL API Error: " + str(e))
            # Rerender the same page with an error message.
            return self.render_to_response(self.get_context_data())
        return super().form_valid(form)


class GroupAccountMembershipDetail(auth.AnVILConsortiumManagerStaffViewRequired, DetailView):
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
                _("No %(verbose_name)s found matching the query") % {"verbose_name": queryset.model._meta.verbose_name}
            )
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        edit_permission_codename = models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME
        context["show_edit_links"] = self.request.user.has_perm("anvil_consortium_manager." + edit_permission_codename)
        return context


class GroupAccountMembershipCreate(auth.AnVILConsortiumManagerStaffEditRequired, SuccessMessageMixin, CreateView):
    model = models.GroupAccountMembership
    form_class = forms.GroupAccountMembershipForm
    success_message = "Successfully added account membership."

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
            messages.add_message(self.request, messages.ERROR, "AnVIL API Error: " + str(e))
            return self.render_to_response(self.get_context_data(form=form))
        # The object is saved by the super's form_valid method.
        return super().form_valid(form)


class GroupAccountMembershipCreateByGroup(GroupAccountMembershipCreate):
    """View to create a new GroupAccountMembership for the group specified in the url."""

    template_name = "anvil_consortium_manager/groupaccountmembership_form_bygroup.html"

    message_not_managed_by_app = "Cannot add Account because this group is not managed by the app."
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

    template_name = "anvil_consortium_manager/groupaccountmembership_form_byaccount.html"

    message_not_managed_by_app = "Cannot add Account because this group is not managed by the app."
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

    template_name = "anvil_consortium_manager/groupaccountmembership_form_bygroupaccount.html"

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
            obj = models.GroupAccountMembership.objects.get(account=self.account, group=self.group)
            messages.error(self.request, self.message_already_exists)
            return HttpResponseRedirect(obj.get_absolute_url())
        except models.GroupAccountMembership.DoesNotExist:
            return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.account = self.get_account()
        self.group = self.get_group()
        try:
            obj = models.GroupAccountMembership.objects.get(account=self.account, group=self.group)
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


class GroupAccountMembershipList(auth.AnVILConsortiumManagerStaffViewRequired, SingleTableView):
    """Show a list of all group memberships regardless of account active/inactive status."""

    model = models.GroupAccountMembership
    table_class = tables.GroupAccountMembershipStaffTable


class GroupAccountMembershipActiveList(auth.AnVILConsortiumManagerStaffViewRequired, SingleTableView):
    """Show a list of all group memberships for active accounts."""

    model = models.GroupAccountMembership
    table_class = tables.GroupAccountMembershipStaffTable
    ordering = (
        "group__name",
        "account__email",
    )

    def get_queryset(self):
        return self.model.objects.filter(account__status=models.Account.ACTIVE_STATUS)


class GroupAccountMembershipInactiveList(auth.AnVILConsortiumManagerStaffViewRequired, SingleTableView):
    """Show a list of all group memberships for inactive accounts."""

    model = models.GroupAccountMembership
    table_class = tables.GroupAccountMembershipStaffTable
    ordering = (
        "group__name",
        "account__email",
    )

    def get_queryset(self):
        return self.model.objects.filter(account__status=models.Account.INACTIVE_STATUS)


class GroupAccountMembershipDelete(auth.AnVILConsortiumManagerStaffEditRequired, SuccessMessageMixin, DeleteView):
    model = models.GroupAccountMembership
    success_message = "Successfully deleted account membership on AnVIL."

    message_group_not_managed_by_app = "Cannot remove members from group because it is not managed by this app."

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
                _("No %(verbose_name)s found matching the query") % {"verbose_name": queryset.model._meta.verbose_name}
            )
        return obj

    def get_success_url(self):
        return self.group.get_absolute_url()

    def get(self, request, *args, **kwargs):
        response = super().get(self, *args, **kwargs)
        # Check if managed by the app.
        if not self.object.group.is_managed_by_app:
            messages.add_message(self.request, messages.ERROR, self.message_group_not_managed_by_app)
            # Redirect to the object detail page.
            return HttpResponseRedirect(self.object.get_absolute_url())
        # Otherwise, return the response.
        return response

    def form_valid(self, form):
        """
        Make an API call to AnVIL and then call the delete method on the object.
        """
        self.object = self.get_object()
        self.group = self.object.group
        # Check if managed by the app.
        if not self.object.group.is_managed_by_app:
            messages.add_message(self.request, messages.ERROR, self.message_group_not_managed_by_app)
            # Redirect to the object detail page.
            return HttpResponseRedirect(self.object.get_absolute_url())
        # Try to delete from AnVIL.
        try:
            self.object.anvil_delete()
        except AnVILAPIError as e:
            # The AnVIL call has failed for some reason.
            messages.add_message(self.request, messages.ERROR, "AnVIL API Error: " + str(e))
            # Rerender the same page with an error message.
            return self.render_to_response(self.get_context_data())
        return super().form_valid(form)


class WorkspaceGroupSharingDetail(auth.AnVILConsortiumManagerStaffViewRequired, DetailView):
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
                _("No %(verbose_name)s found matching the query") % {"verbose_name": queryset.model._meta.verbose_name}
            )
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        edit_permission_codename = models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME
        context["show_edit_links"] = self.request.user.has_perm("anvil_consortium_manager." + edit_permission_codename)
        return context


class WorkspaceGroupSharingCreate(auth.AnVILConsortiumManagerStaffEditRequired, SuccessMessageMixin, CreateView):
    """View to create a new WorkspaceGroupSharing object and share the Workspace with a Group on AnVIL."""

    model = models.WorkspaceGroupSharing
    form_class = forms.WorkspaceGroupSharingForm
    success_message = "Successfully shared Workspace with Group."
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
            messages.add_message(self.request, messages.ERROR, self.message_group_not_found)
            return self.render_to_response(self.get_context_data(form=form))
        except AnVILAPIError as e:
            # If the API call failed, rerender the page with the responses and show a message.
            messages.add_message(self.request, messages.ERROR, "AnVIL API Error: " + str(e))
            return self.render_to_response(self.get_context_data(form=form))
        # The object is saved by the super's form_valid method.
        return super().form_valid(form)


class WorkspaceGroupSharingCreateByWorkspace(
    auth.AnVILConsortiumManagerStaffEditRequired,
    viewmixins.WorkspaceCheckAccessMixin,
    SuccessMessageMixin,
    CreateView,
):
    """View to create a new WorkspaceGroupSharing object for the workspace specified in the url."""

    model = models.WorkspaceGroupSharing
    form_class = forms.WorkspaceGroupSharingForm
    template_name = "anvil_consortium_manager/workspacegroupsharing_form_byworkspace.html"
    success_message = "Successfully shared Workspace with Group."
    """Message to display when the WorkspaceGroupSharing object was successfully created in the app and on AnVIL."""

    workspace_access = models.Workspace.AppAccessChoices.OWNER
    workspace_unlocked = False
    workspace_access_error_message = "Cannot share this workspace because it is not owned by the app."
    message_group_not_found = "Managed Group not found on AnVIL."
    """Message to display when the ManagedGroup was not found on AnVIL."""

    message_already_exists = "This workspace has already been shared with this managed group."

    def get_workspace(self):
        try:
            billing_project_slug = self.kwargs["billing_project_slug"]
            workspace_slug = self.kwargs["workspace_slug"]
            workspace = models.Workspace.objects.get(billing_project__name=billing_project_slug, name=workspace_slug)
        except models.Workspace.DoesNotExist:
            raise Http404("Workspace not found.")
        return workspace

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

    def form_valid(self, form):
        """If the form is valid, save the associated model and create it on AnVIL."""
        # Create but don't save the new group.
        self.object = form.save(commit=False)
        # Make an API call to AnVIL to create the group.
        try:
            self.object.anvil_create_or_update()
        except exceptions.AnVILGroupNotFound:
            messages.add_message(self.request, messages.ERROR, self.message_group_not_found)
            return self.render_to_response(self.get_context_data(form=form))
        except AnVILAPIError as e:
            # If the API call failed, rerender the page with the responses and show a message.
            messages.add_message(self.request, messages.ERROR, "AnVIL API Error: " + str(e))
            return self.render_to_response(self.get_context_data(form=form))
        # The object is saved by the super's form_valid method.
        return super().form_valid(form)


class WorkspaceGroupSharingCreateByGroup(
    auth.AnVILConsortiumManagerStaffEditRequired,
    SuccessMessageMixin,
    CreateView,
):
    """View to create a new WorkspaceGroupSharing object for the group specified in the url."""

    model = models.WorkspaceGroupSharing
    form_class = forms.WorkspaceGroupSharingForm
    template_name = "anvil_consortium_manager/workspacegroupsharing_form_bygroup.html"
    success_message = "Successfully shared Workspace with Group."
    """Message to display when the WorkspaceGroupSharing object was successfully created in the app and on AnVIL."""

    message_group_not_found = "Managed Group not found on AnVIL."
    """Message to display when the ManagedGroup was not found on AnVIL."""

    message_already_exists = "This workspace has already been shared with this managed group."

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

    def form_valid(self, form):
        """If the form is valid, save the associated model and create it on AnVIL."""
        # Create but don't save the new group.
        self.object = form.save(commit=False)
        # Make an API call to AnVIL to create the group.
        try:
            self.object.anvil_create_or_update()
        except exceptions.AnVILGroupNotFound:
            messages.add_message(self.request, messages.ERROR, self.message_group_not_found)
            return self.render_to_response(self.get_context_data(form=form))
        except AnVILAPIError as e:
            # If the API call failed, rerender the page with the responses and show a message.
            messages.add_message(self.request, messages.ERROR, "AnVIL API Error: " + str(e))
            return self.render_to_response(self.get_context_data(form=form))
        # The object is saved by the super's form_valid method.
        return super().form_valid(form)


class WorkspaceGroupSharingCreateByWorkspaceGroup(
    auth.AnVILConsortiumManagerStaffEditRequired,
    viewmixins.WorkspaceCheckAccessMixin,
    SuccessMessageMixin,
    CreateView,
):
    """View to create a new WorkspaceGroupSharing object for the workspace and group specified in the url."""

    model = models.WorkspaceGroupSharing
    form_class = forms.WorkspaceGroupSharingForm
    template_name = "anvil_consortium_manager/workspacegroupsharing_form_byworkspacegroup.html"
    success_message = "Successfully shared Workspace with Group."
    """Message to display when the WorkspaceGroupSharing object was successfully created in the app and on AnVIL."""

    workspace_access = models.Workspace.AppAccessChoices.OWNER
    workspace_unlocked = False
    workspace_access_error_message = "Cannot share this workspace because it is not owned by the app."
    message_group_not_found = "Managed Group not found on AnVIL."
    """Message to display when the ManagedGroup was not found on AnVIL."""

    message_already_exists = "This workspace has already been shared with this managed group."

    def get_workspace(self):
        try:
            billing_project_slug = self.kwargs["billing_project_slug"]
            workspace_slug = self.kwargs["workspace_slug"]
            workspace = models.Workspace.objects.get(billing_project__name=billing_project_slug, name=workspace_slug)
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
            obj = models.WorkspaceGroupSharing.objects.get(workspace=self.workspace, group=self.group)
            messages.error(self.request, self.message_already_exists)
            return HttpResponseRedirect(obj.get_absolute_url())
        except models.WorkspaceGroupSharing.DoesNotExist:
            return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.workspace = self.get_workspace()
        self.group = self.get_group()
        try:
            obj = models.WorkspaceGroupSharing.objects.get(workspace=self.workspace, group=self.group)
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

    def form_valid(self, form):
        """If the form is valid, save the associated model and create it on AnVIL."""
        # Create but don't save the new group.
        self.object = form.save(commit=False)
        # Make an API call to AnVIL to create the group.
        try:
            self.object.anvil_create_or_update()
        except exceptions.AnVILGroupNotFound:
            messages.add_message(self.request, messages.ERROR, self.message_group_not_found)
            return self.render_to_response(self.get_context_data(form=form))
        except AnVILAPIError as e:
            # If the API call failed, rerender the page with the responses and show a message.
            messages.add_message(self.request, messages.ERROR, "AnVIL API Error: " + str(e))
            return self.render_to_response(self.get_context_data(form=form))
        # The object is saved by the super's form_valid method.
        return super().form_valid(form)


class WorkspaceGroupSharingUpdate(
    auth.AnVILConsortiumManagerStaffEditRequired,
    viewmixins.WorkspaceCheckAccessMixin,
    SuccessMessageMixin,
    UpdateView,
):
    """View to update a WorkspaceGroupSharing object and on AnVIL."""

    model = models.WorkspaceGroupSharing
    fields = (
        "access",
        "can_compute",
    )
    template_name = "anvil_consortium_manager/workspacegroupsharing_update.html"
    workspace_access = models.Workspace.AppAccessChoices.OWNER
    workspace_access_error_message = (
        "Cannot update this workspace sharing because the workspace is not owned by the app."
    )
    workspace_unlocked = False
    success_message = "Successfully updated Workspace sharing."
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
                _("No %(verbose_name)s found matching the query") % {"verbose_name": queryset.model._meta.verbose_name}
            )
        return obj

    def get_workspace(self):
        return self.object.workspace

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        return super().get(self, request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        return super().post(self, request, *args, **kwargs)

    def get_access_error_redirect_url(self):
        return self.object.get_absolute_url()

    def form_valid(self, form):
        """If the form is valid, save the associated model and create it on AnVIL."""
        # Create but don't save the new group.
        self.object = form.save(commit=False)
        # Make an API call to AnVIL to create the group.
        try:
            self.object.anvil_create_or_update()
        except AnVILAPIError as e:
            # If the API call failed, rerender the page with the responses and show a message.
            messages.add_message(self.request, messages.ERROR, "AnVIL API Error: " + str(e))
            return self.render_to_response(self.get_context_data(form=form))
        # The object is saved by the super's form_valid method.
        return super().form_valid(form)


class WorkspaceGroupSharingList(auth.AnVILConsortiumManagerStaffViewRequired, SingleTableView):
    model = models.WorkspaceGroupSharing
    table_class = tables.WorkspaceGroupSharingStaffTable


class WorkspaceGroupSharingDelete(
    auth.AnVILConsortiumManagerStaffEditRequired,
    viewmixins.WorkspaceCheckAccessMixin,
    SuccessMessageMixin,
    DeleteView,
):
    model = models.WorkspaceGroupSharing
    success_message = "Successfully removed workspace sharing on AnVIL."
    workspace_access = models.Workspace.AppAccessChoices.OWNER
    workspace_unlocked = False
    workspace_access_error_message = "Cannot remove this record because the workspace is not owned by the app."

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
                _("No %(verbose_name)s found matching the query") % {"verbose_name": queryset.model._meta.verbose_name}
            )
        return obj

    def get_workspace(self):
        return self.get_object().workspace

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        return super().get(self, request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        return super().post(self, request, *args, **kwargs)

    def get_success_url(self):
        return reverse("anvil_consortium_manager:workspace_group_sharing:list")

    def get_access_error_redirect_url(self):
        return self.object.get_absolute_url()

    def form_valid(self, form):
        """
        Make an API call to AnVIL and then call the delete method on the object.
        """
        self.object = self.get_object()
        try:
            self.object.anvil_delete()
        except AnVILAPIError as e:
            # The AnVIL call has failed for some reason.
            messages.add_message(self.request, messages.ERROR, "AnVIL API Error: " + str(e))
            # Rerender the same page with an error message.
            return self.render_to_response(self.get_context_data())
        return super().form_valid(form)
