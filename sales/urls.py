from django.urls import path

from sales import views

urlpatterns = [
    path("", views.sales_explorer, name="sales_explorer"),
    path("orders/<int:sale_id>/", views.sales_receipt, name="sales_receipt"),
]
