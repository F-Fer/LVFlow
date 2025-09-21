from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..db import get_db_session
from ..services import ingest_from_json, ingest_from_pdf
from ..models import Offer, ProdGroup, ProdVariant, ProdVariantComponent, Component


router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("index.html", {"request": request})


@router.post("/ingest", response_class=HTMLResponse)
async def ingest_view(
    request: Request,
    offer_name: str = Form(...),
    session: AsyncSession = Depends(get_db_session),
) -> HTMLResponse:
    inserted = await ingest_from_json(session, offer_name=offer_name)
    return templates.TemplateResponse(
        "partials/ingest_result.html",
        {"request": request, "inserted": inserted},
    )


@router.post("/upload", response_class=HTMLResponse)
async def upload_view(
    request: Request,
    offer_name: str = Form(...),
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db_session),
) -> HTMLResponse:
    pdf_bytes = await file.read()
    inserted = await ingest_from_pdf(session, offer_name=offer_name, pdf_bytes=pdf_bytes)
    return templates.TemplateResponse(
        "partials/ingest_result.html",
        {"request": request, "inserted": inserted},
    )


@router.get("/offers", response_class=HTMLResponse)
async def offers_list(request: Request, session: AsyncSession = Depends(get_db_session)) -> HTMLResponse:
    offers = (await session.execute(select(Offer).order_by(Offer.id.desc()))).scalars().all()
    return templates.TemplateResponse("offers/list.html", {"request": request, "offers": offers})


@router.get("/offers/{offer_id}", response_class=HTMLResponse)
async def offer_detail(offer_id: int, request: Request, session: AsyncSession = Depends(get_db_session)) -> HTMLResponse:
    offer = await session.get(Offer, offer_id)
    if not offer:
        return templates.TemplateResponse("offers/detail.html", {"request": request, "offer": None, "groups": [], "matrix": {}})

    groups = (await session.execute(select(ProdGroup).where(ProdGroup.offer_id == offer_id).order_by(ProdGroup.group_nr))).scalars().all()

    # Build variant-component matrix per group
    detail = []
    for g in groups:
        variants = (await session.execute(select(ProdVariant).where(ProdVariant.group_id == g.id).order_by(ProdVariant.var_nr))).scalars().all()
        # collect components used by these variants
        var_ids = [v.id for v in variants]
        links = (await session.execute(select(ProdVariantComponent).where(ProdVariantComponent.prod_variant_id.in_(var_ids)))).scalars().all()
        comp_ids = sorted({lnk.component_id for lnk in links})
        components = []
        if comp_ids:
            components = (await session.execute(select(Component).where(Component.id.in_(comp_ids)).order_by(Component.id))).scalars().all()
        # matrix counts
        counts: dict[tuple[int, int], int] = {}
        for lnk in links:
            key = (lnk.prod_variant_id, lnk.component_id)
            counts[key] = (counts.get(key) or 0) + (lnk.count or 1)
        detail.append({
            "group": g,
            "variants": variants,
            "components": components,
            "counts": counts,
        })

    return templates.TemplateResponse("offers/detail.html", {"request": request, "offer": offer, "detail": detail})

