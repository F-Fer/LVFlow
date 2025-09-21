from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db_session
from ..services import ingest_from_json, ingest_from_pdf


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

