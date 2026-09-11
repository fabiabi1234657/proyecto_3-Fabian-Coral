import os
from flask import Flask
from src.controllers.controller import productos_c

app = Flask(__name__, template_folder='src/templates', static_folder='src/static')
app.secret_key = 'super_secret_mercancia_key_2026'

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src', 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB máximo

app.register_blueprint(productos_c)

if __name__ == '__main__':
    app.run(debug=True)
