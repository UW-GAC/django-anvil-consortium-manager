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


class InvestigatorDetailTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_project_manager:investigators:detail", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.InvestigatorDetail.as_view()

    def test_view_status_code_with_existing_object(self):
        """Returns a successful status code for an existing object pk."""
        obj = factories.InvestigatorFactory.create()
        request = self.factory.get(self.get_url(obj.pk))
        response = self.get_view()(request, pk=obj.pk)
        self.assertEqual(response.status_code, 200)

    def test_view_status_code_with_invalid_pk(self):
        """Raises a 404 error with an invalid object pk."""
        obj = factories.InvestigatorFactory.create()
        request = self.factory.get(self.get_url(obj.pk + 1))
        with self.assertRaises(Http404):
            self.get_view()(request, pk=obj.pk + 1)


class InvestigatorCreateTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_project_manager:investigators:new", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.InvestigatorCreate.as_view()

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
        new_object = models.Investigator.objects.latest("pk")
        self.assertIsInstance(new_object, models.Investigator)

    def test_redirects_to_new_object_detail(self):
        """After successfully creating an object, view redirects to the object's detail page."""
        # This needs to use the client because the RequestFactory doesn't handle redirects.
        response = self.client.post(self.get_url(), {"email": "test@example.com"})
        new_object = models.Investigator.objects.latest("pk")
        self.assertRedirects(
            response,
            new_object.get_absolute_url(),
        )

    def test_cannot_create_duplicate_object(self):
        """Cannot create two investigators with the same email."""
        obj = factories.InvestigatorFactory.create()
        request = self.factory.post(self.get_url(), {"email": obj.email})
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors.keys())
        self.assertIn("already exists", form.errors["email"][0])
        self.assertQuerysetEqual(
            models.Investigator.objects.all(),
            models.Investigator.objects.filter(pk=obj.pk),
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
        self.assertEqual(models.Investigator.objects.count(), 0)

    def test_post_blank_data(self):
        """Posting blank data does not create an object."""
        request = self.factory.post(self.get_url(), {})
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors.keys())
        self.assertIn("required", form.errors["email"][0])
        self.assertEqual(models.Investigator.objects.count(), 0)


class InvestigatorListTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_project_manager:investigators:list", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.InvestigatorList.as_view()

    def test_view_status_code(self):
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_view_has_correct_table_class(self):
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertIn("table", response.context_data)
        self.assertIsInstance(response.context_data["table"], tables.InvestigatorTable)

    def test_view_with_no_objects(self):
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 0)

    def test_view_with_one_object(self):
        factories.InvestigatorFactory()
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)

    def test_view_with_two_objects(self):
        factories.InvestigatorFactory.create_batch(2)
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
            self.get_url(), {"namespace": billing_project.pk, "name": "test-workspace"}
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
            self.get_url(), {"namespace": billing_project.pk, "name": "test-workspace"}
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
                "namespace": billing_project.pk,
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
        """Cannot create two workspaces with the same namespace and name."""
        obj = factories.WorkspaceFactory.create()
        request = self.factory.post(
            self.get_url(), {"namespace": obj.namespace.pk, "name": obj.name}
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
        """Cannot create two workspaces with the same namespace and name if the first has an authorization domain."""
        auth_domain = factories.GroupFactory.create()
        obj = factories.WorkspaceFactory.create(authorization_domain=auth_domain)
        # Attempt to create a workspace with the same name and no auth domain.
        request = self.factory.post(
            self.get_url(), {"namespace": obj.namespace.pk, "name": obj.name}
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
        """Cannot create two workspaces with the same namespace and name if the second has an authorization domain."""
        auth_domain = factories.GroupFactory.create()
        obj = factories.WorkspaceFactory.create()
        # Attempt to create a workspace with the same name and no auth domain.
        request = self.factory.post(
            self.get_url(),
            {
                "namespace": obj.namespace.pk,
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

    def test_can_create_workspace_with_same_namespace_different_name(self):
        """Can create a workspace with a different name in the same namespace."""
        billing_project = factories.BillingProjectFactory.create()
        factories.WorkspaceFactory.create(namespace=billing_project, name="test-name-1")
        request = self.factory.post(
            self.get_url(), {"namespace": billing_project.pk, "name": "test-name-2"}
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.Workspace.objects.count(), 2)
        # Make sure you can get the new object.
        models.Workspace.objects.get(namespace=billing_project, name="test-name-2")

    def test_can_create_workspace_with_same_name_different_namespace(self):
        """Can create a workspace with the same name in a different namespace."""
        billing_project_1 = factories.BillingProjectFactory.create(name="project-1")
        billing_project_2 = factories.BillingProjectFactory.create(name="project-2")
        workspace_name = "test-name"
        factories.WorkspaceFactory.create(
            namespace=billing_project_1, name=workspace_name
        )
        request = self.factory.post(
            self.get_url(), {"namespace": billing_project_2.pk, "name": workspace_name}
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.Workspace.objects.count(), 2)
        # Make sure you can get the new object.
        models.Workspace.objects.get(namespace=billing_project_2, name=workspace_name)

    def test_invalid_input_name(self):
        """Posting invalid data to name field does not create an object."""
        billing_project = factories.BillingProjectFactory.create()
        request = self.factory.post(
            self.get_url(), {"namespace": billing_project.pk, "name": "invalid name"}
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors.keys())
        self.assertIn("slug", form.errors["name"][0])
        self.assertEqual(models.Workspace.objects.count(), 0)

    def test_invalid_input_namespace(self):
        """Posting invalid data to namespace field does not create an object."""
        request = self.factory.post(
            self.get_url(), {"namespace": 1, "name": "test-name"}
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("namespace", form.errors.keys())
        self.assertIn("valid choice", form.errors["namespace"][0])
        self.assertEqual(models.Workspace.objects.count(), 0)

    def test_post_invalid_name_namespace(self):
        """Posting blank data does not create an object."""
        request = self.factory.post(self.get_url(), {})
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("namespace", form.errors.keys())
        self.assertIn("required", form.errors["namespace"][0])
        self.assertIn("name", form.errors.keys())
        self.assertIn("required", form.errors["name"][0])
        self.assertEqual(models.Workspace.objects.count(), 0)

    def test_post_invalid_authorization_domain(self):
        """Posting an invalid authorization domain does not create an object."""
        auth_domain = factories.GroupFactory.create()
        request = self.factory.post(
            self.get_url(),
            {
                "namespace": "test-namespace",
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
        self.assertIn("namespace", form.errors.keys())
        self.assertIn("required", form.errors["namespace"][0])
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
        investigator = factories.InvestigatorFactory.create()
        request = self.factory.post(
            self.get_url(),
            {
                "group": group.pk,
                "investigator": investigator.pk,
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
        investigator = factories.InvestigatorFactory.create()
        request = self.factory.post(
            self.get_url(),
            {
                "group": group.pk,
                "investigator": investigator.pk,
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
        investigator = factories.InvestigatorFactory.create()
        response = self.client.post(
            self.get_url(),
            {
                "group": group.pk,
                "investigator": investigator.pk,
                "role": models.GroupMembership.ADMIN,
            },
        )
        self.assertRedirects(
            response, reverse("anvil_project_manager:group_membership:list")
        )

    def test_cannot_create_duplicate_object_with_same_role(self):
        """Cannot create a second GroupMembership object for the same investigator and group with the same role."""
        group = factories.GroupFactory.create()
        investigator = factories.InvestigatorFactory.create()
        obj = factories.GroupMembershipFactory(
            group=group, investigator=investigator, role=models.GroupMembership.MEMBER
        )
        request = self.factory.post(
            self.get_url(),
            {
                "group": group.pk,
                "investigator": investigator.pk,
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
        """Cannot create a second GroupMembership object for the same investigator and group with a different role."""
        group = factories.GroupFactory.create()
        investigator = factories.InvestigatorFactory.create()
        obj = factories.GroupMembershipFactory(
            group=group, investigator=investigator, role=models.GroupMembership.MEMBER
        )
        request = self.factory.post(
            self.get_url(),
            {
                "group": group.pk,
                "investigator": investigator.pk,
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

    def test_can_add_two_groups_for_one_investigator(self):
        group_1 = factories.GroupFactory.create(name="test-group-1")
        group_2 = factories.GroupFactory.create(name="test-group-2")
        investigator = factories.InvestigatorFactory.create()
        factories.GroupMembershipFactory.create(
            group=group_1, investigator=investigator
        )
        request = self.factory.post(
            self.get_url(),
            {
                "group": group_2.pk,
                "investigator": investigator.pk,
                "role": models.GroupMembership.MEMBER,
            },
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.GroupMembership.objects.count(), 2)

    def test_can_add_two_investigators_to_one_group(self):
        group = factories.GroupFactory.create()
        investigator_1 = factories.InvestigatorFactory.create(
            email="test_1@example.com"
        )
        investigator_2 = factories.InvestigatorFactory.create(
            email="test_2@example.com"
        )
        factories.GroupMembershipFactory.create(
            group=group, investigator=investigator_1
        )
        request = self.factory.post(
            self.get_url(),
            {
                "group": group.pk,
                "investigator": investigator_2.pk,
                "role": models.GroupMembership.MEMBER,
            },
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.GroupMembership.objects.count(), 2)

    def test_invalid_input_investigator(self):
        """Posting invalid data to investigator field does not create an object."""
        group = factories.GroupFactory.create()
        request = self.factory.post(
            self.get_url(),
            {
                "group": group.pk,
                "investigator": 1,
                "role": models.GroupMembership.MEMBER,
            },
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("investigator", form.errors.keys())
        self.assertIn("valid choice", form.errors["investigator"][0])
        self.assertEqual(models.GroupMembership.objects.count(), 0)

    def test_invalid_input_group(self):
        """Posting invalid data to group field does not create an object."""
        investigator = factories.InvestigatorFactory.create()
        request = self.factory.post(
            self.get_url(),
            {
                "group": 1,
                "investigator": investigator.pk,
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
        investigator = factories.InvestigatorFactory.create()
        request = self.factory.post(
            self.get_url(),
            {"group": group.pk, "investigator": investigator.pk, "role": "foo"},
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
        self.assertIn("investigator", form.errors.keys())
        self.assertIn("required", form.errors["investigator"][0])
        self.assertIn("role", form.errors.keys())
        self.assertIn("required", form.errors["role"][0])
        self.assertEqual(models.GroupMembership.objects.count(), 0)

    def test_post_blank_data_group(self):
        """Posting blank data to the group field does not create an object."""
        investigator = factories.InvestigatorFactory.create()
        request = self.factory.post(
            self.get_url(),
            {"investigator": investigator.pk, "role": models.GroupMembership.MEMBER},
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("group", form.errors.keys())
        self.assertIn("required", form.errors["group"][0])
        self.assertEqual(models.GroupMembership.objects.count(), 0)

    def test_post_blank_data_investigator(self):
        """Posting blank data to the investigator field does not create an object."""
        group = factories.GroupFactory.create()
        request = self.factory.post(
            self.get_url(), {"group": group.pk, "role": models.GroupMembership.MEMBER}
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("investigator", form.errors.keys())
        self.assertIn("required", form.errors["investigator"][0])
        self.assertEqual(models.GroupMembership.objects.count(), 0)

    def test_post_blank_data_role(self):
        """Posting blank data to the role field does not create an object."""
        investigator = factories.InvestigatorFactory.create()
        group = factories.GroupFactory.create()
        request = self.factory.post(
            self.get_url(), {"group": group.pk, "investigator": investigator.pk}
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
                "access_level": models.WorkspaceGroupAccess.READER,
            },
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 302)
        new_object = models.WorkspaceGroupAccess.objects.latest("pk")
        self.assertIsInstance(new_object, models.WorkspaceGroupAccess)
        self.assertEqual(new_object.access_level, models.WorkspaceGroupAccess.READER)

    def test_can_create_an_object_writer(self):
        """Posting valid data to the form creates an object."""
        group = factories.GroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        request = self.factory.post(
            self.get_url(),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access_level": models.WorkspaceGroupAccess.WRITER,
            },
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 302)
        new_object = models.WorkspaceGroupAccess.objects.latest("pk")
        self.assertIsInstance(new_object, models.WorkspaceGroupAccess)
        self.assertEqual(new_object.access_level, models.WorkspaceGroupAccess.WRITER)

    def test_can_create_an_object_owner(self):
        """Posting valid data to the form creates an object."""
        group = factories.GroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        request = self.factory.post(
            self.get_url(),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access_level": models.WorkspaceGroupAccess.OWNER,
            },
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 302)
        new_object = models.WorkspaceGroupAccess.objects.latest("pk")
        self.assertIsInstance(new_object, models.WorkspaceGroupAccess)
        self.assertEqual(new_object.access_level, models.WorkspaceGroupAccess.OWNER)

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
                "access_level": models.WorkspaceGroupAccess.OWNER,
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
            access_level=models.WorkspaceGroupAccess.READER,
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
            access_level=models.WorkspaceGroupAccess.READER,
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
                "access_level": models.WorkspaceGroupAccess.READER,
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
                "access_level": models.WorkspaceGroupAccess.READER,
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
                "access_level": models.WorkspaceGroupAccess.READER,
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
                "access_level": models.WorkspaceGroupAccess.READER,
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
                "access_level": "foo",
            },
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("access_level", form.errors.keys())
        self.assertIn("valid choice", form.errors["access_level"][0])
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
        self.assertIn("access_level", form.errors.keys())
        self.assertIn("required", form.errors["access_level"][0])
        self.assertEqual(models.WorkspaceGroupAccess.objects.count(), 0)

    def test_post_blank_data_group(self):
        """Posting blank data to the group field does not create an object."""
        workspace = factories.WorkspaceFactory.create()
        request = self.factory.post(
            self.get_url(),
            {
                "workspace": workspace.pk,
                "access_level": models.WorkspaceGroupAccess.READER,
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
            {"group": group.pk, "access_level": models.WorkspaceGroupAccess.READER},
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
        self.assertIn("access_level", form.errors.keys())
        self.assertIn("required", form.errors["access_level"][0])
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
