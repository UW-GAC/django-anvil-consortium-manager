from django.urls import path

from . import views

app_name = "anvil_tracker"

urlpatterns = [path("", views.Index.as_view(), name="index")]
