from src.config.mongo_connection import get_mongo_connection
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
    def guardar_o_actualizar(idproducto, producto, marca=None, precio=None, descripcion="", url=""):
        db = get_mongo_connection()
        filtro = {}
        if idproducto is not None:
            filtro = {"$or": [{"idproducto": int(idproducto)}, {"producto": re.compile(f"^{re.escape(str(producto))}$", re.IGNORECASE)}]}
        else:
            filtro = {"producto": re.compile(f"^{re.escape(str(producto))}$", re.IGNORECASE)}

        existente = db.producto.find_one(filtro)
        
        datos_actualizar = {
            "producto": producto,
            "descripcion": descripcion if descripcion else (existente.get("descripcion") if existente and existente.get("descripcion") else f"Descripción de {producto}"),
            "url": url if url else (existente.get("url") if existente and existente.get("url") else "https://via.placeholder.com/300x200?text=" + str(producto))
        }
        if marca is not None:
            datos_actualizar["marca"] = marca
        if precio is not None:
            datos_actualizar["precio"] = float(precio)
        if idproducto is not None:
            datos_actualizar["idproducto"] = int(idproducto)

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
            return db.producto.delete_many(filtro).deleted_count
        return 0