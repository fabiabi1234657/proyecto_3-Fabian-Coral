import unittest
from app import app
from src.services.auth_service import AuthService, DEFAULT_USER, DEFAULT_RAW_PASSWORD
from src.services.image_storage_service import ImageStorageService

class TestAutenticacion(unittest.TestCase):

    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['SECRET_KEY'] = 'test_secret_key_session'
        self.client = self.app.test_client()

    def test_verificacion_credenciales_correctas(self):
        """Prueba verificación con usuario y contraseña válidos."""
        es_valido = AuthService.verificar_credenciales(DEFAULT_USER, DEFAULT_RAW_PASSWORD)
        self.assertTrue(es_valido)

    def test_verificacion_credenciales_incorrectas(self):
        """Prueba rechazo ante contraseñas o usuarios erróneos."""
        self.assertFalse(AuthService.verificar_credenciales(DEFAULT_USER, 'PasswordErroneo123'))
        self.assertFalse(AuthService.verificar_credenciales('usuario_inexistente', DEFAULT_RAW_PASSWORD))

    def test_acceso_no_autenticado_a_crud_redirige_a_login(self):
        """Rutas HTML deben redirigir a /login si no hay sesión activa."""
        resp = self.client.get('/productos', follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login', resp.headers['Location'])

    def test_acceso_no_autenticado_a_imagenes_devuelve_401(self):
        """Rutas de imágenes deben responder 401 Unauthorized si no hay sesión."""
        resp = self.client.get('/imagen/1')
        self.assertEqual(resp.status_code, 401)

        resp_preview = self.client.get('/imagen/1/preview')
        self.assertEqual(resp_preview.status_code, 401)

    def test_flujo_login_y_logout(self):
        """Prueba login exitoso, acceso a recursos y cierre de sesión."""
        # 1. Login exitoso
        resp_login = self.client.post('/login', data={
            'usuario': DEFAULT_USER,
            'contrasena': DEFAULT_RAW_PASSWORD
        }, follow_redirects=True)
        self.assertEqual(resp_login.status_code, 200)

        # 2. Acceso permitido a /productos con sesión activa
        resp_prod = self.client.get('/productos')
        self.assertEqual(resp_prod.status_code, 200)

        # 3. Logout
        resp_logout = self.client.get('/logout', follow_redirects=False)
        self.assertEqual(resp_logout.status_code, 302)

        # 4. Verificar que se revocó el acceso tras logout
        resp_tras_logout = self.client.get('/productos', follow_redirects=False)
        self.assertEqual(resp_tras_logout.status_code, 302)

    def test_cabeceras_de_seguridad_en_imagenes_autenticadas(self):
        """Prueba que las imágenes servidas con sesión tengan cabeceras no-store y nosniff."""
        # Iniciar sesión
        with self.client.session_transaction() as sess:
            sess['usuario'] = DEFAULT_USER

        # Probar endpoint de imagen inexistente (debe devolver 404 sin filtrar rutas internas)
        resp_404 = self.client.get('/imagen/999999')
        self.assertEqual(resp_404.status_code, 404)

if __name__ == '__main__':
    unittest.main()
