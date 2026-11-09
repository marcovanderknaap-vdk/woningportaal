from django.urls import path

from . import views

app_name = "aanbod"
urlpatterns = [
    path("", views.index, name="index"),
    path("woning/<int:pk>/", views.detail, name="detail"),
    path("makelaars/", views.makelaars, name="makelaars"),
]
