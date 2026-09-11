# Wrapper para compatibilidad hacia atrás que delega en ImageStorageService
from src.services.image_storage_service import (
    ImageStorageService,
    ImageValidationError,
    LIMIT_TIER_1,
    LIMIT_TIER_2,
    GLOBAL_MAX_SIZE,
    BASE_DIR,
    STORAGE_DIR,
    IMAGES_DIR,
    COMPRESSED_DIR
)

class ImageService(ImageStorageService):
    @staticmethod
    def procesar_imagen_bytes(nombre_archivo: str, contenido: bytes, content_type: str = None):
        return ImageStorageService.almacenar_imagen(nombre_archivo, contenido, content_type)

    @staticmethod
    def eliminar_archivos_mongo(doc_mongo: dict):
        return ImageStorageService.eliminar_archivos_fisicos(doc_mongo)
