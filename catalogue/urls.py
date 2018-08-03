from django.conf.urls import include, url
from django.urls import include, path, re_path
from rest_framework import routers
from .api import RecordViewSet
from . import views

router = routers.DefaultRouter()
router.register(r'^records', RecordViewSet)

api_patterns = [
    path('', include(router.urls))
]

urlpatterns = [
    path('api/', include(api_patterns)),
    path('', views.CswEndpoint.as_view(), name='csw_endpoint'),
    re_path(r'^(?P<app>[a-z0-9_]*)/$', views.CswEndpoint.as_view(), name='csw_app_endpoint'),
]
