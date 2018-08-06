from django.urls import include, path, re_path
from rest_framework import routers
from catalogue.api import RecordViewSet
from catalogue import views

router = routers.DefaultRouter()
router.register(r'^records', RecordViewSet)

urlpatterns = [
    path('api/', include(router.urls)),
    path('', views.CswEndpoint.as_view(), name='csw_endpoint'),
    re_path(r'^(?P<app>[a-z0-9_]*)/$', views.CswEndpoint.as_view(), name='csw_app_endpoint'),
]
