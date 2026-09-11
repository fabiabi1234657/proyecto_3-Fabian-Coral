import io
import os
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file, abort, session
from src.models.model_productos import Producto
from src.models.models_imagenes import ImagenProducto
from src.services.image_storage_service import ImageStorageService, ImageValidationError
from src.services.auth_service import AuthService, login_required

productos_c = Blueprint('productos_c', __name__, template_folder='../templates')

# =========================================================================
# RUTAS DE AUTENTICACIÓN
# =========================================================================

@productos_c.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form.get('usuario', '').strip()
        contrasena = request.form.get('contrasena', '').strip()

        if AuthService.verificar_credenciales(usuario, contrasena):
            session['usuario'] = usuario
            flash(f'¡Bienvenido de nuevo, {usuario}!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('productos_c.obtener_productos'))
        else:
            flash('Usuario o contraseña incorrectos.', 'danger')

    return render_template('login.html')

@productos_c.route('/logout')
def logout():
    session.clear()
    flash('Has cerrado sesión exitosamente.', 'info')
    return redirect(url_for('productos_c.login'))

# =========================================================================
# RUTAS CRUD PROTEGIDAS
# =========================================================================

@productos_c.route('/')
@login_required
def index():
    return redirect(url_for('productos_c.obtener_productos'))

@productos_c.route('/productos')
@login_required
def obtener_productos():
    busqueda = request.args.get('q', '').strip()
    if busqueda:
        data = Producto.buscar_productos(busqueda)
    else:
        data = Producto.leer_productos()
    return render_template('productos.html', data=data, busqueda=busqueda, usuario_actual=session.get('usuario'))

@productos_c.route('/productos/crear', methods=['POST'])
@login_required
def crear_producto():
    producto = request.form.get('producto', '').strip()
    marca = request.form.get('marca', '').strip()
    precio = request.form.get('precio', '0').strip()
    descripcion = request.form.get('descripcion', '').strip()
    url_texto = request.form.get('url', '').strip()
    archivo_imagen = request.files.get('imagen_archivo')

    if not producto or not marca or not precio:
        flash('Por favor completa los campos obligatorios (Producto, Marca, Precio).', 'danger')
        return redirect(url_for('productos_c.obtener_productos'))

    imagen_bytes = None
    imagen_mime = None
    mongo_meta = None

    # Procesar y almacenar imagen si se adjuntó archivo
    if archivo_imagen and archivo_imagen.filename != '':
        try:
            contenido = archivo_imagen.read()
            resultado_img = ImageStorageService.almacenar_imagen(
                archivo_imagen.filename,
                contenido,
                archivo_imagen.mimetype
            )
            imagen_bytes = resultado_img['mysql']['imagen']
            imagen_mime = resultado_img['mysql']['imagen_mime']
            mongo_meta = resultado_img['mongo']
        except ImageValidationError as ve:
            flash(f'Error de validación de imagen: {ve}', 'danger')
            return redirect(url_for('productos_c.obtener_productos'))
        except Exception as e:
            flash('Error al procesar el almacenamiento seguro de la imagen.', 'danger')
            return redirect(url_for('productos_c.obtener_productos'))

    try:
        nuevo_id = Producto.crear_producto(
            producto=producto,
            marca=marca,
            precio=float(precio),
            descripcion=descripcion,
            url=url_texto,
            imagen_bytes=imagen_bytes,
            imagen_mime=imagen_mime,
            mongo_meta=mongo_meta
        )
        flash(f'¡Producto "{producto}" (ID #{nuevo_id}) creado y sincronizado exitosamente!', 'success')
    except Exception as e:
        flash(f'Error al crear el producto: {e}', 'danger')

    return redirect(url_for('productos_c.obtener_productos'))

@productos_c.route('/productos/editar/<int:idproducto>', methods=['POST'])
@login_required
def editar_producto(idproducto):
    producto = request.form.get('producto', '').strip()
    marca = request.form.get('marca', '').strip()
    precio = request.form.get('precio', '0').strip()
    descripcion = request.form.get('descripcion', '').strip()
    url_texto = request.form.get('url', '').strip()
    archivo_imagen = request.files.get('imagen_archivo')

    actualizar_imagen = False
    imagen_bytes = None
    imagen_mime = None
    mongo_meta = None

    if archivo_imagen and archivo_imagen.filename != '':
        try:
            contenido = archivo_imagen.read()
            resultado_img = ImageStorageService.almacenar_imagen(
                archivo_imagen.filename,
                contenido,
                archivo_imagen.mimetype
            )
            imagen_bytes = resultado_img['mysql']['imagen']
            imagen_mime = resultado_img['mysql']['imagen_mime']
            mongo_meta = resultado_img['mongo']
            actualizar_imagen = True
        except ImageValidationError as ve:
            flash(f'Error de validación de imagen: {ve}', 'danger')
            return redirect(url_for('productos_c.obtener_productos'))
        except Exception as e:
            flash('Error al procesar la nueva imagen.', 'danger')
            return redirect(url_for('productos_c.obtener_productos'))

    try:
        Producto.actualizar_producto(
            idproducto=idproducto,
            producto=producto,
            marca=marca,
            precio=float(precio),
            descripcion=descripcion,
            url=url_texto,
            imagen_bytes=imagen_bytes,
            imagen_mime=imagen_mime,
            mongo_meta=mongo_meta,
            actualizar_imagen=actualizar_imagen
        )
        flash(f'¡Producto #{idproducto} actualizado y sincronizado en MySQL y MongoDB!', 'success')
    except Exception as e:
        flash(f'Error al actualizar el producto: {e}', 'danger')

    return redirect(url_for('productos_c.obtener_productos'))

@productos_c.route('/productos/eliminar/<int:idproducto>', methods=['POST', 'GET'])
@login_required
def eliminar_producto(idproducto):
    try:
        Producto.eliminar_producto(idproducto)
        flash(f'¡Producto #{idproducto} eliminado correctamente de ambas bases de datos y del almacenamiento!', 'warning')
    except Exception as e:
        flash(f'Error al eliminar el producto: {e}', 'danger')

    return redirect(url_for('productos_c.obtener_productos'))

# =========================================================================
# RUTAS DE IMÁGENES AUTENTICADAS (CON HEADERS DE SEGURIDAD ESTRICTOS)
# =========================================================================

@productos_c.route('/imagen/<int:idproducto>')
@login_required
def servir_imagen(idproducto):
    """
    Ruta autenticada para 'Ver imagen':
    1. Valida sesión activa.
    2. Localiza registro en MySQL o MongoDB.
    3. Descifra en memoria (io.BytesIO) sin dejar archivos temporales en disco.
    4. Envía con Cache-Control: no-store y X-Content-Type-Options: nosniff.
    """
    prod_mysql = Producto.obtener_producto_por_id(idproducto)
    doc_mongo = ImagenProducto.obtener_por_idproducto(idproducto)

    if not prod_mysql and not doc_mongo:
        abort(404, description="Producto no encontrado.")

    try:
        bytes_claros, mime_type = ImageStorageService.obtener_imagen_original(doc_mongo, prod_mysql)
        
        # Nombre de archivo anonimizado mediante UUID
        extension = mime_type.split('/')[-1] if '/' in mime_type else 'jpg'
        nombre_anonimo = f"{uuid.uuid4().hex}.{extension}"

        response = send_file(
            io.BytesIO(bytes_claros),
            mimetype=mime_type,
            as_attachment=False,
            download_name=nombre_anonimo
        )
        # Cabeceras de seguridad estrictas anti-filtración y anti-caché
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response
    except FileNotFoundError:
        if doc_mongo and doc_mongo.get('url') and doc_mongo.get('url').startswith('http'):
            return redirect(doc_mongo['url'])
        abort(404, description="Imagen no encontrada.")
    except Exception:
        # Devuelve 500 genérico sin exponer rutas internas ni detalles de excepción
        abort(500, description="Error al recuperar la imagen protegida.")

@productos_c.route('/imagen/<int:idproducto>/preview')
@login_required
def servir_imagen_preview(idproducto):
    """
    Ruta autenticada para 'Previsualización':
    1. Valida sesión activa.
    2. Descifra la copia comprimida optimizada en memoria.
    3. Envía con cabeceras no-store y nosniff.
    """
    prod_mysql = Producto.obtener_producto_por_id(idproducto)
    doc_mongo = ImagenProducto.obtener_por_idproducto(idproducto)

    if not prod_mysql and not doc_mongo:
        abort(404, description="Producto no encontrado.")

    try:
        bytes_claros, mime_type = ImageStorageService.obtener_imagen_preview(doc_mongo, prod_mysql)
        nombre_anonimo = f"preview_{uuid.uuid4().hex}.webp"

        response = send_file(
            io.BytesIO(bytes_claros),
            mimetype=mime_type,
            as_attachment=False,
            download_name=nombre_anonimo
        )
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response
    except FileNotFoundError:
        if doc_mongo and doc_mongo.get('url') and doc_mongo.get('url').startswith('http'):
            return redirect(doc_mongo['url'])
        abort(404, description="Previsualización no disponible.")
    except Exception:
        abort(500, description="Error al recuperar la previsualización.")

@productos_c.route('/imagenes')
@productos_c.route('/mongo')
@login_required
def obtener_imagenes():
    busqueda = request.args.get('q', '').strip()
    if busqueda:
        data2 = ImagenProducto.buscar_en_mongo(busqueda)
    else:
        data2 = ImagenProducto.leer_imagenes()
    return render_template('imagenes_productos.html', data2=data2, busqueda=busqueda, usuario_actual=session.get('usuario'))

@productos_c.route('/sincronizar', methods=['POST', 'GET'])
@login_required
def sincronizar():
    try:
        total = Producto.sincronizar_todo()
        flash(f'¡Sincronización completada! {total} productos sincronizados con MongoDB.', 'info')
    except Exception as e:
        flash(f'Error durante la sincronización: {e}', 'danger')
    return redirect(url_for('productos_c.obtener_productos'))

# Endpoints API JSON protegidos
@productos_c.route('/api/productos')
@login_required
def api_productos():
    return jsonify(Producto.leer_productos())

@productos_c.route('/api/mongo')
@login_required
def api_mongo():
    return jsonify(ImagenProducto.leer_imagenes())
