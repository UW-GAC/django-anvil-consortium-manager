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

from . import anvil_audit, exceptions
from .adapters.workspace import workspace_adapter_registry
from .anvil_api import AnVILAPIClient, AnVILAPIError, AnVILAPIError404
from .tokens import account_verification_token


class AnVILProjectManagerAccess(models.Model):
    """A meta model used to define app level permissions"""

    EDIT_PERMISSION_CODENAME = "anvil_project_manager_edit"
    VIEW_PERMISSION_CODENAME = "anvil_project_manager_view"
    ACCOUNT_LINK_PERMISSION_CODENAME = "anvil_project_manager_account_link"

    class Meta:
        """Not a concrete model."""

        managed = False

        """Disable add, change, view and delete default model permissions"""
        default_permissions = ()

        permissions = [
            ("anvil_project_manager_edit", "AnVIL Project Manager Edit Permission"),
            ("anvil_project_manager_view", "AnVIL Project Manager View Permission"),
            (
                "anvil_project_manager_account_link",
                "AnVIL Project Manager Account Link Permission",
            ),
        ]


class BillingProject(TimeStampedModel):
    """A model to store information about AnVIL billing projects."""

    name = models.SlugField(
        max_length=64, unique=True, help_text="Name of the Billing Project on AnVIL."
    )
    has_app_as_user = models.BooleanField(
        help_text="Indicator of whether the app is a user in this BillingProject."
    )
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
            billing_project = cls(
                name=billing_project_name, has_app_as_user=True, **kwargs
            )
            billing_project.full_clean()
        else:
            # The billing project already exists in the database.
            raise exceptions.AnVILAlreadyImported(
                "BillingProject: " + billing_project_name
            )
        # I think we only care if this doesn't raise an exception.
        # That should mean that it is successful, and we don't care about any of the information returned.
        AnVILAPIClient().get_billing_project(billing_project_name)
        billing_project.save()
        return billing_project

    @classmethod
    def anvil_audit(cls):
        """Verify data in the app against AnVIL.

        Only billing projects with ``have_app_as_user=True`` are checked, because the AnVIL API does not
        differentiate between billing projects that don't exist and billing projects where the app is
        not a user.

        Returns:
            An instance of :class:`~anvil_consortium_manager.anvil_audit.BillingProjectAuditResults`.
        """
        # Check that all billing projects exist.
        audit_results = anvil_audit.BillingProjectAuditResults()
        for billing_project in cls.objects.filter(has_app_as_user=True).all():
            if not billing_project.anvil_exists():
                audit_results.add_error(
                    billing_project, audit_results.ERROR_NOT_IN_ANVIL
                )
            else:
                audit_results.add_verified(billing_project)
        return audit_results


class UserEmailEntry(TimeStampedModel, models.Model):
    """A model to store emails that users could link to their AnVIL account after verification."""

    uuid = models.UUIDField(default=uuid.uuid4)
    """UUID for use in urls."""

    email = models.EmailField()
    """The email entered by the user."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.CASCADE
    )
    """The user who created the record."""

    date_verification_email_sent = models.DateTimeField()
    """Most recent date that a verification email was sent."""

    date_verified = models.DateTimeField(null=True, blank=True)
    """The date that the email was verified by the user."""

    history = HistoricalRecords()
    """Django simple history."""

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["email", "user"], name="unique_user_email_entry"
            )
        ]
        verbose_name_plural = "user email entries"

    def __str__(self):
        """String method."""
        return "{email} for {user}".format(email=self.email, user=self.user)

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

    def save(self, *args, **kwargs):
        self.email = self.email.lower()
        return super().save(*args, **kwargs)

    def send_verification_email(self, domain):
        """Send a verification email to the email on record.

        Args:
            domain (str): The domain of the current site, used to create the link.
        """
        mail_subject = settings.ANVIL_ACCOUNT_LINK_EMAIL_SUBJECT
        url_subdirectory = "http://{domain}{url}".format(
            domain=domain,
            url=reverse(
                "anvil_consortium_manager:accounts:verify",
                args=[self.uuid, account_verification_token.make_token(self)],
            ),
        )
        message = render_to_string(
            "anvil_consortium_manager/account_verification_email.html",
            {
                "user": self.user,
                "verification_link": url_subdirectory,
            },
        )
        send_mail(mail_subject, message, None, [self.email], fail_silently=False)

    def send_notification_email(self):
        """Send notification email after account is verified if the email setting is set"""
        if (
            hasattr(settings, "ANVIL_ACCOUNT_VERIFY_NOTIFICATION_EMAIL")
            and settings.ANVIL_ACCOUNT_VERIFY_NOTIFICATION_EMAIL
            and not settings.ANVIL_ACCOUNT_VERIFY_NOTIFICATION_EMAIL.isspace()
        ):
            mail_subject = "User verified AnVIL account"
            message = render_to_string(
                "anvil_consortium_manager/account_notification_email.html",
                {
                    "email": self.email,
                    "user": self.user,
                },
            )
            send_mail(
                mail_subject,
                message,
                None,
                [settings.ANVIL_ACCOUNT_VERIFY_NOTIFICATION_EMAIL],
                fail_silently=False,
            )


class Account(TimeStampedModel, ActivatorModel):
    """A model to store information about AnVIL accounts."""

    ERROR_USER_WITHOUT_VERIFIED_EMAIL_ENTRY = (
        "Accounts with a user must have a verified_email_entry."
    )
    ERROR_VERIFIED_EMAIL_ENTRY_WITHOUT_USER = (
        "Accounts with a verified_email_entry must have a user."
    )
    ERROR_UNVERIFIED_VERIFIED_EMAIL_ENTRY = (
        "verified_email_entry must have date_verified."
    )
    ERROR_MISMATCHED_USER = "Account.user and verified_email_entry.user do not match."
    ERROR_MISMATCHED_EMAIL = (
        "Account.email and verified_email_entry.email do not match."
    )

    # TODO: Consider using CIEmailField if using postgres.
    email = models.EmailField(
        unique=True, help_text="""Email associated with this account on AnVIL."""
    )
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
    is_service_account = models.BooleanField(
        help_text="Indicator of whether this Account is a service account."
    )
    verified_email_entry = models.OneToOneField(
        UserEmailEntry,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="verified_account",
        help_text="""The UserEmailEntry object used to verify the email,
        if the account was created by a user linking their email.""",
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
            raise ValidationError(
                {"verified_email_entry": self.ERROR_USER_WITHOUT_VERIFIED_EMAIL_ENTRY}
            )
        elif self.verified_email_entry and not self.user:
            raise ValidationError(
                {"user": self.ERROR_VERIFIED_EMAIL_ENTRY_WITHOUT_USER}
            )
        elif self.verified_email_entry and self.user:
            # Make sure the email entry is actually verified.
            if not self.verified_email_entry.date_verified:
                raise ValidationError(
                    {"verified_email_entry": self.ERROR_UNVERIFIED_VERIFIED_EMAIL_ENTRY}
                )
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
        return reverse(
            "anvil_consortium_manager:accounts:detail", kwargs={"uuid": self.uuid}
        )

    def deactivate(self):
        """Set status to deactivated and remove from any AnVIL groups."""
        self.anvil_remove_from_groups()
        self.deactivate_date = timezone.now()
        self.status = self.INACTIVE_STATUS
        self.save()

    def reactivate(self):
        """Set status to reactivated and add to any AnVIL groups."""
        self.status = self.ACTIVE_STATUS
        self.save()
        group_memberships = self.groupaccountmembership_set.all()
        for membership in group_memberships:
            membership.anvil_create()

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
        """Remove this account from all groups on AnVIL."""
        group_memberships = self.groupaccountmembership_set.all()
        for membership in group_memberships:
            membership.anvil_delete()

    @classmethod
    def anvil_audit(cls):
        """Verify data in the app against AnVIL.

        Only billing projects with have_app_as_user=True are checked, because the AnVIL API does not
        differentiate between billing projects that don't exist and billing projects where the app is
        not a user.

        Returns:
            An instance of :class:`~anvil_consortium_manager.anvil_audit.AccountAuditResults`
        """
        # Check that all accounts exist on AnVIL.
        audit_results = anvil_audit.AccountAuditResults()
        for account in cls.objects.filter(status=cls.ACTIVE_STATUS).all():
            if not account.anvil_exists():
                audit_results.add_error(account, audit_results.ERROR_NOT_IN_ANVIL)
            else:
                audit_results.add_verified(account)
        return audit_results

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


class ManagedGroup(TimeStampedModel):
    """A model to store information about AnVIL Managed Groups."""

    name = models.SlugField(
        max_length=64, unique=True, help_text="Name of the group on AnVIL."
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
        return reverse(
            "anvil_consortium_manager:managed_groups:detail", kwargs={"slug": self.name}
        )

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
        group = cls(
            name=group_name,
            is_managed_by_app=False,
            email=group_name.lower() + "@firecloud.org",
            **kwargs
        )
        # Make sure we don't already have it in the database.
        group.full_clean()
        # Note that we have to be a member of the group to import it.
        response = AnVILAPIClient().get_groups()
        json = response.json()
        # Use a generator expression to extract details about the requested group.
        try:
            group_details = next(
                group for group in json if group["groupName"] == group_name
            )
        except StopIteration:
            raise exceptions.AnVILNotGroupMemberError
        # Check if we're an admin.
        if group_details["role"].lower() == "admin":
            group.is_managed_by_app = True
        # Set the email using the json response.
        group.email = group_details["groupEmail"].lower()
        group.save()
        return group

    def anvil_audit_membership(self):
        """Audit the membership for a single group against AnVIL.

        Returns:
            An instance of :class:`~anvil_consortium_manager.anvil_audit.ManagedGroupMembershipAuditResults`.
        """
        api_client = AnVILAPIClient()
        audit_results = anvil_audit.ManagedGroupMembershipAuditResults()
        response = api_client.get_group_members(self.name)
        # Convert to case-insensitive emails.
        members_in_anvil = [x.lower() for x in response.json()]
        response = api_client.get_group_admins(self.name)
        # Convert to case-insensitive emails.
        admins_in_anvil = [x.lower() for x in response.json()]
        # Remove the service account as admin.
        admins_in_anvil.remove(
            api_client.auth_session.credentials.service_account_email.lower()
        )
        # Sometimes the service account is also listed as a member. Remove that too.
        try:
            members_in_anvil.remove(
                api_client.auth_session.credentials.service_account_email.lower()
            )
        except ValueError:
            # Not listed as a member -- this is ok.
            pass
        # Check group-account membership.
        for membership in self.groupaccountmembership_set.all():
            if membership.role == GroupAccountMembership.ADMIN:
                try:
                    admins_in_anvil.remove(membership.account.email.lower())
                except ValueError:
                    # This email is not in the list of members.
                    audit_results.add_error(
                        membership, audit_results.ERROR_ACCOUNT_ADMIN_NOT_IN_ANVIL
                    )
                else:
                    audit_results.add_verified(membership)
            elif membership.role == GroupAccountMembership.MEMBER:
                try:
                    members_in_anvil.remove(membership.account.email.lower())
                except ValueError:
                    # This email is not in the list of members.
                    audit_results.add_error(
                        membership, audit_results.ERROR_ACCOUNT_MEMBER_NOT_IN_ANVIL
                    )
                else:
                    audit_results.add_verified(membership)

        # Check group-group membership.
        for membership in self.child_memberships.all():
            if membership.role == GroupGroupMembership.ADMIN:
                try:
                    admins_in_anvil.remove(membership.child_group.email.lower())
                except ValueError:
                    # This email is not in the list of members.
                    audit_results.add_error(
                        membership, audit_results.ERROR_GROUP_ADMIN_NOT_IN_ANVIL
                    )
                else:
                    audit_results.add_verified(membership)
            elif membership.role == GroupGroupMembership.MEMBER:
                try:
                    members_in_anvil.remove(membership.child_group.email.lower())
                except ValueError:
                    # This email is not in the list of members.
                    audit_results.add_error(
                        membership, audit_results.ERROR_GROUP_MEMBER_NOT_IN_ANVIL
                    )
                else:
                    audit_results.add_verified(membership)

        # Add any admin that the app doesn't know about.
        for member in admins_in_anvil:
            audit_results.add_not_in_app(
                "{}: {}".format(GroupAccountMembership.ADMIN, member)
            )
        # Add any members that the app doesn't know about.
        for member in members_in_anvil:
            audit_results.add_not_in_app(
                "{}: {}".format(GroupAccountMembership.MEMBER, member)
            )

        return audit_results

    @classmethod
    def anvil_audit(cls):
        """Verify data in the app against AnVIL.

        Returns:
            An instance of :class:`~anvil_consortium_manager.anvil_audit.ManagedGroupAuditResults`.
        """
        audit_results = anvil_audit.ManagedGroupAuditResults()
        # Check the list of groups.
        response = AnVILAPIClient().get_groups()
        # Change from list of group dictionaries to dictionary of roles. That way we can handle being both
        # a member and an admin of a group.
        groups_on_anvil = {}
        for group_details in response.json():
            group_name = group_details["groupName"]
            role = group_details["role"].lower()
            try:
                groups_on_anvil[group_name] = groups_on_anvil[group_name] + [role]
            except KeyError:
                groups_on_anvil[group_name] = [role]
        # Audit groups that exist in the app.
        for group in cls.objects.all():
            try:
                group_roles = groups_on_anvil.pop(group.name)
            except KeyError:
                # Check if the group actually does exist but we're not a member of it.
                try:
                    # If this returns a 404 error, then the group actually does not exist.
                    response = AnVILAPIClient().get_group_email(group.name)
                    if group.is_managed_by_app:
                        audit_results.add_error(
                            group, audit_results.ERROR_DIFFERENT_ROLE
                        )

                except AnVILAPIError404:
                    audit_results.add_error(group, audit_results.ERROR_NOT_IN_ANVIL)
                    # Perhaps we want to add has_app_as_member as a field and check that.
            else:
                # Check role.
                if group.is_managed_by_app:
                    if "admin" not in group_roles:
                        audit_results.add_error(
                            group, audit_results.ERROR_DIFFERENT_ROLE
                        )
                    else:
                        if not group.anvil_audit_membership().ok():
                            audit_results.add_error(
                                group, audit_results.ERROR_GROUP_MEMBERSHIP
                            )
                elif not group.is_managed_by_app and "admin" in group_roles:
                    audit_results.add_error(group, audit_results.ERROR_DIFFERENT_ROLE)

            try:
                audit_results.add_verified(group)
            except ValueError:
                # ValueError is raised when the group already has errors reported, so
                # ignore this exception -- we don't want to add it to the verified list.
                pass
        # Check for groups that exist on AnVIL but not the app.
        for group_name in groups_on_anvil:
            audit_results.add_not_in_app(group_name)
        return audit_results

    def is_in_authorization_domain(self, workspace):
        """Check if this group (or a group that it is part of) is in the auth domain of a workspace."""
        return workspace.is_in_authorization_domain(self)

    def is_shared(self, workspace):
        """Check if a workspace is shared with this group (or a group that it is part of)."""
        return workspace.is_shared(self)

    def has_access(self, workspace):
        """Check if this group has access to a workspace.

        Both criteria need to be met for a group to have access to a workspace:
        1. The workspace must be shared with the group (or a group that it is in).
        2. The group (or a group that it is in) must be in all auth domains for the workspace.
        """
        return workspace.has_access(self)


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
        max_length=64,
        help_text="Name of the workspace on AnVIL, not including billing project name.",
    )
    # This makes it possible to easily select the authorization domains in the WorkspaceCreateForm.
    # However, it does not create a record in django-simple-history for creating the many-to-many field.
    authorization_domains = models.ManyToManyField(
        "ManagedGroup",
        through="WorkspaceAuthorizationDomain",
        blank=True,
        help_text="Authorization domain(s) for this workspace.",
    )
    note = models.TextField(blank=True, help_text="Additional notes.")
    # If this doesn't work easily, we could switch to using generic relationships.
    workspace_type = models.CharField(
        max_length=255, help_text="""Workspace data type as indicated by an adapter."""
    )
    is_locked = models.BooleanField(
        help_text="Indicator of whether the workspace is locked or not.",
        default=False,
    )

    history = HistoricalRecords()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["billing_project", "name"], name="unique_workspace"
            )
        ]

    def clean_fields(self, exclude=None):
        super().clean_fields(exclude=exclude)
        # Check that workspace type is a registered adapter type.
        if not exclude or "workspace_type" not in exclude:
            registered_adapters = workspace_adapter_registry.get_registered_adapters()
            if self.workspace_type not in registered_adapters:
                raise ValidationError(
                    {
                        "workspace_type": "Value ``workspace_type`` is not a registered adapter type."
                    }
                )

    def __str__(self):
        return "{billing_project}/{name}".format(
            billing_project=self.billing_project, name=self.name
        )

    def get_absolute_url(self):
        return reverse(
            "anvil_consortium_manager:workspaces:detail",
            kwargs={
                "billing_project_slug": self.billing_project.name,
                "workspace_slug": self.name,
            },
        )

    def get_full_name(self):
        return "{billing_project}/{name}".format(
            billing_project=self.billing_project, name=self.name
        )

    def get_anvil_url(self):
        """Return the URL of the workspace on AnVIL."""
        return "https://anvil.terra.bio/#workspaces/{billing_project}/{group}".format(
            billing_project=self.billing_project.name, group=self.name
        )

    def is_in_authorization_domain(self, group):
        """Check if a group (or a group that it is part of) is in the auth domain of this workspace."""
        in_auth_domain = True
        for auth_domain in self.authorization_domains.all():
            in_auth_domain = (in_auth_domain) and (
                group in auth_domain.get_all_children()
            )
        return in_auth_domain

    def is_shared(self, group):
        """Check if this workspace is shared with a group (or a group that it is part of)."""
        parents = group.get_all_parents()
        is_shared = self.workspacegroupsharing_set.filter(
            models.Q(group=group) | models.Q(group__in=parents)
        ).exists()
        return is_shared

    def has_access(self, group):
        """Check if a group has access to a workspace.

        Both criteria need to be met for a group to have access to a workspace:
        1. The workspace must be shared with the group (or a group that it is in).
        2. The group (or a group that it is in) must be in all auth domains for the workspace.
        """
        return self.is_shared(group) and self.is_in_authorization_domain(group)

    def anvil_exists(self):
        """Check if the workspace exists on AnVIL."""
        try:
            response = AnVILAPIClient().get_workspace(
                self.billing_project.name, self.name
            )
        except AnVILAPIError404:
            return False
        return response.status_code == 200

    def anvil_create(self):
        """Create the workspace on AnVIL."""
        auth_domains = list(
            self.authorization_domains.all().values_list("name", flat=True)
        )
        AnVILAPIClient().create_workspace(
            self.billing_project.name, self.name, authorization_domains=auth_domains
        )

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
    def anvil_import(
        cls, billing_project_name, workspace_name, workspace_type, note=""
    ):
        """Create a new instance for a workspace that already exists on AnVIL.

        Methods calling this should handle AnVIL API exceptions appropriately.
        """
        # Check if the workspace already exists in the database.
        try:
            cls.objects.get(
                billing_project__name=billing_project_name, name=workspace_name
            )
            raise exceptions.AnVILAlreadyImported(
                billing_project_name + "/" + workspace_name
            )
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
                    billing_project = BillingProject.objects.get(
                        name=billing_project_name
                    )
                    billing_project_exists = True
                except BillingProject.DoesNotExist:
                    temporary_billing_project = BillingProject(
                        name=billing_project_name, has_app_as_user=False
                    )
                    temporary_billing_project.clean_fields()
                    billing_project_exists = False

                # Do not set the Billing yet, since we might be importing it or creating it later.
                # This is only to validate the other fields.
                workspace = cls(
                    name=workspace_name, workspace_type=workspace_type, note=note
                )
                workspace.clean_fields(exclude="billing_project")
                # At this point, they should be valid objects.

                # Make sure we actually have access to the workspace.
                response = AnVILAPIClient().get_workspace(
                    billing_project_name, workspace_name
                )
                workspace_json = response.json()

                # Make sure that we are owners of the workspace.
                if workspace_json["accessLevel"] != "OWNER":
                    raise exceptions.AnVILNotWorkspaceOwnerError(
                        billing_project_name + "/" + workspace_name
                    )

                # Now we can proceed with saving the objects.

                # Import the billing project from AnVIL if it doesn't already exist.
                if not billing_project_exists:
                    try:
                        billing_project = BillingProject.anvil_import(
                            billing_project_name
                        )
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
                auth_domains = [
                    ad["membersGroupName"]
                    for ad in workspace_json["workspace"]["authorizationDomain"]
                ]

                # We don't need to check if we are members of the auth domains, because if we weren't we wouldn't be
                # able to see the workspace.
                for auth_domain in auth_domains:
                    # Either get the group from the Django database or import it.
                    try:
                        group = ManagedGroup.objects.get(name=auth_domain)
                    except ManagedGroup.DoesNotExist:
                        group = ManagedGroup.anvil_import(auth_domain)
                    # Add it as an authorization domain for this workspace.
                    WorkspaceAuthorizationDomain.objects.create(
                        workspace=workspace, group=group
                    )

                # Get the list of groups that it is shared with and create records for them.
                response = AnVILAPIClient().get_workspace_acl(
                    workspace.billing_project.name, workspace.name
                )
                # import ipdb; ipdb.set_trace()
                acl = response.json()["acl"]
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

    def anvil_audit_sharing(self):
        """Audit the sharing for a single Workspace against AnVIL.

        Returns:
            An instance of :class:`~anvil_consortium_manager.anvil_audit.WorkspaceGroupSharingAuditResults`.
        """
        api_client = AnVILAPIClient()
        audit_results = anvil_audit.WorkspaceGroupSharingAuditResults()
        response = api_client.get_workspace_acl(self.billing_project.name, self.name)
        acl_in_anvil = {k.lower(): v for k, v in response.json()["acl"].items()}
        # Remove the service account.
        try:
            acl_in_anvil.pop(
                api_client.auth_session.credentials.service_account_email.lower()
            )
        except KeyError:
            # In some cases, the workspace is shared with a group we are part of instead of directly with us.
            pass
        for access in self.workspacegroupsharing_set.all():
            try:
                access_details = acl_in_anvil.pop(access.group.email.lower())
            except KeyError:
                audit_results.add_error(access, audit_results.ERROR_NOT_SHARED_IN_ANVIL)
            else:
                # Check access level.
                if access.access != access_details["accessLevel"]:
                    audit_results.add_error(
                        access, audit_results.ERROR_DIFFERENT_ACCESS
                    )
                # Check can_compute value.
                if access.can_compute != access_details["canCompute"]:
                    audit_results.add_error(
                        access, audit_results.ERROR_DIFFERENT_CAN_COMPUTE
                    )
                # Check can_share value -- the app never grants this, so it should always be false.
                # Can share should be True for owners and false for others.
                can_share = access.access == "OWNER"
                if access_details["canShare"] != can_share:
                    audit_results.add_error(
                        access, audit_results.ERROR_DIFFERENT_CAN_SHARE
                    )

            try:
                audit_results.add_verified(access)
            except ValueError:
                # This means that the access instance already has errors reported, so do nothing.
                pass

        # Add any access that the app doesn't know about.
        for key in acl_in_anvil:
            audit_results.add_not_in_app(
                "{}: {}".format(acl_in_anvil[key]["accessLevel"], key)
            )

        return audit_results

    @classmethod
    def anvil_audit(cls):
        """Verify data in the app against AnVIL.

        This method checks if any workspaces where the service account is an owner exist in AnVIL.

        Returns:
            An instance of :class:`~anvil_consortium_manager.anvil_audit.WorkspaceAuditResults`.
        """
        audit_results = anvil_audit.WorkspaceAuditResults()
        # Check the list of workspaces.
        response = AnVILAPIClient().list_workspaces(
            fields="workspace.namespace,workspace.name,workspace.authorizationDomain,workspace.isLocked,accessLevel"
        )
        workspaces_on_anvil = response.json()
        for workspace in cls.objects.all():
            try:
                i = next(
                    idx
                    for idx, x in enumerate(workspaces_on_anvil)
                    if (
                        x["workspace"]["name"] == workspace.name
                        and x["workspace"]["namespace"]
                        == workspace.billing_project.name
                    )
                )
            except StopIteration:
                audit_results.add_error(workspace, audit_results.ERROR_NOT_IN_ANVIL)
            else:
                # Check role.
                workspace_details = workspaces_on_anvil.pop(i)
                if workspace_details["accessLevel"] != "OWNER":
                    audit_results.add_error(
                        workspace, audit_results.ERROR_NOT_OWNER_ON_ANVIL
                    )
                elif not workspace.anvil_audit_sharing().ok():
                    # Since we're the owner, check workspace access.
                    audit_results.add_error(
                        workspace, audit_results.ERROR_WORKSPACE_SHARING
                    )
                # Check auth domains.
                auth_domains_on_anvil = [
                    x["membersGroupName"]
                    for x in workspace_details["workspace"]["authorizationDomain"]
                ]
                auth_domains_in_app = workspace.authorization_domains.all().values_list(
                    "name", flat=True
                )
                if set(auth_domains_on_anvil) != set(auth_domains_in_app):
                    audit_results.add_error(
                        workspace, audit_results.ERROR_DIFFERENT_AUTH_DOMAINS
                    )
                # Check lock status.
                if workspace.is_locked != workspace_details["workspace"]["isLocked"]:
                    audit_results.add_error(
                        workspace, audit_results.ERROR_DIFFERENT_LOCK
                    )
                try:
                    audit_results.add_verified(workspace)
                except ValueError:
                    # ValueError is raised when the workspace already has errors reported, so
                    # ignore this exception -- we don't want to add it to the verified list.
                    pass

        # Check for remaining workspaces on AnVIL where we are OWNER.
        not_in_app = [
            "{}/{}".format(x["workspace"]["namespace"], x["workspace"]["name"])
            for x in workspaces_on_anvil
            if x["accessLevel"] == "OWNER"
        ]
        for workspace_name in not_in_app:
            audit_results.add_not_in_app(workspace_name)
        return audit_results


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
        constraints = [
            models.UniqueConstraint(
                fields=["group", "workspace"], name="unique_workspace_auth_domain"
            )
        ]

    def __str__(self):
        """String method for WorkspaceAuthorizationDomains"""
        return "Auth domain {group} for {workspace}".format(
            group=self.group.name, workspace=self.workspace
        )


class GroupGroupMembership(TimeStampedModel):
    """A model to store which groups are in a group."""

    MEMBER = "MEMBER"
    ADMIN = "ADMIN"

    ROLE_CHOICES = [
        (MEMBER, "Member"),
        (ADMIN, "Admin"),
    ]

    parent_group = models.ForeignKey(
        "ManagedGroup", on_delete=models.CASCADE, related_name="child_memberships"
    )
    child_group = models.ForeignKey(
        "ManagedGroup", on_delete=models.PROTECT, related_name="parent_memberships"
    )
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
        AnVILAPIClient().add_user_to_group(
            self.parent_group.name, self.role.lower(), self.child_group.email
        )

    def anvil_delete(self):
        """Remove the child group from the parent on AnVIL"""
        AnVILAPIClient().remove_user_from_group(
            self.parent_group.name, self.role.lower(), self.child_group.email
        )


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
        constraints = [
            models.UniqueConstraint(
                fields=["account", "group"], name="unique_group_account_membership"
            )
        ]

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
        AnVILAPIClient().add_user_to_group(
            self.group.name, self.role.lower(), self.account.email
        )

    def anvil_delete(self):
        """Remove the account from the group on AnVIL"""
        AnVILAPIClient().remove_user_from_group(
            self.group.name, self.role.lower(), self.account.email
        )


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
        constraints = [
            models.UniqueConstraint(
                fields=["group", "workspace"], name="unique_workspace_group_access"
            )
        ]

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
            raise exceptions.AnVILGroupNotFound(
                "{} not found on AnVIL".format(self.group)
            )

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
        AnVILAPIClient().update_workspace_acl(
            self.workspace.billing_project.name, self.workspace.name, acl_updates
        )
