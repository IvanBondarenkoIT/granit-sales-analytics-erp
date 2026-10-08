"""Product picker dialogs for promos: Granit groups tree and website categories tree."""
from __future__ import annotations

from collections import defaultdict

from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import render

from core.models import GranitWpMapping, Product, ProductGroup, SiteCategory, SiteProduct

PAGE_SIZE = 100
GROUP_ALL_LIMIT = 2000


def _descendant_ids(pairs, root_id: int) -> list[int]:
    children = defaultdict(list)
    for pk, parent_id in pairs:
        if parent_id is not None:
            children[parent_id].append(pk)
    out, stack = [], [root_id]
    while stack:
        pk = stack.pop()
        out.append(pk)
        stack.extend(children.get(pk, []))
    return out


def granit_group_ids(root_id: int) -> list[int]:
    return _descendant_ids(ProductGroup.objects.values_list("id", "parent_id"), root_id)


def site_category_ids(root_id: int) -> list[int]:
    return _descendant_ids(SiteCategory.objects.values_list("id", "parent_id"), root_id)


def site_names_by_granit(granit_ids) -> dict[int, str]:
    wp_by_granit = defaultdict(list)
    for wp_id, gid in GranitWpMapping.objects.filter(granit_id__in=list(granit_ids)).values_list(
        "wp_product_id", "granit_id"
    ):
        wp_by_granit[gid].append(wp_id)
    names = dict(
        SiteProduct.objects.filter(
            wp_product_id__in=[w for ws in wp_by_granit.values() for w in ws]
        ).values_list("wp_product_id", "name")
    )
    return {
        gid: ", ".join(names[w] for w in wps if w in names)
        for gid, wps in wp_by_granit.items()
        if any(w in names for w in wps)
    }


def product_items(products) -> list[dict]:
    """Rows for the selected-products table and picker JSON."""
    products = list(products)
    site_names = site_names_by_granit(p.granit_id for p in products)
    return [
        {
            "pk": p.pk,
            "name": p.name,
            "granit_id": p.granit_id,
            "site": site_names.get(p.granit_id, ""),
        }
        for p in products
    ]


def _int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _offset(request) -> int:
    return max(_int(request.GET.get("offset")) or 0, 0)


# --- Granit -----------------------------------------------------------------


def _granit_queryset(request):
    q = (request.GET.get("q") or "").strip()
    group = _int(request.GET.get("group"))
    qs = Product.objects.select_related("group").order_by("name")
    if not request.GET.get("inactive"):
        qs = qs.filter(is_active=True)
    if group and request.GET.get("direct"):
        qs = qs.filter(group_id=group)
    elif group:
        qs = qs.filter(group_id__in=granit_group_ids(group))
    if q:
        cond = Q(name__icontains=q)
        if q.isdigit():
            cond |= Q(granit_id=int(q))
        qs = qs.filter(cond)
    return qs, group, q


def picker_granit_groups(request):
    parent = _int(request.GET.get("parent"))
    groups = (
        ProductGroup.objects.filter(parent_id=parent)
        .annotate(n_children=Count("children", distinct=True))
        .order_by("name")
    )
    return render(request, "promos/picker/_granit_groups.html", {"groups": groups})


def picker_granit_products(request):
    qs, group, q = _granit_queryset(request)
    offset = _offset(request)
    if not group and not q:
        return render(request, "promos/picker/_rows.html", {"hint": True, "kind": "granit"})
    total = qs.count()
    page = list(qs[offset : offset + PAGE_SIZE])
    return render(
        request,
        "promos/picker/_rows.html",
        {
            "kind": "granit",
            "items": product_items(page),
            "total": total,
            "offset": offset,
            "next_offset": offset + PAGE_SIZE if offset + PAGE_SIZE < total else None,
            "group": ProductGroup.objects.filter(pk=group).first() if group else None,
            "append": offset > 0,
        },
    )


def picker_granit_all(request):
    qs, group, q = _granit_queryset(request)
    if not group and not q:
        return JsonResponse({"items": []})
    return JsonResponse({"items": product_items(qs[:GROUP_ALL_LIMIT])})


# --- Website ----------------------------------------------------------------


def _site_queryset(request):
    q = (request.GET.get("q") or "").strip()
    category = _int(request.GET.get("category"))
    qs = SiteProduct.objects.order_by("name")
    if category:
        qs = qs.filter(categories__in=site_category_ids(category)).distinct()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(sku__icontains=q) | Q(wp_product_id=q))
    return qs, category, q


def _site_items(site_products) -> list[dict]:
    site_products = list(site_products)
    mapping = dict(
        GranitWpMapping.objects.filter(
            wp_product_id__in=[s.wp_product_id for s in site_products]
        ).values_list("wp_product_id", "granit_id")
    )
    products = {p.granit_id: p for p in Product.objects.filter(granit_id__in=mapping.values())}
    items = []
    for s in site_products:
        product = products.get(mapping.get(s.wp_product_id))
        items.append(
            {
                "pk": product.pk if product else None,
                "name": product.name if product else "",
                "granit_id": product.granit_id if product else mapping.get(s.wp_product_id),
                "site": s.name,
                "site_price": s.effective_sale_price,
                "regular_price": s.regular_price,
                "in_stock": s.in_stock,
            }
        )
    return items


def picker_site_categories(request):
    parent = _int(request.GET.get("parent"))
    cats = (
        SiteCategory.objects.filter(parent_id=parent)
        .annotate(n_children=Count("children", distinct=True))
        .order_by("name")
    )
    return render(request, "promos/picker/_site_categories.html", {"categories": cats})


def picker_site_products(request):
    qs, category, q = _site_queryset(request)
    offset = _offset(request)
    if not category and not q:
        return render(request, "promos/picker/_rows.html", {"hint": True, "kind": "site"})
    total = qs.count()
    page = qs[offset : offset + PAGE_SIZE]
    return render(
        request,
        "promos/picker/_rows.html",
        {
            "kind": "site",
            "items": _site_items(page),
            "total": total,
            "offset": offset,
            "next_offset": offset + PAGE_SIZE if offset + PAGE_SIZE < total else None,
            "group": SiteCategory.objects.filter(pk=category).first() if category else None,
            "append": offset > 0,
        },
    )


def picker_site_all(request):
    qs, category, q = _site_queryset(request)
    if not category and not q:
        return JsonResponse({"items": []})
    items = [i for i in _site_items(qs[:GROUP_ALL_LIMIT]) if i["pk"]]
    seen, unique = set(), []
    for item in items:
        if item["pk"] not in seen:
            seen.add(item["pk"])
            unique.append({k: item[k] for k in ("pk", "name", "granit_id", "site")})
    return JsonResponse({"items": unique})
