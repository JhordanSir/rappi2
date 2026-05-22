from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from core.database import Base


class Rol(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(50), unique=True, nullable=False)

    usuarios = relationship("Usuario", back_populates="rol")
    permisos = relationship("Permiso", back_populates="rol", cascade="all, delete-orphan")


class Permiso(Base):
    __tablename__ = "permisos"

    id = Column(Integer, primary_key=True, index=True)
    rol_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)
    recurso = Column(String(50), nullable=False)
    accion = Column(String(20), nullable=False)

    __table_args__ = (
        UniqueConstraint("rol_id", "recurso", "accion", name="uq_permisos_rol_recurso_accion"),
    )

    rol = relationship("Rol", back_populates="permisos")
