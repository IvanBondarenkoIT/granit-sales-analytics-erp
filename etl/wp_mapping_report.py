"""Report Granit↔Woo mapping gaps (orphan Sheets ids / unmapped site products)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from openpyxl import Workbook

from core.models import GranitWpMapping, Product, SiteProduct


@dataclass(frozen=True)
class MappingWithoutSite:
    wp_product_id: str
    granit_id: int
    granit_name: str


@dataclass(frozen=True)
class SiteWithoutMapping:
    wp_product_id: str
    site_name: str
    sku: str


@dataclass(frozen=True)
class MappingGapsReport:
    mapping_without_site: list[MappingWithoutSite]
    site_without_mapping: list[SiteWithoutMapping]


def build_mapping_gaps_report() -> MappingGapsReport:
    mapped_wp = {m.wp_product_id: m.granit_id for m in GranitWpMapping.objects.all()}
    site_wp = {
        s.wp_product_id: s
        for s in SiteProduct.objects.all().only("wp_product_id", "name", "sku")
    }
    granit_names = {
        p.granit_id: p.name
        for p in Product.objects.filter(granit_id__in=set(mapped_wp.values())).only(
            "granit_id", "name"
        )
    }

    mapping_without_site = [
        MappingWithoutSite(
            wp_product_id=wp,
            granit_id=gid,
            granit_name=granit_names.get(gid, ""),
        )
        for wp, gid in sorted(mapped_wp.items(), key=lambda item: (item[1], item[0]))
        if wp not in site_wp
    ]
    site_without_mapping = [
        SiteWithoutMapping(
            wp_product_id=wp,
            site_name=site.name,
            sku=site.sku or "",
        )
        for wp, site in sorted(site_wp.items(), key=lambda item: item[1].name.lower())
        if wp not in mapped_wp
    ]
    return MappingGapsReport(
        mapping_without_site=mapping_without_site,
        site_without_mapping=site_without_mapping,
    )


def write_mapping_gaps_xlsx(report: MappingGapsReport, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    orphan = wb.active
    orphan.title = "mapping_without_site"
    orphan.append(["wp_product_id", "granit_id", "granit_name"])
    for row in report.mapping_without_site:
        orphan.append([row.wp_product_id, row.granit_id, row.granit_name])

    unmapped = wb.create_sheet("site_without_mapping")
    unmapped.append(["wp_product_id", "site_name", "sku"])
    for row in report.site_without_mapping:
        unmapped.append([row.wp_product_id, row.site_name, row.sku])

    wb.save(path)
    return path
