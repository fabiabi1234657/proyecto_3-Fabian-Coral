import os
from functools import wraps
from flask import session, redirect, url_for, flash, request, abort, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
load_dotenv(os.path.join(BASE_DIR, '.env'))

# Configuración de cuenta inicial desde variables de entorno
DEFAULT_USER = os.getenv("ADMIN_USERNAME", "admin")
DEFAULT_RAW_PASSWORD = os.getenv("ADMIN_PASSWORD", "Admin2026*")

# Hash seguro sin almacenar contraseñas en texto plano
INITIAL_PASSWORD_HASH = os.getenv(
    "ADMIN_PASSWORD_HASH",
    generate_password_hash(DEFAULT_RAW_PASSWORD, method='scrypt')
)

class AuthService:

    @staticmethod
    def verificar_credenciales(usuario: str, contrasena: str) -> bool:
        """Valida las credenciales contra el hash criptográfico configurado."""
        if not usuario or not contrasena:
            return False
        
        # Comparación constante de usuario y hash de contraseña
        if usuario.strip() == DEFAULT_USER:
            return check_password_hash(INITIAL_PASSWORD_HASH, contrasena)
        return False

def login_required(f):
    """
    Decorador para proteger rutas.
    - Si es ruta de imagen o API -> Devuelve HTTP 401 Unauthorized.
    - Si es vista HTML -> Redirige al login.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('usuario'):
            # Si se solicita una imagen o API sin sesión válida
            if request.path.startswith('/imagen/') or request.path.startswith('/api/'):
                abort(401, description="Acceso no autorizado. Debe iniciar sesión.")
            
            flash('Debes iniciar sesión para acceder a este recurso.', 'warning')
            return redirect(url_for('productos_c.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function
