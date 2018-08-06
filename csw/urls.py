from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView
admin.autodiscover()

urlpatterns = [
    path('admin/', admin.site.urls),
    path('catalogue/', include('catalogue.urls')),
    path('', RedirectView.as_view(url='/admin/')),
]

# Serve media using Django (only works when DEBUG==True).
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
