from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.mail import send_mail
from django.db import transaction
from django.forms.forms import Form
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    FormView,
    TemplateView,
    UpdateView,
)
from django.views.generic.detail import SingleObjectMixin
from django_tables2 import SingleTableMixin, SingleTableView

from . import anvil_api, auth, exceptions, forms, models, tables
from .anvil_api import AnVILAPIClient, AnVILAPIError


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


class Index(auth.AnVILConsortiumManagerViewRequired, TemplateView):
    template_name = "anvil_consortium_manager/index.html"


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
            self.object = models.BillingProject.anvil_import(form.cleaned_data["name"])
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


class BillingProjectDetail(
    auth.AnVILConsortiumManagerViewRequired, SingleTableMixin, DetailView
):
    model = models.BillingProject
    context_table_name = "workspace_table"

    def get_table(self):
        return tables.WorkspaceTable(
            self.object.workspace_set.all(), exclude="billing_project"
        )


class BillingProjectList(auth.AnVILConsortiumManagerViewRequired, SingleTableView):
    model = models.BillingProject
    table_class = tables.BillingProjectTable


class AccountDetail(
    auth.AnVILConsortiumManagerViewRequired, SingleTableMixin, DetailView
):
    model = models.Account
    context_table_name = "group_table"

    def get_table(self):
        return tables.GroupAccountMembershipTable(
            self.object.groupaccountmembership_set.all(),
            exclude=["account", "is_service_account"],
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add an indicator of whether the account is inactive.
        context["is_inactive"] = self.object.status == models.Account.INACTIVE_STATUS
        context["date_verified"] = self.object.date_verified
        context["show_deactivate_button"] = not context["is_inactive"]
        context["show_reactivate_button"] = context["is_inactive"]
        return context


class AccountImport(
    auth.AnVILConsortiumManagerEditRequired, SuccessMessageMixin, CreateView
):
    model = models.Account
    message_account_does_not_exist = "This account does not exist on AnVIL."
    form_class = forms.AccountImportForm
    success_msg = "Successfully imported Account from AnVIL."

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

class AccountLink(LoginRequiredMixin, FormView):
    login_url = '/accounts/login'
    template_name = "anvil_consortium_manager/account_form.html"
    model = models.Account
    message_account_does_not_exist = "This account does not exist on AnVIL."
    form_class = forms.AccountLinkForm

    def form_valid(self, form):
        """If the form is valid, check that the account exists on AnVIL and send verification email."""
        email = form.cleaned_data.get('email')
        acct = models.Account(
                    email = email,
                )
        try:
            account_exists = acct.anvil_exists()

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

        #Account exists in ACM and is not verified
        if models.Account.objects.filter(email__iexact=email, date_verified__isnull=True).count() == 1:
            self.send_mail(email)
            messages.add_message(
                 self.request, messages.ERROR, "This email is not verified, check your email for a verification link"
             )

        #Account exists in ACM and is verified
        elif models.Account.objects.filter(email__iexact=email, date_verified__isnull=False).count() == 1:
            messages.add_message(
                 self.request, messages.ERROR, "Account is already linked to this email."
             )

        else:
            self.send_mail(email)
            models.Account(
                    user = self.request.user,
                    email = email,
                    status = models.Account.INACTIVE_STATUS,
                    is_service_account = False
                ).save()
            messages.add_message(
                 self.request, messages.ERROR, "To complete linking the account, check your email for a verification link"
             )

        return self.render_to_response(self.get_context_data(form=form))


    def send_mail(self, email):
        mail_subject = 'Activate your account.'
        message = 'Test send email'
        to_email = email
        send_mail(mail_subject, message, 'wkirdpoo@uw.edu', [to_email],fail_silently=False,)
        print(email)
        pass


class AccountList(auth.AnVILConsortiumManagerViewRequired, SingleTableView):
    model = models.Account
    table_class = tables.AccountTable


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
    DeleteView,
):
    """Deactivate an account and remove it from all groups on AnVIL."""

    model = models.Account
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
    SingleObjectMixin,
    FormView,
):
    """Reactivate an account and re-add it to all groups on AnVIL."""

    model = models.Account
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
    auth.AnVILConsortiumManagerEditRequired, SuccessMessageMixin, DeleteView
):
    model = models.Account
    message_error_removing_from_groups = "Error removing account from groups; manually verify group memberships on AnVIL. (AnVIL API Error: {})"  # noqa
    success_msg = "Successfully deleted Account from app."

    def get_success_url(self):
        return reverse("anvil_consortium_manager:accounts:list")
        # exceptions.AnVILRemoveAccountFromGroupError

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


class ManagedGroupDetail(auth.AnVILConsortiumManagerViewRequired, DetailView):
    model = models.ManagedGroup

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["workspace_authorization_domain_table"] = tables.WorkspaceTable(
            self.object.workspace_set.all(), exclude="group"
        )
        context["workspace_table"] = tables.WorkspaceGroupAccessTable(
            self.object.workspacegroupaccess_set.all(), exclude="group"
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
        return context


class ManagedGroupCreate(
    auth.AnVILConsortiumManagerEditRequired, SuccessMessageMixin, CreateView
):
    model = models.ManagedGroup
    form_class = forms.ManagedGroupCreateForm
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


class ManagedGroupList(auth.AnVILConsortiumManagerViewRequired, SingleTableView):
    model = models.ManagedGroup
    table_class = tables.ManagedGroupTable


class ManagedGroupDelete(
    auth.AnVILConsortiumManagerEditRequired, SuccessMessageMixin, DeleteView
):
    model = models.ManagedGroup
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
    message_could_not_delete_group = (
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
        if self.object.workspacegroupaccess_set.count() > 0:
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
        if self.object.workspacegroupaccess_set.count() > 0:
            messages.add_message(
                self.request, messages.ERROR, self.message_has_access_to_workspace
            )
            return HttpResponseRedirect(self.object.get_absolute_url())

        try:
            self.object.anvil_delete()
        except exceptions.AnVILGroupDeletionError:
            messages.add_message(
                self.request, messages.ERROR, self.message_could_not_delete_group
            )
            return HttpResponseRedirect(self.object.get_absolute_url())
        except AnVILAPIError as e:
            # The AnVIL call has failed for some reason.
            messages.add_message(
                self.request, messages.ERROR, "AnVIL API Error: " + str(e)
            )
            # Rerender the same page with an error message.
            return self.render_to_response(self.get_context_data())
        return super().delete(request, *args, **kwargs)


class WorkspaceDetail(auth.AnVILConsortiumManagerViewRequired, DetailView):
    model = models.Workspace

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["group_access_table"] = tables.WorkspaceGroupAccessTable(
            self.object.workspacegroupaccess_set.all(), exclude="workspace"
        )
        context["authorization_domain_table"] = tables.ManagedGroupTable(
            self.object.authorization_domains.all(),
            exclude=["workspace", "number_groups", "number_accounts"],
        )
        return context


class WorkspaceCreate(
    auth.AnVILConsortiumManagerEditRequired, SuccessMessageMixin, CreateView
):
    model = models.Workspace
    form_class = forms.WorkspaceCreateForm
    success_msg = "Successfully created Workspace on AnVIL."

    @transaction.atomic
    def form_valid(self, form):
        """If the form is valid, save the associated model and create it on AnVIL."""
        # Need to use a transaction because the object needs to be saved to access the many-to-many field.
        try:
            with transaction.atomic():
                # Calling form.save() does not create the history for the authorization domain many to many field.
                # Instead, save the workspace first and then create the auth domain relationships one by one.
                self.object = form.save(commit=False)
                self.object.save()
                self.object.refresh_from_db()
                for auth_domain in form.cleaned_data["authorization_domains"]:
                    models.WorkspaceAuthorizationDomain.objects.create(
                        workspace=self.object, group=auth_domain
                    )
                self.object.anvil_create()
        except AnVILAPIError as e:
            # If the API call failed, rerender the page with the responses and show a message.
            messages.add_message(
                self.request, messages.ERROR, "AnVIL API Error: " + str(e)
            )
            return self.render_to_response(self.get_context_data(form=form))
        # Add the success message here because we're not calling a super method.
        self.add_success_message()
        return HttpResponseRedirect(self.get_success_url())


class WorkspaceImport(
    auth.AnVILConsortiumManagerEditRequired, SuccessMessageMixin, FormView
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

    def get_success_url(self):
        return self.workspace.get_absolute_url()

    def form_valid(self, form):
        """If the form is valid, check that the workspace exists on AnVIL and save the associated model."""
        # Separate the billing project and workspace name.
        billing_project_name, workspace_name = form.cleaned_data["workspace"].split("/")

        try:
            self.workspace = models.Workspace.anvil_import(
                billing_project_name, workspace_name
            )
        except anvil_api.AnVILAPIError as e:
            messages.add_message(
                self.request, messages.ERROR, "AnVIL API Error: " + str(e)
            )
            return self.render_to_response(self.get_context_data(form=form))

        return super().form_valid(form)


class WorkspaceList(auth.AnVILConsortiumManagerViewRequired, SingleTableView):
    model = models.Workspace
    table_class = tables.WorkspaceTable


class WorkspaceDelete(
    auth.AnVILConsortiumManagerEditRequired, SuccessMessageMixin, DeleteView
):
    model = models.Workspace
    success_msg = "Successfully deleted Workspace on AnVIL."

    def get_success_url(self):
        return reverse("anvil_consortium_manager:workspaces:list")

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


class GroupGroupMembershipDetail(auth.AnVILConsortiumManagerViewRequired, DetailView):
    model = models.GroupGroupMembership


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

    def get_success_url(self):
        return reverse("anvil_consortium_manager:group_group_membership:list")

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

    def get_success_url(self):
        return reverse("anvil_consortium_manager:group_account_membership:list")

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


class WorkspaceGroupAccessDetail(auth.AnVILConsortiumManagerViewRequired, DetailView):
    model = models.WorkspaceGroupAccess


class WorkspaceGroupAccessCreate(
    auth.AnVILConsortiumManagerEditRequired, SuccessMessageMixin, CreateView
):
    model = models.WorkspaceGroupAccess
    fields = ("workspace", "group", "access")
    success_msg = "Successfully shared Workspace with Group."

    def get_success_url(self):
        return reverse("anvil_consortium_manager:workspace_group_access:list")

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


class WorkspaceGroupAccessUpdate(
    auth.AnVILConsortiumManagerEditRequired, SuccessMessageMixin, UpdateView
):
    model = models.WorkspaceGroupAccess
    fields = ("access",)
    template_name = "anvil_consortium_manager/workspacegroupaccess_update.html"
    success_msg = "Successfully updated Workspace sharing."

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


class WorkspaceGroupAccessList(
    auth.AnVILConsortiumManagerViewRequired, SingleTableView
):
    model = models.WorkspaceGroupAccess
    table_class = tables.WorkspaceGroupAccessTable


class WorkspaceGroupAccessDelete(
    auth.AnVILConsortiumManagerEditRequired, SuccessMessageMixin, DeleteView
):
    model = models.WorkspaceGroupAccess
    success_msg = "Successfully removed workspace sharing on AnVIL."

    def get_success_url(self):
        return reverse("anvil_consortium_manager:workspace_group_access:list")

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
