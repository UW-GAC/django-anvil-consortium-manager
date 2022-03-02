from django.contrib import messages
from django.urls import reverse
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    TemplateView,
    UpdateView,
)
from django_tables2 import SingleTableMixin, SingleTableView

from . import models, tables
from .anvil_api import AnVILAPIError


class Index(TemplateView):
    template_name = "anvil_project_manager/index.html"


class BillingProjectDetail(SingleTableMixin, DetailView):
    model = models.BillingProject
    context_table_name = "workspace_table"

    def get_table(self):
        return tables.WorkspaceTable(
            self.object.workspace_set.all(), exclude="billing_project"
        )


class BillingProjectCreate(CreateView):
    model = models.BillingProject
    fields = ("name",)


class BillingProjectList(SingleTableView):
    model = models.BillingProject
    table_class = tables.BillingProjectTable


class BillingProjectDelete(DeleteView):
    model = models.BillingProject

    def get_success_url(self):
        return reverse("anvil_project_manager:billing_projects:list")


class AccountDetail(SingleTableMixin, DetailView):
    model = models.Account
    context_table_name = "group_table"

    def get_table(self):
        return tables.GroupAccountMembershipTable(
            self.object.groupaccountmembership_set.all(), exclude="account"
        )


class AccountCreate(CreateView):
    model = models.Account
    fields = ("email", "is_service_account")


class AccountList(SingleTableView):
    model = models.Account
    table_class = tables.AccountTable


class AccountDelete(DeleteView):
    model = models.Account

    def get_success_url(self):
        return reverse("anvil_project_manager:accounts:list")


class GroupDetail(DetailView):
    model = models.Group

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
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


class GroupCreate(CreateView):
    model = models.Group
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


class GroupList(SingleTableView):
    model = models.Group
    table_class = tables.GroupTable


class GroupDelete(DeleteView):
    model = models.Group

    def get_success_url(self):
        return reverse("anvil_project_manager:groups:list")

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


class WorkspaceDetail(SingleTableMixin, DetailView):
    model = models.Workspace
    table_class = tables.WorkspaceGroupAccessTable
    context_table_name = "group_table"

    def get_table(self):
        return tables.WorkspaceGroupAccessTable(
            self.object.workspacegroupaccess_set.all(), exclude="workspace"
        )


class WorkspaceCreate(CreateView):
    model = models.Workspace
    fields = (
        "billing_project",
        "name",
    )

    def form_valid(self, form):
        """If the form is valid, save the associated model and create it on AnVIL."""
        # Create but don't save the new workspace.
        self.object = form.save(commit=False)
        # Make an API call to AnVIL to create the workspace.
        try:
            self.object.anvil_create()
        except AnVILAPIError as e:
            # If the API call failed, rerender the page with the responses and show a message.
            messages.add_message(
                self.request, messages.ERROR, "AnVIL API Error: " + str(e)
            )
            print(str(e))
            return self.render_to_response(self.get_context_data(form=form))
        # Save the workspace.
        self.object.save()
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
    fields = ("parent_group", "child_group", "role")

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


class GroupGroupMembershipUpdate(UpdateView):
    model = models.GroupGroupMembership
    fields = ("role",)
    template_name = "anvil_project_manager/groupgroupmembership_update.html"


class GroupGroupMembershipList(SingleTableView):
    model = models.GroupGroupMembership
    table_class = tables.GroupGroupMembershipTable


class GroupGroupMembershipDelete(DeleteView):
    model = models.GroupGroupMembership

    def get_success_url(self):
        return reverse("anvil_project_manager:group_group_membership:list")

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


class GroupAccountMembershipDetail(DetailView):
    model = models.GroupAccountMembership


class GroupAccountMembershipCreate(CreateView):
    model = models.GroupAccountMembership
    fields = ("account", "group", "role")

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


class GroupAccountMembershipUpdate(UpdateView):
    model = models.GroupAccountMembership
    fields = ("role",)
    template_name = "anvil_project_manager/groupaccountmembership_update.html"


class GroupAccountMembershipList(SingleTableView):
    model = models.GroupAccountMembership
    table_class = tables.GroupAccountMembershipTable


class GroupAccountMembershipDelete(DeleteView):
    model = models.GroupAccountMembership

    def get_success_url(self):
        return reverse("anvil_project_manager:group_account_membership:list")

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


class WorkspaceGroupAccessDetail(DetailView):
    model = models.WorkspaceGroupAccess


class WorkspaceGroupAccessCreate(CreateView):
    model = models.WorkspaceGroupAccess
    fields = ("workspace", "group", "access")

    def get_success_url(self):
        return reverse("anvil_project_manager:workspace_group_access:list")


class WorkspaceGroupAccessUpdate(UpdateView):
    model = models.WorkspaceGroupAccess
    fields = ("access",)
    template_name = "anvil_project_manager/workspacegroupaccess_update.html"


class WorkspaceGroupAccessList(SingleTableView):
    model = models.WorkspaceGroupAccess
    table_class = tables.WorkspaceGroupAccessTable


class WorkspaceGroupAccessDelete(DeleteView):
    model = models.WorkspaceGroupAccess

    def get_success_url(self):
        return reverse("anvil_project_manager:workspace_group_access:list")
