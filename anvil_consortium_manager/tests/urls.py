from django.urls import include, path

urlpatterns = [
    path("anvil/", include("anvil_consortium_manager.urls")),
]
