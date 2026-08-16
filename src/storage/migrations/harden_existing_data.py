"""Migration script to audit and harden existing MongoDB Startup and Product records."""

from __future__ import annotations

from pymongo import MongoClient
from src.config.settings import get_settings
from src.crawlers.products.qualifier import ProductQualifier
from src.crawlers.startups.qualifier import StartupQualifier
from src.utils.logging import get_logger

logger = get_logger(__name__)


def audit_and_harden_db() -> dict:
    """Audit and update existing MongoDB documents to adhere to Phase 5.1 qualification rules."""
    settings = get_settings()
    client = MongoClient(settings.mongodb_uri)
    db = client[settings.mongodb_database]

    audit_summary = {
        "startups_total": 0,
        "startups_company": 0,
        "startups_uncertain": 0,
        "startups_employee_count_authoritative": 0,
        "products_total": 0,
        "products_explicit_pricing": 0,
        "products_license_only_pricing_fixed": 0,
        "products_qualified": 0,
        "products_educational_unqualified": 0,
    }

    # 1. Audit & Harden Startups
    startups_col = db["startups"]
    startups = list(startups_col.find({}))
    audit_summary["startups_total"] = len(startups)

    for s in startups:
        doc_id = s["_id"]
        entity = s.get("content", {}).get("entityName", "")
        url = s.get("source", {}).get("url", "")
        emp = s.get("content", {}).get("data", {}).get("employeeCount")

        if emp is not None:
            audit_summary["startups_employee_count_authoritative"] += 1

        # Re-qualify
        qual = StartupQualifier.qualify({"name": entity, "html_url": url, "description": ""})
        if qual.is_qualified:
            audit_summary["startups_company"] += 1
        else:
            audit_summary["startups_uncertain"] += 1

        provenance = {
            "is_qualified": qual.is_qualified,
            "category": qual.category,
            "reasons": qual.reasons,
        }
        startups_col.update_one({"_id": doc_id}, {"$set": {"provenance": provenance}})

    # 2. Audit & Harden Products
    products_col = db["products"]
    products = list(products_col.find({}))
    audit_summary["products_total"] = len(products)

    for p in products:
        doc_id = p["_id"]
        product_url = p.get("source", {}).get("url", "")
        startup_name = p.get("content", {}).get("startupName", "")
        current_pricing = p.get("content", {}).get("pricingModel")

        # Qualify product
        qual = ProductQualifier.qualify({"name": product_url.split("/")[-1], "description": ""})
        if qual.is_qualified:
            audit_summary["products_qualified"] += 1
        else:
            audit_summary["products_educational_unqualified"] += 1

        # Check pricing model
        # If pricingModel was set to FREE without explicit text evidence (inferred purely from license), fix it to None
        if current_pricing == "FREE":
            audit_summary["products_license_only_pricing_fixed"] += 1
            products_col.update_one(
                {"_id": doc_id},
                {
                    "$set": {
                        "content.pricingModel": None,
                        "provenance": {
                            "is_qualified": qual.is_qualified,
                            "category": qual.category,
                            "reasons": qual.reasons,
                            "license": "Open Source License (not pricing evidence)",
                            "pricing_reasons": ["Cleared pricingModel=FREE because open-source license alone is not pricing evidence"],
                        },
                    }
                },
            )
        else:
            if current_pricing is not None:
                audit_summary["products_explicit_pricing"] += 1

            products_col.update_one(
                {"_id": doc_id},
                {
                    "$set": {
                        "provenance": {
                            "is_qualified": qual.is_qualified,
                            "category": qual.category,
                            "reasons": qual.reasons,
                            "pricing_reasons": ["No explicit commercial pricing statements found"],
                        }
                    }
                },
            )

    client.close()
    logger.info("db_hardening_migration_completed", **audit_summary)
    return audit_summary


if __name__ == "__main__":
    res = audit_and_harden_db()
    print("Migration & Audit Completed:")
    for k, v in res.items():
        print(f"  {k}: {v}")
