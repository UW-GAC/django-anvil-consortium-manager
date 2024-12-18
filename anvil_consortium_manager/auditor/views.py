from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.forms import HiddenInput
from django.http import Http404, HttpResponseRedirect
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, DeleteView, DetailView, TemplateView, UpdateView

from anvil_consortium_manager import auth
from anvil_consortium_manager.audit import billing_projects as billing_project_audit
from anvil_consortium_manager.models import ManagedGroup
from anvil_consortium_manager.viewmixins import AnVILAuditMixin

from . import forms, models


class BillingProjectAudit(auth.AnVILConsortiumManagerStaffViewRequired, AnVILAuditMixin, TemplateView):
    """View to run an audit on Workspaces and display the results."""

    template_name = "anvil_consortium_manager/billing_project_audit.html"
    audit_class = billing_project_audit.BillingProjectAudit


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
