from django.urls import path, register_converter

from sales import reconcile_views, views


class SignedIntConverter:
    regex = "-?[0-9]+"

    def to_python(self, value):
        return int(value)

    def to_url(self, value):
        return str(value)


register_converter(SignedIntConverter, "sint")

urlpatterns = [
    path("reconcile/", reconcile_views.reconcile_overview, name="sales_reconcile"),
    path("reconcile/refresh/", reconcile_views.reconcile_refresh, name="sales_reconcile_refresh"),
    path("reconcile/<str:month>/", reconcile_views.reconcile_month, name="sales_reconcile_month"),
    path(
        "reconcile/<str:month>/store/<int:store_id>/",
        reconcile_views.reconcile_documents,
        name="sales_reconcile_docs",
    ),
    path("", views.sales_explorer, name="sales_explorer"),
    path("matrix/", views.sales_matrix, name="sales_matrix"),
    path("matrix/xlsx/", views.sales_matrix_xlsx, name="sales_matrix_xlsx"),
    path("matrix/edit/", views.sales_matrix_edit, name="sales_matrix_edit"),
    path("matrix/sg/<int:pk>/", views.sales_matrix_sg, name="sales_matrix_sg"),
    path("matrix/group/<sint:granit_id>/", views.sales_matrix_group, name="sales_matrix_group"),
    path("orders/<int:sale_id>/", views.sales_receipt, name="sales_receipt"),
]
