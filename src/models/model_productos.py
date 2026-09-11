from src.config.mysql_connection import get_mysql_connection
from src.models.models_imagenes import ImagenProducto

class Producto:

    @staticmethod
    def leer_productos():
        connection = get_mysql_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM producto ORDER BY idproducto DESC")
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
            query = "SELECT * FROM producto WHERE producto LIKE %s OR marca LIKE %s OR idproducto = %s ORDER BY idproducto DESC"
            val = f"%{termino}%"
            id_val = int(termino) if str(termino).isdigit() else -1
            cursor.execute(query, (val, val, id_val))
            return cursor.fetchall()

    @staticmethod
    def crear_producto(producto, marca, precio, descripcion="", url=""):
        connection = get_mysql_connection()
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO producto (producto, marca, precio) VALUES (%s, %s, %s)",
                (producto, marca, precio)
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
                url=url
            )
        except Exception as e:
            print(f"Error sincronizando con MongoDB en creación: {e}")

        return id_generado

    @staticmethod
    def actualizar_producto(idproducto, producto, marca, precio, descripcion="", url=""):
        connection = get_mysql_connection()
        with connection.cursor() as cursor:
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
                url=url
            )
        except Exception as e:
            print(f"Error sincronizando con MongoDB en actualización: {e}")

        return True

    @staticmethod
    def eliminar_producto(idproducto):
        prod = Producto.obtener_producto_por_id(idproducto)
        nombre_prod = prod['producto'] if prod else None

        connection = get_mysql_connection()
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM producto WHERE idproducto = %s", (idproducto,))

        # Sincronización automática con MongoDB
        try:
            ImagenProducto.eliminar_de_mongo(idproducto=idproducto, producto=nombre_prod)
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

