from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, declarative_base, mapped_column, relationship


Base = declarative_base()


class Offer(Base):
    __tablename__ = "offer"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    doc_name: Mapped[str] = mapped_column(String(255), nullable=False)
    pdf_filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    groups: Mapped[list["ProdGroup"]] = relationship(back_populates="offer", cascade="all, delete-orphan")


class ProdGroup(Base):
    __tablename__ = "prod_group"
    __table_args__ = (UniqueConstraint("offer_id", "group_nr", name="uq_group_per_offer"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_nr: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    page_from: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    page_to: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    offer_id: Mapped[int] = mapped_column(ForeignKey("offer.id", ondelete="CASCADE"), nullable=False)

    offer: Mapped[Offer] = relationship(back_populates="groups")
    variants: Mapped[list["ProdVariant"]] = relationship(back_populates="group", cascade="all, delete-orphan")


class ProdVariant(Base):
    __tablename__ = "prod_variant"
    __table_args__ = (UniqueConstraint("group_id", "var_nr", name="uq_variant_per_group"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    var_nr: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    short_text: Mapped[str] = mapped_column(String(255), nullable=False)
    long_text: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    page_from: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    page_to: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("prod_group.id", ondelete="CASCADE"), nullable=False)

    group: Mapped[ProdGroup] = relationship(back_populates="variants")
    components: Mapped[list["ProdVariantComponent"]] = relationship(back_populates="variant", cascade="all, delete-orphan")


class Component(Base):
    __tablename__ = "component"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    description: Mapped[str] = mapped_column(String, nullable=False)

    variants: Mapped[list["ProdVariantComponent"]] = relationship(back_populates="component", cascade="all, delete-orphan")


class ProdVariantComponent(Base):
    __tablename__ = "prod_variant_component"
    __table_args__ = (UniqueConstraint("prod_variant_id", "component_id", name="uq_variant_component"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prod_variant_id: Mapped[int] = mapped_column(ForeignKey("prod_variant.id", ondelete="CASCADE"), nullable=False)
    component_id: Mapped[int] = mapped_column(ForeignKey("component.id", ondelete="CASCADE"), nullable=False)
    count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    variant: Mapped[ProdVariant] = relationship(back_populates="components")
    component: Mapped[Component] = relationship(back_populates="variants")

