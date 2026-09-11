import os
from cryptography.fernet import Fernet
from dotenv import load_dotenv

# Cargar variables de entorno desde la raíz del proyecto
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
dotenv_path = os.path.join(BASE_DIR, '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

def _obtener_clave_cifrado():
    clave = os.getenv("STORAGE_ENCRYPTION_KEY")
    if not clave:
        # Generar clave por defecto para desarrollo si no existe y persistir si es posible
        clave = Fernet.generate_key().decode('utf-8')
        try:
            with open(dotenv_path, 'a', encoding='utf-8') as f:
                f.write(f"\nSTORAGE_ENCRYPTION_KEY={clave}\n")
        except Exception:
            pass
        os.environ["STORAGE_ENCRYPTION_KEY"] = clave
    if isinstance(clave, str):
        clave = clave.strip().encode('utf-8')
    return clave

_FERNET_INSTANCE = None

def get_fernet():
    global _FERNET_INSTANCE
    if _FERNET_INSTANCE is None:
        key = _obtener_clave_cifrado()
        _FERNET_INSTANCE = Fernet(key)
    return _FERNET_INSTANCE

class CryptoService:
    @staticmethod
    def encrypt_bytes(data: bytes) -> bytes:
        """Cifra un bloque de bytes utilizando AES en modo seguro autenticado."""
        fernet = get_fernet()
        return fernet.encrypt(data)

    @staticmethod
    def decrypt_bytes(encrypted_data: bytes) -> bytes:
        """Descifra un bloque de bytes cifrado."""
        fernet = get_fernet()
        return fernet.decrypt(encrypted_data)
