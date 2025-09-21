from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Base, Component, Offer, ProdGroup, ProdVariant, ProdVariantComponent


async def init_db(session: AsyncSession) -> None:
    async with session.bind.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def ingest_from_json(session: AsyncSession, offer_name: str, base_dir: str = "data") -> dict[str, int]:
    import json

    base_path = Path(base_dir)
    groups_json: dict[str, Any] = json.loads((base_path / "product_groups.json").read_text())
    variants_json: dict[str, Any] = json.loads((base_path / "product_variants.json").read_text())
    required_components_path = base_path / "required_components.json"
    required_components_json: dict[str, Any] | None = None
    if required_components_path.exists():
        required_components_json = json.loads(required_components_path.read_text())

    offer = Offer(doc_name=offer_name)
    session.add(offer)
    await session.flush()

    group_no_to_id: dict[str, int] = {}
    for g in groups_json.get("groups", []):
        group = ProdGroup(
            group_nr=g.get("group_no"),
            title=g["title"],
            page_from=g.get("page_from"),
            page_to=g.get("page_to"),
            offer_id=offer.id,
        )
        session.add(group)
        await session.flush()
        if g.get("group_no"):
            group_no_to_id[g["group_no"]] = group.id

    inserted_variants = 0
    for v in variants_json.get("variants", []):
        var_nr = v.get("variant_no")
        short_text = v.get("title") or ""
        long_text = v.get("text")
        page_from = v.get("page_from")
        page_to = v.get("page_to")

        group_nr = None
        if isinstance(var_nr, str) and "." in var_nr:
            group_nr = ".".join(var_nr.split(".")[:2])
        result_group_id = group_no_to_id.get(group_nr)
        if not result_group_id:
            first_group_id = await session.scalar(select(ProdGroup.id).where(ProdGroup.offer_id == offer.id).limit(1))
            result_group_id = int(first_group_id or 0)

        variant = ProdVariant(
            var_nr=var_nr,
            short_text=short_text,
            long_text=long_text,
            page_from=page_from,
            page_to=page_to,
            group_id=result_group_id,
        )
        session.add(variant)
        inserted_variants += 1

    await session.flush()

    inserted_components = 0
    inserted_links = 0
    if required_components_json:
        desc_to_component_id: dict[str, int] = {}
        for c in required_components_json.get("components", []):
            description = c["component_description"].strip()
            comp_id = desc_to_component_id.get(description)
            if not comp_id:
                comp = Component(description=description)
                session.add(comp)
                await session.flush()
                desc_to_component_id[description] = comp.id
                inserted_components += 1

            variant_nos = c.get("variant_nos", [])
            if not variant_nos:
                continue
            result = await session.execute(select(ProdVariant).where(ProdVariant.var_nr.in_(variant_nos)))
            variants = result.scalars().all()
            for v in variants:
                link = ProdVariantComponent(
                    prod_variant_id=v.id,
                    component_id=desc_to_component_id[description],
                )
                session.add(link)
                inserted_links += 1

    await session.commit()

    return {
        "offers": 1,
        "groups": len(group_no_to_id) or 0,
        "variants": inserted_variants,
        "components": inserted_components,
        "variant_components": inserted_links,
    }

