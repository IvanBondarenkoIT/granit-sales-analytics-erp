"""Read-only Firebird SQL for Stage 2 ETL (via firebird-db-proxy)."""
from __future__ import annotations

import re

from django.conf import settings

SALES_TYPES = (1, 2, 3, 5)
# DGVDT.TYP 0 = sales invoice; rows with SZID duplicate receipts already loaded from STORZAKAZDT.
INVOICE_TYPES = (0,)
STOCK_CHUNK = 80
_SAFE_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def sales_store_field() -> str:
    field = getattr(settings, "ETL_SALES_STORE_FIELD", "STORGRPID") or "STORGRPID"
    if not _SAFE_IDENT.match(field):
        raise ValueError(f"Unsafe ETL_SALES_STORE_FIELD: {field!r}")
    return field


def product_param_id() -> int:
    return int(getattr(settings, "ETL_PRODUCT_PARAM_ID", 2))


def sql_stores() -> str:
    return "SELECT ID, NAME FROM STORGRP"


def sql_warehouses() -> str:
    return "SELECT ID, NAME FROM STORLIST"


def sql_warehouse_groups() -> str:
    return "SELECT STORID, GRPID FROM STORGRPREF"


def sql_product_groups() -> str:
    return "SELECT ID, NAME, PARENTID FROM GOODSGROUPS"


def sql_products() -> str:
    return """
        SELECT G.ID AS PRODUCT_ID,
               G.NAME AS PRODUCT_NAME,
               G.OWNER AS GROUP_ID
        FROM GOODS G
    """


def sql_product_parameters() -> tuple[str, list[int]]:
    param_id = product_param_id()
    sql = """
        SELECT R.GOODSID AS PRODUCT_ID,
               R.PARAMID AS PARAM_ID,
               R.FIXVAL AS PARAM_VALUE_ID,
               P.NAME AS PARAM_NAME,
               V.STRVAL AS PARAM_VALUE_LABEL
        FROM GDSPARAMGDSREF R
        JOIN GOODS G ON G.ID = R.GOODSID
        JOIN GDSPARAMPRM P ON P.ID = R.PARAMID
        LEFT JOIN GDSPARAMVAL V ON V.ID = R.FIXVAL
        WHERE R.PARAMID = ?
    """
    return sql, [param_id]


_CLIENT_COLUMNS = """
        SELECT O.ID AS CLIENT_ID,
               COALESCE(NULLIF(TRIM(O.FULLNAME), ''), O.NAME) AS CLIENT_NAME,
               O.PHONE AS PHONE,
               TRIM(O.NAME) AS CARD_RAW
        FROM ORGN O
"""


def sql_clients() -> str:
    return _CLIENT_COLUMNS


def sql_clients_by_ids(ids: list[int]) -> tuple[str, list[int]]:
    placeholders = ",".join(["?"] * len(ids))
    return f"{_CLIENT_COLUMNS} WHERE O.ID IN ({placeholders})", ids


def sql_clients_by_cards(cards: list[str]) -> tuple[str, list[str]]:
    placeholders = ",".join(["?"] * len(cards))
    return f"{_CLIENT_COLUMNS} WHERE TRIM(O.NAME) IN ({placeholders})", cards


def sql_sales_day() -> tuple[str, list]:
    store_field = sales_store_field()
    sql = f"""
        SELECT D.ID AS SALE_ID,
               GD.ID AS LINE_ID,
               D.DAT_ AS SALE_DATE,
               D.{store_field} AS STORE_ID,
               D.ORGNID AS CLIENT_ID,
               GD.GODSID AS PRODUCT_ID,
               COALESCE(NULLIF(GD.RSQUANT, 0), GD.SOURCE, 0) AS QTY,
               COALESCE(NULLIF(GD.RSQUANT, 0), GD.SOURCE, 0) * GD.PRICE AS AMOUNT
        FROM STORZAKAZDT D
        JOIN STORZDTGDS GD ON D.ID = GD.SZID
        WHERE D.CSDTKTHBID IN ({",".join(["?"] * len(SALES_TYPES))})
          AND D.DAT_ >= ? AND D.DAT_ < ?
    """
    return sql, list(SALES_TYPES)


def sql_invoices_day() -> tuple[str, list]:
    sql = f"""
        SELECT H.ID AS SALE_ID,
               G.ID AS LINE_ID,
               H.DAT_ AS SALE_DATE,
               COALESCE(H.STOR, H.STORID) AS WAREHOUSE_ID,
               H.NAMEID AS CLIENT_ID,
               COALESCE(G.GDSKEY, K.GDSKEY) AS PRODUCT_ID,
               COALESCE(G.QUANT, 0) AS QTY,
               COALESCE(G.QUANT, 0) * COALESCE(G.PRICE, 0) AS AMOUNT
        FROM DGVDT H
        JOIN GDDDT G ON G.DGVKEY = H.ID
        LEFT JOIN GDDKT K ON K.ID = G.GDDKEY
        WHERE H.TYP IN ({",".join(["?"] * len(INVOICE_TYPES))})
          AND H.SZID IS NULL
          AND H.DAT_ >= ? AND H.DAT_ < ?
    """
    return sql, list(INVOICE_TYPES)


def sql_stock_chunk(ids: list[int]) -> tuple[str, list[int]]:
    placeholders = ",".join(["?"] * len(ids))
    sql = f"""
        SELECT K.GDSKEY AS PRODUCT_ID,
               COALESCE(SUM(K.QUANT), 0) AS CURRENT_STOCK
        FROM GDDKT K
        WHERE K.GDSKEY IN ({placeholders})
          AND K.QUANT IS NOT NULL
        GROUP BY K.GDSKEY
    """
    return sql, ids
