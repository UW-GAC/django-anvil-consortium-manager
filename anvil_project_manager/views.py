from django.contrib import messages
from django.db import transaction
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
from django_tables2 import SingleTableMixin, SingleTableView

from . import anvil_api, exceptions, forms, models, tables
from .anvil_api import AnVILAPIClient, AnVILAPIError


class Index(TemplateView):
    template_name = "anvil_project_manager/index.html"


class AnVILStatus(TemplateView):
    template_name = "anvil_project_manager/status.html"

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


class BillingProjectImport(CreateView):
    model = models.BillingProject
    fields = ("name",)
    template_name = "anvil_project_manager/billingproject_import.html"
    message_not_users_of_billing_project = (
        "Not a user of requested billing project or it doesn't exist on AnVIL."
    )

    def form_valid(self, form):
        """If the form is valid, check that we can access the BillingProject on AnVIL and save the associated model."""
        try:
            self.object = models.BillingProject.anvil_import(form.cleaned_data["name"])
            self.object.save()
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

        return HttpResponseRedirect(self.get_success_url())


class BillingProjectDetail(SingleTableMixin, DetailView):
    model = models.BillingProject
    context_table_name = "workspace_table"

    def get_table(self):
        return tables.WorkspaceTable(
            self.object.workspace_set.all(), exclude="billing_project"
        )


class BillingProjectList(SingleTableView):
    model = models.BillingProject
    table_class = tables.BillingProjectTable


class AccountDetail(SingleTableMixin, DetailView):
    model = models.Account
    context_table_name = "group_table"

    def get_table(self):
        return tables.GroupAccountMembershipTable(
            self.object.groupaccountmembership_set.all(),
            exclude=["account", "is_service_account"],
        )


class AccountImport(CreateView):
    model = models.Account
    message_account_does_not_exist = "This account does not exist on AnVIL."
    form_class = forms.AccountImportForm

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

        # Otherwise, proceed as if
        return super().form_valid(form)


class AccountList(SingleTableView):
    model = models.Account
    table_class = tables.AccountTable


class AccountDelete(DeleteView):
    model = models.Account

    def get_success_url(self):
        return reverse("anvil_project_manager:accounts:list")


class ManagedGroupDetail(DetailView):
    model = models.ManagedGroup

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["workspace_authorization_domain_table"] = tables.WorkspaceTable(
            self.object.workspace_set.all(), exclude="group"
        )
        context["workspace_table"] = tables.WorkspaceGroupAccessTable(
            self.object.workspacegroupaccess_set.all(), exclude="group"
        )
        context["account_table"] = tables.GroupAccountMembershipTable(
            self.object.groupaccountmembership_set.all(), exclude="group"
        )
        context["group_table"] = tables.GroupGroupMembershipTable(
            self.object.child_memberships.all(), exclude="parent_group"
        )
        return context


class ManagedGroupCreate(CreateView):
    model = models.ManagedGroup
    fields = ("name",)

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
        # Save the group.
        self.object.save()
        return super().form_valid(form)


class ManagedGroupList(SingleTableView):
    model = models.ManagedGroup
    table_class = tables.ManagedGroupTable


class ManagedGroupDelete(DeleteView):
    model = models.ManagedGroup
    message_not_managed_by_app = (
        "Cannot delete group because it is not managed by this app."
    )
    message_is_auth_domain = (
        "Cannot delete group since it is an authorization domain for a workspace."
    )

    def get_success_url(self):
        return reverse("anvil_project_manager:managed_groups:list")

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
            print("HERE")
            # Add a message and redirect.
            messages.add_message(
                self.request, messages.ERROR, self.message_is_auth_domain
            )
            # Redirect to the object detail page.
            return HttpResponseRedirect(self.object.get_absolute_url())

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


class WorkspaceDetail(DetailView):
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


class WorkspaceCreate(CreateView):
    model = models.Workspace
    form_class = forms.WorkspaceCreateForm

    @transaction.atomic
    def form_valid(self, form):
        """If the form is valid, save the associated model and create it on AnVIL."""
        # Need to use a transaction because the object needs to be saved to access the many-to-many field.
        try:
            with transaction.atomic():
                self.object = form.save()
                self.object.anvil_create()
        except AnVILAPIError as e:
            # If the API call failed, rerender the page with the responses and show a message.
            messages.add_message(
                self.request, messages.ERROR, "AnVIL API Error: " + str(e)
            )
            print(str(e))
            return self.render_to_response(self.get_context_data(form=form))
        return super().form_valid(form)


class WorkspaceImport(FormView):
    template_name = "anvil_project_manager/workspace_import.html"
    form_class = forms.WorkspaceImportForm
    message_anvil_no_access_to_workspace = (
        "Requested workspace doesn't exist or you don't have permission to see it."
    )
    message_anvil_not_owner = "Not an owner of this workspace."
    message_workspace_exists = "This workspace already exists in the web app."

    def get_success_url(self):
        return self.workspace.get_absolute_url()

    def form_valid(self, form):
        """If the form is valid, check that the workspace exists on AnVIL and save the associated model."""
        billing_project_name = form.cleaned_data["billing_project_name"]
        workspace_name = form.cleaned_data["workspace_name"]

        try:
            self.workspace = models.Workspace.anvil_import(
                billing_project_name, workspace_name
            )
        except exceptions.AnVILAlreadyImported:
            # The workspace already exists in the database.
            messages.add_message(
                self.request, messages.ERROR, self.message_workspace_exists
            )
            return self.render_to_response(self.get_context_data(form=form))
        except anvil_api.AnVILAPIError404:
            # Either the workspace doesn't exist or we don't have permission for it.
            messages.add_message(
                self.request, messages.ERROR, self.message_anvil_no_access_to_workspace
            )
            return self.render_to_response(self.get_context_data(form=form))
        except anvil_api.AnVILAPIError as e:
            messages.add_message(
                self.request, messages.ERROR, "AnVIL API Error: " + str(e)
            )
            return self.render_to_response(self.get_context_data(form=form))
        except exceptions.AnVILNotWorkspaceOwnerError:
            # We are not an owner of the workspace.
            messages.add_message(
                self.request, messages.ERROR, self.message_anvil_not_owner
            )
            return self.render_to_response(self.get_context_data(form=form))

        return super().form_valid(form)


class WorkspaceList(SingleTableView):
    model = models.Workspace
    table_class = tables.WorkspaceTable


class WorkspaceDelete(DeleteView):
    model = models.Workspace

    def get_success_url(self):
        return reverse("anvil_project_manager:workspaces:list")

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


class GroupGroupMembershipDetail(DetailView):
    model = models.GroupGroupMembership


class GroupGroupMembershipCreate(CreateView):
    model = models.GroupGroupMembership
    form_class = forms.GroupGroupMembershipForm

    def get_success_url(self):
        return reverse("anvil_project_manager:group_group_membership:list")

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
        # Save the group.
        self.object.save()
        return super().form_valid(form)


class GroupGroupMembershipList(SingleTableView):
    model = models.GroupGroupMembership
    table_class = tables.GroupGroupMembershipTable


class GroupGroupMembershipDelete(DeleteView):
    model = models.GroupGroupMembership

    message_parent_group_not_managed_by_app = (
        "Cannot remove members from parent group because it is not managed by this app."
    )

    def get_success_url(self):
        return reverse("anvil_project_manager:group_group_membership:list")

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


class GroupAccountMembershipDetail(DetailView):
    model = models.GroupAccountMembership


class GroupAccountMembershipCreate(CreateView):
    model = models.GroupAccountMembership
    form_class = forms.GroupAccountMembershipForm

    def get_success_url(self):
        return reverse("anvil_project_manager:group_account_membership:list")

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
        # Save the group.
        self.object.save()
        return super().form_valid(form)


class GroupAccountMembershipList(SingleTableView):
    model = models.GroupAccountMembership
    table_class = tables.GroupAccountMembershipTable


class GroupAccountMembershipDelete(DeleteView):
    model = models.GroupAccountMembership

    message_group_not_managed_by_app = (
        "Cannot remove members from group because it is not managed by this app."
    )

    def get_success_url(self):
        return reverse("anvil_project_manager:group_account_membership:list")

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


class WorkspaceGroupAccessDetail(DetailView):
    model = models.WorkspaceGroupAccess


class WorkspaceGroupAccessCreate(CreateView):
    model = models.WorkspaceGroupAccess
    fields = ("workspace", "group", "access")

    def get_success_url(self):
        return reverse("anvil_project_manager:workspace_group_access:list")

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
        # Save the group.
        self.object.save()
        return super().form_valid(form)


class WorkspaceGroupAccessUpdate(UpdateView):
    model = models.WorkspaceGroupAccess
    fields = ("access",)
    template_name = "anvil_project_manager/workspacegroupaccess_update.html"

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
        # Save the group.
        self.object.save()
        return super().form_valid(form)


class WorkspaceGroupAccessList(SingleTableView):
    model = models.WorkspaceGroupAccess
    table_class = tables.WorkspaceGroupAccessTable


class WorkspaceGroupAccessDelete(DeleteView):
    model = models.WorkspaceGroupAccess

    def get_success_url(self):
        return reverse("anvil_project_manager:workspace_group_access:list")

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
