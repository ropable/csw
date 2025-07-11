from django.urls import include, path
from rest_framework import routers

from catalogue import views
from catalogue.api import RecordViewSet

router = routers.DefaultRouter()
router.register("records", RecordViewSet)

urlpatterns = [
    path("api/", include(router.urls)),
    path("<str:app>/", views.CswEndpoint.as_view(), name="csw_app_endpoint"),
    path("", views.CswEndpoint.as_view(), name="csw_endpoint"),
]
