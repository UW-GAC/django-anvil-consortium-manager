from dal import autocomplete
from django.contrib import messages
from django.db import transaction
from django.forms import Form, inlineformset_factory
from django.http import Http404, HttpResponseRedirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
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
from .adapter import workspace_adapter_registry
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
    slug_field = "name"
    context_table_name = "workspace_table"

    def get_table(self):
        return tables.WorkspaceTable(
            self.object.workspace_set.all(), exclude="billing_project"
        )


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

    def get_queryset(self):
        # Only active accounts.
        qs = models.Account.objects.filter(
            status=models.Account.ACTIVE_STATUS
        ).order_by("email")

        if self.q:
            # When Accounts are linked to users, we'll want to figure out how to filter on fields in the user model.
            qs = qs.filter(email__icontains=self.q)

        return qs


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


class WorkspaceAdapterMixin:
    """Class for handling workspace adapters."""

    def get_adapter(self):
        workspace_type = self.kwargs.get("workspace_type")
        if workspace_type:
            try:
                adapter = workspace_adapter_registry.get_adapter(workspace_type)
            except KeyError:
                raise Http404("workspace_type is not registered.")
        else:
            raise AttributeError(
                "View %s must be called with `workspace_type` in the URLconf."
                % self.__class__.__name__
            )
        return adapter

    def get(self, request, *args, **kwargs):
        self.adapter = self.get_adapter()
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.adapter = self.get_adapter()
        return super().post(request, *args, **kwargs)


class WorkspaceDetail(auth.AnVILConsortiumManagerViewRequired, DetailView):
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
    auth.AnVILConsortiumManagerEditRequired,
    SuccessMessageMixin,
    WorkspaceAdapterMixin,
    FormView,
):
    form_class = forms.WorkspaceCreateForm
    success_msg = "Successfully created Workspace on AnVIL."
    template_name = "anvil_consortium_manager/workspace_form.html"

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
                form.instance.workspace_data_type = self.adapter.get_type()
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
            workspace_data_type = self.adapter.get_type()
            # This is not ideal because we attempt to import the workspace before validating the workspace_data_Form.
            # However, we need to add the workspace to the form before validating it.
            self.workspace = models.Workspace.anvil_import(
                billing_project_name,
                workspace_name,
                workspace_data_type=workspace_data_type,
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


class WorkspaceList(
    auth.AnVILConsortiumManagerViewRequired, WorkspaceAdapterMixin, SingleTableView
):
    model = models.Workspace

    def get_queryset(self):
        return self.model.objects.filter(workspace_data_type=self.adapter.get_type())

    def get_table_class(self):
        """Use the adapter to get the table class."""
        table_class = self.adapter.get_list_table_class()
        return table_class


class WorkspaceDelete(
    auth.AnVILConsortiumManagerEditRequired, SuccessMessageMixin, DeleteView
):
    model = models.Workspace
    success_msg = "Successfully deleted Workspace on AnVIL."

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
            args=[self.object.workspace_data_type],
        )

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


class WorkspaceGroupAccessDetail(auth.AnVILConsortiumManagerViewRequired, DetailView):
    model = models.WorkspaceGroupAccess

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


class WorkspaceGroupAccessCreate(
    auth.AnVILConsortiumManagerEditRequired, SuccessMessageMixin, CreateView
):
    """View to create a new WorkspaceGroupAccess object and share the Workspace with a Group on AnVIL."""

    model = models.WorkspaceGroupAccess
    form_class = forms.WorkspaceGroupAccessForm
    success_msg = "Successfully shared Workspace with Group."
    """Message to display when the WorkspaceGroupAccess object was successfully created in the app and on AnVIL."""

    message_group_not_found = "Managed Group not found on AnVIL."
    """Message to display when the ManagedGroup was not found on AnVIL."""

    def get_success_url(self):
        """URL to redirect to upon success."""
        return reverse("anvil_consortium_manager:workspace_group_access:list")

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


class WorkspaceGroupAccessUpdate(
    auth.AnVILConsortiumManagerEditRequired, SuccessMessageMixin, UpdateView
):
    """View to update a WorkspaceGroupAccess object and update access for the ManagedGroup to the Workspace on AnVIL."""

    model = models.WorkspaceGroupAccess
    fields = (
        "access",
        "can_compute",
    )
    template_name = "anvil_consortium_manager/workspacegroupaccess_update.html"
    success_msg = "Successfully updated Workspace sharing."
    """Message to display when the WorkspaceGroupAccess object was successfully updated."""

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
