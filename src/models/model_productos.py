from src.config.mysql_connection import get_mysql_connection
from src.models.models_imagenes import ImagenProducto

class Producto:

    @staticmethod
    def leer_productos():
        connection = get_mysql_connection()
        with connection.cursor() as cursor:
            # Seleccionamos campos estándar y un indicador de si tiene blob para optimizar rendimiento
            cursor.execute("SELECT idproducto, producto, marca, precio, imagen_mime, (imagen IS NOT NULL) AS tiene_blob FROM producto ORDER BY idproducto DESC")
            datos = cursor.fetchall()
        return datos

    @staticmethod
    def obtener_producto_por_id(idproducto):
        connection = get_mysql_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM producto WHERE idproducto = %s", (idproducto,))
            return cursor.fetchone()

    @staticmethod
    def buscar_productos(termino):
        connection = get_mysql_connection()
        with connection.cursor() as cursor:
            query = """
                SELECT idproducto, producto, marca, precio, imagen_mime, (imagen IS NOT NULL) AS tiene_blob 
                FROM producto 
                WHERE producto LIKE %s OR marca LIKE %s OR idproducto = %s 
                ORDER BY idproducto DESC
            """
            val = f"%{termino}%"
            id_val = int(termino) if str(termino).isdigit() else -1
            cursor.execute(query, (val, val, id_val))
            return cursor.fetchall()

    @staticmethod
    def crear_producto(producto, marca, precio, descripcion="", url="", imagen_bytes=None, imagen_mime=None, mongo_meta=None):
        connection = get_mysql_connection()
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO producto (producto, marca, precio, imagen, imagen_mime) VALUES (%s, %s, %s, %s, %s)",
                (producto, marca, precio, imagen_bytes, imagen_mime)
            )
            id_generado = cursor.lastrowid

        # Sincronización automática con MongoDB
        try:
            ImagenProducto.guardar_o_actualizar(
                idproducto=id_generado,
                producto=producto,
                marca=marca,
                precio=precio,
                descripcion=descripcion,
                url=url,
                meta_imagen=mongo_meta
            )
        except Exception as e:
            print(f"Error sincronizando con MongoDB en creación: {e}")

        return id_generado

    @staticmethod
    def actualizar_producto(idproducto, producto, marca, precio, descripcion="", url="", imagen_bytes=None, imagen_mime=None, mongo_meta=None, actualizar_imagen=False):
        connection = get_mysql_connection()
        with connection.cursor() as cursor:
            if actualizar_imagen:
                cursor.execute(
                    "UPDATE producto SET producto = %s, marca = %s, precio = %s, imagen = %s, imagen_mime = %s WHERE idproducto = %s",
                    (producto, marca, precio, imagen_bytes, imagen_mime, idproducto)
                )
            else:
                cursor.execute(
                    "UPDATE producto SET producto = %s, marca = %s, precio = %s WHERE idproducto = %s",
                    (producto, marca, precio, idproducto)
                )

        # Sincronización automática con MongoDB
        try:
            ImagenProducto.guardar_o_actualizar(
                idproducto=idproducto,
                producto=producto,
                marca=marca,
                precio=precio,
                descripcion=descripcion,
                url=url,
                meta_imagen=mongo_meta if actualizar_imagen else None
            )
        except Exception as e:
            print(f"Error sincronizando con MongoDB en actualización: {e}")

        return True

    @staticmethod
    def eliminar_producto(idproducto):
        connection = get_mysql_connection()
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM producto WHERE idproducto = %s", (idproducto,))

        # Sincronización automática con MongoDB y limpieza de storage
        try:
            ImagenProducto.eliminar_de_mongo(idproducto=idproducto)
        except Exception as e:
            print(f"Error eliminando de MongoDB: {e}")

        return True

    @staticmethod
    def sincronizar_todo():
        """Sincroniza todos los productos de MySQL hacia MongoDB."""
        productos_mysql = Producto.leer_productos()
        sincronizados = 0
        for p in productos_mysql:
            ImagenProducto.guardar_o_actualizar(
                idproducto=p['idproducto'],
                producto=p['producto'],
                marca=p['marca'],
                precio=p['precio']
            )
            sincronizados += 1
        return sincronizados
