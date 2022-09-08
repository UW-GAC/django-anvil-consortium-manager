import uuid

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models, transaction
from django.urls import reverse
from django.utils import timezone
from django_extensions.db.models import ActivatorModel, TimeStampedModel
from simple_history.models import HistoricalRecords, HistoricForeignKey

from . import exceptions
from .anvil_api import AnVILAPIClient, AnVILAPIError404


class AnVILProjectManagerAccess(models.Model):
    """A meta model used to define app level permissions"""

    EDIT_PERMISSION_CODENAME = "anvil_project_manager_edit"
    VIEW_PERMISSION_CODENAME = "anvil_project_manager_view"

    class Meta:
        """Not a concrete model."""

        managed = False

        """Disable add, change, view and delete default model permissions"""
        default_permissions = ()

        permissions = [
            ("anvil_project_manager_edit", "AnVIL Project Manager Edit Permission"),
            ("anvil_project_manager_view", "AnVIL Project Manager View Permission"),
        ]


class BillingProject(TimeStampedModel):
    """A model to store information about AnVIL billing projects."""

    name = models.SlugField(max_length=64, unique=True)
    has_app_as_user = models.BooleanField()
    history = HistoricalRecords()

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse(
            "anvil_consortium_manager:billing_projects:detail", kwargs={"pk": self.pk}
        )

    def anvil_exists(self):
        try:
            response = AnVILAPIClient().get_billing_project(self.name)
        except AnVILAPIError404:
            # The billing project was not found on AnVIL.
            return False
        return response.status_code == 200

    @classmethod
    def anvil_import(cls, billing_project_name):
        """BiillingProject class method to import an existing billing project from AnVIL."""
        try:
            billing_project = cls.objects.get(name=billing_project_name)
        except cls.DoesNotExist:
            billing_project = cls(name=billing_project_name, has_app_as_user=True)
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

    def __str__(self):
        """String method."""
        return "{email} for {user}".format(email=self.email, user=self.user)

    def anvil_account_exists(self):
        """Check if this account exists on AnVIL."""
        try:
            AnVILAPIClient().get_proxy_group(self.email)
        except AnVILAPIError404:
            return False
        return True

    def save(self, *args, **kwargs):
        self.email = self.email.lower()
        return super().save(*args, **kwargs)


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
    email = models.EmailField(unique=True)
    # Use on_delete=PROTECT here because additional things need to happen when an account is deleted,
    # and we're not sure what that should be. Deactivate the account or and/or remove it from groups?
    # I think it's unlikely we will be deleting users frequently, and we can revisit this if necessary.
    # So table it for later.
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT
    )
    is_service_account = models.BooleanField()

    verified_email_entry = models.OneToOneField(
        UserEmailEntry,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="verified_account",
    )
    """The UserEmailEntry object used to verify the email, if the account was created by a user linking their email."""

    history = HistoricalRecords()

    def __str__(self):
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
        self.email = self.email.lower()
        return super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse(
            "anvil_consortium_manager:accounts:detail", kwargs={"pk": self.pk}
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
        """Check if this account exists on AnVIL."""
        try:
            AnVILAPIClient().get_proxy_group(self.email)
        except AnVILAPIError404:
            return False
        return True

    def anvil_remove_from_groups(self):
        """From user from all groups on AnVIL."""
        group_memberships = self.groupaccountmembership_set.all()
        for membership in group_memberships:
            membership.anvil_delete()


class ManagedGroup(TimeStampedModel):
    """A model to store information about AnVIL Managed Groups."""

    name = models.SlugField(max_length=64, unique=True)
    is_managed_by_app = models.BooleanField(default=True)
    history = HistoricalRecords()

    def __str__(self):
        return "{name}".format(name=self.name)

    def get_absolute_url(self):
        return reverse(
            "anvil_consortium_manager:managed_groups:detail", kwargs={"pk": self.pk}
        )

    def get_email(self):
        # Email suffix is hardcoded by Terra, I think.
        return self.name + "@firecloud.org"

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

    def anvil_exists(self):
        """Check if the group exists on AnVIL."""
        try:
            response = AnVILAPIClient().get_group(self.name)
        except AnVILAPIError404:
            # The group was not found on AnVIL.
            return False
        return response.status_code == 200

    def anvil_create(self):
        """Creates the group on AnVIL."""
        AnVILAPIClient().create_group(self.name)

    def anvil_delete(self):
        """Deletes the group on AnVIL."""
        # Try to delete the group.
        AnVILAPIClient().delete_group(self.name)
        # The API for deleting groups is buggy, so verify that it was actually deleted.
        try:
            AnVILAPIClient().get_group(self.name)
        except AnVILAPIError404:
            # The group was actually deleted, as requested.
            pass
        else:
            # No exception was raised, so the group still exists. Raise a specific exception for this.
            raise exceptions.AnVILGroupDeletionError(self.name)

    @classmethod
    def anvil_import(cls, group_name):
        """Import an existing group from AnVIL."""
        # Create the group but don't save it yet.
        # Assume that it's not managed by the app until we figure out that it is.
        group = cls(name=group_name, is_managed_by_app=False)
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
        if group_details["role"] == "Admin":
            group.is_managed_by_app = True
        group.save()
        return group


class Workspace(TimeStampedModel):
    """A model to store information about AnVIL workspaces."""

    # NB: In the APIs some documentation, this is also referred to as "namespace".
    # In other places, it is "billing project".
    # For internal consistency, call it "billing project" here.
    billing_project = models.ForeignKey("BillingProject", on_delete=models.PROTECT)
    name = models.SlugField(max_length=64)
    # This makes it possible to easily select the authorization domains in the WorkspaceCreateForm.
    # However, it does not create a record in django-simple-history for creating the many-to-many field.
    authorization_domains = models.ManyToManyField(
        "ManagedGroup", through="WorkspaceAuthorizationDomain", blank=True
    )
    history = HistoricalRecords()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["billing_project", "name"], name="unique_workspace"
            )
        ]

    def clean(self):
        super().clean()
        # Check for the same case insensitive name in the same billing group.
        try:
            Workspace.objects.get(
                billing_project=self.billing_project, name__iexact=self.name
            )
        except ObjectDoesNotExist:
            # No workspace with the same billing project and case-insensitive name exists.
            pass
        else:
            # The workspace already exists - raise a Validation error.
            raise ValidationError(
                "Workspace with this Billing Project and Name already exists."
            )

    def __str__(self):
        return "{billing_project}/{name}".format(
            billing_project=self.billing_project, name=self.name
        )

    def get_absolute_url(self):
        return reverse(
            "anvil_consortium_manager:workspaces:detail", kwargs={"pk": self.pk}
        )

    def get_full_name(self):
        return "{billing_project}/{name}".format(
            billing_project=self.billing_project, name=self.name
        )

    def get_anvil_url(self):
        """Return the URL of the workspace on AnVIL."""
        return "https://app.terra.bio/#workspaces/{billing_project}/{group}".format(
            billing_project=self.billing_project.name, group=self.name
        )

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

    @classmethod
    def anvil_import(cls, billing_project_name, workspace_name):
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
                workspace = cls(name=workspace_name)
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
                        # We are not users, but we want a record of it anyway.
                        # We may want to modify BillingProject.anvil_import to throw a better exception here.
                        billing_project = BillingProject(
                            name=billing_project_name, has_app_as_user=False
                        )
                        billing_project.full_clean()
                        billing_project.save()

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
        except Exception:
            # If it fails for any reason we haven't already handled, we don't want the transaction to happen.
            raise

        return workspace


class WorkspaceAuthorizationDomain(TimeStampedModel):
    """Through table for the Workspace authorization_domains field."""

    group = models.ForeignKey(ManagedGroup, on_delete=models.PROTECT)
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE)
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
            "anvil_consortium_manager:group_group_membership:detail",
            kwargs={"pk": self.pk},
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
            self.parent_group.name, self.role, self.child_group.get_email()
        )

    def anvil_delete(self):
        """Remove the child group from the parent on AnVIL"""
        AnVILAPIClient().remove_user_from_group(
            self.parent_group.name, self.role, self.child_group.get_email()
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
            "anvil_consortium_manager:group_account_membership:detail",
            kwargs={"pk": self.pk},
        )

    def anvil_create(self):
        """Add the account to the group on AnVIL."""
        AnVILAPIClient().add_user_to_group(
            self.group.name, self.role, self.account.email
        )

    def anvil_delete(self):
        """Remove the account from the group on AnVIL"""
        AnVILAPIClient().remove_user_from_group(
            self.group.name, self.role, self.account.email
        )


class WorkspaceGroupAccess(TimeStampedModel):
    """A model to store which groups have access to a workspace."""

    OWNER = "OWNER"
    WRITER = "WRITER"
    READER = "READER"

    ACCESS_CHOICES = [
        (OWNER, "Owner"),
        (WRITER, "Writer"),
        (READER, "Reader"),
    ]

    group = models.ForeignKey("ManagedGroup", on_delete=models.PROTECT)
    workspace = models.ForeignKey("Workspace", on_delete=models.CASCADE)
    access = models.CharField(max_length=10, choices=ACCESS_CHOICES, default=READER)
    history = HistoricalRecords()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["group", "workspace"], name="unique_workspace_group_access"
            )
        ]

    def __str__(self):
        return "{group} with {access} to {workspace}".format(
            group=self.group,
            access=self.access,
            workspace=self.workspace,
        )

    def get_absolute_url(self):
        return reverse(
            "anvil_consortium_manager:workspace_group_access:detail",
            kwargs={"pk": self.pk},
        )

    def anvil_create_or_update(self):
        acl_updates = [
            {
                "email": self.group.get_email(),
                "accessLevel": self.access,
                "canShare": False,
                "canCompute": False,
            }
        ]
        AnVILAPIClient().update_workspace_acl(
            self.workspace.billing_project.name, self.workspace.name, acl_updates
        )

    def anvil_delete(self):
        acl_updates = [
            {
                "email": self.group.get_email(),
                "accessLevel": "NO ACCESS",
                "canShare": False,
                "canCompute": False,
            }
        ]
        AnVILAPIClient().update_workspace_acl(
            self.workspace.billing_project.name, self.workspace.name, acl_updates
        )
