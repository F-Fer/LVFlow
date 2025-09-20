from typing import Optional

from pydantic import BaseModel, ConfigDict


class OfferCreate(BaseModel):
    doc_name: str


class OfferOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    doc_name: str


class ProdGroupCreate(BaseModel):
    group_nr: Optional[str] = None
    title: str
    page_from: Optional[int] = None
    page_to: Optional[int] = None
    offer_id: int


class ProdGroupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    group_nr: Optional[str] = None
    title: str
    page_from: Optional[int] = None
    page_to: Optional[int] = None
    offer_id: int


class ProdVariantCreate(BaseModel):
    var_nr: Optional[str] = None
    short_text: str
    long_text: Optional[str] = None
    count: Optional[int] = None
    page_from: Optional[int] = None
    page_to: Optional[int] = None
    group_id: int


class ProdVariantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    var_nr: Optional[str] = None
    short_text: str
    long_text: Optional[str] = None
    count: Optional[int] = None
    page_from: Optional[int] = None
    page_to: Optional[int] = None
    group_id: int


class ComponentCreate(BaseModel):
    description: str


class ComponentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    description: str


class ProdVariantComponentCreate(BaseModel):
    prod_variant_id: int
    component_id: int
    count: Optional[int] = None


class ProdVariantComponentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    prod_variant_id: int
    component_id: int
    count: Optional[int] = None

