from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView
admin.autodiscover()

urlpatterns = [
    path('admin/', admin.site.urls),
    path('catalogue/', include('catalogue.urls')),
    path('', RedirectView.as_view(url='/admin/')),
]
