# -*- coding: utf-8 -*-
import os
from datetime import datetime
from typing import List, Optional
import io
import unicodedata
import pandas as pd
from fastapi import FastAPI, Request, Form, Depends, status, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import or_, extract, func
from starlette.middleware.base import BaseHTTPMiddleware
import bcrypt

from config.database import SessionLocal, engine, Base
from config.models import Usuario, Cliente, Producto, Venta, DetalleVenta

# Crear directorios necesarios
os.makedirs("static/css", exist_ok=True)
os.makedirs("static/img", exist_ok=True)
os.makedirs("templates", exist_ok=True)

# Crear tablas en la base de datos
Base.metadata.create_all(bind=engine)

app = FastAPI(title="VC Admin")
app.add_middleware(SessionMiddleware, secret_key="vc_admin_secret_key_clean")

# --- MIDDLEWARE ANTI-CACHÉ (Evita navegación hacia atrás post-logout) ---
class NoCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

app.add_middleware(NoCacheMiddleware)

# Montaje correcto de archivos estáticos
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
templates.env.filters["cop"] = lambda val: f"${int(round(float(val))):,}".replace(",", ".") if val is not None else "$0"

# --- DEPENDENCIA DE BASE DE DATOS ---

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- LISTA OFICIAL DE CATEGORÍAS VC ADMIN ---
CATEGORIAS_OFICIALES = [
    "Sudadera premium",
    "Sudadera multimarca",
    "Pantaloneta premium",
    "Pantaloneta beisbolera",
    "Reloj 1.1",
    "Loción premium",
    "Jean premium",
    "Jean americano",
    "Buzo turco",
    "Buzo promoción",
    "Tenis originales",
    "Tenis premium",
    "Camiseta promoción",
    "Camiseta gama alta",
    "Camiseta premium",
    "Gorra original",
    "Gorra 1.1",
    "Camiseta multimarca",
    "Camiseta turca",
    "Camisa tipo polo turca",
    "Bodys económico",
    "Buzo corto americano",
    "Vestido",
    "Bodys americano",
    "Conjunto dama",
    "Conjunto hombre",
    "Conjunto premium",
    "Blusa económica",
    "Blusa premium",
    "Buzo económico",
    "Otros"
]


# --- FUNCIÓN DE GENERACIÓN DE NOMBRE ---
def generar_nombre_producto(categoria: str, referencia: str, marca: str, color: str, talla: str) -> str:
    partes = [
        str(categoria).strip() if categoria else "",
        str(referencia).strip() if referencia else "",
        str(marca).strip() if marca else "",
        str(color).strip() if color else "",
        str(talla).strip() if talla else ""
    ]
    return " ".join([p for p in partes if p])


# --- FUNCIÓN DE AUTOGENERACIÓN DE CÓDIGOS ---
def generar_codigo_automatico(categoria: str, nombre: str, referencia: str) -> str:
    cat_limpia = "".join([c for c in unicodedata.normalize('NFKD', str(categoria)) if not unicodedata.combining(c)]).upper()
    cat_code = cat_limpia[:3] if len(cat_limpia) >= 3 else "GEN"
    
    palabras_nombre = [w for w in str(nombre).split() if len(w) > 2]
    nom_code = "".join([w[0].upper() for w in palabras_nombre[:2]]) if palabras_nombre else "PRD"
    if len(nom_code) < 2:
        nom_code = str(nombre)[:3].upper()
        
    ref_code = "".join([c for c in str(referencia) if c.isalnum()]).upper() if referencia and str(referencia).strip() != "" else "01"
    
    return f"{cat_code}-{nom_code}-{ref_code}"


# --- INICIALIZACIÓN DE USUARIOS ---

def init_users():
    db = SessionLocal()
    
    if not db.query(Usuario).filter(Usuario.nombre == "admin").first():
        hashed_admin = bcrypt.hashpw("admin123".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        admin = Usuario(nombre="admin", email="admin@vcadmin.com", password_hash=hashed_admin, rol="ADMIN", activo=True)
        db.add(admin)
    
    if not db.query(Usuario).filter(Usuario.nombre == "colaborador").first():
        hashed_colab = bcrypt.hashpw("colab123".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        colab = Usuario(nombre="colaborador", email="colab@vcadmin.com", password_hash=hashed_colab, rol="COLABORADOR", activo=True)
        db.add(colab)

    db.commit()
    db.close()

init_users()


# --- VERIFICACIÓN DE SESIÓN Y ROLES ---

def get_current_user(request: Request):
    user = request.session.get("user")
    if not user:
        return None
    return user

def require_admin(request: Request):
    user = get_current_user(request)
    if not user or user.get("rol") != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso restringido: Esta acción requiere permisos de Administrador."
        )
    return user


# --- RUTAS PRINCIPALES Y AUTENTICACIÓN ---

@app.get("/", response_class=HTMLResponse)
async def home(request: Request, mes: Optional[str] = None, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    
    if user.get("rol") == "COLABORADOR":
        return RedirectResponse(url="/inventario", status_code=status.HTTP_303_SEE_OTHER)
    
    now = datetime.now()
    mes_actual = mes if mes else now.strftime("%Y-%m")
    
    try:
        anio_str, mes_str = mes_actual.split("-")
        anio_int, mes_int = int(anio_str), int(mes_str)
    except ValueError:
        anio_int, mes_int = now.year, now.month
        mes_actual = now.strftime("%Y-%m")

    ventas_completadas = db.query(Venta).filter(
        Venta.estado == "COMPLETADA",
        extract('year', Venta.fecha_venta) == anio_int,
        extract('month', Venta.fecha_venta) == mes_int
    ).order_by(Venta.fecha_venta.desc()).all()
    
    total_ventas_count = len(ventas_completadas)
    ingresos_totales = sum(v.total for v in ventas_completadas)
    
    costo_total_vendido = 0.0
    for venta in ventas_completadas:
        for detalle in venta.detalles:
            prod = db.query(Producto).filter(Producto.id == detalle.producto_id).first()
            if prod:
                costo_total_vendido += ((prod.precio_costo or 0.0) * detalle.cantidad)
                
    ganancia_neta = ingresos_totales - costo_total_vendido

    todos_los_productos = db.query(Producto).all()
    
    inversion_total_inventario = 0.0
    for p in todos_los_productos:
        stock_actual = p.stock if p.stock is not None else 0
        unidades_vendidas = db.query(func.sum(DetalleVenta.cantidad)).filter(
            DetalleVenta.producto_id == p.id,
            DetalleVenta.venta_id.in_(
                db.query(Venta.id).filter(Venta.estado == "COMPLETADA")
            )
        ).scalar() or 0
        costo_unitario = p.precio_costo if p.precio_costo is not None else 0.0
        inversion_total_inventario += (costo_unitario * (stock_actual + unidades_vendidas))

    stock_bajo_count = db.query(Producto).filter(Producto.stock < 2).count()

    alerta_push = None
    if not request.session.get("alerta_stock_mostrada", False):
        if stock_bajo_count > 0:
            alerta_push = "Revisa tu stock"
            request.session["alerta_stock_mostrada"] = True

    top_clientes_query = db.query(
        Cliente, 
        func.sum(Venta.total).label('total_gastado'),
        func.count(Venta.id).label('cantidad_compras')
    ).join(Venta, Venta.cliente_id == Cliente.id).filter(
        Venta.estado == "COMPLETADA",
        extract('year', Venta.fecha_venta) == anio_int,
        extract('month', Venta.fecha_venta) == mes_int
    ).group_by(Cliente.id).order_by(func.sum(Venta.total).desc()).limit(3).all()

    top_clientes = []
    for cliente, total_gastado, cantidad_compras in top_clientes_query:
        top_clientes.append({
            "nombre": cliente.nombre,
            "total_gastado": total_gastado,
            "cantidad_compras": cantidad_compras
        })

    top_productos_query = db.query(
        Producto,
        func.sum(DetalleVenta.cantidad).label('total_vendido'),
        func.sum(DetalleVenta.subtotal).label('ingresos_generados')
    ).join(DetalleVenta, DetalleVenta.producto_id == Producto.id)\
     .join(Venta, Venta.id == DetalleVenta.venta_id)\
     .filter(
        Venta.estado == "COMPLETADA",
        extract('year', Venta.fecha_venta) == anio_int,
        extract('month', Venta.fecha_venta) == mes_int
    ).group_by(Producto.id).order_by(func.sum(DetalleVenta.cantidad).desc()).limit(5).all()

    top_productos = []
    for producto, total_vendido, ingresos_generados in top_productos_query:
        top_productos.append({
            "nombre": producto.nombre,
            "marca": producto.marca,
            "total_vendido": total_vendido,
            "ingresos_generados": ingresos_generados
        })

    ventas_pendientes_anulacion = db.query(Venta).filter(Venta.estado == "SOLICITADA_ANULACION").all()

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "user": user,
            "active_page": "dashboard",
            "total_ventas_count": total_ventas_count,
            "ingresos_totales": ingresos_totales,
            "ganancia_neta": ganancia_neta,
            "inversion_mes": inversion_total_inventario,
            "stock_bajo": stock_bajo_count,
            "mes_actual": mes_actual,
            "ultimas_ventas": ventas_completadas[:5],
            "top_clientes": top_clientes,
            "top_productos": top_productos,
            "ventas_pendientes_anulacion": ventas_pendientes_anulacion,
            "alerta_push": alerta_push
        }
    )

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if get_current_user(request):
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": None}
    )

@app.post("/login", response_class=HTMLResponse)
async def login_post(
    request: Request, 
    username: str = Form(...), 
    password: str = Form(...), 
    db: Session = Depends(get_db)
):
    usuario = db.query(Usuario).filter(Usuario.nombre == username, Usuario.activo == True).first()
    
    if usuario and bcrypt.checkpw(password.encode('utf-8'), usuario.password_hash.encode('utf-8')):
        request.session["user"] = {
            "id": usuario.id,
            "nombre": usuario.nombre,
            "rol": usuario.rol
        }
        request.session["alerta_stock_mostrada"] = False
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": "Credenciales incorrectas o usuario inactivo."}
    )

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return HTMLResponse(content="", status_code=204)


# --- MÓDULO DE CLIENTES ---

@app.get("/clientes", response_class=HTMLResponse)
async def listar_clientes(request: Request, q: Optional[str] = None, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    query = db.query(Cliente)
    if q and q.strip():
        search_term = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Cliente.nombre.ilike(search_term),
                Cliente.documento.ilike(search_term),
                Cliente.telefono.ilike(search_term)
            )
        )

    clientes_raw = query.order_by(Cliente.nombre.asc()).all()

    clientes = []
    for c in clientes_raw:
        total_compras = db.query(Venta).filter(Venta.cliente_id == c.id).count()
        clientes.append({
            "id": c.id,
            "nombre": c.nombre,
            "documento": c.documento,
            "telefono": c.telefono,
            "email": c.email,
            "ciudad": c.ciudad,
            "total_compras": total_compras
        })

    return templates.TemplateResponse(
        request=request,
        name="clientes.html",
        context={
            "user": user,
            "clientes": clientes,
            "busqueda": q,
            "active_page": "clientes"
        }
    )

@app.get("/clientes/nuevo", response_class=HTMLResponse)
async def vista_nuevo_cliente(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    return templates.TemplateResponse(
        request=request,
        name="cliente_nuevo.html",
        context={"user": user, "cliente": None, "active_page": "clientes", "error": None}
    )

@app.get("/clientes/exportar-excel")
async def exportar_clientes_excel(
    request: Request, 
    fecha_inicio: Optional[str] = None, 
    fecha_fin: Optional[str] = None, 
    db: Session = Depends(get_db)
):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    query = db.query(Cliente)
    
    if fecha_inicio and fecha_fin:
        try:
            dt_inicio = datetime.strptime(fecha_inicio, "%Y-%m-%d")
            dt_fin = datetime.strptime(fecha_fin, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            query = query.filter(Cliente.creado_en >= dt_inicio, Cliente.creado_en <= dt_fin)
        except ValueError:
            pass

    clientes_raw = query.all()
    
    data = []
    for c in clientes_raw:
        total_compras = db.query(Venta).filter(Venta.cliente_id == c.id).count()
        data.append({
            "Nombre": c.nombre,
            "Documento": c.documento or 'N/A',
            "Teléfono": c.telefono or 'N/A',
            "Email": c.email or 'N/A',
            "Ciudad": c.ciudad or 'N/A',
            "Dirección": c.direccion or 'N/A',
            "Total Compras": total_compras,
            "Notas": c.notas or 'N/A',
            "Fecha Registro": c.creado_en.strftime('%Y-%m-%d %H:%M') if hasattr(c, 'creado_en') and c.creado_en else 'N/A'
        })
    
    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Reporte Clientes')
    output.seek(0)
    
    filename = f"reporte_clientes_{fecha_inicio}_al_{fecha_fin}.xlsx" if fecha_inicio and fecha_fin else "reporte_clientes_general.xlsx"
    
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.post("/clientes/guardar")
async def guardar_cliente(
    request: Request,
    nombre: str = Form(...),
    documento: Optional[str] = Form(None),
    telefono: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    ciudad: Optional[str] = Form(None),
    direccion: Optional[str] = Form(None),
    notas: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    if documento and documento.strip():
        cliente_existente = db.query(Cliente).filter(Cliente.documento == documento.strip()).first()
        if cliente_existente:
            return templates.TemplateResponse(
                request=request,
                name="cliente_nuevo.html",
                context={
                    "user": user, 
                    "cliente": None, 
                    "active_page": "clientes",
                    "error": "Ya existe un cliente registrado con este número de documento."
                }
            )

    nuevo_cliente = Cliente(
        nombre=nombre.strip(),
        documento=documento.strip() if documento and documento.strip() else None,
        telefono=telefono.strip() if telefono and telefono.strip() else None,
        email=email.strip() if email and email.strip() else None,
        ciudad=ciudad.strip() if ciudad and ciudad.strip() else None,
        direccion=direccion.strip() if direccion and direccion.strip() else None,
        notas=notas.strip() if notas and notas.strip() else None
    )
    db.add(nuevo_cliente)
    db.commit()

    return RedirectResponse(url="/clientes", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/clientes/{cliente_id}", response_class=HTMLResponse)
async def detalle_cliente(cliente_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    cliente = db.query(Cliente).filter(Cliente.id == cliente_id).first()
    if not cliente:
        return RedirectResponse(url="/clientes", status_code=status.HTTP_303_SEE_OTHER)

    historial_ventas = db.query(Venta).filter(Venta.cliente_id == cliente_id).order_by(Venta.fecha_venta.desc()).all()
    total_historico = sum(v.total for v in historial_ventas if v.estado == "COMPLETADA")

    return templates.TemplateResponse(
        request=request,
        name="cliente_detalle.html",
        context={
            "user": user,
            "cliente": cliente,
            "historial_ventas": historial_ventas,
            "total_historico": total_historico,
            "active_page": "clientes"
        }
    )

@app.get("/clientes/{cliente_id}/editar", response_class=HTMLResponse)
async def vista_editar_cliente(cliente_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    cliente = db.query(Cliente).filter(Cliente.id == cliente_id).first()
    if not cliente:
        return RedirectResponse(url="/clientes", status_code=status.HTTP_303_SEE_OTHER)

    return templates.TemplateResponse(
        request=request,
        name="cliente_nuevo.html",
        context={"user": user, "cliente": cliente, "active_page": "clientes", "error": None}
    )

@app.post("/clientes/{cliente_id}/actualizar")
async def actualizar_cliente(
    cliente_id: int,
    request: Request,
    nombre: str = Form(...),
    documento: Optional[str] = Form(None),
    telefono: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    ciudad: Optional[str] = Form(None),
    direccion: Optional[str] = Form(None),
    notas: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    cliente = db.query(Cliente).filter(Cliente.id == cliente_id).first()
    if cliente:
        if documento and documento.strip():
            duplicado = db.query(Cliente).filter(Cliente.documento == documento.strip(), Cliente.id != cliente_id).first()
            if duplicado:
                return templates.TemplateResponse(
                    request=request,
                    name="cliente_nuevo.html",
                    context={
                        "user": user, 
                        "cliente": cliente, 
                        "active_page": "clientes",
                        "error": "Ya existe otro cliente registrado con este mismo documento."
                    }
                )

        cliente.nombre = nombre.strip()
        cliente.documento = documento.strip() if documento and documento.strip() else None
        cliente.telefono = telefono.strip() if telefono and telefono.strip() else None
        cliente.email = email.strip() if email and email.strip() else None
        cliente.ciudad = ciudad.strip() if ciudad and ciudad.strip() else None
        cliente.direccion = direccion.strip() if direccion and direccion.strip() else None
        cliente.notas = notas.strip() if notas and notas.strip() else None
        db.commit()

    return RedirectResponse(url=f"/clientes/{cliente_id}", status_code=status.HTTP_303_SEE_OTHER)


# --- MÓDULO DE VENTAS ---

@app.get("/ventas", response_class=HTMLResponse)
async def listar_ventas(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    ventas = db.query(Venta).order_by(Venta.fecha_venta.desc()).all()
    
    return templates.TemplateResponse(
        request=request,
        name="ventas.html",
        context={"user": user, "ventas": ventas, "filtro": "todas", "active_page": "ventas"}
    )

@app.get("/ventas/nueva", response_class=HTMLResponse)
async def nueva_venta_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    clientes = db.query(Cliente).order_by(Cliente.nombre.asc()).all()
    productos = db.query(Producto).filter(Producto.stock > 0).all()

    return templates.TemplateResponse(
        request=request,
        name="venta_nueva.html",
        context={
            "user": user, 
            "clientes": clientes, 
            "productos": productos, 
            "categorias_oficiales": CATEGORIAS_OFICIALES,
            "active_page": "ventas"
        }
    )

@app.get("/ventas/exportar-excel")
async def exportar_ventas_excel(
    request: Request, 
    fecha_inicio: Optional[str] = None, 
    fecha_fin: Optional[str] = None, 
    db: Session = Depends(get_db)
):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    query = db.query(Venta)
    
    if fecha_inicio and fecha_fin:
        try:
            dt_inicio = datetime.strptime(fecha_inicio, "%Y-%m-%d")
            dt_fin = datetime.strptime(fecha_fin, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            query = query.filter(Venta.fecha_venta >= dt_inicio, Venta.fecha_venta <= dt_fin)
        except ValueError:
            pass

    ventas = query.order_by(Venta.fecha_venta.desc()).all()
    
    data = []
    for v in ventas:
        productos_str = ", ".join([f"{d.cantidad}x {d.producto.nombre if d.producto else 'Prod'}" for d in v.detalles]) if v.detalles else "N/A"
        data.append({
            "ID Venta": v.id,
            "Fecha Venta": v.fecha_venta.strftime('%Y-%m-%d %H:%M') if v.fecha_venta else 'N/A',
            "Cliente": v.cliente.nombre if v.cliente else 'Cliente General',
            "Productos": productos_str,
            "Método Pago": v.metodo_pago,
            "Estado": v.estado,
            "Total Venta": v.total
        })
    
    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Reporte Ventas')
    output.seek(0)
    
    filename = f"reporte_ventas_{fecha_inicio}_al_{fecha_fin}.xlsx" if fecha_inicio and fecha_fin else "reporte_ventas_general.xlsx"
    
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.post("/ventas/guardar")
async def guardar_venta(
    request: Request,
    cliente_id: int = Form(0),
    metodo_pago: str = Form(...),
    producto_ids: List[int] = Form(...),
    cantidades: List[int] = Form(...),
    precios_unitarios: List[float] = Form(...),
    tipos_precio: List[str] = Form(...),
    db: Session = Depends(get_db)
):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    if not producto_ids or len(producto_ids) == 0:
        raise HTTPException(status_code=400, detail="Debe seleccionar al menos un producto.")

    total_venta = 0.0
    detalles = []

    for p_id, cant, precio_mod, t_precio in zip(producto_ids, cantidades, precios_unitarios, tipos_precio):
        if cant <= 0:
            continue
        prod = db.query(Producto).filter(Producto.id == p_id).first()
        if not prod or prod.stock < cant:
            raise HTTPException(
                status_code=400, 
                detail=f"Stock insuficiente para el producto {prod.nombre if prod else 'desconocido'}."
            )
        
        subtotal = precio_mod * cant
        total_venta += subtotal
        prod.stock -= cant
        
        detalles.append(
            DetalleVenta(
                producto_id=prod.id, 
                cantidad=cant, 
                precio_unitario=precio_mod,
                tipo_precio=t_precio,
                subtotal=subtotal
            )
        )

    venta = Venta(
        cliente_id=cliente_id if cliente_id != 0 else None,
        usuario_id=user["id"],
        total=total_venta,
        metodo_pago=metodo_pago,
        estado="COMPLETADA",
        detalles=detalles
    )

    db.add(venta)
    db.commit()

    return RedirectResponse(url="/ventas", status_code=status.HTTP_303_SEE_OTHER)


# --- MÓDULO DE ANULACIONES ---

@app.get("/ventas/anulaciones", response_class=HTMLResponse)
async def gestion_anulaciones(request: Request, db: Session = Depends(get_db)):
    admin_user = require_admin(request)

    solicitudes = db.query(Venta).filter(Venta.estado == "SOLICITADA_ANULACION").all()
    anuladas = db.query(Venta).filter(Venta.estado == "ANULADA").order_by(Venta.fecha_anulacion.desc()).all()

    return templates.TemplateResponse(
        request=request,
        name="ventas_anulaciones.html",
        context={
            "user": admin_user,
            "solicitudes": solicitudes,
            "anuladas": anuladas,
            "active_page": "anulaciones"
        }
    )

@app.post("/ventas/{venta_id}/solicitar-anulacion")
async def solicitar_anulacion(venta_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    venta = db.query(Venta).filter(Venta.id == venta_id).first()
    if not venta:
        raise HTTPException(status_code=404, detail="Venta no encontrada")

    if venta.estado == "COMPLETADA":
        venta.estado = "SOLICITADA_ANULACION"
        db.commit()

    return RedirectResponse(url="/ventas", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/ventas/{venta_id}/procesar-anulacion")
async def procesar_anulacion(
    venta_id: int, 
    request: Request,
    motivo: str = Form(...), 
    db: Session = Depends(get_db)
):
    admin_user = require_admin(request)

    if not motivo or len(motivo.strip()) < 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Debe ingresar un motivo válido de anulación (mínimo 5 caracteres)."
        )

    venta = db.query(Venta).filter(Venta.id == venta_id).first()
    if not venta:
        raise HTTPException(status_code=404, detail="Venta no encontrada")

    venta.estado = "ANULADA"
    venta.motivo_anulacion = motivo.strip()
    venta.anulado_por_id = admin_user["id"]
    venta.fecha_anulacion = datetime.utcnow()
    
    if venta.detalles:
        for detalle in venta.detalles:
            prod = db.query(Producto).filter(Producto.id == detalle.producto_id).first()
            if prod:
                prod.stock += detalle.cantidad

    db.commit()

    return RedirectResponse(url="/ventas/anulaciones", status_code=status.HTTP_303_SEE_OTHER)


# --- API REGISTRO RÁPIDO DE CLIENTE ---

@app.post("/api/clientes/rapido")
async def crear_cliente_rapido(
    request: Request,
    nombre: str = Form(...),
    documento: Optional[str] = Form(None),
    telefono: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")

    if documento and documento.strip():
        existente = db.query(Cliente).filter(Cliente.documento == documento.strip()).first()
        if existente:
            return JSONResponse(
                status_code=400, 
                content={"error": "El documento ya se encuentra registrado."}
            )

    nuevo_cliente = Cliente(
        nombre=nombre.strip(),
        documento=documento.strip() if documento else None,
        telefono=telefono.strip() if telefono else None
    )
    db.add(nuevo_cliente)
    db.commit()
    db.refresh(nuevo_cliente)

    return {"status": "ok", "id": nuevo_cliente.id, "nombre": nuevo_cliente.nombre}


# --- MÓDULO DE INVENTARIO ---

@app.get("/inventario", response_class=HTMLResponse)
async def listar_inventario(request: Request, q: Optional[str] = None, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    alerta_push = request.session.pop("alerta_importacion", None)

    query = db.query(Producto)
    if q and q.strip():
        search_term = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Producto.nombre.ilike(search_term),
                Producto.codigo.ilike(search_term)
            )
        )
    productos = query.order_by(Producto.nombre.asc()).all()

    return templates.TemplateResponse(
        request=request,
        name="inventario.html",
        context={
            "user": user,
            "productos": productos,
            "busqueda": q,
            "active_page": "inventario",
            "alerta_push": alerta_push
        }
    )

@app.get("/inventario/nuevo", response_class=HTMLResponse)
async def vista_nuevo_producto(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    return templates.TemplateResponse(
        request=request,
        name="producto_nuevo.html",
        context={
            "user": user, 
            "producto": None, 
            "categorias_oficiales": CATEGORIAS_OFICIALES,
            "active_page": "inventario", 
            "error": None
        }
    )

@app.get("/api/inventario/por-codigo/{codigo}")
async def buscar_producto_por_codigo(codigo: str, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    prod = db.query(Producto).filter(Producto.codigo == codigo.strip()).first()
    if not prod:
        return {"encontrado": False}
    
    return {
        "encontrado": True,
        "nombre": prod.nombre,
        "categoria": prod.categoria,
        "marca": prod.marca,
        "referencia": prod.referencia,
        "color": prod.color,
        "talla": prod.talla,
        "precio": prod.precio,
        "precio_costo": prod.precio_costo,
        "stock": prod.stock
    }

@app.post("/inventario/guardar")
async def guardar_producto(
    request: Request,
    categoria: str = Form(...),
    marca: str = Form(...),
    referencia: str = Form(...),
    color: str = Form(...),
    talla: str = Form(...),
    codigo: Optional[str] = Form(None),
    precio: float = Form(...),
    precio_costo: float = Form(0.0),
    stock: int = Form(...),
    db: Session = Depends(get_db)
):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    if user.get("rol") not in ["ADMIN", "COLABORADOR"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: No tienes permisos para crear o modificar productos en el inventario."
        )

    nombre = generar_nombre_producto(categoria, referencia, marca, color, talla)

    codigo_limpio = codigo.strip() if codigo and codigo.strip() and codigo.strip().upper() != "S/C" else None
    producto_existente = None

    if codigo_limpio:
        producto_existente = db.query(Producto).filter(Producto.codigo == codigo_limpio).first()

    if not producto_existente:
        producto_existente = db.query(Producto).filter(
            func.lower(Producto.nombre) == nombre.strip().lower(),
            func.lower(Producto.marca) == marca.strip().lower(),
            func.lower(Producto.referencia) == referencia.strip().lower(),
            func.lower(Producto.color) == color.strip().lower(),
            func.lower(Producto.talla) == talla.strip().lower()
        ).first()

    if producto_existente:
        producto_existente.stock += stock
        producto_existente.precio = precio
        producto_existente.precio_costo = precio_costo
        producto_existente.categoria = categoria
        producto_existente.nombre = nombre
    else:
        if codigo_limpio:
            codigo_final = codigo_limpio
        else:
            codigo_final = generar_codigo_automatico(categoria, nombre, referencia)
            base_gen = codigo_final
            contador = 1
            while db.query(Producto).filter(Producto.codigo == codigo_final).first() is not None:
                codigo_final = f"{base_gen}-{contador}"
                contador += 1

        nuevo_prod = Producto(
            nombre=nombre,
            categoria=categoria,
            marca=marca.strip(),
            referencia=referencia.strip(),
            color=color.strip(),
            talla=talla.strip(),
            codigo=codigo_final,
            precio=precio,
            precio_costo=precio_costo,
            stock=stock
        )
        db.add(nuevo_prod)

    db.commit()

    return RedirectResponse(url="/inventario", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/inventario/importar")
async def importar_inventario(
    request: Request,
    archivo_excel: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    
    if user.get("rol") not in ["ADMIN", "COLABORADOR"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: No tienes permisos para importar inventario."
        )

    if not archivo_excel.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Formato de archivo inválido. Debe ser un archivo Excel (.xlsx o .xls).")
    
    try:
        contenido = await archivo_excel.read()
        
        excel_dict = pd.read_excel(io.BytesIO(contenido), sheet_name=None)
        df = None
        for sheet_name, sheet_df in excel_dict.items():
            if not sheet_df.empty and len(sheet_df.columns) > 0:
                df = sheet_df
                break
                
        if df is None or df.empty:
            raise HTTPException(status_code=400, detail="El archivo Excel no contiene hojas con datos válidos.")
        
        def normalizar_columna(col):
            if not isinstance(col, str):
                return str(col)
            nfkd = unicodedata.normalize('NFKD', col)
            sin_tilde = "".join([c for c in nfkd if not unicodedata.combining(c)])
            return sin_tilde.strip().lower()

        df.columns = [normalizar_columna(col) for col in df.columns]
        
        required_cols = ['precio', 'stock']
        for col in required_cols:
            if col not in df.columns:
                raise HTTPException(status_code=400, detail=f"Falta la columna obligatoria en el Excel: {col}")
        
        codigos_en_lote = set()

        for _, row in df.iterrows():
            precio = float(row['precio'])
            stock = int(row['stock'])
            
            categoria = str(row.get('categoria', 'Otros')) if pd.notna(row.get('categoria')) and str(row.get('categoria')).strip() != "" else 'Otros'
            marca = str(row.get('marca', '')) if pd.notna(row.get('marca')) else ''
            referencia = str(row.get('referencia', '')) if pd.notna(row.get('referencia')) else ''
            color = str(row.get('color', '')) if pd.notna(row.get('color')) else ''
            talla = str(row.get('talla', '')) if pd.notna(row.get('talla')) else ''
            precio_costo = float(row.get('precio_costo', 0.0)) if pd.notna(row.get('precio_costo')) else 0.0

            nombre = generar_nombre_producto(categoria, referencia, marca, color, talla)

            raw_codigo = row.get('codigo')
            if pd.notna(raw_codigo) and str(raw_codigo).strip() != "" and str(raw_codigo).strip().upper() != "S/C":
                codigo = str(raw_codigo).strip()
            else:
                codigo = generar_codigo_automatico(categoria, nombre, referencia)
                base_codigo = codigo
                contador = 1
                while codigo in codigos_en_lote or db.query(Producto).filter(Producto.codigo == codigo).first() is not None:
                    codigo = f"{base_codigo}-{contador}"
                    contador += 1

            codigos_en_lote.add(codigo)

            producto_existente = db.query(Producto).filter(Producto.codigo == codigo).first()
            
            if producto_existente:
                producto_existente.nombre = nombre
                producto_existente.precio = precio
                producto_existente.categoria = categoria
                producto_existente.marca = marca
                producto_existente.referencia = referencia
                producto_existente.color = color
                producto_existente.talla = talla
                producto_existente.stock += stock
            else:
                nuevo_prod = Producto(
                    codigo=codigo,
                    nombre=nombre,
                    categoria=categoria,
                    marca=marca,
                    referencia=referencia,
                    color=color,
                    talla=talla,
                    precio=precio,
                    precio_costo=precio_costo,
                    stock=stock
                )
                db.add(nuevo_prod)
        
        db.commit()

        stock_bajo_count = db.query(Producto).filter(Producto.stock <= 5).count()
        if stock_bajo_count > 0:
            request.session["alerta_importacion"] = f"¡Inventario importado con éxito! ⚠️ Atención: Hay {stock_bajo_count} producto(s) con stock crítico o agotado (5 o menos unidades)."
        else:
            request.session["alerta_importacion"] = "¡Inventario importado con éxito! Todo el stock se encuentra en niveles óptimos."

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al procesar el archivo Excel: {str(e)}")
        
    return RedirectResponse(url="/inventario", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/inventario/exportar-etiquetas")
async def exportar_etiquetas_excel(
    request: Request, 
    fecha_inicio: Optional[str] = None, 
    fecha_fin: Optional[str] = None, 
    db: Session = Depends(get_db)
):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    query = db.query(Producto)
    
    if fecha_inicio and fecha_fin:
        try:
            dt_inicio = datetime.strptime(fecha_inicio, "%Y-%m-%d")
            dt_fin = datetime.strptime(fecha_fin, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            query = query.filter(Producto.creado_en >= dt_inicio, Producto.creado_en <= dt_fin)
        except ValueError:
            pass

    productos = query.all()
    
    cambios_realizados = False
    codigos_existentes = {p.codigo for p in productos if p.codigo and p.codigo != "S/C"}

    data = []
    for p in productos:
        codigo_actual = p.codigo
        if not codigo_actual or codigo_actual.strip() == "" or codigo_actual.strip().upper() == "S/C":
            nuevo_gen = generar_codigo_automatico(p.categoria or "General", p.nombre, p.referencia or "")
            base_gen = nuevo_gen
            contador = 1
            while nuevo_gen in codigos_existentes:
                nuevo_gen = f"{base_gen}-{contador}"
                contador += 1
            
            p.codigo = nuevo_gen
            codigos_existentes.add(nuevo_gen)
            cambios_realizados = True

        cantidad = p.stock if p.stock is not None else 0
        precio_costo = p.precio_costo if p.precio_costo is not None else 0.0
        precio_venta = p.precio if p.precio is not None else 0.0
        inversion_total = cantidad * precio_costo

        data.append({
            "Código de Producto": p.codigo,
            "Nombre del Producto": p.nombre,
            "Categoría": p.categoria or "General",
            "Marca": p.marca or "N/A",
            "Color": p.color or "N/A",
            "Talla": p.talla or "N/A",
            "Referencia": p.referencia or "N/A",
            "Cantidad": cantidad,
            "Precio de Compra Unitario": precio_costo,
            "Precio de Venta": precio_venta,
            "Inversión Total": inversion_total
        })

    if cambios_realizados:
        db.commit()
    
    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Reporte Inversión')
    output.seek(0)
    
    filename = f"reporte_inversion_{fecha_inicio}_al_{fecha_fin}.xlsx" if fecha_inicio and fecha_fin else "reporte_inversion_inventario.xlsx"
    
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.get("/inventario/{producto_id}/editar", response_class=HTMLResponse)
async def vista_editar_producto(producto_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    producto = db.query(Producto).filter(Producto.id == producto_id).first()
    if not producto:
        return RedirectResponse(url="/inventario", status_code=status.HTTP_303_SEE_OTHER)

    return templates.TemplateResponse(
        request=request,
        name="producto_nuevo.html",
        context={
            "user": user, 
            "producto": producto, 
            "categorias_oficiales": CATEGORIAS_OFICIALES,
            "active_page": "inventario", 
            "error": None
        }
    )

@app.post("/inventario/{producto_id}/actualizar")
async def actualizar_producto(
    producto_id: int,
    request: Request,
    categoria: str = Form(...),
    marca: str = Form(...),
    referencia: str = Form(...),
    color: str = Form(...),
    talla: str = Form(...),
    precio: float = Form(...),
    precio_costo: float = Form(0.0),
    stock: int = Form(...),
    db: Session = Depends(get_db)
):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    producto = db.query(Producto).filter(Producto.id == producto_id).first()
    if not producto:
        return RedirectResponse(url="/inventario", status_code=status.HTTP_303_SEE_OTHER)

    if user.get("rol") not in ["ADMIN", "COLABORADOR"]:
        return templates.TemplateResponse(
            request=request,
            name="producto_nuevo.html",
            context={
                "user": user, 
                "producto": producto, 
                "categorias_oficiales": CATEGORIAS_OFICIALES,
                "active_page": "inventario",
                "error": "Acceso denegado: No cuentas con permisos para modificar registros del inventario."
            }
        )

    producto.nombre = generar_nombre_producto(categoria, referencia, marca, color, talla)
    producto.categoria = categoria
    producto.marca = marca.strip()
    producto.referencia = referencia.strip()
    producto.color = color.strip()
    producto.talla = talla.strip()
    producto.precio = precio
    producto.precio_costo = precio_costo
    producto.stock = stock
    db.commit()

    return RedirectResponse(url="/inventario", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/inventario/{producto_id}/eliminar-directo")
async def eliminar_producto_directo(
    producto_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    require_admin(request)
    producto = db.query(Producto).filter(Producto.id == producto_id).first()
    if producto:
        db.delete(producto)
        db.commit()
    return RedirectResponse(url="/inventario", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/inventario/{producto_id}/procesar-solicitud-eliminacion")
async def procesar_solicitud_eliminacion(
    producto_id: int,
    request: Request,
    accion: str = Form(...),
    db: Session = Depends(get_db)
):
    require_admin(request)
    producto = db.query(Producto).filter(Producto.id == producto_id).first()
    if producto:
        if hasattr(producto, "solicitud_eliminacion"):
            if accion == "aprobar":
                db.delete(producto)
            elif accion == "rechazar":
                producto.solicitud_eliminacion = False
                producto.motivo_eliminacion = None
            db.commit()
    return RedirectResponse(url="/inventario", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/ventas/{venta_id}/factura", response_class=HTMLResponse)
async def ver_factura(venta_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    venta = db.query(Venta).filter(Venta.id == venta_id).first()
    if not venta:
        raise HTTPException(status_code=404, detail="Venta no encontrada")

    return templates.TemplateResponse(
        request=request,
        name="factura.html",
        context={"user": user, "venta": venta}
    )

@app.post("/ventas/{id}/rechazar-anulacion")
async def rechazar_anulacion(id: int, request: Request, db: Session = Depends(get_db)):
    admin_user = require_admin(request)
    venta = db.query(Venta).filter(Venta.id == id).first()
    if venta and venta.estado == "SOLICITADA_ANULACION":
        venta.estado = "COMPLETADA"
    db.commit()
    return RedirectResponse(url="/ventas/anulaciones", status_code=status.HTTP_303_SEE_OTHER)


# --- MANEJADORES GLOBALES DE ERRORES ---

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    if request.url.path.startswith("/api/"):
        return JSONResponse(status_code=422, content={"error": "Datos inválidos en el formulario."})
    
    return templates.TemplateResponse(
        request=request,
        name="error.html",
        context={
            "codigo": 422,
            "detalle": "Por favor verifica los datos ingresados. Hay campos obligatorios vacíos o con formato incorrecto."
        },
        status_code=422
    )

@app.exception_handler(IntegrityError)
async def sqlalchemy_integrity_handler(request: Request, exc: IntegrityError):
    mensaje_amigable = "Ya existe un registro en el sistema con estos mismos datos (por ejemplo, el número de documento o código ya se encuentra registrado)."
    
    if request.url.path.startswith("/api/"):
        return JSONResponse(status_code=400, content={"error": mensaje_amigable})
        
    return templates.TemplateResponse(
        request=request,
        name="error.html",
        context={
            "codigo": 400,
            "detalle": mensaje_amigable
        },
        status_code=400
    )

@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.detail}
        )
    
    return templates.TemplateResponse(
        request=request,
        name="error.html",
        context={
            "codigo": exc.status_code,
            "detalle": exc.detail
        },
        status_code=exc.status_code
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            status_code=500,
            content={"error": str(exc)}
        )
        
    return templates.TemplateResponse(
        request=request,
        name="error.html",
        context={
            "codigo": 500,
            "detalle": f"Ocurrió un error inesperado en el sistema: {str(exc)}"
        },
        status_code=500
    )