from django.urls import path

from sales import views

urlpatterns = [
    path("", views.sales_explorer, name="sales_explorer"),
    path("matrix/", views.sales_matrix, name="sales_matrix"),
    path("matrix/xlsx/", views.sales_matrix_xlsx, name="sales_matrix_xlsx"),
    path("matrix/edit/", views.sales_matrix_edit, name="sales_matrix_edit"),
    path("matrix/sg/<int:pk>/", views.sales_matrix_sg, name="sales_matrix_sg"),
    path("matrix/group/<int:granit_id>/", views.sales_matrix_group, name="sales_matrix_group"),
    path("orders/<int:sale_id>/", views.sales_receipt, name="sales_receipt"),
]
