import uuid

import networkx as nx
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.mail import send_mail
from django.db import models, transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django_extensions.db.models import ActivatorModel, TimeStampedModel
from simple_history.models import HistoricalRecords, HistoricForeignKey

from . import exceptions
from .adapters.account import get_account_adapter
from .adapters.workspace import workspace_adapter_registry
from .anvil_api import AnVILAPIClient, AnVILAPIError, AnVILAPIError404
from .tokens import account_verification_token


class AnVILProjectManagerAccess(models.Model):  # noqa: DJ008
    """A meta model used to define app level permissions"""

    STAFF_EDIT_PERMISSION_CODENAME = "anvil_consortium_manager_staff_edit"
    STAFF_VIEW_PERMISSION_CODENAME = "anvil_consortium_manager_staff_view"
    VIEW_PERMISSION_CODENAME = "anvil_consortium_manager_view"
    ACCOUNT_LINK_PERMISSION_CODENAME = "anvil_consortium_manager_account_link"

    class Meta:
        """Not a concrete model."""

        managed = False

        """Disable add, change, view and delete default model permissions"""
        default_permissions = ()

        permissions = [
            ("anvil_consortium_manager_staff_edit", "AnVIL Consortium Manager Staff Edit Permission"),
            ("anvil_consortium_manager_staff_view", "AnVIL Consortium Manager Staff View Permission"),
            (
                "anvil_consortium_manager_account_link",
                "AnVIL Consortium Manager Account Link Permission",
            ),
            (
                "anvil_consortium_manager_view",
                "AnVIL Consortium Manager View Permission",
            ),
        ]


class BillingProject(TimeStampedModel):
    """A model to store information about AnVIL billing projects."""

    name = models.SlugField(max_length=64, unique=True, help_text="Name of the Billing Project on AnVIL.")
    has_app_as_user = models.BooleanField(help_text="Indicator of whether the app is a user in this BillingProject.")
    note = models.TextField(blank=True, help_text="Additional notes.")
    history = HistoricalRecords()

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse(
            "anvil_consortium_manager:billing_projects:detail",
            kwargs={"slug": self.name},
        )

    def anvil_exists(self):
        try:
            response = AnVILAPIClient().get_billing_project(self.name)
        except AnVILAPIError404:
            # The billing project was not found on AnVIL.
            return False
        return response.status_code == 200

    @classmethod
    def anvil_import(cls, billing_project_name, **kwargs):
        """BiillingProject class method to import an existing billing project from AnVIL."""
        try:
            billing_project = cls.objects.get(name=billing_project_name)
        except cls.DoesNotExist:
            billing_project = cls(name=billing_project_name, has_app_as_user=True, **kwargs)
            billing_project.full_clean()
        else:
            # The billing project already exists in the database.
            raise exceptions.AnVILAlreadyImported("BillingProject: " + billing_project_name)
        # I think we only care if this doesn't raise an exception.
        # That should mean that it is successful, and we don't care about any of the information returned.
        AnVILAPIClient().get_billing_project(billing_project_name)
        billing_project.save()
        return billing_project


class UserEmailEntry(TimeStampedModel, models.Model):
    """A model to store emails that users could link to their AnVIL account after verification."""

    uuid = models.UUIDField(default=uuid.uuid4)
    """UUID for use in urls."""

    email = models.EmailField()
    """The email entered by the user."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.CASCADE)
    """The user who created the record."""

    date_verification_email_sent = models.DateTimeField()
    """Most recent date that a verification email was sent."""

    date_verified = models.DateTimeField(null=True, blank=True)
    """The date that the email was verified by the user."""

    history = HistoricalRecords()
    """Django simple history."""

    class Meta:
        constraints = [models.UniqueConstraint(fields=["email", "user"], name="unique_user_email_entry")]
        verbose_name_plural = "user email entries"

    def __str__(self):
        """String method."""
        return "{email} for {user}".format(email=self.email, user=self.user)

    def save(self, *args, **kwargs):
        self.email = self.email.lower()
        return super().save(*args, **kwargs)

    def anvil_account_exists(self):
        """Check if this account exists on AnVIL."""
        try:
            AnVILAPIClient().get_user(self.email)
        except AnVILAPIError404:
            return False
        except AnVILAPIError as e:
            if e.status_code == 204:
                return False
            else:
                raise
        return True

    def send_verification_email(self, domain):
        """Send a verification email to the email on record.

        Args:
            domain (str): The domain of the current site, used to create the link.
        """
        mail_subject = get_account_adapter().account_link_email_subject
        account_verification_template = get_account_adapter().account_link_email_template

        url_subdirectory = "http://{domain}{url}".format(
            domain=domain,
            url=reverse(
                "anvil_consortium_manager:accounts:verify",
                args=[self.uuid, account_verification_token.make_token(self)],
            ),
        )
        message = render_to_string(
            account_verification_template,
            {
                "user": self.user,
                "verification_link": url_subdirectory,
            },
        )
        send_mail(mail_subject, message, None, [self.email], fail_silently=False)


class Account(TimeStampedModel, ActivatorModel):
    """A model to store information about AnVIL accounts."""

    ERROR_USER_WITHOUT_VERIFIED_EMAIL_ENTRY = "Accounts with a user must have a verified_email_entry."
    ERROR_VERIFIED_EMAIL_ENTRY_WITHOUT_USER = "Accounts with a verified_email_entry must have a user."
    ERROR_UNVERIFIED_VERIFIED_EMAIL_ENTRY = "verified_email_entry must have date_verified."
    ERROR_MISMATCHED_USER = "Account.user and verified_email_entry.user do not match."
    ERROR_MISMATCHED_EMAIL = "Account.email and verified_email_entry.email do not match."

    # TODO: Consider using CIEmailField if using postgres.
    email = models.EmailField(unique=True, help_text="""Email associated with this account on AnVIL.""")
    is_service_account = models.BooleanField(
        help_text="""Indicator of whether this account is a service account or a user account."""
    )
    uuid = models.UUIDField(default=uuid.uuid4, help_text="""UUID for use in urls.""")
    # Use on_delete=PROTECT here because additional things need to happen when an account is deleted,
    # and we're not sure what that should be. Deactivate the account or and/or remove it from groups?
    # I think it's unlikely we will be deleting users frequently, and we can revisit this if necessary.
    # So table it for later.
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        help_text="User linked to this AnVIL account.",
    )
    is_service_account = models.BooleanField(help_text="Indicator of whether this Account is a service account.")
    verified_email_entry = models.OneToOneField(
        UserEmailEntry,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="verified_account",
        help_text="""The UserEmailEntry object used to verify the email,
        if the account was created by a user linking their email.""",
    )
    unlinked_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="unlinked_accounts",
        help_text="Previous users that this account has been linked to.",
        blank=True,
        through="AccountUserArchive",
    )
    note = models.TextField(blank=True, help_text="Additional notes.")

    history = HistoricalRecords()
    """Django simple history record for this model."""

    def __str__(self):
        """String method.

        Returns:
            A string representing the object.
        """
        return "{email}".format(email=self.email)

    def clean(self):
        """Additional custom cleaning steps.

        * user and verified_email_entry: both or neither must be set.
        * verified_email_entry must have a non-null date_verified value.
        * user and verified_email_entry.user must match.
        * email and verified_email_entry.email must match.
        """

        if self.user and not self.verified_email_entry:
            raise ValidationError({"verified_email_entry": self.ERROR_USER_WITHOUT_VERIFIED_EMAIL_ENTRY})
        elif self.verified_email_entry and not self.user:
            raise ValidationError({"user": self.ERROR_VERIFIED_EMAIL_ENTRY_WITHOUT_USER})
        elif self.verified_email_entry and self.user:
            # Make sure the email entry is actually verified.
            if not self.verified_email_entry.date_verified:
                raise ValidationError({"verified_email_entry": self.ERROR_UNVERIFIED_VERIFIED_EMAIL_ENTRY})
            # Check that emails match.
            if self.email != self.verified_email_entry.email:
                raise ValidationError({"email": self.ERROR_MISMATCHED_EMAIL})
            # Check that users match.
            if self.user != self.verified_email_entry.user:
                raise ValidationError({"user": self.ERROR_MISMATCHED_USER})

    def save(self, *args, **kwargs):
        """Save method to set the email address to lowercase before saving."""
        self.email = self.email.lower()
        return super().save(*args, **kwargs)

    def get_absolute_url(self):
        """Get the absolute url for this object.

        Returns:
            A string with the url to the detail page for this object.
        """
        return reverse("anvil_consortium_manager:accounts:detail", kwargs={"uuid": self.uuid})

    def deactivate(self):
        """Set status to deactivated and remove from any AnVIL groups."""
        self.anvil_remove_from_groups()
        self.deactivate_date = timezone.now()
        self.status = self.INACTIVE_STATUS
        self.save()

    def reactivate(self):
        """Set status to reactivated."""
        self.status = self.ACTIVE_STATUS
        self.save()

    def anvil_exists(self):
        """Check if this account exists on AnVIL.

        Returns:
            Boolean indicator of whether ``email`` is associated with an account on AnVIL.
        """
        try:
            AnVILAPIClient().get_user(self.email)
        except AnVILAPIError404:
            return False
        except AnVILAPIError as e:
            if e.status_code == 204:
                return False
            else:
                raise
        return True

    def anvil_remove_from_groups(self):
        """Remove this account from all groups on AnVIL and delete membership records from the app."""
        group_memberships = self.groupaccountmembership_set.all()
        for membership in group_memberships:
            membership.anvil_delete()
            membership.delete()

    def get_accessible_workspaces(self):
        """Get a list of workspaces an Account has access to.

        To be considered accessible, two criteria must be met:
        1. The workspace is shared the Account via a group (or parent group).
        2. The Account must be part of all groups used as the authorization domain for the workspace,
        either directly or indirectly.

        Returns:
            A list of workspaces that are accessible to the account.
        """
        groups = self.get_all_groups()
        # check what workspaces have been shared with any of those groups;
        workspaces = WorkspaceGroupSharing.objects.filter(group__in=groups)
        # check if all the auth domains for each workspace are in the Account's set of groups.
        accessible_workspaces = set()
        for ws in workspaces:
            authorized_domains = list(ws.workspace.authorization_domains.all())
            # Check if the app controls all auth domains; it might not.
            # import ipdb; ipdb.set_trace()
            if len(set(authorized_domains).difference(set(groups))) == 0:
                accessible_workspaces.add(ws.workspace)
        return accessible_workspaces

    def get_all_groups(self):
        """get a list of all groups that an Account is in, directly and indirectly"""
        groups = set()
        group_memberships = self.groupaccountmembership_set.all()
        for membership in group_memberships:
            groups.add(membership.group)
            parents = membership.group.get_all_parents()

            for group in parents:
                groups.add(group)
        return groups

    def has_workspace_access(self, workspace):
        """Return a boolean indicator of whether the workspace can be accessed by this Account."""
        accessible_workspaces = self.get_accessible_workspaces()
        return workspace in accessible_workspaces

    def unlink_user(self):
        """Unlink the user from this account.

        This will remove the user from the account and add the user (and verified email entry, if applicable) to the
        unlinked_users field.

        Raises:
            ValueError: If there is no user linked to the account.
        """
        if not self.user:
            raise ValueError("No user is linked to this account.")
        self.unlinked_users.add(self.user, through_defaults={"verified_email_entry": self.verified_email_entry})
        self.user = None
        self.verified_email_entry = None
        self.save()


class AccountUserArchive(TimeStampedModel):
    """A model to store information about the previous users of an Account."""

    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    verified_email_entry = models.ForeignKey(UserEmailEntry, on_delete=models.CASCADE, null=True, blank=True)
    history = HistoricalRecords()

    def __str__(self):
        return "{user} for {account}".format(user=self.user, account=self.account)


class ManagedGroup(TimeStampedModel):
    """A model to store information about AnVIL Managed Groups."""

    name = models.SlugField(
        max_length=60,  # Max allowed by AnVIL.
        unique=True,
        help_text="Name of the group on AnVIL.",
    )
    email = models.EmailField(
        help_text="Email for this group.",
        blank=False,
        unique=True,
    )
    is_managed_by_app = models.BooleanField(
        default=True, help_text="Indicator of whether this group is managed by the app."
    )
    note = models.TextField(blank=True, help_text="Additional notes.")
    history = HistoricalRecords()

    def __str__(self):
        return "{name}".format(name=self.name)

    def get_absolute_url(self):
        return reverse("anvil_consortium_manager:managed_groups:detail", kwargs={"slug": self.name})

    def get_direct_parents(self):
        """Return a queryset of the direct parents of this group. Does not include grandparents."""
        return ManagedGroup.objects.filter(child_memberships__child_group=self)

    def get_direct_children(self):
        """Return a queryset of the direct children of this group. Does not include grandchildren."""
        return ManagedGroup.objects.filter(parent_memberships__parent_group=self)

    def get_all_parents(self):
        """Return a queryset of all direct and indirect parents of this group. Includes all grandparents.

        Not optimized.
        """
        these_parents = self.get_direct_parents().distinct()
        parents = these_parents
        for parent in these_parents:
            # Chained unions don't work in MariaDB 10.3.
            # parents = parents.union(parent.get_all_parents())
            parents = parents | parent.get_all_parents()
        return parents.distinct()

    def get_all_children(self):
        """Return a queryset of all direct and indirect children of this group. Includes all childrenparents.

        Not optimized.
        """
        these_children = self.get_direct_children().distinct()
        children = these_children
        for child in these_children:
            # Chained unions don't work in MariaDB 10.3.
            # children = children.union(child.get_all_children())
            children = children | child.get_all_children().distinct()
        return children.distinct()

    def get_anvil_url(self):
        """Return the URL of the group on AnVIL."""
        return "https://app.terra.bio/#groups/{group}".format(group=self.name)

    def _add_parents_to_graph(self, G):
        parent_memberships = self.parent_memberships.all()
        for membership in parent_memberships:
            # Add a node and an edge.
            if membership.parent_group.name not in G.nodes:
                G.add_node(
                    membership.parent_group.name,
                    n_groups=membership.parent_group.child_memberships.count(),
                    n_accounts=membership.parent_group.groupaccountmembership_set.count(),
                )
            G.add_edge(membership.parent_group.name, self.name, role=membership.role)
            # Get the parents of that parent.
            membership.parent_group._add_parents_to_graph(G)

    def _add_children_to_graph(self, G):
        child_memberships = self.child_memberships.all()
        for membership in child_memberships:
            if membership.child_group.name not in G.nodes:
                G.add_node(
                    membership.child_group.name,
                    n_groups=membership.child_group.child_memberships.count(),
                    n_accounts=membership.child_group.groupaccountmembership_set.count(),
                )
            G.add_edge(self.name, membership.child_group.name, role=membership.role)
            # Get the parents of that parent.
            membership.child_group._add_children_to_graph(G)

    def get_graph(self):
        """Return a networkx graph of the group structure for this group.

        The graph contains parents and children that can be reached from this group.

        Returns:
            A networkx.DiGraph object representing the group relationships.
        """
        # Set up the graph.
        G = nx.DiGraph()
        G.add_node(
            self.name,
            n_groups=self.child_memberships.count(),
            n_accounts=self.groupaccountmembership_set.count(),
        )
        # Needs to be split up into subfunctions or else you get infinite recursion.
        self._add_parents_to_graph(G)
        self._add_children_to_graph(G)
        return G

    @classmethod
    def get_full_graph(cls):
        """Return a networkx graph of the group structure for all ManagedGroups in the app.

        Returns:
            A networkx.DiGraph object representing the group relationships.
        """
        # Build the graph with nx.
        G = nx.DiGraph()
        # Add nodes to the graph.
        for node in cls.objects.all():
            G.add_node(
                node.name,
                n_groups=node.child_memberships.count(),
                n_accounts=node.groupaccountmembership_set.count(),
            )
        # Add edges.
        for membership in GroupGroupMembership.objects.all():
            G.add_edge(
                membership.parent_group.name,
                membership.child_group.name,
                role=membership.role,
            )
        return G

    def anvil_exists(self):
        """Check if the group exists on AnVIL."""
        try:
            response = AnVILAPIClient().get_group_email(self.name)
        except AnVILAPIError404:
            # The group was not found on AnVIL.
            return False
        return response.status_code == 200

    def anvil_create(self):
        """Creates the group on AnVIL."""
        AnVILAPIClient().create_group(self.name)

    def anvil_delete(self):
        """Deletes the group on AnVIL."""
        # The firecloud API occasionally returend successful codes when a group could not be deleted.
        # Switching to the SAM API seems to have fixed this.
        AnVILAPIClient().delete_group(self.name)

    @classmethod
    def anvil_import(cls, group_name, **kwargs):
        """Import an existing group from AnVIL."""
        # Create the group but don't save it yet.
        # Assume that it's not managed by the app until we figure out that it is.
        # Assume the email is the default until we figure out what it is.
        group = cls(name=group_name, is_managed_by_app=False, email=group_name.lower() + "@firecloud.org", **kwargs)
        # Make sure we don't already have it in the database.
        group.full_clean()
        # Note that we have to be a member of the group to import it.
        response = AnVILAPIClient().get_groups()
        json = response.json()
        # Apparently the AnVIL API will return two records if you are both a member and an admin
        # of a group. We will need to check all the records for this group to see if any of them
        # indiciate that we are an admin.
        count = 0
        for group_details in json:
            if group_details["groupName"] == group_name:
                count += 1
                # Set email using the json response.
                group.email = group_details["groupEmail"].lower()
                # If any of them are admin, set is_managed_by_app.
                if group_details["role"].lower() == "admin":
                    group.is_managed_by_app = True
        # Make sure a group was found.
        if count == 0:
            # Check that the group actually exists in AnVIL.
            response = AnVILAPIClient().get_group_email(group_name)
            group.email = response.json()
        # Verify it is still correct after modifying some fields.
        with transaction.atomic():
            group.full_clean()
            group.save()
            # Import membership records.
            if group.is_managed_by_app:
                group.anvil_import_membership()
        return group

    def anvil_import_membership(self):
        """Import group membership records from AnVIL, as long as the members/admins already exist in the app.

        Groups or accounts that are not already in the app are not imported."""
        if not self.is_managed_by_app:
            raise exceptions.AnVILNotGroupAdminError("group {} is not managed by app".format(self.name))
        # Now add membership records.
        api_client = AnVILAPIClient()
        response = api_client.get_group_members(self.name)
        # Convert to case-insensitive emails.
        members_in_anvil = [x.lower() for x in response.json()]
        response = api_client.get_group_admins(self.name)
        # Convert to case-insensitive emails.
        admins_in_anvil = [x.lower() for x in response.json()]
        for email in admins_in_anvil:
            # Check groups.
            try:
                child_group = ManagedGroup.objects.get(email__iexact=email)
                membership = GroupGroupMembership(
                    parent_group=self,
                    child_group=child_group,
                    role=GroupGroupMembership.ADMIN,
                )
                membership.full_clean()
                membership.save()
            except ManagedGroup.DoesNotExist:
                # This email is not associated with a group in the app.
                pass
            # Check accounts.
            try:
                account = Account.objects.get(email=email)
                membership = GroupAccountMembership(group=self, account=account, role=GroupAccountMembership.ADMIN)
                membership.full_clean()
                membership.save()
            except Account.DoesNotExist:
                # This email is not associated with an Account in the app.
                pass
            # Remove this email from the members.
            try:
                members_in_anvil.remove(email)
            except ValueError:
                # Not also listed as a member - this is ok.
                pass
        for email in members_in_anvil:
            try:
                child_group = ManagedGroup.objects.get(email__iexact=email)
                membership = GroupGroupMembership(
                    parent_group=self,
                    child_group=child_group,
                    role=GroupGroupMembership.MEMBER,
                )
                membership.full_clean()
                membership.save()
            except ManagedGroup.DoesNotExist:
                # This email is not associated with a group in the app.
                pass
            # Check accounts.
            try:
                account = Account.objects.get(email=email)
                membership = GroupAccountMembership(group=self, account=account, role=GroupAccountMembership.MEMBER)
                membership.full_clean()
                membership.save()
            except Account.DoesNotExist:
                # This email is not associated with an Account in the app.
                pass


class Workspace(TimeStampedModel):
    """A model to store information about AnVIL workspaces."""

    # NB: In the APIs some documentation, this is also referred to as "namespace".
    # In other places, it is "billing project".
    # For internal consistency, call it "billing project" here.
    billing_project = models.ForeignKey(
        "BillingProject",
        on_delete=models.PROTECT,
        help_text="Billing project associated with this Workspace.",
    )
    name = models.SlugField(
        max_length=254,  # Max allowed by AnVIL.
        help_text="Name of the workspace on AnVIL, not including billing project name.",
    )
    # This makes it possible to easily select the authorization domains in the WorkspaceForm.
    # However, it does not create a record in django-simple-history for creating the many-to-many field.
    authorization_domains = models.ManyToManyField(
        "ManagedGroup",
        through="WorkspaceAuthorizationDomain",
        blank=True,
        help_text="Authorization domain(s) for this workspace.",
    )
    note = models.TextField(blank=True, help_text="Additional notes.")
    # If this doesn't work easily, we could switch to using generic relationships.
    workspace_type = models.CharField(max_length=255, help_text="""Workspace data type as indicated by an adapter.""")
    is_locked = models.BooleanField(
        help_text="Indicator of whether the workspace is locked or not.",
        default=False,
    )
    is_requester_pays = models.BooleanField(
        verbose_name="Requester pays",
        help_text="Indicator of whether the workspace is set to requester pays.",
        default=False,
    )
    history = HistoricalRecords()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["billing_project", "name"], name="unique_workspace")]

    def clean_fields(self, exclude=None):
        super().clean_fields(exclude=exclude)
        # Check that workspace type is a registered adapter type.
        if not exclude or "workspace_type" not in exclude:
            registered_adapters = workspace_adapter_registry.get_registered_adapters()
            if self.workspace_type not in registered_adapters:
                raise ValidationError({"workspace_type": "Value ``workspace_type`` is not a registered adapter type."})

    def __str__(self):
        return "{billing_project}/{name}".format(billing_project=self.billing_project, name=self.name)

    def get_absolute_url(self):
        return reverse(
            "anvil_consortium_manager:workspaces:detail",
            kwargs={
                "billing_project_slug": self.billing_project.name,
                "workspace_slug": self.name,
            },
        )

    def get_full_name(self):
        return "{billing_project}/{name}".format(billing_project=self.billing_project, name=self.name)

    def get_anvil_url(self):
        """Return the URL of the workspace on AnVIL."""
        return "https://anvil.terra.bio/#workspaces/{billing_project}/{group}".format(
            billing_project=self.billing_project.name, group=self.name
        )

    def anvil_exists(self):
        """Check if the workspace exists on AnVIL."""
        try:
            response = AnVILAPIClient().get_workspace(self.billing_project.name, self.name)
        except AnVILAPIError404:
            return False
        return response.status_code == 200

    def anvil_create(self):
        """Create the workspace on AnVIL."""
        auth_domains = list(self.authorization_domains.all().values_list("name", flat=True))
        AnVILAPIClient().create_workspace(self.billing_project.name, self.name, authorization_domains=auth_domains)

    def anvil_delete(self):
        """Delete the workspace on AnVIL."""
        AnVILAPIClient().delete_workspace(self.billing_project.name, self.name)

    def anvil_clone(self, billing_project, workspace_name, authorization_domains=[]):
        """Clone this workspace to create a new workspace on AnVIL.

        If the workspace to clone already has authorization domains, they will be added to
        the authorization domains specified in `authorization_domains`."""
        # Check that the app can create workspaes in this billing project.
        if not billing_project.has_app_as_user:
            raise ValueError("BillingProject must have has_app_as_user=True.")
        # Do not check if the new workspace already exists in the app.
        # It may have already been created for some reason.
        # if Workspace.objects.filter(
        #     billing_project=billing_project, name=workspace_name
        # ).exists():
        #     raise ValueError(
        #         "Workspace with this BillingProject and Name already exists."
        #     )
        # All checks have passed, so start the cloning process.
        # Set up new auth domains using:
        # - existing auth domains for the workspace being cloned
        # - new auth domains that are specified when cloning.
        current_auth_domains = self.authorization_domains.all()
        auth_domains = [g.name for g in current_auth_domains] + [
            g.name for g in authorization_domains if g not in current_auth_domains
        ]
        # Clone the workspace on AnVIL.
        AnVILAPIClient().clone_workspace(
            self.billing_project.name,
            self.name,
            billing_project.name,
            workspace_name,
            authorization_domains=auth_domains,
            copy_files_with_prefix="notebooks",
        )
        # Do not create the cloned workspace - it can be imported or created elsewhere.
        # That way, the workspace_type can be set.

    @classmethod
    def anvil_import(cls, billing_project_name, workspace_name, workspace_type, note=""):
        """Create a new instance for a workspace that already exists on AnVIL.

        Methods calling this should handle AnVIL API exceptions appropriately.
        """
        # Check if the workspace already exists in the database.
        try:
            cls.objects.get(billing_project__name=billing_project_name, name=workspace_name)
            raise exceptions.AnVILAlreadyImported(billing_project_name + "/" + workspace_name)
        except cls.DoesNotExist:
            # The workspace doesn't exist: continue to creation.
            pass

        # Run in a transaction since we may need to create the billing project, but we only want
        # it to be saved if everything succeeds.
        try:
            with transaction.atomic():
                # Make temporary versions of the objects to validate them before checking for the workspace.
                # This is primarily to check that the fields are valid.
                # We only want ot make the API call if they are valid.
                try:
                    billing_project = BillingProject.objects.get(name=billing_project_name)
                    billing_project_exists = True
                except BillingProject.DoesNotExist:
                    temporary_billing_project = BillingProject(name=billing_project_name, has_app_as_user=False)
                    temporary_billing_project.clean_fields()
                    billing_project_exists = False

                # Do not set the Billing yet, since we might be importing it or creating it later.
                # This is only to validate the other fields.
                workspace = cls(name=workspace_name, workspace_type=workspace_type, note=note)
                workspace.clean_fields(exclude="billing_project")
                # At this point, they should be valid objects.

                # Make sure we actually have access to the workspace.
                try:
                    response = AnVILAPIClient().get_workspace(billing_project_name, workspace_name)
                    workspace_json = response.json()
                except AnVILAPIError404:
                    # This exception is raised if a workspace is shared with us, but we aren't in the auth domain.
                    # In this case, we need to pull the information we need from the list of all workspaces.
                    response = AnVILAPIClient().list_workspaces()
                    workspaces = [
                        x
                        for x in response.json()
                        if x["workspace"]["name"] == workspace_name
                        and x["workspace"]["namespace"] == billing_project_name
                    ]
                    if len(workspaces) == 1:
                        workspace_json = workspaces[0]
                    else:
                        raise exceptions.AnVILNotWorkspaceOwnerError(billing_project_name + "/" + workspace_name)

                # Make sure that we are owners of the workspace.
                # We will either be listed as "OWNER" or "NO ACCESS" in the response.
                if workspace_json["accessLevel"] == "OWNER" or workspace_json["accessLevel"] == "NO ACCESS":
                    # Get the list of groups that it is shared with and create records for them.
                    try:
                        response = AnVILAPIClient().get_workspace_acl(billing_project_name, workspace_name)
                        acl = response.json()["acl"]
                    except AnVILAPIError404:
                        # This exception is raised if the workspace is not shared with us.
                        raise exceptions.AnVILNotWorkspaceOwnerError(billing_project_name + "/" + workspace_name)
                else:
                    raise exceptions.AnVILNotWorkspaceOwnerError(billing_project_name + "/" + workspace_name)

                # Now we can proceed with saving the objects.

                # Import the billing project from AnVIL if it doesn't already exist.
                if not billing_project_exists:
                    try:
                        billing_project = BillingProject.anvil_import(billing_project_name)
                    except AnVILAPIError404:
                        # Use the temporary billing project we previously created above.
                        billing_project = temporary_billing_project
                        billing_project.save()

                # Check if the workspace is locked.
                if workspace_json["workspace"]["isLocked"]:
                    workspace.is_locked = True

                # Finally, set the workspace's billing project to the existing or newly-added BillingProject.
                workspace.billing_project = billing_project
                # Redo cleaning, including checks for uniqueness.
                workspace.full_clean()
                workspace.save()

                # Check the authorization domains and import them.
                auth_domains = [ad["membersGroupName"] for ad in workspace_json["workspace"]["authorizationDomain"]]
                # We don't need to check if we are members of the auth domains, because if we weren't we wouldn't be
                # able to see the workspace.
                for auth_domain in auth_domains:
                    # Either get the group from the Django database or import it.
                    try:
                        group = ManagedGroup.objects.get(name=auth_domain)
                    except ManagedGroup.DoesNotExist:
                        group = ManagedGroup.anvil_import(auth_domain)
                    # Add it as an authorization domain for this workspace.
                    WorkspaceAuthorizationDomain.objects.create(workspace=workspace, group=group)

                # Set up group sharing.
                for email, item in acl.items():
                    if email.endswith("@firecloud.org"):
                        try:
                            group = ManagedGroup.objects.get(name=email.split("@")[0])
                            WorkspaceGroupSharing.objects.create(
                                workspace=workspace,
                                group=group,
                                access=item["accessLevel"].upper(),
                                can_compute=item["canCompute"],
                            )
                        except ManagedGroup.DoesNotExist:
                            # The group doesn't exist in the app - don't do anything.
                            pass

        except Exception:
            # If it fails for any reason we haven't already handled, we don't want the transaction to happen.
            raise

        return workspace

    def has_in_authorization_domain(self, account):
        """Check if an account is in the authorization domain(s) for this workspace.

        Args:
            account (Account): The account to check.

        Returns:
            bool: True if the user is in the authorization domain, False otherwise.

        Raises:
            WorkspaceAccountAuthorizationDomainUnknownError: If any authorization domains are not managed by the app.
        """
        if not isinstance(account, Account):
            raise ValueError("account must be an instance of `Account`.")
        # Get the groups that are in the authorization domain.
        auth_domains = self.authorization_domains.all()
        # Separate into managed by app and not managed by app.
        groups_managed_by_app = auth_domains.filter(is_managed_by_app=True)
        groups_not_managed_by_app = auth_domains.filter(is_managed_by_app=False)
        # Get the list of groups that the user is in.
        account_groups = account.get_all_groups()
        # Check if the user is in any of the groups that are managed by the app.
        if len(set(groups_managed_by_app).difference(set(account_groups))) == 0:
            # Now check if any are not managed by the app - this would be an "unknown" case.
            if groups_not_managed_by_app.exists():
                raise exceptions.WorkspaceAccountAuthorizationDomainUnknownError(
                    "At least one auth domain is not managed by the app."
                )
            else:
                return True
        else:
            return False

    def is_shared_with(self, account):
        """Check if the workspace is shared with any groups the account is in.

        Args:
            account (Account): The account to check.

        Returns:
            bool: True if the user is in the authorization domain, False otherwise.

        Raises:
            WorkspaceAccountSharingUnknownError: If the code cannot determine whether the workspace is shared or not.
        """
        if not isinstance(account, Account):
            raise ValueError("account must be an instance of `Account`.")
        # Get the list of groups that the workspace is shared with.
        workspace_groups = ManagedGroup.objects.filter(workspacegroupsharing__workspace=self)
        # Get the list of groups that the account is in.
        account_groups = account.get_all_groups()
        # Check if any of the groups that the workspace is shared with are in the account's groups.
        if len(set(workspace_groups).intersection(set(account_groups))) > 0:
            return True
        else:
            if workspace_groups.filter(is_managed_by_app=False).exists():
                raise exceptions.WorkspaceAccountSharingUnknownError(
                    "Workspace is shared with some groups that are not managed by the app."
                )
            return False

    def is_accessible_by(self, account):
        """Check if an account has access to a workspace.

        Args:
            account (Account): The account to check.

        Returns:
            bool: True if the account has access, False otherwise.

        Raises:
            ValueError: If the account is not an instance of Account.
            WorkspaceAccessUnknownError: If the code cannot determine both sharing status and auth domain status.
            WorkspaceAccountSharingUnknownError: If the code cannot determine sharing status.
            WorkspaceAccountAuthorizationDomainUnknownError: If the code cannot determine auth domain status.
        """
        # First check sharing, then check auth domain membership.
        try:
            is_shared = self.is_shared_with(account)
            if not is_shared:
                return False
        except exceptions.WorkspaceAccountSharingUnknownError as e:
            try:
                in_auth_domain = self.has_in_authorization_domain(account)
            except exceptions.WorkspaceAccountAuthorizationDomainUnknownError:
                # In this case, we don't know sharing status OR auth domain status.
                raise exceptions.WorkspaceAccountAccessUnknownError(
                    "Workspace sharing and auth domain status is unknown for {}.".format(account)
                )
            # If we don't know if it's shared but the account is not in the auth domain, they don't have access.
            # If the account is in the auth domain, then we should re-raise the sharing exception.
            if not in_auth_domain:
                return False
            else:
                raise e
        else:
            # If we've gotten here, sharing is either False or True.
            # Check auth domain membership. If it is unknown, this method raises the correct exception.
            in_auth_domain = self.has_in_authorization_domain(account)
            return in_auth_domain and is_shared


class BaseWorkspaceData(models.Model):
    """Abstract base class to subclass when creating a custom WorkspaceData model."""

    workspace = models.OneToOneField(Workspace, on_delete=models.CASCADE)
    history = HistoricalRecords(inherit=True)

    class Meta:
        abstract = True

    def __str__(self):
        return str(self.workspace)

    def get_absolute_url(self):
        return self.workspace.get_absolute_url()


class DefaultWorkspaceData(BaseWorkspaceData):
    """Default empty WorkspaceData model."""

    pass


class WorkspaceAuthorizationDomain(TimeStampedModel):
    """Through table for the Workspace authorization_domains field."""

    group = models.ForeignKey(
        ManagedGroup,
        on_delete=models.PROTECT,
        help_text="Group used as an authorization domain.",
    )
    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        help_text="Workspace for which this group is an authorization domain.",
    )
    history = HistoricalRecords()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["group", "workspace"], name="unique_workspace_auth_domain")]

    def __str__(self):
        """String method for WorkspaceAuthorizationDomains"""
        return "Auth domain {group} for {workspace}".format(group=self.group.name, workspace=self.workspace)


class GroupGroupMembership(TimeStampedModel):
    """A model to store which groups are in a group."""

    MEMBER = "MEMBER"
    ADMIN = "ADMIN"

    ROLE_CHOICES = [
        (MEMBER, "Member"),
        (ADMIN, "Admin"),
    ]

    parent_group = models.ForeignKey("ManagedGroup", on_delete=models.CASCADE, related_name="child_memberships")
    child_group = models.ForeignKey("ManagedGroup", on_delete=models.PROTECT, related_name="parent_memberships")
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=MEMBER)
    history = HistoricalRecords()

    class Meta:
        verbose_name = "group-group membership"

        constraints = [
            models.UniqueConstraint(
                fields=["parent_group", "child_group"],
                name="unique_group_group_membership",
            )
        ]

    def __str__(self):
        return "{child_group} as {role} in {parent_group}".format(
            child_group=self.child_group, role=self.role, parent_group=self.parent_group
        )

    def get_absolute_url(self):
        return reverse(
            "anvil_consortium_manager:managed_groups:member_groups:detail",
            kwargs={
                "parent_group_slug": self.parent_group.name,
                "child_group_slug": self.child_group.name,
            },
        )

    def clean(self):
        super().clean()
        # Don't allow the same group to be added as both a parent and a child.
        try:
            if self.parent_group.pk == self.child_group.pk:
                raise ValidationError("Cannot add a group to itself.")
        except ObjectDoesNotExist:
            # This should already be handled elsewhere - in other field clean or form methods.
            pass
        # Check if this would create a circular group relationship, eg if the child is a parent of itself.
        try:
            # Do we need to check both of these, or just one?
            children = self.child_group.get_all_children()
            parents = self.parent_group.get_all_parents()
            if self.parent_group in children or self.child_group in parents:
                raise ValidationError("Cannot add a circular group relationship.")
        except ObjectDoesNotExist:
            # This should already be handled elsewhere - in other field clean or form methods.
            pass

    def anvil_create(self):
        """Add the child group to the parent group on AnVIL."""
        AnVILAPIClient().add_user_to_group(self.parent_group.name, self.role.lower(), self.child_group.email)

    def anvil_delete(self):
        """Remove the child group from the parent on AnVIL"""
        AnVILAPIClient().remove_user_from_group(self.parent_group.name, self.role.lower(), self.child_group.email)


class GroupAccountMembership(TimeStampedModel):
    """A model to store which accounts are in a group."""

    MEMBER = "MEMBER"
    ADMIN = "ADMIN"

    ROLE_CHOICES = [
        (MEMBER, "Member"),
        (ADMIN, "Admin"),
    ]

    # When querying with as_of, HistoricForeignKey follows relationships at the same timepoint.
    # There is a (minor?) bug in the released v3.1.1 version:
    # https://github.com/jazzband/django-simple-history/issues/983
    account = HistoricForeignKey("Account", on_delete=models.CASCADE)
    group = models.ForeignKey("ManagedGroup", on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=MEMBER)
    history = HistoricalRecords()

    class Meta:
        verbose_name = "group-account membership"
        constraints = [models.UniqueConstraint(fields=["account", "group"], name="unique_group_account_membership")]

    def __str__(self):
        return "{account} as {role} in {group}".format(
            account=self.account,
            group=self.group,
            role=self.role,
        )

    def get_absolute_url(self):
        return reverse(
            "anvil_consortium_manager:managed_groups:member_accounts:detail",
            kwargs={"group_slug": self.group.name, "account_uuid": self.account.uuid},
        )

    def anvil_create(self):
        """Add the account to the group on AnVIL."""
        AnVILAPIClient().add_user_to_group(self.group.name, self.role.lower(), self.account.email)

    def anvil_delete(self):
        """Remove the account from the group on AnVIL"""
        AnVILAPIClient().remove_user_from_group(self.group.name, self.role.lower(), self.account.email)


class WorkspaceGroupSharing(TimeStampedModel):
    """A model to store which workspaces have been shared with which groups."""

    OWNER = "OWNER"
    """Constant indicating "OWNER" access."""

    WRITER = "WRITER"
    """Constant indicating "WRITER" access."""

    READER = "READER"
    """Constant indicating "READER" access."""

    ACCESS_CHOICES = [
        (OWNER, "Owner"),
        (WRITER, "Writer"),
        (READER, "Reader"),
    ]
    """Allowed choices for the ``access`` field."""

    group = models.ForeignKey(
        "ManagedGroup",
        on_delete=models.PROTECT,
        help_text="""ManagedGroup that has access to this Workspace.""",
    )
    workspace = models.ForeignKey(
        "Workspace",
        on_delete=models.CASCADE,
        help_text="""Workspace that the ManagedGroup has access to.""",
    )
    access = models.CharField(
        max_length=10,
        choices=ACCESS_CHOICES,
        default=READER,
        help_text="""Access level that this ManagedGroup has to this Workspace.
            A "Reader" can see data in the workspace.
            A "Writer" can add or remove data in the workspace.
            An "Owner" can share the workspace with others or delete the workspace.""",
    )
    can_compute = models.BooleanField(
        default=False,
        verbose_name="Allow compute in this workspace?",
        help_text="""Indicator of whether the group is able to perform compute in this workspace.
        "READERS" cannot be granted compute permission.""",
    )

    history = HistoricalRecords()
    """Historical records from django-simple-history."""

    class Meta:
        verbose_name_plural = "workspace group sharing"
        # NOTE - we intentionally have left the name of the constraint
        # as group_access instead of updating to group_sharing to get around
        # django bug: #31335 - when the fix for this is patched in we can update
        constraints = [models.UniqueConstraint(fields=["group", "workspace"], name="unique_workspace_group_access")]

    def __str__(self):
        """String method for this object.

        Returns:
            str: a string description of the object."""
        return "{group} with {access} to {workspace}".format(
            group=self.group,
            access=self.access,
            workspace=self.workspace,
        )

    def clean(self):
        """Perform model cleaning steps.

        This method checks that can_compute is not set to ``True`` for "READERS".
        """

        if self.access == self.READER and self.can_compute:
            raise ValidationError("READERs cannot be granted compute privileges.")
        if self.access == self.OWNER and not self.can_compute:
            raise ValidationError("OWNERs must be granted compute privileges.")

    def get_absolute_url(self):
        """Get the absolute url for this object.

        Returns:
            str: The absolute url for the object."""
        return reverse(
            "anvil_consortium_manager:workspaces:sharing:detail",
            kwargs={
                "billing_project_slug": self.workspace.billing_project.name,
                "workspace_slug": self.workspace.name,
                "group_slug": self.group.name,
            },
        )

    def anvil_create_or_update(self):
        """Create or update the access to ``workspace`` for the ``group`` on AnVIL.

        Raises:
            exceptions.AnVILGroupNotFound: The group that the workspace is being shared with does not exist on AnVIL.
        """
        acl_updates = [
            {
                "email": self.group.email,
                "accessLevel": self.access,
                "canShare": False,
                "canCompute": self.can_compute,
            }
        ]
        response = AnVILAPIClient().update_workspace_acl(
            self.workspace.billing_project.name, self.workspace.name, acl_updates
        )
        if len(response.json()["usersNotFound"]) > 0:
            raise exceptions.AnVILGroupNotFound("{} not found on AnVIL".format(self.group))

    def anvil_delete(self):
        """Remove the access to ``workspace`` for the ``group`` on AnVIL."""

        acl_updates = [
            {
                "email": self.group.email,
                "accessLevel": "NO ACCESS",
                "canShare": False,
                "canCompute": self.can_compute,
            }
        ]
        # It is ok if we try to remove access for a group that doesn't exist on AnVIL.
        AnVILAPIClient().update_workspace_acl(self.workspace.billing_project.name, self.workspace.name, acl_updates)
