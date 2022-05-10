from django.urls import include, path
from django.views.generic import TemplateView

urlpatterns = [
    # Auth is required.
    path("accounts/", include("django.contrib.auth.urls")),
    # Unprotected URL for testing login redirect without a template.
    path(
        "test_login/",
        TemplateView.as_view(
            template_name="../templates/anvil_consortium_manager/index.html"
        ),
        name="test_login",
    ),
    # path("test_login/", View.as_view(), name="test_login"),
    # These urls.
    path("anvil/", include("anvil_consortium_manager.urls")),
]
