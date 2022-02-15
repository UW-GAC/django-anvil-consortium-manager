from django.test import RequestFactory, TestCase
from django.urls import reverse

from .. import views


class IndexTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def get_url(self, *args):
        return reverse("anvil_tracker:index", args=args)

    def get_view(self):
        return views.Index.as_view()

    def test_view_success_code(self):
        request = self.factory.get(self.get_url())
        # request.user = AnonymousUser()
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
