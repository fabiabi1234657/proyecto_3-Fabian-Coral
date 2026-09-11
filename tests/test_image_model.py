import io
import os
import unittest
from PIL import Image
from src.services.image_storage_service import (
    ImageStorageService,
    ImageValidationError,
    LIMIT_TIER_1,
    LIMIT_TIER_2,
    GLOBAL_MAX_SIZE,
    BASE_DIR
)
from src.services.crypto_service import CryptoService

def generar_imagen_bytes(formato='PNG', size=(100, 100), color='blue', target_bytes=None) -> bytes:
    """Genera bytes de una imagen válida ajustando el peso exacto si se requiere."""
    img = Image.new('RGB', size, color=color)
    buf = io.BytesIO()
    img.save(buf, format=formato)
    raw_bytes = buf.getvalue()

    if target_bytes and len(raw_bytes) < target_bytes:
        padding = b'\x00' * (target_bytes - len(raw_bytes))
        return raw_bytes + padding
    return raw_bytes

class TestImageStorageService(unittest.TestCase):

    def setUp(self):
        self.archivos_para_limpiar = []

    def tearDown(self):
        # Limpieza de archivos creados durante los tests
        for ruta in self.archivos_para_limpiar:
            if os.path.exists(ruta):
                try:
                    os.remove(ruta)
                except Exception:
                    pass

    def test_limite_1_menor_igual_1mb(self):
        """Prueba imagen <= 1.048.576 bytes: Almacena en MySQL, campos nulos en MongoDB."""
        datos_500kb = generar_imagen_bytes(formato='PNG', target_bytes=500_000)
        resultado = ImageStorageService.almacenar_imagen('mi_foto_personal.png', datos_500kb, 'image/png')

        # Verificación en MySQL
        self.assertIsNotNone(resultado['mysql']['imagen'])
        self.assertEqual(resultado['mysql']['imagen_mime'], 'image/png')
        self.assertEqual(len(resultado['mysql']['imagen']), 500_000)

        # Verificación en MongoDB
        mongo = resultado['mongo']
        self.assertIsNone(mongo['ruta'])
        self.assertIsNone(mongo['tamano_real'])
        self.assertIsNone(mongo['tamano_comprimido'])
        self.assertEqual(mongo['mime_type'], 'image/png')
        self.assertEqual(mongo['almacenamiento'], 'mysql')
        self.assertFalse(mongo['cifrada'])
        self.assertEqual(len(resultado['archivos_creados']), 0)

        # Test de recuperación
        bytes_recuperados, mime = ImageStorageService.obtener_imagen_original(mongo, resultado['mysql'])
        self.assertEqual(bytes_recuperados, datos_500kb)
        self.assertEqual(mime, 'image/png')

    def test_limite_1_frontera_exacta_1048576_bytes(self):
        """Prueba frontera exacta de 1.048.576 bytes (1 MB exacto)."""
        datos_1mb = generar_imagen_bytes(formato='JPEG', target_bytes=LIMIT_TIER_1)
        resultado = ImageStorageService.almacenar_imagen('limite_exacto.jpg', datos_1mb, 'image/jpeg')

        self.assertIsNotNone(resultado['mysql']['imagen'])
        self.assertIsNone(resultado['mongo']['ruta'])
        self.assertIsNone(resultado['mongo']['tamano_real'])
        self.assertIsNone(resultado['mongo']['tamano_comprimido'])
        self.assertEqual(resultado['mongo']['almacenamiento'], 'mysql')
        self.assertFalse(resultado['mongo']['cifrada'])

    def test_limite_2_entre_1mb_y_3mb_cifrado_fernet(self):
        """Prueba imagen > 1.048.576 y <= 3.145.728 bytes: Cifrado con Fernet, UUID sin nombre de usuario."""
        tamano_2mb = 2 * 1024 * 1024
        datos_2mb = generar_imagen_bytes(formato='JPEG', target_bytes=tamano_2mb)
        resultado = ImageStorageService.almacenar_imagen('documento_secreto_usuario.jpg', datos_2mb, 'image/jpeg')
        self.archivos_para_limpiar.extend(resultado['archivos_creados'])

        # MySQL no debe tener binario
        self.assertIsNone(resultado['mysql']['imagen'])
        self.assertEqual(resultado['mysql']['imagen_mime'], 'image/jpeg')

        # MongoDB
        mongo = resultado['mongo']
        self.assertIsNotNone(mongo['ruta'])
        self.assertTrue(mongo['ruta'].startswith('storage/images/'))
        self.assertTrue(mongo['ruta'].endswith('.enc'))
        # No debe incluir el nombre original del usuario
        self.assertNotIn('documento_secreto_usuario', mongo['ruta'])
        self.assertEqual(mongo['tamano_real'], tamano_2mb)
        self.assertIsNone(mongo['tamano_comprimido'])
        self.assertEqual(mongo['almacenamiento'], 'filesystem')
        self.assertTrue(mongo['cifrada'])

        # El archivo en disco debe estar cifrado e ilegible
        ruta_abs = os.path.join(BASE_DIR, mongo['ruta'])
        self.assertTrue(os.path.exists(ruta_abs))
        with open(ruta_abs, 'rb') as f:
            contenido_leido = f.read()
        self.assertNotEqual(contenido_leido, datos_2mb)

        # La recuperación debe descifrar los bytes intactos
        bytes_recuperados, mime = ImageStorageService.obtener_imagen_original(mongo, resultado['mysql'])
        self.assertEqual(bytes_recuperados, datos_2mb)
        self.assertEqual(mime, 'image/jpeg')

    def test_limite_3_mayor_3mb_doble_cifrado(self):
        """Prueba imagen > 3.145.728 bytes: Cifra original y CIFRA versión comprimida en imagesCompresed."""
        tamano_4mb = 4 * 1024 * 1024
        datos_4mb = generar_imagen_bytes(formato='PNG', size=(1200, 1200), target_bytes=tamano_4mb)
        resultado = ImageStorageService.almacenar_imagen('foto_alta_resolucion.png', datos_4mb, 'image/png')
        self.archivos_para_limpiar.extend(resultado['archivos_creados'])

        # MySQL
        self.assertIsNone(resultado['mysql']['imagen'])

        # MongoDB
        mongo = resultado['mongo']
        self.assertIsNotNone(mongo['ruta'])
        self.assertTrue(mongo['ruta'].startswith('storage/images/'))
        self.assertIsNotNone(mongo['ruta_comprimida'])
        self.assertTrue(mongo['ruta_comprimida'].startswith('storage/imagesCompresed/'))
        self.assertTrue(mongo['ruta_comprimida'].endswith('.enc'))
        
        # Tamaños
        self.assertEqual(mongo['tamano_real'], tamano_4mb)
        self.assertIsNotNone(mongo['tamano_comprimido'])
        self.assertGreater(mongo['tamano_comprimido'], 0)
        self.assertLess(mongo['tamano_comprimido'], tamano_4mb)

        # Comprobar que la copia comprimida en disco TAMBIÉN está cifrada con Fernet
        ruta_comp_abs = os.path.join(BASE_DIR, mongo['ruta_comprimida'])
        self.assertTrue(os.path.exists(ruta_comp_abs))
        with open(ruta_comp_abs, 'rb') as f:
            bytes_comp_en_disco = f.read()
        # No puede ser leída directamente por Pillow sin descifrar
        with self.assertRaises(Exception):
            Image.open(io.BytesIO(bytes_comp_en_disco)).verify()

        # Comprobar que la previsualización descifra la copia comprimida
        preview_bytes, preview_mime = ImageStorageService.obtener_imagen_preview(mongo, resultado['mysql'])
        self.assertEqual(preview_mime, 'image/webp')
        self.assertEqual(len(preview_bytes), mongo['tamano_comprimido'])
        # La copia descifrada sí es una imagen WebP válida
        with Image.open(io.BytesIO(preview_bytes)) as img_preview:
            self.assertEqual(img_preview.format, 'WEBP')

        # Comprobar que 'Ver imagen original' descifra el original intacto
        orig_bytes, orig_mime = ImageStorageService.obtener_imagen_original(mongo, resultado['mysql'])
        self.assertEqual(orig_bytes, datos_4mb)
        self.assertEqual(orig_mime, 'image/png')

    def test_limite_global_excedido(self):
        """Prueba de rechazo cuando se supera el límite global de subida configurado."""
        datos_excesivos = b'0' * (GLOBAL_MAX_SIZE + 1)
        with self.assertRaises(ImageValidationError) as ctx:
            ImageStorageService.almacenar_imagen('archivo_gigante.png', datos_excesivos, 'image/png')
        self.assertIn("supera el límite global", str(ctx.exception))

    def test_archivo_vacio(self):
        """Prueba de rechazo para archivos vacíos (0 bytes)."""
        with self.assertRaises(ImageValidationError) as ctx:
            ImageStorageService.almacenar_imagen('vacio.jpg', b'', 'image/jpeg')
        self.assertIn("vacío", str(ctx.exception))

    def test_extension_invalida(self):
        """Prueba de rechazo para extensiones peligrosas (.sh, .exe, .php)."""
        with self.assertRaises(ImageValidationError) as ctx:
            ImageStorageService.almacenar_imagen('payload.php', b'<?php phpinfo(); ?>', 'text/x-php')
        self.assertIn("no permitida", str(ctx.exception))

    def test_archivo_falso_o_corrupto(self):
        """Prueba de rechazo si la extensión es .jpg pero el binario no es una imagen."""
        with self.assertRaises(ImageValidationError) as ctx:
            ImageStorageService.almacenar_imagen('falso.jpg', b'BINARIO_CORRUPTO_NO_IMAGEN', 'image/jpeg')
        self.assertIn("no es una imagen válida", str(ctx.exception))

if __name__ == '__main__':
    unittest.main()
