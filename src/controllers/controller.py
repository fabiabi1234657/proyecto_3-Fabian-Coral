import os
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from werkzeug.utils import secure_filename
from src.models.model_productos import Producto
from src.models.models_imagenes import ImagenProducto

productos_c = Blueprint('productos_c', __name__, template_folder='../templates')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'svg'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def procesar_imagen_subida(archivo_file, url_texto=""):
    """Guarda el archivo en static/uploads si existe o retorna la URL provista."""
    if archivo_file and archivo_file.filename != '' and allowed_file(archivo_file.filename):
        nombre_limpio = secure_filename(archivo_file.filename)
        extension = nombre_limpio.rsplit('.', 1)[1].lower() if '.' in nombre_limpio else 'jpg'
        nombre_unico = f"{uuid.uuid4().hex[:10]}_{nombre_limpio}"
        
        upload_folder = current_app.config.get('UPLOAD_FOLDER', 'src/static/uploads')
        os.makedirs(upload_folder, exist_ok=True)
        
        ruta_destino = os.path.join(upload_folder, nombre_unico)
        archivo_file.save(ruta_destino)
        return f"/static/uploads/{nombre_unico}"
    
    return url_texto.strip() if url_texto else ""

@productos_c.route('/')
def index():
    return redirect(url_for('productos_c.obtener_productos'))

@productos_c.route('/productos')
def obtener_productos():
    busqueda = request.args.get('q', '').strip()
    if busqueda:
        data = Producto.buscar_productos(busqueda)
    else:
        data = Producto.leer_productos()
    return render_template('productos.html', data=data, busqueda=busqueda)

@productos_c.route('/productos/crear', methods=['POST'])
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

    url_final = procesar_imagen_subida(archivo_imagen, url_texto)

    try:
        nuevo_id = Producto.crear_producto(
            producto=producto,
            marca=marca,
            precio=float(precio),
            descripcion=descripcion,
            url=url_final
        )
        flash(f'¡Producto "{producto}" (ID #{nuevo_id}) creado y sincronizado exitosamente con su imagen en MongoDB!', 'success')
    except Exception as e:
        flash(f'Error al crear el producto: {e}', 'danger')

    return redirect(url_for('productos_c.obtener_productos'))

@productos_c.route('/productos/editar/<int:idproducto>', methods=['POST'])
def editar_producto(idproducto):
    producto = request.form.get('producto', '').strip()
    marca = request.form.get('marca', '').strip()
    precio = request.form.get('precio', '0').strip()
    descripcion = request.form.get('descripcion', '').strip()
    url_texto = request.form.get('url', '').strip()
    archivo_imagen = request.files.get('imagen_archivo')

    url_final = procesar_imagen_subida(archivo_imagen, url_texto)

    try:
        Producto.actualizar_producto(
            idproducto=idproducto,
            producto=producto,
            marca=marca,
            precio=float(precio),
            descripcion=descripcion,
            url=url_final
        )
        flash(f'¡Producto #{idproducto} actualizado y sincronizado en MySQL y MongoDB!', 'success')
    except Exception as e:
        flash(f'Error al actualizar el producto: {e}', 'danger')

    return redirect(url_for('productos_c.obtener_productos'))

@productos_c.route('/productos/eliminar/<int:idproducto>', methods=['POST', 'GET'])
def eliminar_producto(idproducto):
    try:
        Producto.eliminar_producto(idproducto)
        flash(f'¡Producto #{idproducto} eliminado correctamente de ambas bases de datos!', 'warning')
    except Exception as e:
        flash(f'Error al eliminar el producto: {e}', 'danger')

    return redirect(url_for('productos_c.obtener_productos'))

@productos_c.route('/imagenes')
@productos_c.route('/mongo')
def obtener_imagenes():
    busqueda = request.args.get('q', '').strip()
    if busqueda:
        data2 = ImagenProducto.buscar_en_mongo(busqueda)
    else:
        data2 = ImagenProducto.leer_imagenes()
    return render_template('imagenes_productos.html', data2=data2, busqueda=busqueda)

@productos_c.route('/sincronizar', methods=['POST', 'GET'])
def sincronizar():
    try:
        total = Producto.sincronizar_todo()
        flash(f'¡Sincronización completada! {total} productos sincronizados con MongoDB.', 'info')
    except Exception as e:
        flash(f'Error durante la sincronización: {e}', 'danger')
    return redirect(url_for('productos_c.obtener_productos'))

# Endpoints API JSON
@productos_c.route('/api/productos')
def api_productos():
    return jsonify(Producto.leer_productos())

@productos_c.route('/api/mongo')
def api_mongo():
    return jsonify(ImagenProducto.leer_imagenes())
