from pathlib import Path
from typing import Any
import logging
import os
import io
import json
import dotenv
import asyncio

import pdfplumber
from openai import AsyncOpenAI

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Base, Component, Offer, ProdGroup, ProdVariant, ProdVariantComponent
from .db import SessionLocal

from .utils.extraction import get_group_extraction_prompt, get_variant_extraction_prompt, get_required_components_prompt

dotenv.load_dotenv()

logger = logging.getLogger("uvicorn.error")

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

async def ingest_from_pdf(
    session: AsyncSession,
    offer_name: str,
    pdf_bytes: bytes,
    progress_cb=None,
    num_concurrent_groups: int = 4,
) -> dict[str, int]:
    """Extract structure from a PDF and persist via existing JSON ingestion.

    Steps (MVP):
      1) Save uploaded PDF to data/uploads for traceability
      2) Extract plain text from pages using pdfplumber
      3) Use OpenAI to extract product groups
      4) Use OpenAI to extract product variants for each product group
      5) Use OpenAI to extract required components for each product group
      6) Write temporary JSON files matching the existing ingestion contract
      7) Reuse ingest_from_json to insert into Postgres
    """
    # 1) Save PDF
    upload_dir = Path("data/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = upload_dir / f"{offer_name.replace(' ', '_')}.pdf"
    # Offload sync file write to a thread
    await asyncio.to_thread(pdf_path.write_bytes, pdf_bytes)
    logger.info(f"Saved uploaded PDF to {pdf_path}")
    if progress_cb:
        progress_cb("save_pdf", 5, "PDF saved")

    # 2) Extract texts per page
    def _extract_texts(data: bytes) -> list[str]:
        texts_local: list[str] = []
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                if page_text.strip():
                    texts_local.append(page_text)
        return texts_local

    texts: list[str] = await asyncio.to_thread(_extract_texts, pdf_bytes)

    full_text = "\n".join(texts)
    if progress_cb:
        progress_cb("extract_text", 15, f"Extracted {len(texts)} pages")
    logger.info(f"Extracted {len(texts)} pages of text from PDF")

    # 2a) Page offset (if needed later for variants)
    import re
    page_offset = 0
    for i in range(len(texts)):
        if re.search(r"Seite\s*:\s*\d+", texts[i]):
            page_offset = i
            break
    logger.info(f"Detected page_offset={page_offset}")
    if progress_cb:
        progress_cb("detect_offset", 20, f"Page offset {page_offset}")

    # Setup OpenAI client
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "":
        raise RuntimeError("OPENAI_API_KEY is not set")

    client = AsyncOpenAI(api_key=api_key)
    logger.info("Setup OpenAI client")

    # Utilities
    def _safe_json(text: str) -> dict[str, Any]:
        try:
            return json.loads(text)
        except Exception:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                return json.loads(text[start:end + 1])
            raise

    async def _get_or_create_offer(doc_name: str) -> Offer:
        existing = await session.scalar(select(Offer).where(Offer.doc_name == doc_name))
        if existing:
            return existing
        offer = Offer(doc_name=doc_name)
        session.add(offer)
        await session.flush()
        return offer

    async def _upsert_group(offer_id: int, group_nr: str | None, title: str, page_from: int | None, page_to: int | None) -> ProdGroup:
        stmt = select(ProdGroup).where(ProdGroup.offer_id == offer_id)
        if group_nr is None:
            stmt = stmt.where(ProdGroup.group_nr.is_(None))
        else:
            stmt = stmt.where(ProdGroup.group_nr == group_nr)
        existing = await session.scalar(stmt)
        if existing:
            existing.title = title
            existing.page_from = page_from
            existing.page_to = page_to
            return existing
        group = ProdGroup(offer_id=offer_id, group_nr=group_nr, title=title, page_from=page_from, page_to=page_to)
        session.add(group)
        await session.flush()
        return group

    async def _upsert_variant(group_id: int, var_nr: str | None, short_text: str, long_text: str | None, page_from: int | None, page_to: int | None) -> ProdVariant:
        stmt = select(ProdVariant).where(ProdVariant.group_id == group_id)
        if var_nr is None:
            stmt = stmt.where(ProdVariant.var_nr.is_(None))
        else:
            stmt = stmt.where(ProdVariant.var_nr == var_nr)
        existing = await session.scalar(stmt)
        if existing:
            existing.short_text = short_text
            existing.long_text = long_text
            existing.page_from = page_from
            existing.page_to = page_to
            return existing
        pv = ProdVariant(group_id=group_id, var_nr=var_nr, short_text=short_text, long_text=long_text, page_from=page_from, page_to=page_to)
        session.add(pv)
        await session.flush()
        return pv

    async def _get_or_create_component(description: str) -> Component:
        existing = await session.scalar(select(Component).where(Component.description == description))
        if existing:
            return existing
        comp = Component(description=description)
        session.add(comp)
        await session.flush()
        return comp

    async def _link_variant_component(variant_id: int, component_id: int) -> None:
        exists = await session.scalar(
            select(ProdVariantComponent).where(
                ProdVariantComponent.prod_variant_id == variant_id,
                ProdVariantComponent.component_id == component_id,
            )
        )
        if exists:
            return
        session.add(ProdVariantComponent(prod_variant_id=variant_id, component_id=component_id))

    # 3) Extract product groups
    group_prompt = get_group_extraction_prompt(full_text)
    g_resp = await client.responses.create(model="gpt-5", input=group_prompt)
    groups_payload = _safe_json(g_resp.output_text)
    groups = groups_payload.get("groups", [])
    logger.info(f"Extracted {len(groups)} product groups")
    if progress_cb:
        progress_cb("groups", 40, f"{len(groups)} groups")

    offer = await _get_or_create_offer(offer_name)
    # Persist filename of stored PDF on the offer for later embedding
    offer.pdf_filename = pdf_path.name
    # Persist the offer early so it survives if later steps fail
    await session.commit()
    if progress_cb:
        progress_cb("offer", 30, f"Offer {offer.id} created")
    logger.info(f"Created offer {offer.id}")

    # Concurrency: process groups in parallel using isolated DB sessions
    sem = asyncio.Semaphore(max(1, num_concurrent_groups))

    async def process_one(idx: int, g: dict[str, Any]) -> dict[str, int]:
        async with sem:
            # New session per group to avoid cross-task state
            async with SessionLocal() as s:
                # Upsert group in this session
                group_nr = g.get("group_no")
                title = g.get("title") or ""
                g_from = g.get("page_from")
                g_to = g.get("page_to")

                # Query existing
                stmt = select(ProdGroup).where(ProdGroup.offer_id == offer.id)
                stmt = stmt.where(ProdGroup.group_nr == group_nr) if group_nr is not None else stmt.where(ProdGroup.group_nr.is_(None))
                existing = await s.scalar(stmt)
                if existing:
                    existing.title = title
                    existing.page_from = g_from
                    existing.page_to = g_to
                    group_obj = existing
                else:
                    group_obj = ProdGroup(offer_id=offer.id, group_nr=group_nr, title=title, page_from=g_from, page_to=g_to)
                    s.add(group_obj)
                    await s.flush()

                if progress_cb:
                    progress_cb("group_upsert", 45, f"Group {idx}/{len(groups)}")
                logger.info(f"Upserted group {group_obj.id}")
                await s.commit()

                # Slice text for this group
                start_idx = max(0, page_offset + (g_from or 1) - 1)
                end_idx = page_offset + (g_to or (g_from or 1)) + 1
                group_text = "\n".join(texts[start_idx:end_idx])

                # Variants extraction
                v_prompt = get_variant_extraction_prompt(group_nr or "", title) + "\n\nInput:\n" + group_text
                v_resp = await client.responses.create(model="gpt-5", input=v_prompt)
                variants_payload = _safe_json(v_resp.output_text)
                variants = variants_payload.get("variants", [])
                if progress_cb:
                    progress_cb("variants", 60, f"{len(variants)} variants in group {idx}")
                logger.info(f"Extracted {len(variants)} product variants")

                variant_nos: list[str] = []
                variant_titles: list[str] = []
                variant_texts: list[str] = []
                variant_nr_to_id: dict[str, int] = {}
                inserted_variants_local = 0
                for v in variants:
                    var_nr = v.get("variant_no")
                    short_text = v.get("title") or ""
                    long_text = v.get("text")
                    v_from = v.get("page_from")
                    v_to = v.get("page_to")

                    # Upsert variant in s
                    stmt_v = select(ProdVariant).where(ProdVariant.group_id == group_obj.id)
                    stmt_v = stmt_v.where(ProdVariant.var_nr == var_nr) if var_nr is not None else stmt_v.where(ProdVariant.var_nr.is_(None))
                    existing_v = await s.scalar(stmt_v)
                    if existing_v:
                        existing_v.short_text = short_text
                        existing_v.long_text = long_text
                        existing_v.page_from = v_from
                        existing_v.page_to = v_to
                        pv = existing_v
                    else:
                        pv = ProdVariant(group_id=group_obj.id, var_nr=var_nr, short_text=short_text, long_text=long_text, page_from=v_from, page_to=v_to)
                        s.add(pv)
                        await s.flush()
                    inserted_variants_local += 1
                    if var_nr:
                        variant_nos.append(var_nr)
                        variant_titles.append(short_text)
                        variant_texts.append(long_text or "")
                        variant_nr_to_id[var_nr] = pv.id
                await s.commit()

                # Components
                inserted_components_local = 0
                inserted_links_local = 0
                if variant_nos:
                    c_prompt = get_required_components_prompt(group_nr or "", title, variant_nos, variant_titles, variant_texts)
                    c_resp = await client.responses.create(model="gpt-5", input=c_prompt)
                    comps_payload = _safe_json(c_resp.output_text)
                    comps = comps_payload.get("components", [])
                    logger.info(f"Extracted {len(comps)} required components")
                    for comp in comps:
                        description = str(comp.get("component_description", "")).strip()
                        if not description:
                            continue
                        # get or create component
                        existing_c = await s.scalar(select(Component).where(Component.description == description))
                        if existing_c:
                            comp_obj = existing_c
                        else:
                            comp_obj = Component(description=description)
                            s.add(comp_obj)
                            await s.flush()
                        inserted_components_local += 1
                        for vno in comp.get("variant_nos", []) or []:
                            vid = variant_nr_to_id.get(vno)
                            if not vid:
                                continue
                            exists_link = await s.scalar(
                                select(ProdVariantComponent).where(
                                    ProdVariantComponent.prod_variant_id == vid,
                                    ProdVariantComponent.component_id == comp_obj.id,
                                )
                            )
                            if not exists_link:
                                s.add(ProdVariantComponent(prod_variant_id=vid, component_id=comp_obj.id))
                                inserted_links_local += 1
                if progress_cb:
                    progress_cb("components", 80, f"Components linked for group {idx}")
                await s.commit()
                if progress_cb:
                    progress_cb("commit_group", 90, f"Committed group {idx}")

                return {
                    "groups": 1,
                    "variants": inserted_variants_local,
                    "components": inserted_components_local,
                    "variant_components": inserted_links_local,
                }

    tasks = [process_one(idx, g) for idx, g in enumerate(groups, start=1)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    inserted_groups = inserted_variants = inserted_components = inserted_links = 0
    for r in results:
        if isinstance(r, Exception):
            logger.exception("Group task failed", exc_info=r)
            continue
        inserted_groups += r.get("groups", 0)
        inserted_variants += r.get("variants", 0)
        inserted_components += r.get("components", 0)
        inserted_links += r.get("variant_components", 0)

    await session.commit()
    if progress_cb:
        progress_cb("commit", 95, "Committed to DB")

    return {
        "offers": 1,
        "groups": inserted_groups,
        "variants": inserted_variants,
        "components": inserted_components,
        "variant_components": inserted_links,
    }