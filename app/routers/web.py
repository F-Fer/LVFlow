from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db_session
from ..services import ingest_from_json


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

