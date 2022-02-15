from django.http.response import Http404
from django.test import RequestFactory, TestCase
from django.urls import reverse

from .. import views
from . import factories


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


class InvestigatorDetailTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def get_url(self, *args):
        return reverse("anvil_tracker:investigators:detail", args=args)

    def get_view(self):
        return views.InvestigatorDetail.as_view()

    def test_view_status_code_with_existing_object(self):
        obj = factories.InvestigatorFactory.create()
        request = self.factory.get(self.get_url(obj.pk))
        response = self.get_view()(request, pk=obj.pk)
        self.assertEqual(response.status_code, 200)

    def test_view_status_code_with_invalid_pk(self):
        obj = factories.InvestigatorFactory.create()
        request = self.factory.get(self.get_url(obj.pk + 1))
        with self.assertRaises(Http404):
            self.get_view()(request, pk=obj.pk + 1)
