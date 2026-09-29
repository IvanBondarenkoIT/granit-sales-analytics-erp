from django.urls import path

from promos import views

urlpatterns = [
    path("", views.promo_list, name="promo_list"),
    path("new/", views.promo_create, name="promo_create"),
    path("example.xlsx", views.promo_example_xlsx, name="promo_example_xlsx"),
    path("new/products/", views.promo_product_options, name="promo_product_options"),
    path("<int:pk>/", views.promo_detail, name="promo_detail"),
    path("<int:pk>/reanalyze/", views.promo_reanalyze, name="promo_reanalyze"),
]
