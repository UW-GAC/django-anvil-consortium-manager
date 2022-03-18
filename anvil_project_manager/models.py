from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models, transaction
from django.urls import reverse

from . import exceptions
from .anvil_api import AnVILAPIClient, AnVILAPIError404


def validate_billing_project_name(value):
    """Custom validator for unique case-insensitive emails. This primarily provides a nice message on a form."""
    if BillingProject.objects.filter(name__iexact=value).exists():
        raise ValidationError("Billing Project with this Name already exists.")
    return value


class BillingProject(models.Model):
    """A model to store information about AnVIL billing projects."""

    name = models.SlugField(
        max_length=64, unique=True, validators=[validate_billing_project_name]
    )
    has_app_as_user = models.BooleanField()

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse(
            "anvil_project_manager:billing_projects:detail", kwargs={"pk": self.pk}
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


def validate_account_email(value):
    """Custom validator for unique case-insensitive emails. This primarily provides a nice message on a form."""
    if Account.objects.filter(email__iexact=value).exists():
        raise ValidationError("Account with this Email already exists.")
    return value


class Account(models.Model):
    """A model to store information about AnVIL accounts."""

    # TODO: Consider using CIEmailField if using postgres.
    email = models.EmailField(unique=True, validators=[validate_account_email])
    is_service_account = models.BooleanField()

    def __str__(self):
        return "{email}".format(email=self.email)

    def save(self, *args, **kwargs):
        self.email = self.email.lower()
        return super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("anvil_project_manager:accounts:detail", kwargs={"pk": self.pk})

    def anvil_exists(self):
        """Check if this account exists on AnVIL."""
        try:
            AnVILAPIClient().get_proxy_group(self.email)
        except AnVILAPIError404:
            return False
        return True


def validate_group_name(value):
    """Custom validator for unique case-insensitive names. This primarily provides a nice message on a form."""
    if Group.objects.filter(name__iexact=value).exists():
        raise ValidationError("Group with this Name already exists.")
    return value


class Group(models.Model):
    """A model to store information about AnVIL groups."""

    name = models.SlugField(
        max_length=64, unique=True, validators=[validate_group_name]
    )
    is_managed_by_app = models.BooleanField(default=True)

    def __str__(self):
        return "{name}".format(name=self.name)

    def get_absolute_url(self):
        return reverse("anvil_project_manager:groups:detail", kwargs={"pk": self.pk})

    def get_email(self):
        # Email suffix is hardcoded by Terra, I think.
        return self.name + "@firecloud.org"

    def get_direct_parents(self):
        """Return a queryset of the direct parents of this group. Does not include grandparents."""
        return Group.objects.filter(child_memberships__child_group=self)

    def get_direct_children(self):
        """Return a queryset of the direct children of this group. Does not include grandchildren."""
        return Group.objects.filter(parent_memberships__parent_group=self)

    def get_all_parents(self):
        """Return a queryset of all direct and indirect parents of this group. Includes all grandparents.

        Not optimized.
        """
        these_parents = self.get_direct_parents()
        parents = these_parents
        for parent in these_parents:
            parents = parents.union(parent.get_all_parents())
        return parents

    def get_all_children(self):
        """Return a queryset of all direct and indirect children of this group. Includes all childrenparents.

        Not optimized.
        """
        these_children = self.get_direct_children()
        print(these_children)
        children = these_children
        for child in these_children:
            children = children.union(child.get_all_children())
        return children

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
        AnVILAPIClient().delete_group(self.name)

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


class Workspace(models.Model):
    """A model to store information about AnVIL workspaces."""

    # NB: In the APIs some documentation, this is also referred to as "namespace".
    # In other places, it is "billing project".
    # For internal consistency, call it "billing project" here.
    billing_project = models.ForeignKey("BillingProject", on_delete=models.PROTECT)
    name = models.SlugField(max_length=64)
    authorization_domains = models.ManyToManyField(
        Group, through="WorkspaceAuthorizationDomain", blank=True
    )

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
            "anvil_project_manager:workspaces:detail", kwargs={"pk": self.pk}
        )

    def get_full_name(self):
        return "{billing_project}/{name}".format(
            billing_project=self.billing_project, name=self.name
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
                # Get or create the billing project.
                try:
                    billing_project = BillingProject.objects.get(
                        name=billing_project_name
                    )
                except BillingProject.DoesNotExist:
                    billing_project = BillingProject(name=billing_project_name)
                    billing_project.full_clean()
                    billing_project.save()
                # Create the workspace.
                workspace = cls(billing_project=billing_project, name=workspace_name)
                workspace.full_clean()

                # Check the workspace on AnVIL.
                response = AnVILAPIClient().get_workspace(
                    billing_project_name, workspace_name
                )
                workspace_json = response.json()
                print(workspace_json)
                # Make sure that we are owners of the workspace.
                if workspace_json["accessLevel"] != "OWNER":
                    raise exceptions.AnVILNotWorkspaceOwnerError(
                        billing_project_name + "/" + workspace_name
                    )
                workspace.save()
                # Check the authorization domains and import them.
                auth_domains = [
                    ad["membersGroupName"]
                    for ad in workspace_json["workspace"]["authorizationDomain"]
                ]
                print(auth_domains)
                # We don't need to check if we are members of the auth domains, because if we weren't we wouldn't be
                # able to see the workspace.
                for auth_domain in auth_domains:
                    # Either get the group from the Django database or import it.
                    try:
                        group = Group.objects.get(name=auth_domain)
                    except Group.DoesNotExist:
                        group = Group.anvil_import(auth_domain)
                    workspace.authorization_domains.add(group)
        except Exception:
            # If it fails for any reason, we don't want the transaction to happen.
            raise

        return workspace


class WorkspaceAuthorizationDomain(models.Model):
    """Through table for the Workspace authorization_domains field."""

    group = models.ForeignKey(Group, on_delete=models.PROTECT)
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE)

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


class GroupGroupMembership(models.Model):
    """A model to store which groups are in a group."""

    MEMBER = "MEMBER"
    ADMIN = "ADMIN"

    ROLE_CHOICES = [
        (MEMBER, "Member"),
        (ADMIN, "Admin"),
    ]

    parent_group = models.ForeignKey(
        "Group", on_delete=models.CASCADE, related_name="child_memberships"
    )
    child_group = models.ForeignKey(
        "Group", on_delete=models.CASCADE, related_name="parent_memberships"
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=MEMBER)

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
            "anvil_project_manager:group_group_membership:detail",
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


class GroupAccountMembership(models.Model):
    """A model to store which accounts are in a group."""

    MEMBER = "MEMBER"
    ADMIN = "ADMIN"

    ROLE_CHOICES = [
        (MEMBER, "Member"),
        (ADMIN, "Admin"),
    ]

    account = models.ForeignKey("Account", on_delete=models.CASCADE)
    group = models.ForeignKey("Group", on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=MEMBER)

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
            "anvil_project_manager:group_account_membership:detail",
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


class WorkspaceGroupAccess(models.Model):
    """A model to store which groups have access to a workspace."""

    OWNER = "OWNER"
    WRITER = "WRITER"
    READER = "READER"

    ACCESS_CHOICES = [
        (OWNER, "Owner"),
        (WRITER, "Writer"),
        (READER, "Reader"),
    ]

    group = models.ForeignKey("Group", on_delete=models.CASCADE)
    workspace = models.ForeignKey("Workspace", on_delete=models.CASCADE)
    access = models.CharField(max_length=10, choices=ACCESS_CHOICES, default=READER)

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
            "anvil_project_manager:workspace_group_access:detail",
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
