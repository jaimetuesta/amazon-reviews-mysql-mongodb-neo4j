"""
Proyecto Bases de Datos - Carga de datos
Jaime Tuesta de Simón y Juan Tabuyo Castell

Lee los ficheros JSON de reviews de Amazon línea a línea y carga los datos
repartidos entre MySQL (datos estructurados) y MongoDB (datos de texto).

Diseño:
    MySQL:
        - usuarios(reviewerID PK, reviewerName)
        - articulos(asin PK, categoria)
        - reviews(review_id AUTO PK, reviewerID FK, asin FK, overall,
                  helpful_1, helpful_2, unixReviewTime, reviewTime DATE, categoria)
    MongoDB:
        - reviews_texto: {reviewerID, asin, reviewText, summary, unixReviewTime}

Justificación:
    - MySQL almacena los datos estructurados y numéricos (notas, fechas, ids, helpful)
      porque permite hacer consultas relacionales eficientes con JOINs, agrupaciones
      y filtros por fecha/nota/categoría para las visualizaciones.
    - MongoDB almacena los campos de texto libre (reviewText, summary) porque son
      datos no estructurados de longitud variable, ideales para una base documental.
      Se usan principalmente para la nube de palabras.
"""

import os
import json
from datetime import datetime

import pymysql
import pymongo

from configuracion import (
    FICHEROS_REVIEWS, BATCH_SIZE, MYSQL_HOST, MYSQL_PORT, MYSQL_USER,
    MYSQL_PASSWORD, MYSQL_DB, MONGO_URI, MONGO_DB, MONGO_COLECCION)

conexion_mysql = pymysql.connect(
    host=MYSQL_HOST,
    port=MYSQL_PORT,
    user=MYSQL_USER,
    password=MYSQL_PASSWORD,
    charset="utf8mb4",
    autocommit=False,
)

cliente_mongo = pymongo.MongoClient(MONGO_URI)


def validar_ficheros():
    """Comprueba que todos los ficheros JSON existen"""
    for categoria, ruta in FICHEROS_REVIEWS.items():
        if not os.path.isfile(ruta):
            raise FileNotFoundError(f"No existe el fichero para {categoria}: {ruta}")
    print("Todos los ficheros JSON encontrados correctamente")

def leer_reviews(ruta):
    """
    Lee el fichero línea a línea y devuelve cada review como diccionario.
    No carga el fichero completo en memoria.
    """
    with open(ruta, "r", encoding="utf-8") as f:
        for numero_linea, linea in enumerate(f, start=1):
            linea = linea.strip()
            if linea == "":
                continue
            try:
                yield json.loads(linea)
            except json.JSONDecodeError as e:
                print(f"  Línea {numero_linea} ignorada (JSON inválido): {e}")

def parsear_fecha(review_time_str):
    """
    Convierte el campo reviewTime (formato 'MM DD, YYYY' o 'M D, YYYY') a datetime.date.
    Si falla, devuelve None.
    """
    try:
        return datetime.strptime(review_time_str.strip(), "%m %d, %Y").date()
    except (ValueError, AttributeError):
        return None


def extraer_helpful(review):
    """Convierte helpful = [x, y] en dos valores separados"""
    helpful = review.get("helpful")
    if isinstance(helpful, list) and len(helpful) == 2:
        return helpful[0], helpful[1]
    return None, None


def crear_base_datos_mysql():
    """Crea la base de datos en MySQL si no existe"""
    cursor = conexion_mysql.cursor()
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {MYSQL_DB} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    cursor.execute(f"USE {MYSQL_DB}")
    conexion_mysql.commit()
    cursor.close()
    print(f"Base de datos MySQL '{MYSQL_DB}' creada/verificada")

def crear_tablas_mysql():
    """Crea las tablas usuarios, articulos y reviews en MySQL"""
    cursor = conexion_mysql.cursor()
    cursor.execute(f"USE {MYSQL_DB}")

    # limpiamos tablas si existen (en orden por FK)
    cursor.execute("DROP TABLE IF EXISTS reviews")
    cursor.execute("DROP TABLE IF EXISTS articulos")
    cursor.execute("DROP TABLE IF EXISTS usuarios")

    cursor.execute("""
        CREATE TABLE usuarios (
            reviewerID VARCHAR(64) NOT NULL,
            reviewerName VARCHAR(255) NULL,
            PRIMARY KEY (reviewerID)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    cursor.execute("""
        CREATE TABLE articulos (
            asin VARCHAR(32) NOT NULL,
            categoria VARCHAR(64) NOT NULL,
            PRIMARY KEY (asin)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    cursor.execute("""
        CREATE TABLE reviews (
            review_id BIGINT NOT NULL AUTO_INCREMENT,
            reviewerID VARCHAR(64) NOT NULL,
            asin VARCHAR(32) NOT NULL,
            overall DECIMAL(3,1) NULL,
            helpful_1 INT NULL,
            helpful_2 INT NULL,
            unixReviewTime BIGINT NULL,
            reviewTime DATE NULL,
            categoria VARCHAR(64) NOT NULL,
            PRIMARY KEY (review_id),
            FOREIGN KEY (reviewerID) REFERENCES usuarios(reviewerID),
            FOREIGN KEY (asin) REFERENCES articulos(asin)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    conexion_mysql.commit()
    cursor.close()
    print("Tablas MySQL creadas: usuarios, articulos, reviews")

def crear_coleccion_mongo():
    """Limpia y prepara la colección de MongoDB"""
    db = cliente_mongo[MONGO_DB]
    db[MONGO_COLECCION].drop()
    print(f"Colección MongoDB '{MONGO_COLECCION}' preparada")

def insertar_datos(categoria, ruta):
    """
    Lee un fichero JSON de reviews línea a línea e inserta los datos repartidos
    entre MySQL (estructurados) y MongoDB (texto).
    Usa batches para mayor eficiencia.
    """
    print(f"\nCargando '{categoria}' desde: {ruta}")

    cursor = conexion_mysql.cursor()
    cursor.execute(f"USE {MYSQL_DB}")
    coleccion_mongo = cliente_mongo[MONGO_DB][MONGO_COLECCION]

    # sets para controlar duplicados de usuarios y articulos ya insertados
    usuarios_insertados = set()
    articulos_insertados = set()

    # cargamos los que ya existen en la BBDD (de ficheros anteriores)
    cursor.execute("SELECT reviewerID FROM usuarios")
    for row in cursor.fetchall():
        usuarios_insertados.add(row[0])

    cursor.execute("SELECT asin FROM articulos")
    for row in cursor.fetchall():
        articulos_insertados.add(row[0])

    # batches
    batch_usuarios = []
    batch_articulos = []
    batch_reviews = []
    batch_mongo = []
    total = 0

    sql_usuario = "INSERT INTO usuarios (reviewerID, reviewerName) VALUES (%s, %s)"
    sql_articulo = "INSERT INTO articulos (asin, categoria) VALUES (%s, %s)"
    sql_review = """
        INSERT INTO reviews (reviewerID, asin, overall, helpful_1, helpful_2,
                             unixReviewTime, reviewTime, categoria)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """

    for review in leer_reviews(ruta):
        reviewer_id = review.get("reviewerID", "")
        asin = review.get("asin", "")
        reviewer_name = review.get("reviewerName")
        helpful_1, helpful_2 = extraer_helpful(review)
        overall = review.get("overall")
        unix_time = review.get("unixReviewTime")
        review_time = parsear_fecha(review.get("reviewTime", ""))

        # usuario (si no se ha insertado aún)
        if reviewer_id and reviewer_id not in usuarios_insertados:
            batch_usuarios.append((reviewer_id, reviewer_name))
            usuarios_insertados.add(reviewer_id)

        # articulo (si no se ha insertado aún)
        if asin and asin not in articulos_insertados:
            batch_articulos.append((asin, categoria))
            articulos_insertados.add(asin)

        # review para MySQL
        batch_reviews.append((
            reviewer_id, asin, overall, helpful_1, helpful_2,
            unix_time, review_time, categoria
        ))

        # documento para MongoDB (texto)
        batch_mongo.append({
            "reviewerID": reviewer_id,
            "asin": asin,
            "reviewText": review.get("reviewText", ""),
            "summary": review.get("summary", ""),
            "unixReviewTime": unix_time,
            "categoria": categoria,
        })

        total += 1

        if total % BATCH_SIZE == 0:  # insertamos cada BATCH_SIZE reviews
            _flush_batches(cursor, sql_usuario, batch_usuarios,
                           sql_articulo, batch_articulos,
                           sql_review, batch_reviews,
                           coleccion_mongo, batch_mongo)
            print(f"  {categoria}: {total} reviews procesadas...")

    # insertamos lo que quede en los batches
    _flush_batches(cursor, sql_usuario, batch_usuarios,
                   sql_articulo, batch_articulos,
                   sql_review, batch_reviews,
                   coleccion_mongo, batch_mongo)

    conexion_mysql.commit()
    cursor.close()
    print(f"  {categoria}: carga completada. Total = {total}")


def _flush_batches(cursor, sql_u, batch_u, sql_a, batch_a, sql_r, batch_r, col_mongo, batch_m):
    """Inserta los batches acumulados y los vacía"""
    try:
        if batch_u:
            cursor.executemany(sql_u, batch_u)
            batch_u.clear()
        if batch_a:
            cursor.executemany(sql_a, batch_a)
            batch_a.clear()
        if batch_r:
            cursor.executemany(sql_r, batch_r)
            batch_r.clear()
        if batch_m:
            col_mongo.insert_many(batch_m)
            batch_m.clear()
    except pymysql.IntegrityError as e:
        print(f"  Advertencia IntegrityError (posible duplicado): {e}")
        conexion_mysql.commit()  # commit parcial para no perder lo anterior


def crear_indices():
    """Crea índices en MySQL y MongoDB para mejorar el rendimiento de las consultas"""
    cursor = conexion_mysql.cursor()
    cursor.execute(f"USE {MYSQL_DB}")

    # índices en MySQL
    cursor.execute("CREATE INDEX idx_reviews_categoria ON reviews(categoria)")
    cursor.execute("CREATE INDEX idx_reviews_asin ON reviews(asin)")
    cursor.execute("CREATE INDEX idx_reviews_reviewerID ON reviews(reviewerID)")
    cursor.execute("CREATE INDEX idx_reviews_overall ON reviews(overall)")
    cursor.execute("CREATE INDEX idx_reviews_unix ON reviews(unixReviewTime)")
    conexion_mysql.commit()
    cursor.close()

    # índices en MongoDB
    db = cliente_mongo[MONGO_DB]
    db[MONGO_COLECCION].create_index("categoria")
    db[MONGO_COLECCION].create_index("reviewerID")
    db[MONGO_COLECCION].create_index("asin")

    print("Índices creados en MySQL y MongoDB")


def mostrar_resumen():
    """Muestra un resumen de los datos cargados"""
    cursor = conexion_mysql.cursor()
    cursor.execute(f"USE {MYSQL_DB}")

    cursor.execute("SELECT COUNT(*) FROM usuarios")
    n_usuarios = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM articulos")
    n_articulos = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM reviews")
    n_reviews_mysql = cursor.fetchone()[0]
    cursor.execute("SELECT categoria, COUNT(*) FROM reviews GROUP BY categoria")
    por_categoria = cursor.fetchall()
    cursor.close()

    n_reviews_mongo = cliente_mongo[MONGO_DB][MONGO_COLECCION].count_documents({})

    print("\n" + "=" * 60)
    print("RESUMEN DE CARGA")
    print("=" * 60)
    print(f"Usuarios en MySQL:       {n_usuarios}")
    print(f"Artículos en MySQL:      {n_articulos}")
    print(f"Reviews en MySQL:        {n_reviews_mysql}")
    print(f"Documentos en MongoDB:   {n_reviews_mongo}")
    print("\nReviews por categoría (MySQL):")
    for cat, count in por_categoria:
        print(f"  {cat}: {count}")


def main():
    print("=" * 60)
    print("CARGA DE DATOS - PROYECTO BBDD")
    print("=" * 60)

    validar_ficheros()

    print("\n1. Creando base de datos y tablas en MySQL...")
    crear_base_datos_mysql()
    crear_tablas_mysql()

    print("\n2. Preparando colección en MongoDB...")
    crear_coleccion_mongo()

    print("\n3. Cargando datos de los ficheros JSON...")
    for categoria, ruta in FICHEROS_REVIEWS.items():
        insertar_datos(categoria, ruta)

    print("\n4. Creando índices...")
    crear_indices()

    mostrar_resumen()

    conexion_mysql.close()
    cliente_mongo.close()
    print("\nProceso de carga completado correctamente")


if __name__ == "__main__":
    main()
