# Sistema de Gestión de Mercancía e Imágenes Híbridas (MySQL + MongoDB)

Sistema web desarrollado en **Flask** con arquitectura de almacenamiento híbrida y escalonada por tamaño de imagen, utilizando **MySQL** para datos relacionales y binarios pequeños, **MongoDB** para catálogo enriquecido y metadatos de almacenamiento, y **sistema de archivos cifrado con Fernet** para imágenes medianas y grandes fuera de la raíz pública.

---

## 🚀 1. Arquitectura de Almacenamiento por Límites Exactos

El sistema evalúa el peso del archivo binario antes de persistirlo y ejecuta automáticamente una de las tres estrategias:

```
                          [ Subida de Archivo de Imagen ]
                                         │
                       ¿Tamaño del Archivo en Bytes?
                                         │
        ┌────────────────────────────────┼────────────────────────────────┐
        ▼                                ▼                                ▼
[ <= 1.048.576 B ]            [ 1.048.577 - 3.145.728 B ]          [ > 3.145.728 B ]
   (Hasta 1 MB)                      (1 MB a 3 MB)                   (Mayor a 3 MB)
        │                                │                                │
- MySQL: Guarda binario          - MySQL: imagen=NULL             - MySQL: imagen=NULL
  en `imagen MEDIUMBLOB`         - Cifra Original con Fernet      - Cifra Original con Fernet
  y `imagen_mime`.                 y guarda en                      y guarda en
- Mongo:                           `storage/images/<UUID>.enc`      `storage/images/<UUID>.enc`
  ruta: null                     - Mongo:                         - Comprime copia WebP (Pillow)
  tamano_real: null                ruta: "storage/images/..."       y la CIFRA con Fernet en
  tamano_comprimido: null          tamano_real: <bytes>             `storage/imagesCompresed/`
  almacenamiento: "mysql"          tamano_comprimido: null          preview_<UUID>.enc
  cifrada: false                   almacenamiento: "filesystem"   - Mongo:
- Disco: Sin archivos.             cifrada: true                    ruta: "storage/images/..."
                                                                    ruta_comprimida: "storage/..."
                                                                    tamano_real: <bytes>
                                                                    tamano_comprimido: <bytes_comp>
                                                                    almacenamiento: "filesystem"
                                                                    cifrada: true
```

---

## 🔒 2. Seguridad y Privacidad

1. **Autenticación por Sesión**:
   - Protección integral de todas las rutas CRUD y de imágenes mediante el decorador `@login_required`.
   - Contraseñas almacenadas exclusivamente como hashes criptográficos (`scrypt` con `werkzeug.security`).
   - Peticiones anónimas a vistas HTML redirigen a `/login`. Solicitudes anónimas a endpoints de imagen (`/imagen/...`) o APIs responden `401 Unauthorized`.
2. **Cero Exposición mediante `static`**:
   - Ninguna imagen subida se sirve a través de `static_folder`, `send_from_directory` público ni URLs estáticas directas.
   - Las imágenes residen en la carpeta aislada `storage/` fuera de la raíz web.
3. **Descifrado al Vuelo en Memoria**:
   - Los archivos cifrados se leen y descifran en memoria mediante `io.BytesIO` sin generar archivos temporales en texto plano en disco.
4. **Cabeceras HTTP Estrictas**:
   - Todas las respuestas de imagen incluyen:
     - `Cache-Control: no-store, no-cache, must-revalidate, max-age=0`
     - `Pragma: no-cache`
     - `Expires: 0`
     - `X-Content-Type-Options: nosniff`
     - `Content-Disposition: inline; filename="<UUID>.<ext>"`
5. **Nombres Anónimos y Prevención de Sobrescritura**:
   - Los nombres de archivo se generan mediante `uuid.uuid4().hex`, eliminando metadatos o nombres originales del usuario.
6. **Límite Global Configurable**:
   - Controlado mediante `MAX_UPLOAD_SIZE_BYTES` (por defecto 16 MB). Archivos que superen este límite son rechazados antes de ser procesados.
7. **⚠️ Advertencia de Seguridad en Sistema Operativo**:
   > **Nota Crítica:** La protección y autenticación a nivel de aplicación web **no sustituye los permisos del sistema operativo**. Se debe asegurar que las carpetas `storage/` y el archivo `.env` cuenten con permisos de lectura/escritura restringidos (ej. `chmod 700` o permisos NTFS) para el usuario del proceso de ejecución, respetando el principio de menor privilegio.

---

## 📂 3. Estructura del Proyecto

```text
proyecto_3/
│
├── storage/                          # Almacenamiento protegido (fuera de static)
│   ├── images/                       # Archivos originales cifrados (.enc)
│   └── imagesCompresed/              # Previsualizaciones comprimidas cifradas (.enc)
│
├── dbs/
│   ├── mercancia.sql                 # DDL MySQL, tabla producto e índices
│   └── mercancia.js                  # Inicialización de MongoDB, índices y esquema
│
├── src/
│   ├── config/
│   │   ├── __init__.py
│   │   ├── mysql_connection.py       # Conexión MySQL parametrizada con .env
│   │   └── mongo_connection.py       # Conexión MongoDB con connection pooling (singleton)
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── auth_service.py           # Autenticación por sesión, hashes scrypt y @login_required
│   │   ├── crypto_service.py         # Cifrado/Descifrado simétrico autenticado con Fernet
│   │   ├── image_storage_service.py  # Clasificación por bytes, compresión Pillow y almacenamiento
│   │   └── image_service.py          # Wrapper de compatibilidad hacia atrás
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── model_productos.py        # Modelo MySQL con soporte MEDIUMBLOB y sincronización
│   │   └── models_imagenes.py        # Modelo MongoDB con campos de almacenamiento y limpieza
│   │
│   ├── controllers/
│   │   ├── __init__.py
│   │   └── controller.py             # Rutas CRUD, login/logout y streaming de imágenes
│   │
│   ├── templates/
│   │   ├── login.html                # Formulario de autenticación
│   │   ├── productos.html            # Gestión CRUD MySQL con miniaturas y botón Ver Imagen
│   │   └── imagenes_productos.html   # Catálogo visual MongoDB con badges informativos
│   │
│   └── static/                       # Únicamente assets CSS/JS públicos
│
├── tests/                            # Suite automatizada de pruebas unitarias e integración
│   ├── test_auth.py                  # Pruebas de autenticación y control de acceso
│   ├── test_image_model.py           # Pruebas de los 3 límites, cifrado y compresión
│   └── test_crud_integration.py      # Pruebas integrales de ciclo de vida y limpieza
│
├── .env.example                      # Plantilla de variables de entorno seguras
├── .gitignore                        # Reglas para excluir .env, env/ y storage/ de Git
├── app.py                            # Punto de entrada de la aplicación Flask
├── requirements.txt                  # Dependencias del proyecto
└── README.md                         # Documentación técnica completa
```

---

## ⚙️ 4. Instalación y Configuración

### 4.1 Requisitos Previos
- Python 3.10+
- Servidor MySQL activo
- Servidor MongoDB activo

### 4.2 Instalación de Dependencias

```powershell
# 1. Crear y activar entorno virtual
python -m venv env
.\env\Scripts\activate

# 2. Instalar dependencias
pip install -r requirements.txt
```

### 4.3 Variables de Entorno (`.env`)
Copiar el archivo `.env.example` como `.env` y configurar las claves:

```ini
# Configuración Flask
SECRET_KEY=clave_secreta_para_sesiones_flask_2026
MAX_UPLOAD_SIZE_BYTES=16777216

# Cuenta Administrador Inicial
ADMIN_USERNAME=admin
ADMIN_PASSWORD=Admin2026*

# Clave criptográfica Fernet (32 bytes base64)
# Generar con: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
STORAGE_ENCRYPTION_KEY=

# Conexión MySQL
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=
MYSQL_DB=mercancia

# Conexión MongoDB
MONGO_URI=mongodb://127.0.0.1:27017/
MONGO_DB=mercancia
```

---

## 🗄️ 5. Base de Datos y Migraciones

### 5.1 MySQL ([`dbs/mercancia.sql`](file:///C:/Users/fabim/Downloads/proyecto_3/proyecto_3/dbs/mercancia.sql))

```sql
CREATE DATABASE IF NOT EXISTS mercancia CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE mercancia;

CREATE TABLE IF NOT EXISTS producto (
    idproducto INT PRIMARY KEY AUTO_INCREMENT,
    producto VARCHAR(255) NOT NULL,
    marca VARCHAR(100) NOT NULL,
    precio DECIMAL(10, 2) NOT NULL,
    imagen MEDIUMBLOB NULL,
    imagen_mime VARCHAR(100) NULL,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_producto_nombre (producto),
    INDEX idx_producto_marca (marca)
);
```

### 5.2 MongoDB ([`dbs/mercancia.js`](file:///C:/Users/fabim/Downloads/proyecto_3/proyecto_3/dbs/mercancia.js))

```javascript
// Índices de optimización en MongoDB
db.producto.createIndex({ idproducto: 1 }, { unique: true, sparse: true });
db.producto.createIndex({ producto: 1 });
db.producto.createIndex({ marca: 1 });
db.producto.createIndex({ producto: "text", descripcion: "text", marca: "text" });
```

---

## 🌐 6. Endpoints y Rutas Disponibles

| Método | Ruta | Protección | Descripción |
|---|---|:---:|---|
| `GET` / `POST` | `/login` | Pública | Formulario y validación de inicio de sesión. |
| `GET` | `/logout` | Autenticada | Cierre e invalidación de sesión activa. |
| `GET` | `/productos` | Autenticada | Lista de productos con miniaturas y badges de almacenamiento. |
| `POST` | `/productos/crear` | Autenticada | Creación de producto y clasificación automática de imagen. |
| `POST` | `/productos/editar/<id>` | Autenticada | Edición de producto con sustitución y eliminación segura de fotos previas. |
| `POST` / `GET`| `/productos/eliminar/<id>`| Autenticada | Eliminación en cascada en MySQL, MongoDB y disco. |
| `GET` | `/imagen/<id>` | Autenticada | **Ver Imagen**: Descifra en memoria y transmite el original. |
| `GET` | `/imagen/<id>/preview` | Autenticada | **Previsualización**: Descifra copia comprimida WebP o binario MySQL. |
| `GET` | `/mongo` / `/imagenes` | Autenticada | Catálogo de documentos en MongoDB. |
| `GET` / `POST` | `/sincronizar` | Autenticada | Sincroniza productos de MySQL hacia MongoDB. |
| `GET` | `/api/productos` | Autenticada | Endpoint API JSON de productos en MySQL. |
| `GET` | `/api/mongo` | Autenticada | Endpoint API JSON de documentos en MongoDB. |

---

## 🧪 7. Ejecución de Pruebas Automatizadas

El proyecto incluye 22 pruebas unitarias e integrales que cubren autenticación, permisos, límites de tamaño, cifrado, compresión, validación y limpieza:

```powershell
py -m unittest discover tests
```

```text
......................
----------------------------------------------------------------------
Ran 22 tests in 4.052s

OK
```

### Casos de Prueba Incluidos:
- **`test_auth.py`**: Verificación de contraseñas con hash `scrypt`, redirección 302 ante accesos anónimos, 401 en endpoints de imagen y logout.
- **`test_image_model.py`**: Comprobación exacta de límites (500 KB, 1.048.576 B, 2 MB, 4 MB), verificación del doble cifrado Fernet, rechazo de archivos vacíos, extensiones no permitidas y archivos corruptos.
- **`test_crud_integration.py`**: Creación, edición con sustitución y borrado de archivos viejos, eliminación en cascada completa y verificación de cabeceras HTTP (`no-store`, `nosniff`).

---

## 🧑‍💻 8. Guía de Prueba Manual

1. Iniciar la aplicación:
   ```powershell
   py app.py
   ```
2. Abrir `http://127.0.0.1:5000/` en el navegador $\rightarrow$ Redirige a `/login`.
3. Iniciar sesión con:
   - **Usuario**: `admin`
   - **Contraseña**: `Admin2026*`
4. Probar creación de producto con imagen pequeña ($\le 1\text{ MB}$): Se guarda en MySQL `MEDIUMBLOB`.
5. Probar creación con imagen de 2 MB: Se guarda cifrada en `storage/images/` y se enlaza en MongoDB.
6. Probar creación con imagen de 4 MB: Se crea original cifrado y versión optimizada WebP cifrada en `storage/imagesCompresed/`.
7. En la tabla principal, hacer clic en el botón <kbd><i class="bi bi-eye-fill"></i></kbd> ("Ver Foto Original"): Se abre la imagen descifrada en memoria en una nueva pestaña.
8. Editar el producto y cambiar la imagen: Comprobar que los archivos cifrados anteriores se eliminan del disco.
9. Eliminar el producto: Comprobar que desaparece de MySQL, MongoDB y `storage/`.
