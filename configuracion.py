"""
Proyecto Bases de Datos - Configuración
Juan Tabuyo Castell y Jaime Tuesta de Simón
"""

import os

# Las contraseñas no se guardan en el código: se leen de las variables de entorno
# MYSQL_PASSWORD y NEO4J_PASSWORD (ver README).

# MySQL
MYSQL_HOST = "localhost"
MYSQL_PORT = 3306
MYSQL_USER = "root"
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "")
MYSQL_DB = "ProyectoBBDD"

# MongoDB
MONGO_URI = "mongodb://localhost:27017/"
MONGO_DB = "ProyectoBBDD"
MONGO_COLECCION = "reviews_texto"

# Neo4J
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "")

# Rutas datasets (carpeta data/ junto a este fichero)
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
FICHEROS_REVIEWS = {
    "Juguetes": os.path.join(DATA_DIR, "Toys_and_Games_5.json"),
    "Videojuegos": os.path.join(DATA_DIR, "Video_Games_5.json"),
    "Musica_Digital": os.path.join(DATA_DIR, "Digital_Music_5.json"),
    "Instrumentos": os.path.join(DATA_DIR, "Musical_Instruments_5.json"),
}
NUEVA_CATEGORIA = "Deportes"
NUEVO_FICHERO_RUTA = os.path.join(DATA_DIR, "Sports_and_Outdoors_5.json")

# Otros
BATCH_SIZE = 5000
TOP_N_USUARIOS = 30