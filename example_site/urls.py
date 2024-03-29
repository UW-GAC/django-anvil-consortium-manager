from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

urlpatterns = [
    path("", TemplateView.as_view(template_name="home.html"), name="home"),
    # Django Admin, use {% url 'admin:index' %}
    path("admin/", admin.site.urls),
    # Auth.
    path("accounts/", include("django.contrib.auth.urls")),
    # Your stuff: custom urls includes go here
    path("anvil/", include("anvil_consortium_manager.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


if "debug_toolbar" in settings.INSTALLED_APPS:
    import debug_toolbar

    urlpatterns = [path("__debug__/", include(debug_toolbar.urls))] + urlpatterns
