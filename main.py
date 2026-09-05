import os
from datetime import datetime
from typing import List, Optional
import io
import pandas as pd
from fastapi import FastAPI, Request, Form, Depends, status, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import or_, extract, func
import bcrypt

from config.database import SessionLocal, engine, Base
from config.models import Usuario, Cliente, Producto, Venta, DetalleVenta

# Crear directorios necesarios
os.makedirs("static/css", exist_ok=True)
os.makedirs("static/img", exist_ok=True)
os.makedirs("templates", exist_ok=True)

# Crear tablas en la base de datos
Base.metadata.create_all(bind=engine)

app = FastAPI(title="VC-Admin")
app.add_middleware(SessionMiddleware, secret_key="vc_admin_secret_key_clean")

# Montaje correcto de archivos estáticos
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# --- DEPENDENCIA DE BASE DE DATOS ---

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- INICIALIZACIÓN DE USUARIOS ---

def init_users():
    db = SessionLocal()
    
    # Crear Admin si no existe
    if not db.query(Usuario).filter(Usuario.nombre == "admin").first():
        hashed_admin = bcrypt.hashpw("admin123".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        admin = Usuario(nombre="admin", email="admin@vcadmin.com", password_hash=hashed_admin, rol="ADMIN", activo=True)
        db.add(admin)
    
    # Crear Colaborador si no existe
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
    
    costo_total = 0.0
    for venta in ventas_completadas:
        for detalle in venta.detalles:
            prod = db.query(Producto).filter(Producto.id == detalle.producto_id).first()
            if prod:
                costo_total += (prod.precio_costo * detalle.cantidad)
                
    ganancia_neta = ingresos_totales - costo_total
    margen_porcentaje = (ganancia_neta / ingresos_totales * 100) if ingresos_totales > 0 else 0.0

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
            "margen_porcentaje": margen_porcentaje,
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
        context={"user": user, "clientes": clientes, "productos": productos, "active_page": "ventas"}
    )

@app.post("/ventas/guardar")
async def guardar_venta(
    request: Request,
    cliente_id: int = Form(0),
    metodo_pago: str = Form(...),
    producto_ids: List[int] = Form(...),
    cantidades: List[int] = Form(...),
    db: Session = Depends(get_db)
):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    if not producto_ids or len(producto_ids) == 0:
        raise HTTPException(status_code=400, detail="Debe seleccionar al menos un producto.")

    total_venta = 0.0
    detalles = []

    for p_id, cant in zip(producto_ids, cantidades):
        if cant <= 0:
            continue
        prod = db.query(Producto).filter(Producto.id == p_id).first()
        if not prod or prod.stock < cant:
            raise HTTPException(
                status_code=400, 
                detail=f"Stock insuficiente para el producto {prod.nombre if prod else 'desconocido'}."
            )
        
        subtotal = prod.precio * cant
        total_venta += subtotal
        prod.stock -= cant
        
        detalles.append(
            DetalleVenta(
                producto_id=prod.id, 
                cantidad=cant, 
                precio_unitario=prod.precio, 
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
        context={"user": user, "producto": None, "active_page": "inventario", "error": None}
    )

@app.post("/inventario/guardar")
async def guardar_producto(
    request: Request,
    nombre: str = Form(...),
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

    if codigo and codigo.strip():
        prod_existente = db.query(Producto).filter(Producto.codigo == codigo.strip()).first()
        if prod_existente:
            return templates.TemplateResponse(
                request=request,
                name="producto_nuevo.html",
                context={
                    "user": user, 
                    "producto": None, 
                    "active_page": "inventario",
                    "error": "Ya existe un producto registrado con este mismo código."
                }
            )

    nuevo_prod = Producto(
        nombre=nombre.strip(),
        categoria=categoria,
        marca=marca.strip(),
        referencia=referencia.strip(),
        color=color.strip(),
        talla=talla.strip(),
        codigo=codigo.strip() if codigo and codigo.strip() else None,
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
        df = pd.read_excel(io.BytesIO(contenido))
        
        df.columns = [str(col).strip().lower() for col in df.columns]
        
        required_cols = ['nombre', 'precio', 'stock']
        for col in required_cols:
            if col not in df.columns:
                raise HTTPException(status_code=400, detail=f"Falta la columna obligatoria en el Excel: {col}")
        
        for _, row in df.iterrows():
            codigo = str(row.get('codigo', 'S/C')) if pd.notna(row.get('codigo')) else 'S/C'
            nombre = str(row['nombre'])
            precio = float(row['precio'])
            stock = int(row['stock'])
            
            categoria = str(row.get('categoria', 'General')) if pd.notna(row.get('categoria')) else 'General'
            marca = str(row.get('marca', '')) if pd.notna(row.get('marca')) else ''
            referencia = str(row.get('referencia', '')) if pd.notna(row.get('referencia')) else ''
            color = str(row.get('color', '')) if pd.notna(row.get('color')) else ''
            talla = str(row.get('talla', '')) if pd.notna(row.get('talla')) else ''
            precio_costo = float(row.get('precio_costo', 0.0)) if pd.notna(row.get('precio_costo')) else 0.0

            producto_existente = db.query(Producto).filter(Producto.codigo == codigo).first() if codigo != 'S/C' else None
            
            if producto_existente:
                producto_existente.nombre = nombre
                producto_existente.precio = precio
                producto_existente.stock += stock
            else:
                nuevo_prod = Producto(
                    codigo=codigo if codigo != 'S/C' else None,
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
        context={"user": user, "producto": producto, "active_page": "inventario", "error": None}
    )

@app.post("/inventario/{producto_id}/actualizar")
async def actualizar_producto(
    producto_id: int,
    request: Request,
    nombre: str = Form(...),
    categoria: str = Form(...),
    marca: str = Form(...),
    referencia: str = Form(...),
    color: str = Form(...),
    talla: str = Form(...),
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
                "active_page": "inventario",
                "error": "Acceso denegado: No cuentas con permisos para modificar registros del inventario."
            }
        )

    producto.nombre = nombre.strip()
    producto.categoria = categoria
    producto.marca = marca.strip()
    producto.referencia = referencia.strip()
    producto.color = color.strip()
    producto.talla = talla.strip()
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
async def rechazar_anulacion(id: int, db: Session = Depends(get_db)):
    admin_user = require_admin(request) if 'request' in locals() else None # O ajusta según tu control de sesión
    venta = db.query(Venta).filter(Venta.id == id).first()
    if venta and venta.estado == "SOLICITADA_ANULACION":
        venta.estado = "COMPLETADA" # O el estado original que prefieras para devolverla a activa
        db.commit()
    return RedirectResponse(url="/ventas/anulaciones", status_code=status.HTTP_303_SEE_OTHER)