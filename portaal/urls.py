from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = f"{settings.PORTAAL_NAAM} – beheer"
admin.site.site_title = settings.PORTAAL_NAAM
admin.site.index_title = "Beheer"

urlpatterns = [
    path("beheer/", admin.site.urls),
    path("", include("aanbod.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
