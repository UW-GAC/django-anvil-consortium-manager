"""Factories to create API responses."""

import factory
from factory.fuzzy import FuzzyChoice
from faker import Faker

from .. import anvil_api

fake = Faker()


class MockAPIResponse:
    """Mock API response object to use in factories."""

    response = None

    def __init__(self, response):
        self.response = response


class MockAPIResponseFactory(factory.Factory):
    """Factory superclass for mocked API response factories."""

    class Meta:
        model = MockAPIResponse


class ErrorResponseFactory(MockAPIResponseFactory):
    """Factory to create an error response."""

    response = factory.Dict({"message": factory.Faker("sentence")})


class GroupDetailsFactory(factory.DictFactory):

    groupName = factory.Faker("word")
    groupEmail = factory.LazyAttribute(lambda obj: "{}@firecloud.org".format(obj.groupName))
    role = FuzzyChoice(["admin", "member"])


class GroupDetailsAdminFactory(GroupDetailsFactory):
    """Factory for when we are admin of the group."""

    role = "admin"


class GroupDetailsMemberFactory(GroupDetailsFactory):
    """GroupDetailsFactory Factory for when we are members of the group."""

    role = "member"


class GetGroupsResponseFactory(factory.Factory):
    """Factory for the get_groups method."""

    class Meta:
        model = MockAPIResponse

    # Neither of these worked.
    # response = "foo"
    # response = factory.RelatedFactoryList(GetGroupDetailsFactory, size=3)
    response = factory.LazyAttribute(lambda o: [GroupDetailsFactory() for _ in range(o.n_groups)])

    class Params:
        n_groups = 0


class GetGroupMembershipResponseFactory(MockAPIResponseFactory):

    response = factory.LazyAttribute(lambda o: [fake.email() for _ in range(o.n_emails)])

    class Params:
        n_emails = 0


class GetGroupMembershipAdminResponseFactory(GetGroupMembershipResponseFactory):
    @classmethod
    def _after_postgeneration(cls, obj, create, results=None):
        """Populate the response with the service account email."""
        obj.response = obj.response + [anvil_api.AnVILAPIClient().auth_session.credentials.service_account_email]
