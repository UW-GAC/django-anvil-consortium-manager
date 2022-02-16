from django.http.response import Http404
from django.test import RequestFactory, TestCase
from django.urls import reverse

from .. import models, tables, views
from . import factories


class IndexTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_project_manager:index", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.Index.as_view()

    def test_view_success_code(self):
        """Returns a successful status code."""
        request = self.factory.get(self.get_url())
        # request.user = AnonymousUser()
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)


class BillingProjectDetailTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_project_manager:billing_projects:detail", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.BillingProjectDetail.as_view()

    def test_view_status_code_with_existing_object(self):
        """Returns a successful status code for an existing object pk."""
        obj = factories.BillingProjectFactory.create()
        request = self.factory.get(self.get_url(obj.pk))
        response = self.get_view()(request, pk=obj.pk)
        self.assertEqual(response.status_code, 200)

    def test_view_status_code_with_invalid_pk(self):
        """Raises a 404 error with an invalid object pk."""
        obj = factories.BillingProjectFactory.create()
        request = self.factory.get(self.get_url(obj.pk + 1))
        with self.assertRaises(Http404):
            self.get_view()(request, pk=obj.pk + 1)


class BillingProjectCreateTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_project_manager:billing_projects:new", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.BillingProjectCreate.as_view()

    def test_status_code(self):
        """Returns successful response code."""
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_has_form_in_context(self):
        """Response includes a form."""
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertTrue("form" in response.context_data)

    def test_can_create_an_object(self):
        """Posting valid data to the form creates an object."""
        request = self.factory.post(self.get_url(), {"name": "test-group"})
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 302)
        new_object = models.BillingProject.objects.latest("pk")
        self.assertIsInstance(new_object, models.BillingProject)

    def test_redirects_to_new_object_detail(self):
        """After successfully creating an object, view redirects to the object's detail page."""
        # This needs to use the client because the RequestFactory doesn't handle redirects.
        response = self.client.post(self.get_url(), {"name": "test-group"})
        new_object = models.BillingProject.objects.latest("pk")
        self.assertRedirects(response, new_object.get_absolute_url())

    def test_cannot_create_duplicate_object(self):
        """Cannot create two groups with the same name."""
        obj = factories.BillingProjectFactory.create()
        request = self.factory.post(self.get_url(), {"name": obj.name})
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors.keys())
        self.assertIn("already exists", form.errors["name"][0])
        self.assertQuerysetEqual(
            models.BillingProject.objects.all(),
            models.BillingProject.objects.filter(pk=obj.pk),
        )

    def test_invalid_input(self):
        """Posting invalid data does not create an object."""
        request = self.factory.post(self.get_url(), {"name": ""})
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors.keys())
        self.assertIn("required", form.errors["name"][0])
        self.assertEqual(models.BillingProject.objects.count(), 0)

    def test_post_blank_data(self):
        """Posting blank data does not create an object."""
        request = self.factory.post(self.get_url(), {})
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors.keys())
        self.assertIn("required", form.errors["name"][0])
        self.assertEqual(models.BillingProject.objects.count(), 0)


class BillingProjectListTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_project_manager:billing_projects:list", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.BillingProjectList.as_view()

    def test_view_status_code(self):
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_view_has_correct_table_class(self):
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertIn("table", response.context_data)
        self.assertIsInstance(
            response.context_data["table"], tables.BillingProjectTable
        )

    def test_view_with_no_objects(self):
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 0)

    def test_view_with_one_object(self):
        factories.BillingProjectFactory()
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)

    def test_view_with_two_objects(self):
        factories.BillingProjectFactory.create_batch(2)
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 2)


class ResearcherDetailTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_project_manager:researchers:detail", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.ResearcherDetail.as_view()

    def test_view_status_code_with_existing_object(self):
        """Returns a successful status code for an existing object pk."""
        obj = factories.ResearcherFactory.create()
        request = self.factory.get(self.get_url(obj.pk))
        response = self.get_view()(request, pk=obj.pk)
        self.assertEqual(response.status_code, 200)

    def test_view_status_code_with_invalid_pk(self):
        """Raises a 404 error with an invalid object pk."""
        obj = factories.ResearcherFactory.create()
        request = self.factory.get(self.get_url(obj.pk + 1))
        with self.assertRaises(Http404):
            self.get_view()(request, pk=obj.pk + 1)


class ResearcherCreateTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_project_manager:researchers:new", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.ResearcherCreate.as_view()

    def test_status_code(self):
        """Returns successful response code."""
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_has_form_in_context(self):
        """Response includes a form."""
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertTrue("form" in response.context_data)

    def test_can_create_an_object(self):
        """Posting valid data to the form creates an object."""
        request = self.factory.post(self.get_url(), {"email": "test@example.com"})
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 302)
        new_object = models.Researcher.objects.latest("pk")
        self.assertIsInstance(new_object, models.Researcher)

    def test_redirects_to_new_object_detail(self):
        """After successfully creating an object, view redirects to the object's detail page."""
        # This needs to use the client because the RequestFactory doesn't handle redirects.
        response = self.client.post(self.get_url(), {"email": "test@example.com"})
        new_object = models.Researcher.objects.latest("pk")
        self.assertRedirects(
            response,
            new_object.get_absolute_url(),
        )

    def test_cannot_create_duplicate_object(self):
        """Cannot create two researchers with the same email."""
        obj = factories.ResearcherFactory.create()
        request = self.factory.post(self.get_url(), {"email": obj.email})
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors.keys())
        self.assertIn("already exists", form.errors["email"][0])
        self.assertQuerysetEqual(
            models.Researcher.objects.all(),
            models.Researcher.objects.filter(pk=obj.pk),
        )

    def test_invalid_input(self):
        """Posting invalid data does not create an object."""
        request = self.factory.post(self.get_url(), {"email": "1"})
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors.keys())
        self.assertIn("valid email", form.errors["email"][0])
        self.assertEqual(models.Researcher.objects.count(), 0)

    def test_post_blank_data(self):
        """Posting blank data does not create an object."""
        request = self.factory.post(self.get_url(), {})
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors.keys())
        self.assertIn("required", form.errors["email"][0])
        self.assertEqual(models.Researcher.objects.count(), 0)


class ResearcherListTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_project_manager:researchers:list", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.ResearcherList.as_view()

    def test_view_status_code(self):
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_view_has_correct_table_class(self):
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertIn("table", response.context_data)
        self.assertIsInstance(response.context_data["table"], tables.ResearcherTable)

    def test_view_with_no_objects(self):
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 0)

    def test_view_with_one_object(self):
        factories.ResearcherFactory()
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)

    def test_view_with_two_objects(self):
        factories.ResearcherFactory.create_batch(2)
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 2)


class GroupDetailTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_project_manager:groups:detail", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.GroupDetail.as_view()

    def test_view_status_code_with_existing_object(self):
        """Returns a successful status code for an existing object pk."""
        obj = factories.GroupFactory.create()
        request = self.factory.get(self.get_url(obj.pk))
        response = self.get_view()(request, pk=obj.pk)
        self.assertEqual(response.status_code, 200)

    def test_view_status_code_with_invalid_pk(self):
        """Raises a 404 error with an invalid object pk."""
        obj = factories.GroupFactory.create()
        request = self.factory.get(self.get_url(obj.pk + 1))
        with self.assertRaises(Http404):
            self.get_view()(request, pk=obj.pk + 1)


class GroupCreateTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_project_manager:groups:new", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.GroupCreate.as_view()

    def test_status_code(self):
        """Returns successful response code."""
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_has_form_in_context(self):
        """Response includes a form."""
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertTrue("form" in response.context_data)

    def test_can_create_an_object(self):
        """Posting valid data to the form creates an object."""
        request = self.factory.post(self.get_url(), {"name": "test-group"})
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 302)
        new_object = models.Group.objects.latest("pk")
        self.assertIsInstance(new_object, models.Group)

    def test_redirects_to_new_object_detail(self):
        """After successfully creating an object, view redirects to the object's detail page."""
        # This needs to use the client because the RequestFactory doesn't handle redirects.
        response = self.client.post(self.get_url(), {"name": "test-group"})
        new_object = models.Group.objects.latest("pk")
        self.assertRedirects(response, new_object.get_absolute_url())

    def test_cannot_create_duplicate_object(self):
        """Cannot create two groups with the same name."""
        obj = factories.GroupFactory.create()
        request = self.factory.post(self.get_url(), {"name": obj.name})
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors.keys())
        self.assertIn("already exists", form.errors["name"][0])
        self.assertQuerysetEqual(
            models.Group.objects.all(),
            models.Group.objects.filter(pk=obj.pk),
        )

    def test_invalid_input(self):
        """Posting invalid data does not create an object."""
        request = self.factory.post(self.get_url(), {"name": ""})
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors.keys())
        self.assertIn("required", form.errors["name"][0])
        self.assertEqual(models.Group.objects.count(), 0)

    def test_post_blank_data(self):
        """Posting blank data does not create an object."""
        request = self.factory.post(self.get_url(), {})
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors.keys())
        self.assertIn("required", form.errors["name"][0])
        self.assertEqual(models.Group.objects.count(), 0)


class GroupListTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_project_manager:groups:list", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.GroupList.as_view()

    def test_view_status_code(self):
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_view_has_correct_table_class(self):
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertIn("table", response.context_data)
        self.assertIsInstance(response.context_data["table"], tables.GroupTable)

    def test_view_with_no_objects(self):
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 0)

    def test_view_with_one_object(self):
        factories.GroupFactory()
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)

    def test_view_with_two_objects(self):
        factories.GroupFactory.create_batch(2)
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 2)


class WorkspaceDetailTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_project_manager:workspaces:detail", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.WorkspaceDetail.as_view()

    def test_view_status_code_with_existing_object(self):
        """Returns a successful status code for an existing object pk."""
        obj = factories.WorkspaceFactory.create()
        request = self.factory.get(self.get_url(obj.pk))
        response = self.get_view()(request, pk=obj.pk)
        self.assertEqual(response.status_code, 200)

    def test_view_status_code_with_invalid_pk(self):
        """Raises a 404 error with an invalid object pk."""
        obj = factories.WorkspaceFactory.create()
        request = self.factory.get(self.get_url(obj.pk + 1))
        with self.assertRaises(Http404):
            self.get_view()(request, pk=obj.pk + 1)


class WorkspaceCreateTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_project_manager:workspaces:new", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.WorkspaceCreate.as_view()

    def test_status_code(self):
        """Returns successful response code."""
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_has_form_in_context(self):
        """Response includes a form."""
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertTrue("form" in response.context_data)

    def test_can_create_an_object(self):
        """Posting valid data to the form creates an object."""
        billing_project = factories.BillingProjectFactory.create()
        request = self.factory.post(
            self.get_url(),
            {"billing_project": billing_project.pk, "name": "test-workspace"},
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 302)
        new_object = models.Workspace.objects.latest("pk")
        self.assertIsInstance(new_object, models.Workspace)

    def test_redirects_to_new_object_detail(self):
        """After successfully creating an object, view redirects to the object's detail page."""
        # This needs to use the client because the RequestFactory doesn't handle redirects.
        billing_project = factories.BillingProjectFactory.create()
        response = self.client.post(
            self.get_url(),
            {"billing_project": billing_project.pk, "name": "test-workspace"},
        )
        new_object = models.Workspace.objects.latest("pk")
        self.assertRedirects(response, new_object.get_absolute_url())

    def test_can_create_a_workspace_with_an_authorization_domain(self):
        """Posting data with an authorization domain creates a workspace with that authorization domain."""
        billing_project = factories.BillingProjectFactory.create()
        auth_domain = factories.GroupFactory.create()
        request = self.factory.post(
            self.get_url(),
            {
                "billing_project": billing_project.pk,
                "name": "test-workspace",
                "authorization_domain": auth_domain.pk,
            },
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 302)
        new_object = models.Workspace.objects.latest("pk")
        self.assertIsInstance(new_object, models.Workspace)
        self.assertEqual(new_object.authorization_domain, auth_domain)

    def test_cannot_create_duplicate_object(self):
        """Cannot create two workspaces with the same billing project and name."""
        obj = factories.WorkspaceFactory.create()
        request = self.factory.post(
            self.get_url(),
            {"billing_project": obj.billing_project.pk, "name": obj.name},
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("already exists", form.non_field_errors()[0])
        self.assertQuerysetEqual(
            models.Workspace.objects.all(),
            models.Workspace.objects.filter(pk=obj.pk),
        )

    def test_cannot_create_duplicate_object_with_auth_domain(self):
        """Cannot create two workspaces with the same billing project and name if the first has
        an authorization domain."""
        auth_domain = factories.GroupFactory.create()
        obj = factories.WorkspaceFactory.create(authorization_domain=auth_domain)
        # Attempt to create a workspace with the same name and no auth domain.
        request = self.factory.post(
            self.get_url(),
            {"billing_project": obj.billing_project.pk, "name": obj.name},
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("already exists", form.non_field_errors()[0])
        self.assertQuerysetEqual(
            models.Workspace.objects.all(),
            models.Workspace.objects.filter(pk=obj.pk),
        )

    def test_cannot_create_duplicate_object_with_auth_domain_2(self):
        """Cannot create two workspaces with the same billing project and name if the second has
        an authorization domain."""
        auth_domain = factories.GroupFactory.create()
        obj = factories.WorkspaceFactory.create()
        # Attempt to create a workspace with the same name and no auth domain.
        request = self.factory.post(
            self.get_url(),
            {
                "billing_project": obj.billing_project.pk,
                "name": obj.name,
                "authorization_domain": auth_domain.pk,
            },
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("already exists", form.non_field_errors()[0])
        self.assertQuerysetEqual(
            models.Workspace.objects.all(),
            models.Workspace.objects.filter(pk=obj.pk),
        )

    def test_can_create_workspace_with_same_billing_project_different_name(self):
        """Can create a workspace with a different name in the same billing project."""
        billing_project = factories.BillingProjectFactory.create()
        factories.WorkspaceFactory.create(
            billing_project=billing_project, name="test-name-1"
        )
        request = self.factory.post(
            self.get_url(),
            {"billing_project": billing_project.pk, "name": "test-name-2"},
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.Workspace.objects.count(), 2)
        # Make sure you can get the new object.
        models.Workspace.objects.get(
            billing_project=billing_project, name="test-name-2"
        )

    def test_can_create_workspace_with_same_name_different_billing_project(self):
        """Can create a workspace with the same name in a different billing project."""
        billing_project_1 = factories.BillingProjectFactory.create(name="project-1")
        billing_project_2 = factories.BillingProjectFactory.create(name="project-2")
        workspace_name = "test-name"
        factories.WorkspaceFactory.create(
            billing_project=billing_project_1, name=workspace_name
        )
        request = self.factory.post(
            self.get_url(),
            {"billing_project": billing_project_2.pk, "name": workspace_name},
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.Workspace.objects.count(), 2)
        # Make sure you can get the new object.
        models.Workspace.objects.get(
            billing_project=billing_project_2, name=workspace_name
        )

    def test_invalid_input_name(self):
        """Posting invalid data to name field does not create an object."""
        billing_project = factories.BillingProjectFactory.create()
        request = self.factory.post(
            self.get_url(),
            {"billing_project": billing_project.pk, "name": "invalid name"},
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors.keys())
        self.assertIn("slug", form.errors["name"][0])
        self.assertEqual(models.Workspace.objects.count(), 0)

    def test_invalid_input_billing_project(self):
        """Posting invalid data to billing_project field does not create an object."""
        request = self.factory.post(
            self.get_url(), {"billing_project": 1, "name": "test-name"}
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("billing_project", form.errors.keys())
        self.assertIn("valid choice", form.errors["billing_project"][0])
        self.assertEqual(models.Workspace.objects.count(), 0)

    def test_post_invalid_name_billing_project(self):
        """Posting blank data does not create an object."""
        request = self.factory.post(self.get_url(), {})
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("billing_project", form.errors.keys())
        self.assertIn("required", form.errors["billing_project"][0])
        self.assertIn("name", form.errors.keys())
        self.assertIn("required", form.errors["name"][0])
        self.assertEqual(models.Workspace.objects.count(), 0)

    def test_post_invalid_authorization_domain(self):
        """Posting an invalid authorization domain does not create an object."""
        billing_project = factories.BillingProjectFactory.create()
        auth_domain = factories.GroupFactory.create()
        request = self.factory.post(
            self.get_url(),
            {
                "billing_project": billing_project.pk,
                "name": "test-name",
                "authorization_domain": auth_domain.pk + 1,
            },
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context_data)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("authorization_domain", form.errors.keys())
        self.assertIn("Select a valid choice", form.errors["authorization_domain"][0])

    def test_post_blank_data(self):
        """Posting blank data does not create an object."""
        request = self.factory.post(self.get_url(), {})
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("billing_project", form.errors.keys())
        self.assertIn("required", form.errors["billing_project"][0])
        self.assertIn("name", form.errors.keys())
        self.assertIn("required", form.errors["name"][0])
        self.assertEqual(models.Workspace.objects.count(), 0)


class WorkspaceListTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_project_manager:workspaces:list", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.WorkspaceList.as_view()

    def test_view_status_code(self):
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_view_has_correct_table_class(self):
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertIn("table", response.context_data)
        self.assertIsInstance(response.context_data["table"], tables.WorkspaceTable)

    def test_view_with_no_objects(self):
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 0)

    def test_view_with_one_object(self):
        factories.WorkspaceFactory()
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)

    def test_view_with_two_objects(self):
        factories.WorkspaceFactory.create_batch(2)
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 2)


class GroupMembershipCreateTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_project_manager:group_membership:new", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.GroupMembershipCreate.as_view()

    def test_status_code(self):
        """Returns successful response code."""
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_has_form_in_context(self):
        """Response includes a form."""
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertTrue("form" in response.context_data)

    def test_can_create_an_object_member(self):
        """Posting valid data to the form creates an object."""
        group = factories.GroupFactory.create()
        researcher = factories.ResearcherFactory.create()
        request = self.factory.post(
            self.get_url(),
            {
                "group": group.pk,
                "researcher": researcher.pk,
                "role": models.GroupMembership.MEMBER,
            },
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 302)
        new_object = models.GroupMembership.objects.latest("pk")
        self.assertIsInstance(new_object, models.GroupMembership)
        self.assertEqual(new_object.role, models.GroupMembership.MEMBER)

    def test_can_create_an_object_admin(self):
        """Posting valid data to the form creates an object."""
        group = factories.GroupFactory.create()
        researcher = factories.ResearcherFactory.create()
        request = self.factory.post(
            self.get_url(),
            {
                "group": group.pk,
                "researcher": researcher.pk,
                "role": models.GroupMembership.ADMIN,
            },
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 302)
        new_object = models.GroupMembership.objects.latest("pk")
        self.assertIsInstance(new_object, models.GroupMembership)
        self.assertEqual(new_object.role, models.GroupMembership.ADMIN)

    def test_redirects_to_list(self):
        """After successfully creating an object, view redirects to the model's list view."""
        # This needs to use the client because the RequestFactory doesn't handle redirects.
        group = factories.GroupFactory.create()
        researcher = factories.ResearcherFactory.create()
        response = self.client.post(
            self.get_url(),
            {
                "group": group.pk,
                "researcher": researcher.pk,
                "role": models.GroupMembership.ADMIN,
            },
        )
        self.assertRedirects(
            response, reverse("anvil_project_manager:group_membership:list")
        )

    def test_cannot_create_duplicate_object_with_same_role(self):
        """Cannot create a second GroupMembership object for the same researcher and group with the same role."""
        group = factories.GroupFactory.create()
        researcher = factories.ResearcherFactory.create()
        obj = factories.GroupMembershipFactory(
            group=group, researcher=researcher, role=models.GroupMembership.MEMBER
        )
        request = self.factory.post(
            self.get_url(),
            {
                "group": group.pk,
                "researcher": researcher.pk,
                "role": models.GroupMembership.MEMBER,
            },
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("already exists", form.non_field_errors()[0])
        self.assertQuerysetEqual(
            models.GroupMembership.objects.all(),
            models.GroupMembership.objects.filter(pk=obj.pk),
        )

    def test_cannot_create_duplicate_object_with_different_role(self):
        """Cannot create a second GroupMembership object for the same researcher and group with a different role."""
        group = factories.GroupFactory.create()
        researcher = factories.ResearcherFactory.create()
        obj = factories.GroupMembershipFactory(
            group=group, researcher=researcher, role=models.GroupMembership.MEMBER
        )
        request = self.factory.post(
            self.get_url(),
            {
                "group": group.pk,
                "researcher": researcher.pk,
                "role": models.GroupMembership.ADMIN,
            },
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("already exists", form.non_field_errors()[0])
        self.assertQuerysetEqual(
            models.GroupMembership.objects.all(),
            models.GroupMembership.objects.filter(pk=obj.pk),
        )

    def test_can_add_two_groups_for_one_researcher(self):
        group_1 = factories.GroupFactory.create(name="test-group-1")
        group_2 = factories.GroupFactory.create(name="test-group-2")
        researcher = factories.ResearcherFactory.create()
        factories.GroupMembershipFactory.create(group=group_1, researcher=researcher)
        request = self.factory.post(
            self.get_url(),
            {
                "group": group_2.pk,
                "researcher": researcher.pk,
                "role": models.GroupMembership.MEMBER,
            },
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.GroupMembership.objects.count(), 2)

    def test_can_add_two_researchers_to_one_group(self):
        group = factories.GroupFactory.create()
        researcher_1 = factories.ResearcherFactory.create(email="test_1@example.com")
        researcher_2 = factories.ResearcherFactory.create(email="test_2@example.com")
        factories.GroupMembershipFactory.create(group=group, researcher=researcher_1)
        request = self.factory.post(
            self.get_url(),
            {
                "group": group.pk,
                "researcher": researcher_2.pk,
                "role": models.GroupMembership.MEMBER,
            },
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.GroupMembership.objects.count(), 2)

    def test_invalid_input_researcher(self):
        """Posting invalid data to researcher field does not create an object."""
        group = factories.GroupFactory.create()
        request = self.factory.post(
            self.get_url(),
            {
                "group": group.pk,
                "researcher": 1,
                "role": models.GroupMembership.MEMBER,
            },
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("researcher", form.errors.keys())
        self.assertIn("valid choice", form.errors["researcher"][0])
        self.assertEqual(models.GroupMembership.objects.count(), 0)

    def test_invalid_input_group(self):
        """Posting invalid data to group field does not create an object."""
        researcher = factories.ResearcherFactory.create()
        request = self.factory.post(
            self.get_url(),
            {
                "group": 1,
                "researcher": researcher.pk,
                "role": models.GroupMembership.MEMBER,
            },
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("group", form.errors.keys())
        self.assertIn("valid choice", form.errors["group"][0])
        self.assertEqual(models.GroupMembership.objects.count(), 0)

    def test_invalid_input_role(self):
        """Posting invalid data to group field does not create an object."""
        group = factories.GroupFactory.create()
        researcher = factories.ResearcherFactory.create()
        request = self.factory.post(
            self.get_url(),
            {"group": group.pk, "researcher": researcher.pk, "role": "foo"},
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("role", form.errors.keys())
        self.assertIn("valid choice", form.errors["role"][0])
        self.assertEqual(models.GroupMembership.objects.count(), 0)

    def test_post_blank_data(self):
        """Posting blank data does not create an object."""
        request = self.factory.post(self.get_url(), {})
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("group", form.errors.keys())
        self.assertIn("required", form.errors["group"][0])
        self.assertIn("researcher", form.errors.keys())
        self.assertIn("required", form.errors["researcher"][0])
        self.assertIn("role", form.errors.keys())
        self.assertIn("required", form.errors["role"][0])
        self.assertEqual(models.GroupMembership.objects.count(), 0)

    def test_post_blank_data_group(self):
        """Posting blank data to the group field does not create an object."""
        researcher = factories.ResearcherFactory.create()
        request = self.factory.post(
            self.get_url(),
            {"researcher": researcher.pk, "role": models.GroupMembership.MEMBER},
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("group", form.errors.keys())
        self.assertIn("required", form.errors["group"][0])
        self.assertEqual(models.GroupMembership.objects.count(), 0)

    def test_post_blank_data_researcher(self):
        """Posting blank data to the researcher field does not create an object."""
        group = factories.GroupFactory.create()
        request = self.factory.post(
            self.get_url(), {"group": group.pk, "role": models.GroupMembership.MEMBER}
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("researcher", form.errors.keys())
        self.assertIn("required", form.errors["researcher"][0])
        self.assertEqual(models.GroupMembership.objects.count(), 0)

    def test_post_blank_data_role(self):
        """Posting blank data to the role field does not create an object."""
        researcher = factories.ResearcherFactory.create()
        group = factories.GroupFactory.create()
        request = self.factory.post(
            self.get_url(), {"group": group.pk, "researcher": researcher.pk}
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("role", form.errors.keys())
        self.assertIn("required", form.errors["role"][0])
        self.assertEqual(models.GroupMembership.objects.count(), 0)


class GroupMembershipListTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_project_manager:group_membership:list", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.GroupMembershipList.as_view()

    def test_view_status_code(self):
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_view_has_correct_table_class(self):
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertIn("table", response.context_data)
        self.assertIsInstance(
            response.context_data["table"], tables.GroupMembershipTable
        )

    def test_view_with_no_objects(self):
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 0)

    def test_view_with_one_object(self):
        factories.GroupMembershipFactory()
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)

    def test_view_with_two_objects(self):
        factories.GroupMembershipFactory.create_batch(2)
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 2)


class WorkspaceGroupAccessCreateTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_project_manager:workspace_group_access:new", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.WorkspaceGroupAccessCreate.as_view()

    def test_status_code(self):
        """Returns successful response code."""
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_has_form_in_context(self):
        """Response includes a form."""
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertTrue("form" in response.context_data)

    def test_can_create_an_object_reader(self):
        """Posting valid data to the form creates an object."""
        group = factories.GroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        request = self.factory.post(
            self.get_url(),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupAccess.READER,
            },
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 302)
        new_object = models.WorkspaceGroupAccess.objects.latest("pk")
        self.assertIsInstance(new_object, models.WorkspaceGroupAccess)
        self.assertEqual(new_object.access, models.WorkspaceGroupAccess.READER)

    def test_can_create_an_object_writer(self):
        """Posting valid data to the form creates an object."""
        group = factories.GroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        request = self.factory.post(
            self.get_url(),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupAccess.WRITER,
            },
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 302)
        new_object = models.WorkspaceGroupAccess.objects.latest("pk")
        self.assertIsInstance(new_object, models.WorkspaceGroupAccess)
        self.assertEqual(new_object.access, models.WorkspaceGroupAccess.WRITER)

    def test_can_create_an_object_owner(self):
        """Posting valid data to the form creates an object."""
        group = factories.GroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        request = self.factory.post(
            self.get_url(),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupAccess.OWNER,
            },
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 302)
        new_object = models.WorkspaceGroupAccess.objects.latest("pk")
        self.assertIsInstance(new_object, models.WorkspaceGroupAccess)
        self.assertEqual(new_object.access, models.WorkspaceGroupAccess.OWNER)

    def test_redirects_to_list(self):
        """After successfully creating an object, view redirects to the model's list view."""
        # This needs to use the client because the RequestFactory doesn't handle redirects.
        group = factories.GroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        response = self.client.post(
            self.get_url(),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupAccess.OWNER,
            },
        )
        self.assertRedirects(
            response, reverse("anvil_project_manager:workspace_group_access:list")
        )

    def test_cannot_create_duplicate_object_with_same_access(self):
        """Cannot create a second object for the same workspace and group with the same access level."""
        group = factories.GroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        obj = factories.WorkspaceGroupAccessFactory(
            group=group,
            workspace=workspace,
            access=models.WorkspaceGroupAccess.READER,
        )
        request = self.factory.post(
            self.get_url(),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupAccess.READER,
            },
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("already exists", form.non_field_errors()[0])
        self.assertQuerysetEqual(
            models.WorkspaceGroupAccess.objects.all(),
            models.WorkspaceGroupAccess.objects.filter(pk=obj.pk),
        )

    def test_cannot_create_duplicate_object_with_different_access(self):
        """Cannot create a second object for the same workspace and group with a different access level."""
        group = factories.GroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        obj = factories.WorkspaceGroupAccessFactory(
            group=group,
            workspace=workspace,
            access=models.WorkspaceGroupAccess.READER,
        )
        request = self.factory.post(
            self.get_url(),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupAccess.OWNER,
            },
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("already exists", form.non_field_errors()[0])
        self.assertQuerysetEqual(
            models.WorkspaceGroupAccess.objects.all(),
            models.WorkspaceGroupAccess.objects.filter(pk=obj.pk),
        )

    def test_can_have_two_workspaces_for_one_group(self):
        group_1 = factories.GroupFactory.create(name="test-group-1")
        group_2 = factories.GroupFactory.create(name="test-group-2")
        workspace = factories.WorkspaceFactory.create()
        factories.WorkspaceGroupAccessFactory.create(group=group_1, workspace=workspace)
        request = self.factory.post(
            self.get_url(),
            {
                "group": group_2.pk,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupAccess.READER,
            },
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.WorkspaceGroupAccess.objects.count(), 2)

    def test_can_have_two_groups_for_one_workspace(self):
        group = factories.GroupFactory.create()
        workspace_1 = factories.WorkspaceFactory.create(name="test-workspace-1")
        workspace_2 = factories.WorkspaceFactory.create(name="test-workspace-2")
        factories.WorkspaceGroupAccessFactory.create(group=group, workspace=workspace_1)
        request = self.factory.post(
            self.get_url(),
            {
                "group": group.pk,
                "workspace": workspace_2.pk,
                "access": models.WorkspaceGroupAccess.READER,
            },
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.WorkspaceGroupAccess.objects.count(), 2)

    def test_invalid_input_group(self):
        """Posting invalid data to group field does not create an object."""
        workspace = factories.WorkspaceFactory.create()
        request = self.factory.post(
            self.get_url(),
            {
                "group": 1,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupAccess.READER,
            },
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("group", form.errors.keys())
        self.assertIn("valid choice", form.errors["group"][0])
        self.assertEqual(models.WorkspaceGroupAccess.objects.count(), 0)

    def test_invalid_input_workspace(self):
        """Posting invalid data to workspace field does not create an object."""
        group = factories.GroupFactory.create()
        request = self.factory.post(
            self.get_url(),
            {
                "group": group.pk,
                "workspace": 1,
                "access": models.WorkspaceGroupAccess.READER,
            },
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("workspace", form.errors.keys())
        self.assertIn("valid choice", form.errors["workspace"][0])
        self.assertEqual(models.WorkspaceGroupAccess.objects.count(), 0)

    def test_invalid_input_access(self):
        """Posting invalid data to access field does not create an object."""
        workspace = factories.WorkspaceFactory.create()
        group = factories.GroupFactory.create()
        request = self.factory.post(
            self.get_url(),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": "foo",
            },
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("access", form.errors.keys())
        self.assertIn("valid choice", form.errors["access"][0])
        self.assertEqual(models.WorkspaceGroupAccess.objects.count(), 0)

    def test_post_blank_data(self):
        """Posting blank data does not create an object."""
        request = self.factory.post(self.get_url(), {})
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("group", form.errors.keys())
        self.assertIn("required", form.errors["group"][0])
        self.assertIn("workspace", form.errors.keys())
        self.assertIn("required", form.errors["workspace"][0])
        self.assertIn("access", form.errors.keys())
        self.assertIn("required", form.errors["access"][0])
        self.assertEqual(models.WorkspaceGroupAccess.objects.count(), 0)

    def test_post_blank_data_group(self):
        """Posting blank data to the group field does not create an object."""
        workspace = factories.WorkspaceFactory.create()
        request = self.factory.post(
            self.get_url(),
            {
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupAccess.READER,
            },
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("group", form.errors.keys())
        self.assertIn("required", form.errors["group"][0])
        self.assertEqual(models.WorkspaceGroupAccess.objects.count(), 0)

    def test_post_blank_data_workspace(self):
        """Posting blank data to the workspace field does not create an object."""
        group = factories.GroupFactory.create()
        request = self.factory.post(
            self.get_url(),
            {"group": group.pk, "access": models.WorkspaceGroupAccess.READER},
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("workspace", form.errors.keys())
        self.assertIn("required", form.errors["workspace"][0])
        self.assertEqual(models.WorkspaceGroupAccess.objects.count(), 0)

    def test_post_blank_data_access(self):
        """Posting blank data to the access field does not create an object."""
        workspace = factories.WorkspaceFactory.create()
        group = factories.GroupFactory.create()
        request = self.factory.post(
            self.get_url(),
            {"group": group.pk, "workspace": workspace.pk},
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("access", form.errors.keys())
        self.assertIn("required", form.errors["access"][0])
        self.assertEqual(models.WorkspaceGroupAccess.objects.count(), 0)


class WorkspaceGroupAccessListTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_project_manager:workspace_group_access:list", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.WorkspaceGroupAccessList.as_view()

    def test_view_status_code(self):
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_view_has_correct_table_class(self):
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertIn("table", response.context_data)
        self.assertIsInstance(
            response.context_data["table"], tables.WorkspaceGroupAccessTable
        )

    def test_view_with_no_objects(self):
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 0)

    def test_view_with_one_object(self):
        factories.WorkspaceGroupAccessFactory()
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)

    def test_view_with_two_objects(self):
        factories.WorkspaceGroupAccessFactory.create_batch(2)
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 2)
