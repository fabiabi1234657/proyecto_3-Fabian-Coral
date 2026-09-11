import os
from flask import Flask
from dotenv import load_dotenv
from src.controllers.controller import productos_c

# Cargar variables de entorno
load_dotenv()

app = Flask(__name__, template_folder='src/templates', static_folder='src/static')
app.secret_key = os.getenv('SECRET_KEY', 'super_secret_mercancia_key_2026')

# Configuración de límites y almacenamiento seguro (FUERA de static)
STORAGE_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'storage')
os.makedirs(os.path.join(STORAGE_FOLDER, 'images'), exist_ok=True)
os.makedirs(os.path.join(STORAGE_FOLDER, 'imagesCompresed'), exist_ok=True)

app.config['STORAGE_FOLDER'] = STORAGE_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB límite de subida

app.register_blueprint(productos_c)

if __name__ == '__main__':
    app.run(debug=True)