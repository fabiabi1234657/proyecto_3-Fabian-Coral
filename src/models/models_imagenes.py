from src.config.mongo_connection import get_mongo_connection
from src.services.image_service import ImageService
import re

class ImagenProducto:

    @staticmethod
    def leer_imagenes():
        db = get_mongo_connection()
        imagenes = list(db.producto.find())
        for doc in imagenes:
            doc['_id'] = str(doc['_id'])
        return imagenes

    @staticmethod
    def obtener_por_idproducto(idproducto):
        db = get_mongo_connection()
        doc = db.producto.find_one({"idproducto": int(idproducto)})
        if doc:
            doc['_id'] = str(doc['_id'])
        return doc

    @staticmethod
    def buscar_en_mongo(termino):
        db = get_mongo_connection()
        if not termino:
            return ImagenProducto.leer_imagenes()
        
        filtro = {
            "$or": [
                {"producto": {"$regex": termino, "$options": "i"}},
                {"descripcion": {"$regex": termino, "$options": "i"}},
                {"marca": {"$regex": termino, "$options": "i"}}
            ]
        }
        if str(termino).isdigit():
            filtro["$or"].append({"idproducto": int(termino)})

        imagenes = list(db.producto.find(filtro))
        for doc in imagenes:
            doc['_id'] = str(doc['_id'])
        return imagenes

    @staticmethod
    def guardar_o_actualizar(idproducto, producto, marca=None, precio=None, descripcion="", url="", meta_imagen=None):
        db = get_mongo_connection()
        filtro = {}
        if idproducto is not None:
            filtro = {"$or": [{"idproducto": int(idproducto)}, {"producto": re.compile(f"^{re.escape(str(producto))}$", re.IGNORECASE)}]}
        else:
            filtro = {"producto": re.compile(f"^{re.escape(str(producto))}$", re.IGNORECASE)}

        existente = db.producto.find_one(filtro)
        
        # Si se envía una nueva imagen y existían archivos en disco previos, eliminarlos
        if meta_imagen and existente:
            ImageService.eliminar_archivos_mongo(existente)

        datos_actualizar = {
            "producto": producto,
            "descripcion": descripcion if descripcion else (existente.get("descripcion") if existente and existente.get("descripcion") else f"Descripción de {producto}"),
            "url": url if url else (existente.get("url") if existente and existente.get("url") else "")
        }
        if marca is not None:
            datos_actualizar["marca"] = marca
        if precio is not None:
            datos_actualizar["precio"] = float(precio)
        if idproducto is not None:
            datos_actualizar["idproducto"] = int(idproducto)

        # Asignar campos según las especificaciones exactas
        if meta_imagen:
            datos_actualizar["ruta"] = meta_imagen.get("ruta")
            datos_actualizar["tamano_real"] = meta_imagen.get("tamano_real")
            datos_actualizar["tamano_comprimido"] = meta_imagen.get("tamano_comprimido")
            datos_actualizar["mime_type"] = meta_imagen.get("mime_type")
            datos_actualizar["almacenamiento"] = meta_imagen.get("almacenamiento")
            datos_actualizar["cifrada"] = meta_imagen.get("cifrada", False)
            if "ruta_comprimida" in meta_imagen:
                datos_actualizar["ruta_comprimida"] = meta_imagen["ruta_comprimida"]

        if existente:
            db.producto.update_one({"_id": existente["_id"]}, {"$set": datos_actualizar})
            return str(existente["_id"])
        else:
            res = db.producto.insert_one(datos_actualizar)
            return str(res.inserted_id)

    @staticmethod
    def eliminar_de_mongo(idproducto=None, producto=None):
        db = get_mongo_connection()
        filtro = {}
        if idproducto and producto:
            filtro = {"$or": [{"idproducto": int(idproducto)}, {"producto": re.compile(f"^{re.escape(str(producto))}$", re.IGNORECASE)}]}
        elif idproducto:
            filtro = {"idproducto": int(idproducto)}
        elif producto:
            filtro = {"producto": re.compile(f"^{re.escape(str(producto))}$", re.IGNORECASE)}
        
        if filtro:
            # Recuperar documentos para eliminar sus archivos en disco
            docs = list(db.producto.find(filtro))
            for d in docs:
                ImageService.eliminar_archivos_mongo(d)
            return db.producto.delete_many(filtro).deleted_count
        return 0