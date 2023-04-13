"""Factories to create API responses."""

import factory
from factory.fuzzy import FuzzyChoice


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


class GetGroupDetailsFactory(factory.DictFactory):

    groupName = factory.Faker("word")
    groupEmail = factory.LazyAttribute(
        lambda obj: "{}@firecloud.org".format(obj.groupName)
    )
    role = FuzzyChoice(["admin", "member"])


class GetGroupsResponseFactory(factory.Factory):
    """Factory for the get_groups method."""

    class Meta:
        model = MockAPIResponse

    # Neither of these worked.
    # response = "foo"
    # response = factory.RelatedFactoryList(GetGroupDetailsFactory, size=3)
    response = factory.LazyAttribute(
        lambda o: [GetGroupDetailsFactory() for _ in range(o.n_groups)]
    )

    class Params:
        n_groups = 0
