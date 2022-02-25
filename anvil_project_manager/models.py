from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models
from django.urls import reverse

from .anvil_api import AnVILAPISession


class BillingProject(models.Model):
    """A model to store information about AnVIL billing projects."""

    name = models.SlugField(max_length=64, unique=True)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse(
            "anvil_project_manager:billing_projects:detail", kwargs={"pk": self.pk}
        )


class Account(models.Model):
    """A model to store information about AnVIL accounts."""

    # TODO: Consider using CIEmailField if using postgres.
    email = models.EmailField(unique=True)
    is_service_account = models.BooleanField()

    def __str__(self):
        return "{email}".format(email=self.email)

    def save(self, *args, **kwargs):
        self.email = self.email.lower()
        return super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("anvil_project_manager:accounts:detail", kwargs={"pk": self.pk})


class Group(models.Model):
    """A model to store information about AnVIL groups."""

    name = models.SlugField(max_length=64, unique=True)

    def __str__(self):
        return "{name}".format(name=self.name)

    def get_absolute_url(self):
        return reverse("anvil_project_manager:groups:detail", kwargs={"pk": self.pk})

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
        response = AnVILAPISession().get_group(self.name)
        return response.status_code == 200


class Workspace(models.Model):
    """A model to store information about AnVIL workspaces."""

    # NB: In the APIs some documentation, this is also referred to as "namespace".
    # In other places, it is "billing project".
    # For internal consistency, call it "billing project" here.
    billing_project = models.ForeignKey("BillingProject", on_delete=models.PROTECT)
    name = models.SlugField(max_length=64)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["billing_project", "name"], name="unique_workspace"
            )
        ]

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
