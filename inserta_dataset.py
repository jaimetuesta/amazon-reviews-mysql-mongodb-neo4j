"""
Proyecto Bases de Datos - Inserción de nuevo dataset
Jaime Tuesta de Simón y Juan Tabuyo Castell

Inserta un nuevo dataset de Amazon Reviews en la base de datos ya existente
(creada previamente por load_data.py), sin eliminar ni modificar los datos
que ya contiene.

Lógica principal:
- Los usuarios que ya existan en MySQL NO se duplican (se reutilizan).
- Los artículos que ya existan en MySQL NO se duplican (se reutilizan).
- Todas las reviews del nuevo dataset se insertan en MySQL y MongoDB.
- Se verifica que la categoría nueva no esté ya presente en la BBDD.

Nueva categoría: Deportes (desde el fichero Sports_and_Outdoors_5.json)
"""

import os
import json
from datetime import datetime

import pymysql
import pymongo

from configuracion import (
    BATCH_SIZE,
    MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB,
    MONGO_URI, MONGO_DB, MONGO_COLECCION,
    NUEVA_CATEGORIA, NUEVO_FICHERO_RUTA,
)

# Conexiones
conexion_mysql = pymysql.connect(
    host=MYSQL_HOST,
    port=MYSQL_PORT,
    user=MYSQL_USER,
    password=MYSQL_PASSWORD,
    charset="utf8mb4",
    autocommit=False,
)

cliente_mongo = pymongo.MongoClient(MONGO_URI)


# Misma lógica que en que en load_data.py
def leer_reviews(ruta):
    """
    Genera reviews una a una leyendo el fichero JSON línea a línea.
    No carga el fichero completo en memoria, compatible con ficheros de gran tamaño.

    Parámetros
    ----------
    ruta : str
        Ruta al fichero JSON de reviews.

    Yields
    ------
    dict
        Diccionario con los campos de cada review.
    """
    with open(ruta, "r", encoding="utf-8") as f:
        for numero_linea, linea in enumerate(f, start=1):
            linea = linea.strip()
            if not linea:
                continue
            try:
                yield json.loads(linea)
            except json.JSONDecodeError as e:
                print(f"  Línea {numero_linea} ignorada (JSON inválido): {e}")


def parsear_fecha(review_time_str):
    """
    Convierte el campo reviewTime del formato 'MM DD, YYYY' a datetime.date.

    Parámetros
    ----------
    review_time_str : str
        Cadena de fecha en el formato original de Amazon Reviews.

    Retorna
    -------
    datetime.date o None si el formato no es válido.
    """
    try:
        return datetime.strptime(review_time_str.strip(), "%m %d, %Y").date()
    except (ValueError, AttributeError):
        return None


def extraer_helpful(review):
    """
    Descompone el campo helpful = [votos_utiles, total_votos] en dos enteros.

    Retorna
    -------
    tuple (int o None, int o None)
    """
    helpful = review.get("helpful")
    if isinstance(helpful, list) and len(helpful) == 2:
        return helpful[0], helpful[1]
    return None, None


# Validaciones (fichero, nombre categoría)
def validar_fichero(ruta):
    """
    Comprueba que el fichero JSON del nuevo dataset existe en la ruta indicada.

    Parámetros
    ----------
    ruta : str
        Ruta al fichero JSON configurada en NUEVO_FICHERO_RUTA.

    Lanza
    -----
    FileNotFoundError si el fichero no existe.
    """
    if not os.path.isfile(ruta):
        raise FileNotFoundError(
            f"No se encontró el fichero en: '{ruta}'\n"
            "  → Comprueba el valor de NUEVO_FICHERO_RUTA en configuracion.py"
        )
    print(f"  Fichero encontrado: {ruta}")


def validar_categoria_nueva(categoria):
    """
    Verifica que la categoría indicada no existe ya en la base de datos MySQL,
    para evitar insertar un dataset duplicado.

    Parámetros
    ----------
    categoria : str
        Nombre de la categoría configurada en NUEVA_CATEGORIA.

    Lanza
    -----
    ValueError si la categoría ya tiene reviews en MySQL.
    """
    cursor = conexion_mysql.cursor()
    cursor.execute(f"USE {MYSQL_DB}")
    cursor.execute(
        "SELECT COUNT(*) FROM reviews WHERE categoria = %s LIMIT 1",
        (categoria,)
    )
    count = cursor.fetchone()[0]
    cursor.close()

    if count > 0:
        raise ValueError(
            f"La categoría '{categoria}' ya existe en la base de datos "
            f"({count} reviews encontradas)"
        )
    print(f"  Categoría '{categoria}' verificada: no existe aún en la base de datos.")


# Inserción
def _flush_batches(cursor, sql_u, batch_u, sql_a, batch_a, sql_r, batch_r,
                   col_mongo, batch_m):
    """
    Vuelca los batches acumulados a MySQL y MongoDB y los vacía.
    Si hay un IntegrityError (duplicado inesperado) se registra y continúa.
    """
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
        print(f"  Advertencia IntegrityError (duplicado ignorado): {e}")
        conexion_mysql.commit()


def insertar_nuevo_dataset(categoria, ruta):
    """
    Lee el nuevo fichero JSON línea a línea e inserta los datos en la base
    de datos existente (MySQL + MongoDB).

    Usuarios y artículos ya presentes no se vuelven a insertar.
    Todas las reviews del nuevo dataset sí se insertan como registros nuevos.

    Parámetros
    ----------
    categoria : str
        Nombre de la nueva categoría (p.ej. 'Deportes').
    ruta : str
        Ruta al fichero JSON del nuevo dataset.
    """
    print(f"\n  Cargando '{categoria}' desde: {ruta}")

    cursor = conexion_mysql.cursor()
    cursor.execute(f"USE {MYSQL_DB}")
    coleccion_mongo = cliente_mongo[MONGO_DB][MONGO_COLECCION]

    # Precarga de IDs ya existentes en la BBDD para detectar duplicados
    print("  Precargando IDs de usuarios y artículos existentes...")
    cursor.execute("SELECT reviewerID FROM usuarios")
    usuarios_existentes = {row[0] for row in cursor.fetchall()}

    cursor.execute("SELECT asin FROM articulos")
    articulos_existentes = {row[0] for row in cursor.fetchall()}

    print(f"  Usuarios en BBDD antes de insertar : {len(usuarios_existentes)}")
    print(f"  Artículos en BBDD antes de insertar: {len(articulos_existentes)}")

    # Sentencias SQL de inserción
    sql_usuario = "INSERT INTO usuarios (reviewerID, reviewerName) VALUES (%s, %s)"
    sql_articulo = "INSERT INTO articulos (asin, categoria) VALUES (%s, %s)"
    sql_review = """
        INSERT INTO reviews (reviewerID, asin, overall, helpful_1, helpful_2,
                             unixReviewTime, reviewTime, categoria)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """

    # Batches de inserción
    batch_usuarios  = []
    batch_articulos = []
    batch_reviews   = []
    batch_mongo     = []

    total            = 0
    nuevos_usuarios  = 0
    nuevos_articulos = 0
    usuarios_previos = set(usuarios_existentes)   # usuarios que ya estaban antes de esta carga
    usuarios_reutilizados = set()                 # usuarios del dataset que ya existían

    for review in leer_reviews(ruta):
        reviewer_id   = review.get("reviewerID", "")
        asin          = review.get("asin", "")
        reviewer_name = review.get("reviewerName")
        helpful_1, helpful_2 = extraer_helpful(review)
        overall     = review.get("overall")
        unix_time   = review.get("unixReviewTime")
        review_time = parsear_fecha(review.get("reviewTime", ""))

        # Contar el usuario como reutilizado si ya estaba en la BBDD antes de esta carga
        if reviewer_id in usuarios_previos:
            usuarios_reutilizados.add(reviewer_id)

        # Insertar usuario solo si es completamente nuevo (no estaba en ningún dataset)
        if reviewer_id and reviewer_id not in usuarios_existentes:
            batch_usuarios.append((reviewer_id, reviewer_name))
            usuarios_existentes.add(reviewer_id)
            nuevos_usuarios += 1

        # Insertar artículo solo si es nuevo
        if asin and asin not in articulos_existentes:
            batch_articulos.append((asin, categoria))
            articulos_existentes.add(asin)
            nuevos_articulos += 1

        # La review siempre se inserta (es un dato nuevo independientemente del usuario)
        batch_reviews.append((
            reviewer_id, asin, overall, helpful_1, helpful_2,
            unix_time, review_time, categoria
        ))

        # Documento de texto para MongoDB
        batch_mongo.append({
            "reviewerID":     reviewer_id,
            "asin":           asin,
            "reviewText":     review.get("reviewText", ""),
            "summary":        review.get("summary", ""),
            "unixReviewTime": unix_time,
            "categoria":      categoria,
        })

        total += 1

        if total % BATCH_SIZE == 0:
            _flush_batches(
                cursor, sql_usuario, batch_usuarios,
                sql_articulo, batch_articulos,
                sql_review, batch_reviews,
                coleccion_mongo, batch_mongo
            )
            print(f"  {categoria}: {total} reviews procesadas...")

    # Flush del batch final (las que no llegaron al umbral de BATCH_SIZE)
    _flush_batches(
        cursor, sql_usuario, batch_usuarios,
        sql_articulo, batch_articulos,
        sql_review, batch_reviews,
        coleccion_mongo, batch_mongo
    )

    conexion_mysql.commit()
    cursor.close()

    print(f"\n  Inserción completada.")
    print(f"    Reviews insertadas        : {total}")
    print(f"    Usuarios nuevos           : {nuevos_usuarios}")
    print(f"    Usuarios reutilizados     : {len(usuarios_reutilizados)} (ya existían de otros datasets)")
    print(f"    Artículos nuevos          : {nuevos_articulos}")


# Resumen
def mostrar_resumen(categoria):
    """
    Muestra el estado global de la base de datos tras la inserción,
    destacando los datos del nuevo dataset.

    Parámetros
    ----------
    categoria : str
        Nombre de la categoría recién insertada.
    """
    cursor = conexion_mysql.cursor()
    cursor.execute(f"USE {MYSQL_DB}")

    cursor.execute("SELECT COUNT(*) FROM usuarios")
    n_usuarios = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM articulos")
    n_articulos = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM reviews")
    n_reviews_total = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM reviews WHERE categoria = %s", (categoria,))
    n_reviews_nueva = cursor.fetchone()[0]

    cursor.execute(
        "SELECT categoria, COUNT(*) FROM reviews GROUP BY categoria ORDER BY categoria"
    )
    por_categoria = cursor.fetchall()
    cursor.close()

    n_mongo_total = cliente_mongo[MONGO_DB][MONGO_COLECCION].count_documents({})
    n_mongo_nueva = cliente_mongo[MONGO_DB][MONGO_COLECCION].count_documents(
        {"categoria": categoria}
    )

    print("\n" + "=" * 60)
    print("RESUMEN FINAL DE LA BASE DE DATOS")
    print("=" * 60)
    print(f"Total usuarios en MySQL     : {n_usuarios}")
    print(f"Total artículos en MySQL    : {n_articulos}")
    print(f"Total reviews en MySQL      : {n_reviews_total}")
    print(f"  - Nuevo dataset ('{categoria}'): {n_reviews_nueva} reviews")
    print(f"Total documentos en MongoDB : {n_mongo_total}")
    print(f"  - Nuevo dataset ('{categoria}'): {n_mongo_nueva} documentos")
    print("\nDistribución de reviews por categoría (MySQL):")
    for cat, count in por_categoria:
        marcador = "(NUEVO)" if cat == categoria else ""
        print(f"  {cat:25s}: {count:>8}{marcador}")


# Main
def main():
    print("=" * 60)
    print("INSERCIÓN DE NUEVO DATASET - PROYECTO BBDD (PARTE 4)")
    print("=" * 60)
    print(f"  Categoría  : {NUEVA_CATEGORIA}")
    print(f"  Fichero    : {NUEVO_FICHERO_RUTA}")

    try:
        print("\n1. Validando configuración...")
        validar_fichero(NUEVO_FICHERO_RUTA)
        validar_categoria_nueva(NUEVA_CATEGORIA)

        print("\n2. Insertando datos en MySQL y MongoDB...")
        insertar_nuevo_dataset(NUEVA_CATEGORIA, NUEVO_FICHERO_RUTA)

        print("\n3. Resumen de la base de datos:")
        mostrar_resumen(NUEVA_CATEGORIA)

    except FileNotFoundError as e:
        print(f"\n[ERROR] {e}")
    except ValueError as e:
        print(f"\n[ERROR] {e}")
    except Exception as e:
        print(f"\n[ERROR] Error inesperado: {e}")
        conexion_mysql.rollback()
        raise
    finally:
        conexion_mysql.close()
        cliente_mongo.close()
        print("\nConexiones a MySQL y MongoDB cerradas.")


if __name__ == "__main__":
    main()
