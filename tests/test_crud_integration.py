import io
import os
import unittest
from app import app
from PIL import Image
from src.services.auth_service import DEFAULT_USER, DEFAULT_RAW_PASSWORD
from src.services.image_storage_service import BASE_DIR
from src.models.model_productos import Producto
from src.models.models_imagenes import ImagenProducto

def crear_imagen_bytes(formato='PNG', size=(100, 100), color='blue', target_bytes=None) -> bytes:
    """Genera bytes de una imagen válida ajustando el peso exacto si se requiere."""
    img = Image.new('RGB', size, color=color)
    buf = io.BytesIO()
    img.save(buf, format=formato)
    raw_bytes = buf.getvalue()

    if target_bytes and len(raw_bytes) < target_bytes:
        padding = b'\x00' * (target_bytes - len(raw_bytes))
        return raw_bytes + padding
    return raw_bytes

class TestCRUDIntegracionCompleta(unittest.TestCase):

    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['SECRET_KEY'] = 'test_secret_key_session'
        self.client = self.app.test_client()
        self.ids_productos_creados = []

    def tearDown(self):
        # Limpieza de productos creados durante las pruebas
        for pid in self.ids_productos_creados:
            try:
                Producto.eliminar_producto(pid)
            except Exception:
                pass

    def _login(self):
        """Autentica la sesión de prueba."""
        return self.client.post('/login', data={
            'usuario': DEFAULT_USER,
            'contrasena': DEFAULT_RAW_PASSWORD
        }, follow_redirects=True)

    def test_permisos_y_rutas_protegidas(self):
        """Verifica que ninguna ruta sensible sea accesible sin autenticación."""
        # 1. CRUD sin autenticación -> 302 hacia /login
        resp_crud = self.client.get('/productos', follow_redirects=False)
        self.assertEqual(resp_crud.status_code, 302)
        self.assertIn('/login', resp_crud.headers['Location'])

        # 2. Rutas de imagen sin autenticación -> 401 Unauthorized
        resp_img = self.client.get('/imagen/1')
        self.assertEqual(resp_img.status_code, 401)
        resp_prev = self.client.get('/imagen/1/preview')
        self.assertEqual(resp_prev.status_code, 401)

        # 3. Acceso directo a /static/uploads o /storage -> 404 Not Found
        resp_static = self.client.get('/static/uploads/archivo.enc')
        self.assertEqual(resp_static.status_code, 404)

    def test_creacion_y_servicio_tier1_menor_igual_1mb(self):
        """Prueba creación y streaming para producto con imagen <= 1 MB (MySQL MEDIUMBLOB)."""
        self._login()
        bytes_img = crear_imagen_bytes('PNG', target_bytes=300_000)

        # 1. Crear producto
        resp = self.client.post('/productos/crear', data={
            'producto': 'Mouse Óptico Test',
            'marca': 'Logitech',
            'precio': '25.50',
            'descripcion': 'Mouse para gaming',
            'imagen_archivo': (io.BytesIO(bytes_img), 'mouse.png')
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        # Localizar producto creado
        prods = Producto.buscar_productos('Mouse Óptico Test')
        self.assertTrue(len(prods) > 0)
        pid = prods[0]['idproducto']
        self.ids_productos_creados.append(pid)

        # 2. Verificar MySQL y MongoDB
        prod_mysql = Producto.obtener_producto_por_id(pid)
        self.assertIsNotNone(prod_mysql['imagen'])
        self.assertEqual(prod_mysql['imagen_mime'], 'image/png')

        doc_mongo = ImagenProducto.obtener_por_idproducto(pid)
        self.assertEqual(doc_mongo['almacenamiento'], 'mysql')
        self.assertIsNone(doc_mongo['ruta'])
        self.assertFalse(doc_mongo['cifrada'])

        # 3. Obtener imagen original
        resp_img = self.client.get(f'/imagen/{pid}')
        self.assertEqual(resp_img.status_code, 200)
        self.assertEqual(resp_img.headers['X-Content-Type-Options'], 'nosniff')
        self.assertIn('no-store', resp_img.headers['Cache-Control'])
        self.assertEqual(resp_img.data, bytes_img)

    def test_creacion_y_servicio_tier2_entre_1mb_y_3mb(self):
        """Prueba creación y streaming para producto con imagen de 2 MB (Cifrado Fernet en disco)."""
        self._login()
        tamano_2mb = 2 * 1024 * 1024
        bytes_img = crear_imagen_bytes('JPEG', target_bytes=tamano_2mb)

        resp = self.client.post('/productos/crear', data={
            'producto': 'Auriculares Pro Test',
            'marca': 'Sony',
            'precio': '150.00',
            'descripcion': 'Auriculares inalámbricos con cancelación de ruido',
            'imagen_archivo': (io.BytesIO(bytes_img), 'auriculares.jpg')
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        prods = Producto.buscar_productos('Auriculares Pro Test')
        self.assertTrue(len(prods) > 0)
        pid = prods[0]['idproducto']
        self.ids_productos_creados.append(pid)

        # MySQL no debe tener binario
        prod_mysql = Producto.obtener_producto_por_id(pid)
        self.assertIsNone(prod_mysql['imagen'])

        # MongoDB debe tener ruta y flag cifrada
        doc_mongo = ImagenProducto.obtener_por_idproducto(pid)
        self.assertEqual(doc_mongo['almacenamiento'], 'filesystem')
        self.assertTrue(doc_mongo['cifrada'])
        self.assertIsNotNone(doc_mongo['ruta'])
        self.assertIsNone(doc_mongo['tamano_comprimido'])

        # Archivo físico cifrado
        ruta_abs = os.path.join(BASE_DIR, doc_mongo['ruta'])
        self.assertTrue(os.path.exists(ruta_abs))

        # Descifrado al vuelo por el endpoint autenticado
        resp_img = self.client.get(f'/imagen/{pid}')
        self.assertEqual(resp_img.status_code, 200)
        self.assertEqual(resp_img.data, bytes_img)

    def test_creacion_y_servicio_tier3_mayor_3mb_doble_cifrado(self):
        """Prueba creación para imagen > 3 MB con previsualización comprimida y doble cifrado."""
        self._login()
        tamano_4mb = 4 * 1024 * 1024
        bytes_img = crear_imagen_bytes('PNG', size=(1200, 1200), target_bytes=tamano_4mb)

        resp = self.client.post('/productos/crear', data={
            'producto': 'Smart TV 4K Test',
            'marca': 'LG',
            'precio': '1200.00',
            'descripcion': 'Televisor OLED 4K HDR',
            'imagen_archivo': (io.BytesIO(bytes_img), 'tv_4k.png')
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        prods = Producto.buscar_productos('Smart TV 4K Test')
        self.assertTrue(len(prods) > 0)
        pid = prods[0]['idproducto']
        self.ids_productos_creados.append(pid)

        doc_mongo = ImagenProducto.obtener_por_idproducto(pid)
        self.assertEqual(doc_mongo['almacenamiento'], 'filesystem')
        self.assertIsNotNone(doc_mongo['ruta'])
        self.assertIsNotNone(doc_mongo['ruta_comprimida'])
        self.assertGreater(doc_mongo['tamano_comprimido'], 0)

        # Comprobar endpoint de previsualización (debe entregar WebP descifrado)
        resp_preview = self.client.get(f'/imagen/{pid}/preview')
        self.assertEqual(resp_preview.status_code, 200)
        self.assertEqual(resp_preview.mimetype, 'image/webp')

        # Comprobar endpoint original (debe entregar PNG original intacto)
        resp_orig = self.client.get(f'/imagen/{pid}')
        self.assertEqual(resp_orig.status_code, 200)
        self.assertEqual(resp_orig.data, bytes_img)

    def test_limpieza_segura_al_editar(self):
        """Al actualizar la imagen de un producto, los archivos cifrados anteriores deben eliminarse."""
        self._login()
        tamano_2mb = 2 * 1024 * 1024
        bytes_img1 = crear_imagen_bytes('JPEG', target_bytes=tamano_2mb)

        # 1. Crear con imagen Tier 2
        self.client.post('/productos/crear', data={
            'producto': 'Impresora Test',
            'marca': 'Epson',
            'precio': '200.00',
            'imagen_archivo': (io.BytesIO(bytes_img1), 'impresora.jpg')
        }, follow_redirects=True)
        pid = Producto.buscar_productos('Impresora Test')[0]['idproducto']
        self.ids_productos_creados.append(pid)

        doc_mongo1 = ImagenProducto.obtener_por_idproducto(pid)
        ruta_archivo_viejo = os.path.join(BASE_DIR, doc_mongo1['ruta'])
        self.assertTrue(os.path.exists(ruta_archivo_viejo))

        # 2. Editar con imagen Tier 1 (<= 1 MB)
        bytes_img2 = crear_imagen_bytes('PNG', target_bytes=200_000)
        self.client.post(f'/productos/editar/{pid}', data={
            'producto': 'Impresora Test Modificada',
            'marca': 'Epson',
            'precio': '220.00',
            'imagen_archivo': (io.BytesIO(bytes_img2), 'impresora_v2.png')
        }, follow_redirects=True)

        # El archivo viejo debe haber sido eliminado del disco
        self.assertFalse(os.path.exists(ruta_archivo_viejo))

        # Ahora el producto debe estar en MySQL MEDIUMBLOB
        prod_mod = Producto.obtener_producto_por_id(pid)
        self.assertIsNotNone(prod_mod['imagen'])

    def test_limpieza_segura_al_eliminar(self):
        """Al eliminar un producto, se debe borrar de MySQL, MongoDB y el sistema de archivos."""
        self._login()
        tamano_2mb = 2 * 1024 * 1024
        bytes_img = crear_imagen_bytes('JPEG', target_bytes=tamano_2mb)

        self.client.post('/productos/crear', data={
            'producto': 'Tablet a Eliminar',
            'marca': 'Samsung',
            'precio': '300.00',
            'imagen_archivo': (io.BytesIO(bytes_img), 'tablet.jpg')
        }, follow_redirects=True)
        pid = Producto.buscar_productos('Tablet a Eliminar')[0]['idproducto']

        doc_mongo = ImagenProducto.obtener_por_idproducto(pid)
        ruta_archivo = os.path.join(BASE_DIR, doc_mongo['ruta'])
        self.assertTrue(os.path.exists(ruta_archivo))

        # Eliminar producto
        resp_del = self.client.post(f'/productos/eliminar/{pid}', follow_redirects=True)
        self.assertEqual(resp_del.status_code, 200)

        # Verificar eliminación completa en los 3 componentes
        self.assertIsNone(Producto.obtener_producto_por_id(pid))
        self.assertIsNone(ImagenProducto.obtener_por_idproducto(pid))
        self.assertFalse(os.path.exists(ruta_archivo))

    def test_rechazo_archivo_invalido_o_corrupto(self):
        """Prueba rechazo cuando el archivo no es una imagen válida."""
        self._login()
        resp = self.client.post('/productos/crear', data={
            'producto': 'Producto Malicioso',
            'marca': 'Hacker',
            'precio': '1.00',
            'imagen_archivo': (io.BytesIO(b'<?php phpinfo(); ?>'), 'script.php')
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('no permitida', resp.get_data(as_text=True))

    def test_creacion_sin_archivo_imagen(self):
        """Prueba creación exitosa cuando no se adjunta archivo de imagen."""
        self._login()
        resp = self.client.post('/productos/crear', data={
            'producto': 'Producto Sin Foto',
            'marca': 'Genérica',
            'precio': '10.00',
            'url': 'https://via.placeholder.com/150'
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        prods = Producto.buscar_productos('Producto Sin Foto')
        self.assertTrue(len(prods) > 0)
        pid = prods[0]['idproducto']
        self.ids_productos_creados.append(pid)

        doc_mongo = ImagenProducto.obtener_por_idproducto(pid)
        self.assertEqual(doc_mongo['url'], 'https://via.placeholder.com/150')

if __name__ == '__main__':
    unittest.main()
