from factory import Faker, SubFactory
from factory.django import DjangoModelFactory

from ..factories import WorkspaceFactory
from . import models


class TestWorkspaceDataFactory(DjangoModelFactory):
    """Factory for the test_app.models.TestWorkspaceData model."""

    class Meta:
        model = models.TestWorkspaceData

    study_name = Faker("company")
    workspace = SubFactory(WorkspaceFactory, workspace_type="test")
