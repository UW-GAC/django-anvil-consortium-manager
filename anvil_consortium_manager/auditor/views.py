from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.forms import HiddenInput
from django.http import Http404, HttpResponseRedirect
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, DeleteView, DetailView, TemplateView, UpdateView
from django.views.generic.detail import SingleObjectMixin
from django_filters.views import FilterView
from django_tables2.views import SingleTableMixin

from anvil_consortium_manager import auth
from anvil_consortium_manager.models import ManagedGroup, Workspace

from . import filters, forms, models, tables, viewmixins
from .audit import accounts as account_audit
from .audit import billing_projects as billing_project_audit
from .audit import managed_groups as managed_group_audit
from .audit import workspaces as workspace_audit


class BillingProjectAudit(auth.AnVILConsortiumManagerStaffViewRequired, viewmixins.AnVILAuditMixin, TemplateView):
    """View to run an audit on Workspaces and display the results."""

    template_name = "anvil_consortium_manager/billing_project_audit.html"
    audit_class = billing_project_audit.BillingProjectAudit


class AccountAudit(auth.AnVILConsortiumManagerStaffViewRequired, viewmixins.AnVILAuditMixin, TemplateView):
    """View to run an audit on Accounts and display the results."""

    template_name = "anvil_consortium_manager/account_audit.html"
    audit_class = account_audit.AccountAudit


class ManagedGroupAudit(auth.AnVILConsortiumManagerStaffViewRequired, viewmixins.AnVILAuditMixin, TemplateView):
    """View to run an audit on ManagedGroups and display the results."""

    template_name = "anvil_consortium_manager/managedgroup_audit.html"
    audit_class = managed_group_audit.ManagedGroupAudit


class ManagedGroupMembershipAudit(
    auth.AnVILConsortiumManagerStaffViewRequired,
    SingleObjectMixin,
    viewmixins.AnVILAuditMixin,
    TemplateView,
):
    """View to run an audit on ManagedGroups and display the results."""

    model = ManagedGroup
    slug_field = "name"
    template_name = "anvil_consortium_manager/managedgroup_membership_audit.html"
    message_not_managed_by_app = "Cannot audit membership because group is not managed by this app."

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

    def get_audit_instance(self):
        return managed_group_audit.ManagedGroupMembershipAudit(self.object)


class IgnoredManagedGroupMembershipDetail(auth.AnVILConsortiumManagerStaffViewRequired, DetailView):
    """View to display the details of an models.IgnoredManagedGroupMembership."""

    model = models.IgnoredManagedGroupMembership

    def get_object(self, queryset=None):
        """Return the object the view is displaying."""
        if queryset is None:
            queryset = self.get_queryset()
        # Filter the queryset based on kwargs.
        group_slug = self.kwargs.get("slug", None)
        email = self.kwargs.get("email", None)
        queryset = queryset.filter(group__name=group_slug, ignored_email=email)
        try:
            # Get the single item from the filtered queryset
            obj = queryset.get()
        except queryset.model.DoesNotExist:
            raise Http404(
                _("No %(verbose_name)s found matching the query") % {"verbose_name": queryset.model._meta.verbose_name}
            )
        return obj


class IgnoredManagedGroupMembershipCreate(
    auth.AnVILConsortiumManagerStaffEditRequired, SuccessMessageMixin, CreateView
):
    """View to create a new models.IgnoredManagedGroupMembership."""

    model = models.IgnoredManagedGroupMembership
    form_class = forms.IgnoredManagedGroupMembershipForm
    message_already_exists = "Record already exists for this group and email."
    success_message = "Successfully ignored managed group membership."

    def get_group(self):
        try:
            name = self.kwargs["slug"]
            group = ManagedGroup.objects.get(name=name)
        except ManagedGroup.DoesNotExist:
            raise Http404("ManagedGroup not found.")
        return group

    def get_email(self):
        return self.kwargs["email"]

    def get(self, request, *args, **kwargs):
        self.group = self.get_group()
        self.email = self.get_email()
        try:
            obj = models.IgnoredManagedGroupMembership.objects.get(group=self.group, ignored_email=self.email)
            messages.error(self.request, self.message_already_exists)
            return HttpResponseRedirect(obj.get_absolute_url())
        except models.IgnoredManagedGroupMembership.DoesNotExist:
            return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.group = self.get_group()
        self.email = self.get_email()
        try:
            obj = models.IgnoredManagedGroupMembership.objects.get(group=self.group, ignored_email=self.email)
            messages.error(self.request, self.message_already_exists)
            return HttpResponseRedirect(obj.get_absolute_url())
        except models.IgnoredManagedGroupMembership.DoesNotExist:
            return super().post(request, *args, **kwargs)

    def get_initial(self):
        initial = super().get_initial()
        initial["group"] = self.group
        initial["ignored_email"] = self.email
        return initial

    def get_form(self, **kwargs):
        """Get the form and set the inputs to use a hidden widget."""
        form = super().get_form(**kwargs)
        form.fields["group"].widget = HiddenInput()
        form.fields["ignored_email"].widget = HiddenInput()
        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["group"] = self.group
        context["email"] = self.email
        return context

    def form_valid(self, form):
        """If the form is valid, save the associated model."""
        form.instance.added_by = self.request.user
        return super().form_valid(form)


class IgnoredManagedGroupMembershipList(auth.AnVILConsortiumManagerStaffViewRequired, SingleTableMixin, FilterView):
    """View to display a list of models.IgnoredManagedGroupMembership."""

    model = models.IgnoredManagedGroupMembership
    table_class = tables.IgnoredManagedGroupMembershipTable
    template_name = "auditor/ignoredmanagedgroupmembership_list.html"
    filterset_class = filters.IgnoredManagedGroupMembershipFilter


class IgnoredManagedGroupMembershipUpdate(
    auth.AnVILConsortiumManagerStaffEditRequired, SuccessMessageMixin, UpdateView
):
    """View to update an existing models.IgnoredManagedGroupMembership."""

    model = models.IgnoredManagedGroupMembership
    fields = ("note",)
    success_message = "Successfully updated ignored record."

    def get_object(self, queryset=None):
        if queryset is None:
            queryset = self.get_queryset()
        # Filter the queryset based on kwargs.
        group_slug = self.kwargs.get("slug", None)
        email = self.kwargs.get("email", None)
        queryset = queryset.filter(group__name=group_slug, ignored_email=email)
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
        context["group"] = self.object.group
        context["email"] = self.object.ignored_email
        return context


class IgnoredManagedGroupMembershipDelete(
    auth.AnVILConsortiumManagerStaffEditRequired, SuccessMessageMixin, DeleteView
):
    model = models.IgnoredManagedGroupMembership
    success_message = "Successfully stopped ignoring managed group membership record."

    def get_object(self, queryset=None):
        """Return the object the view is displaying."""

        # Use a custom queryset if provided; this is required for subclasses
        # like DateDetailView
        if queryset is None:
            queryset = self.get_queryset()
        # Filter the queryset based on kwargs.
        group_slug = self.kwargs.get("slug", None)
        email = self.kwargs.get("email", None)
        queryset = queryset.filter(
            group__name=group_slug,
            ignored_email=email,
        )
        try:
            # Get the single item from the filtered queryset
            obj = queryset.get()
        except queryset.model.DoesNotExist:
            raise Http404(
                _("No %(verbose_name)s found matching the query") % {"verbose_name": queryset.model._meta.verbose_name}
            )
        return obj

    def get_success_url(self):
        return self.object.group.get_absolute_url()


class WorkspaceAudit(auth.AnVILConsortiumManagerStaffViewRequired, viewmixins.AnVILAuditMixin, TemplateView):
    """View to run an audit on Workspaces and display the results."""

    template_name = "anvil_consortium_manager/workspace_audit.html"
    audit_class = workspace_audit.WorkspaceAudit


class WorkspaceSharingAudit(
    auth.AnVILConsortiumManagerStaffViewRequired,
    SingleObjectMixin,
    viewmixins.AnVILAuditMixin,
    TemplateView,
):
    """View to run an audit on access to a specific Workspace and display the results."""

    model = Workspace
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
        # Otherwise, return the response.
        return super().get(request, *args, **kwargs)

    def get_audit_instance(self):
        return workspace_audit.WorkspaceSharingAudit(self.object)
