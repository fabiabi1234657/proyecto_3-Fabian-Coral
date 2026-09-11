
python -m venv env    #intalar virtualizador
env\Scripts\Activate  #activar virtualizador

#INSTALAR FLASK, CONECTORES DE MYSQL, CONECTORES DE MONGO
pip install Flask mysql-connector-python pymongo python-dotenv

#INSTALAR JINJA2 PARA RENDERIZAR PLANTILLAS HTML
pip show Flask Jinja2 mysql-connector-python pymongo python-dotenv

pip freeze > requirements.txt




