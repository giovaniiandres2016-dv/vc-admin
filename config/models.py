from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from zoneinfo import ZoneInfo
from config.database import Base

def hora_colombia():
    """Devuelve la hora actual en Colombia sin zona horaria adjunta para la base de datos."""
    return datetime.now(ZoneInfo("America/Bogota")).replace(tzinfo=None)

class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    rol = Column(String(20), default="COLABORADOR")  # "ADMIN" o "COLABORADOR"
    activo = Column(Boolean, default=True)
    creado_en = Column(DateTime, default=hora_colombia)


class Cliente(Base):
    __tablename__ = "clientes"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)
    documento = Column(String(20), unique=True, nullable=True)
    telefono = Column(String(20), nullable=True)
    email = Column(String(100), nullable=True)
    ciudad = Column(String(50), nullable=True)
    direccion = Column(String(150), nullable=True)
    notas = Column(Text, nullable=True)
    creado_en = Column(DateTime, default=hora_colombia)

    ventas = relationship("Venta", back_populates="cliente")


class Producto(Base):
    __tablename__ = "productos"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(200), nullable=False)
    categoria = Column(String(50), nullable=True)
    marca = Column(String(50), nullable=True)
    referencia = Column(String(50), nullable=True)
    color = Column(String(50), nullable=True)
    talla = Column(String(20), nullable=True)
    codigo = Column(String(50), unique=True, nullable=True)
    precio = Column(Float, nullable=False)  # Precio de venta
    precio_costo = Column(Float, default=0.0)  # Precio en que nos sale
    stock = Column(Integer, default=0)
    creado_en = Column(DateTime, default=hora_colombia)


class Venta(Base):
    __tablename__ = "ventas"

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    total = Column(Float, nullable=False)
    metodo_pago = Column(String(50), nullable=False)
    estado = Column(String(30), default="COMPLETADA")  # "COMPLETADA", "SOLICITADA_ANULACION", "ANULADA"
    
    # Auditoría
    motivo_anulacion = Column(Text, nullable=True)
    anulado_por_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    fecha_anulacion = Column(DateTime, nullable=True)
    
    fecha_venta = Column(DateTime, default=hora_colombia)

    # Relaciones
    cliente = relationship("Cliente", back_populates="ventas")
    usuario_registro = relationship("Usuario", foreign_keys=[usuario_id])
    usuario_anulo = relationship("Usuario", foreign_keys=[anulado_por_id])
    detalles = relationship("DetalleVenta", back_populates="venta", cascade="all, delete-orphan")


class DetalleVenta(Base):
    __tablename__ = "detalles_venta"

    id = Column(Integer, primary_key=True, index=True)
    venta_id = Column(Integer, ForeignKey("ventas.id"), nullable=False)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    cantidad = Column(Integer, nullable=False)
    precio_unitario = Column(Float, nullable=False)
    subtotal = Column(Float, nullable=False)

    venta = relationship("Venta", back_populates="detalles")
    producto = relationship("Producto")