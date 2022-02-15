from django.urls import include, path

from . import views

app_name = "anvil_tracker"

investigator_patterns = (
    [
        path("<int:pk>", views.InvestigatorDetail.as_view(), name="detail"),
        path("new/", views.InvestigatorCreate.as_view(), name="new"),
    ],
    "investigators",
)

urlpatterns = [
    path("", views.Index.as_view(), name="index"),
    path("investigators/", include(investigator_patterns)),
]
