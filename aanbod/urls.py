from django.urls import path, re_path

from . import views

app_name = "aanbod"
urlpatterns = [
    path("", views.index, name="index"),
    path("woning/<int:pk>/", views.detail, name="detail"),
    path("makelaars/", views.makelaars, name="makelaars"),
    path("robots.txt", views.robots_txt, name="robots"),
    path("site.webmanifest", views.manifest, name="manifest"),
    re_path(r"^(?P<naam>favicon\.ico|favicon\.svg|apple-touch-icon\.png|icon-192\.png|icon-512\.png|og-image\.png)$",
            views.website_bestand, name="website_bestand"),
]
