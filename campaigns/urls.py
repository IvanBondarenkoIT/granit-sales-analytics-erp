from django.urls import path

from campaigns import views

urlpatterns = [
    path("", views.campaign_list, name="campaign_list"),
    path("new/", views.campaign_create, name="campaign_create"),
    path("<int:pk>/", views.campaign_detail, name="campaign_detail"),
    path("<int:pk>/reanalyze/", views.campaign_reanalyze, name="campaign_reanalyze"),
    path("<int:pk>/purchases/", views.campaign_purchases, name="campaign_purchases"),
    path("<int:pk>/clients/<int:row_pk>/", views.campaign_client_purchases, name="campaign_client_purchases"),
]
