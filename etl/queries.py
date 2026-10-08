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


def sql_last_cost_chunk(ids: list[int]) -> tuple[str, list[int]]:
    """Last incoming price: newest arrival card (DGVKT.TYP=0), else newest card with a price.

    GDDKT.QUANT is the remaining batch quantity, so sold-out batches still carry the cost.
    """
    placeholders = ",".join(["?"] * len(ids))
    sql = f"""
        SELECT g.ID AS PRODUCT_ID,
               CAST(COALESCE(
                   (SELECT FIRST 1 d2.PRICE
                    FROM GDDKT d2
                    JOIN DGVKT k2 ON k2.ID = d2.DGVKEY
                    WHERE d2.GDSKEY = g.ID AND d2.PRICE > 0 AND k2.TYP = 0
                    ORDER BY k2.DAT_ DESC, d2.ID DESC),
                   (SELECT FIRST 1 d3.PRICE
                    FROM GDDKT d3
                    LEFT JOIN DGVKT k3 ON k3.ID = d3.DGVKEY
                    WHERE d3.GDSKEY = g.ID AND d3.PRICE > 0
                    ORDER BY COALESCE(k3.DAT_, d3.DATEREAL) DESC, d3.ID DESC)
               ) AS NUMERIC(15, 2)) AS LAST_COST,
               CAST(COALESCE(SUM(CASE WHEN d.QUANT > 0 THEN d.QUANT ELSE 0 END), 0)
                    AS NUMERIC(15, 3)) AS STOCK_QTY
        FROM GOODS g
        LEFT JOIN GDDKT d ON d.GDSKEY = g.ID
        WHERE g.ID IN ({placeholders})
        GROUP BY g.ID
    """
    return sql, ids


def sql_avg_cost_90d_chunk(ids: list[int], date_from, date_to) -> tuple[str, list]:
    """Simple average of arrival card prices (DGVKT.TYP=0) in [date_from, date_to)."""
    placeholders = ",".join(["?"] * len(ids))
    sql = f"""
        SELECT d.GDSKEY AS PRODUCT_ID,
               CAST(SUM(d.PRICE) / COUNT(*) AS NUMERIC(15, 2)) AS AVG_COST
        FROM GDDKT d
        JOIN DGVKT k ON k.ID = d.DGVKEY
        WHERE d.GDSKEY IN ({placeholders})
          AND d.PRICE > 0
          AND k.TYP = 0
          AND k.DAT_ >= ? AND k.DAT_ < ?
        GROUP BY d.GDSKEY
    """
    return sql, list(ids) + [date_from, date_to]
