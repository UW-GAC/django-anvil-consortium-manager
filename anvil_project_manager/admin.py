"""Admin classes for the anvil_project_manager app."""

from django.contrib import admin

from . import models

admin.site.register(models.BillingProject)
admin.site.register(models.Account)
admin.site.register(models.Group)
admin.site.register(models.Workspace)
admin.site.register(models.WorkspaceAuthorizationDomain)
admin.site.register(models.GroupGroupMembership)
admin.site.register(models.GroupAccountMembership)
admin.site.register(models.WorkspaceGroupAccess)
