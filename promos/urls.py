from django.urls import path

from promos import picker, views

urlpatterns = [
    path("", views.promo_list, name="promo_list"),
    path("new/", views.promo_create, name="promo_create"),
    path("sync-catalog/", views.promo_sync_catalog, name="promo_sync_catalog"),
    path("example.xlsx", views.promo_example_xlsx, name="promo_example_xlsx"),
    path("picker/granit/groups/", picker.picker_granit_groups, name="picker_granit_groups"),
    path("picker/granit/products/", picker.picker_granit_products, name="picker_granit_products"),
    path("picker/granit/all/", picker.picker_granit_all, name="picker_granit_all"),
    path("picker/site/categories/", picker.picker_site_categories, name="picker_site_categories"),
    path("picker/site/products/", picker.picker_site_products, name="picker_site_products"),
    path("picker/site/all/", picker.picker_site_all, name="picker_site_all"),
    path("<int:pk>/", views.promo_detail, name="promo_detail"),
    path("<int:pk>/edit/", views.promo_edit, name="promo_edit"),
    path("<int:pk>/charts/", views.promo_charts, name="promo_charts"),
    path("<int:pk>/reanalyze/", views.promo_reanalyze, name="promo_reanalyze"),
]
