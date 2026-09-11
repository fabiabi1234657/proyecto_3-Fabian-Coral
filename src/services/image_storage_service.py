import io
import os
import uuid
from PIL import Image
from src.services.crypto_service import CryptoService

# Constantes de límites exactos en bytes
LIMIT_TIER_1 = 1_048_576      # 1.048.576 bytes (1 MB exacto)
LIMIT_TIER_2 = 3_145_728      # 3.145.728 bytes (3 MB exactos)
GLOBAL_MAX_SIZE = int(os.getenv("MAX_UPLOAD_SIZE_BYTES", 16 * 1024 * 1024)) # 16 MB límite global por defecto

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
STORAGE_DIR = os.path.join(BASE_DIR, 'storage')
IMAGES_DIR = os.path.join(STORAGE_DIR, 'images')
COMPRESSED_DIR = os.path.join(STORAGE_DIR, 'imagesCompresed')

# Crear carpetas de almacenamiento protegidas (fuera de static)
os.makedirs(IMAGES_DIR, exist_ok=True)
os.makedirs(COMPRESSED_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp'}
ALLOWED_MIME_TYPES = {
    'image/png': 'png',
    'image/jpeg': 'jpg',
    'image/pjpeg': 'jpg',
    'image/gif': 'gif',
    'image/webp': 'webp',
    'image/bmp': 'bmp',
    'image/x-ms-bmp': 'bmp'
}

EXTENSION_TO_MIME = {
    'png': 'image/png',
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg',
    'gif': 'image/gif',
    'webp': 'image/webp',
    'bmp': 'image/bmp'
}

class ImageValidationError(ValueError):
    """Excepción para errores de validación de formato, tamaño o integridad."""
    pass

class ImageStorageService:

    @staticmethod
    def validar_y_clasificar(nombre_archivo: str, contenido: bytes, content_type: str = None) -> tuple[str, str, int]:
        """
        Valida que el archivo:
        1. No supere el límite global configurado.
        2. No esté vacío.
        3. Tenga una extensión y tipo MIME permitidos.
        4. Tenga una estructura binaria de imagen válida (Pillow).
        Retorna (extension_normalizada, mime_type, tamano_bytes).
        """
        tamano_bytes = len(contenido) if contenido else 0

        # Validación 1: Límite global
        if tamano_bytes > GLOBAL_MAX_SIZE:
            raise ImageValidationError(
                f"El archivo ({tamano_bytes:,} bytes) supera el límite global permitido de {GLOBAL_MAX_SIZE // (1024 * 1024)} MB."
            )

        # Validación 2: Archivo vacío
        if tamano_bytes == 0:
            raise ImageValidationError("El archivo de imagen está vacío (0 bytes).")

        # Validación 3: Extensión controlada
        if not nombre_archivo or '.' not in nombre_archivo:
            raise ImageValidationError("El archivo no tiene una extensión válida.")

        ext_original = nombre_archivo.rsplit('.', 1)[-1].lower()
        if ext_original not in ALLOWED_EXTENSIONS:
            raise ImageValidationError(
                f"Extensión '.{ext_original}' no permitida. Permitidas: {', '.join(sorted(ALLOWED_EXTENSIONS))}."
            )

        # Determinar y validar MIME type
        mime_type = content_type.lower() if content_type else EXTENSION_TO_MIME.get(ext_original, 'image/jpeg')
        if mime_type not in ALLOWED_MIME_TYPES:
            mime_type = EXTENSION_TO_MIME.get(ext_original)
            if not mime_type:
                raise ImageValidationError(f"Tipo MIME '{content_type}' no permitido.")

        # Validación 4: Integridad binaria con Pillow
        try:
            with Image.open(io.BytesIO(contenido)) as img:
                img.verify()
        except Exception as e:
            raise ImageValidationError(f"El archivo no es una imagen válida o está dañado: {e}")

        extension_normalizada = ALLOWED_MIME_TYPES.get(mime_type, ext_original)
        return extension_normalizada, mime_type, tamano_bytes

    @staticmethod
    def _generar_ruta_unica(directorio: str, prefijo: str = "", extension: str = ".enc") -> tuple[str, str]:
        """
        Genera una ruta segura y única utilizando UUIDv4, garantizando no sobrescribir archivos.
        No incluye el nombre original provisto por el usuario.
        Retorna (ruta_absoluta, ruta_relativa).
        """
        while True:
            nombre_archivo = f"{prefijo}{uuid.uuid4().hex}{extension}"
            ruta_abs = os.path.join(directorio, nombre_archivo)
            if not os.path.exists(ruta_abs):
                ruta_relativa = os.path.relpath(ruta_abs, BASE_DIR).replace('\\', '/')
                return ruta_abs, ruta_relativa

    @staticmethod
    def almacenar_imagen(nombre_archivo: str, contenido: bytes, content_type: str = None) -> dict:
        """
        Clasifica por bytes antes de guardar y ejecuta la estrategia según los 3 rangos:
        - <= 1.048.576 B: Almacena en MySQL (MEDIUMBLOB). En Mongo ruta=null, tamano_real=null, tamano_comprimido=null.
        - > 1.048.576 B y <= 3.145.728 B: Cifra original con Fernet en storage/images con UUID. Mongo: ruta, tamano_real, tamano_comprimido=null.
        - > 3.145.728 B: Cifra original en storage/images, genera y CIFRA copia comprimida en storage/imagesCompresed. Mongo: ambas rutas y tamaños.
        """
        extension_norm, mime_type, tamano_bytes = ImageStorageService.validar_y_clasificar(
            nombre_archivo, contenido, content_type
        )

        # ---------------------------------------------------------------------
        # RANGO 1: Hasta 1.048.576 bytes (<= 1 MB) -> MySQL MEDIUMBLOB
        # ---------------------------------------------------------------------
        if tamano_bytes <= LIMIT_TIER_1:
            return {
                "mysql": {
                    "imagen": contenido,
                    "imagen_mime": mime_type
                },
                "mongo": {
                    "ruta": None,
                    "tamano_real": None,
                    "tamano_comprimido": None,
                    "mime_type": mime_type,
                    "almacenamiento": "mysql",
                    "cifrada": False
                },
                "archivos_creados": []
            }

        # ---------------------------------------------------------------------
        # RANGO 2: Mayor a 1.048.576 y hasta 3.145.728 bytes (1 MB a 3 MB)
        # ---------------------------------------------------------------------
        elif LIMIT_TIER_1 < tamano_bytes <= LIMIT_TIER_2:
            # Cifrar contenido con Fernet
            contenido_cifrado = CryptoService.encrypt_bytes(contenido)
            ruta_abs, ruta_rel = ImageStorageService._generar_ruta_unica(IMAGES_DIR, prefijo="", extension=".enc")

            with open(ruta_abs, 'wb') as f:
                f.write(contenido_cifrado)

            return {
                "mysql": {
                    "imagen": None,
                    "imagen_mime": mime_type
                },
                "mongo": {
                    "ruta": ruta_rel,
                    "tamano_real": tamano_bytes,
                    "tamano_comprimido": None,
                    "mime_type": mime_type,
                    "almacenamiento": "filesystem",
                    "cifrada": True
                },
                "archivos_creados": [ruta_abs]
            }

        # ---------------------------------------------------------------------
        # RANGO 3: Mayor a 3.145.728 bytes (> 3 MB)
        # ---------------------------------------------------------------------
        else:
            # 1. Cifrar y guardar original en images/
            original_cifrado = CryptoService.encrypt_bytes(contenido)
            ruta_orig_abs, ruta_orig_rel = ImageStorageService._generar_ruta_unica(IMAGES_DIR, prefijo="", extension=".enc")
            with open(ruta_orig_abs, 'wb') as f:
                f.write(original_cifrado)

            # 2. Generar versión comprimida para previsualización (en memoria)
            try:
                with Image.open(io.BytesIO(contenido)) as img:
                    if img.mode in ('RGBA', 'LA') and extension_norm in ('jpg', 'jpeg'):
                        img = img.convert('RGB')
                    
                    # Redimensión proporcional manteniendo relación de aspecto (máximo 800x800)
                    img.thumbnail((800, 800), Image.Resampling.LANCZOS)

                    buffer_comp = io.BytesIO()
                    img.save(buffer_comp, format='WEBP', quality=70, optimize=True)
                    bytes_comprimidos_claros = buffer_comp.getvalue()
                    buffer_comp.close()
                    tamano_comprimido_real = len(bytes_comprimidos_claros)

                # 3. CIFRAR TAMBIÉN la versión comprimida
                comprimido_cifrado = CryptoService.encrypt_bytes(bytes_comprimidos_claros)
                ruta_comp_abs, ruta_comp_rel = ImageStorageService._generar_ruta_unica(
                    COMPRESSED_DIR, prefijo="preview_", extension=".enc"
                )
                with open(ruta_comp_abs, 'wb') as f:
                    f.write(comprimido_cifrado)

            except Exception as e:
                # Si ocurre un error en la compresión, limpiar el archivo original creado
                if os.path.exists(ruta_orig_abs):
                    os.remove(ruta_orig_abs)
                raise ImageValidationError(f"Error procesando compresión de imagen: {e}")

            return {
                "mysql": {
                    "imagen": None,
                    "imagen_mime": mime_type
                },
                "mongo": {
                    "ruta": ruta_orig_rel,
                    "ruta_comprimida": ruta_comp_rel,
                    "tamano_real": tamano_bytes,
                    "tamano_comprimido": tamano_comprimido_real,
                    "mime_type": mime_type,
                    "almacenamiento": "filesystem",
                    "cifrada": True
                },
                "archivos_creados": [ruta_orig_abs, ruta_comp_abs]
            }

    @staticmethod
    def obtener_imagen_original(doc_mongo: dict, prod_mysql: dict) -> tuple[bytes, str]:
        """
        Recupera el binario descifrado en memoria de la imagen original.
        No escribe archivos temporales en disco.
        Retorna (bytes_claros, mime_type).
        """
        # 1. Si está en MySQL (<= 1 MB)
        if prod_mysql and prod_mysql.get('imagen'):
            mime = prod_mysql.get('imagen_mime') or 'image/jpeg'
            return prod_mysql['imagen'], mime

        # 2. Si está en Filesystem (MongoDB metadata)
        if doc_mongo and doc_mongo.get('ruta'):
            ruta_rel = doc_mongo['ruta']
            ruta_abs = os.path.join(BASE_DIR, ruta_rel) if not os.path.isabs(ruta_rel) else ruta_rel
            if not os.path.exists(ruta_abs):
                raise FileNotFoundError(f"Archivo no encontrado en almacenamiento: {ruta_rel}")

            with open(ruta_abs, 'rb') as f:
                bytes_leidos = f.read()

            if doc_mongo.get('cifrada', True):
                bytes_claros = CryptoService.decrypt_bytes(bytes_leidos)
            else:
                bytes_claros = bytes_leidos

            mime = doc_mongo.get('mime_type') or 'image/jpeg'
            return bytes_claros, mime

        raise FileNotFoundError("El producto no posee imagen almacenada.")

    @staticmethod
    def obtener_imagen_preview(doc_mongo: dict, prod_mysql: dict) -> tuple[bytes, str]:
        """
        Recupera la previsualización:
        - Si tiene versión comprimida cifrada (> 3 MB), la descifra en memoria y la devuelve.
        - De lo contrario, devuelve la imagen original descifrada.
        """
        if doc_mongo and doc_mongo.get('ruta_comprimida'):
            ruta_comp_rel = doc_mongo['ruta_comprimida']
            ruta_comp_abs = os.path.join(BASE_DIR, ruta_comp_rel) if not os.path.isabs(ruta_comp_rel) else ruta_comp_rel
            if os.path.exists(ruta_comp_abs):
                with open(ruta_comp_abs, 'rb') as f:
                    bytes_leidos = f.read()
                
                # Descifrar la copia comprimida
                if doc_mongo.get('cifrada', True):
                    bytes_claros = CryptoService.decrypt_bytes(bytes_leidos)
                else:
                    bytes_claros = bytes_leidos

                return bytes_claros, 'image/webp'

        # Fallback a la imagen original
        return ImageStorageService.obtener_imagen_original(doc_mongo, prod_mysql)

    @staticmethod
    def eliminar_archivos_fisicos(doc_mongo: dict):
        """Elimina de forma segura los archivos cifrados asociados a un producto."""
        if not doc_mongo or not isinstance(doc_mongo, dict):
            return

        rutas = [
            doc_mongo.get('ruta'),
            doc_mongo.get('ruta_comprimida')
        ]
        for r in rutas:
            if r:
                r_abs = os.path.join(BASE_DIR, r) if not os.path.isabs(r) else r
                try:
                    if os.path.exists(r_abs):
                        os.remove(r_abs)
                except Exception as e:
                    print(f"Error al eliminar archivo protegido {r_abs}: {e}")
