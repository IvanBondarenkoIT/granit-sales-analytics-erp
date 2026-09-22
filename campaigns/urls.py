from django.urls import path

from campaigns import views

urlpatterns = [
    path("", views.campaign_list, name="campaign_list"),
    path("new/", views.campaign_create, name="campaign_create"),
    path("<int:pk>/", views.campaign_detail, name="campaign_detail"),
]
