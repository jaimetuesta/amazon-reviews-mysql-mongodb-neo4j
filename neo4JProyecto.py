"""
Proyecto Bases de Datos - Neo4J
Jaime Tuesta de Simón y Juan Tabuyo Castell

Menú con las funcionalidades de Neo4J:
  4.1 - Similitudes entre usuarios (Pearson) y carga en Neo4J
  4.2 - Artículos aleatorios y sus usuarios en Neo4J
  4.3 - Usuarios con reviews en más de un tipo de artículo
  4.4 - Artículos populares (<40 reviews) y artículos en común
"""

import math
import random
from itertools import combinations

import pymysql
from neo4j import GraphDatabase

from configuracion import (
    MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB,
    NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, TOP_N_USUARIOS)

def obtener_categorias(conn):
    """Devuelve las categorías disponibles en la base de datos (incluye las añadidas con inserta_dataset.py)"""
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT categoria FROM reviews ORDER BY categoria")
    categorias = [row[0] for row in cursor.fetchall()]
    cursor.close()
    return categorias


def conectar_mysql():
    """Crea y devuelve una conexión a MySQL"""
    return pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DB,
        charset="utf8mb4",
        autocommit=True,
    )

def conectar_neo4j():
    """Crea y devuelve un driver de Neo4J"""
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

def limpiar_neo4j(driver):
    """Elimina todos los nodos y relaciones de Neo4J"""
    with driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")
    print("Neo4J limpiado")


#==================================================================
# 4.1 Similitudes entre usuarios (Pearson)


def obtener_top_usuarios(conn, n=TOP_N_USUARIOS):
    """Obtiene los n usuarios con más reviews"""
    cursor = conn.cursor()
    sql = """
        SELECT reviewerID, COUNT(*) AS total
        FROM reviews
        GROUP BY reviewerID
        ORDER BY total DESC
        LIMIT %s
    """
    cursor.execute(sql, (n,))
    usuarios = [row[0] for row in cursor.fetchall()]
    cursor.close()
    return usuarios

def obtener_ratings_usuario(conn, reviewer_id):
    """Devuelve un diccionario {asin: overall} con las puntuaciones de un usuario"""
    cursor = conn.cursor()
    sql = "SELECT asin, overall FROM reviews WHERE reviewerID = %s"
    cursor.execute(sql, (reviewer_id,))
    ratings = {row[0]: float(row[1]) for row in cursor.fetchall()}
    cursor.close()
    return ratings

def pearson_correlation(ratings_u, ratings_v):
    """
    Calcula la correlación de Pearson entre dos usuarios.
    Solo se consideran los artículos puntuados en común (Iuv).
    Devuelve None si no tienen artículos en común o si la correlación no se puede calcular.
    """
    # artículos en común
    comunes = set(ratings_u.keys()) & set(ratings_v.keys())

    if len(comunes) == 0:
        return None

    # medias de las valoraciones de cada usuario (sobre TODOS sus artículos, no solo comunes)
    media_u = sum(ratings_u.values()) / len(ratings_u)
    media_v = sum(ratings_v.values()) / len(ratings_v)

    # numerador y denominador de la fórmula de Pearson
    numerador = 0.0
    sum_sq_u = 0.0
    sum_sq_v = 0.0

    for item in comunes:
        diff_u = ratings_u[item] - media_u
        diff_v = ratings_v[item] - media_v
        numerador += diff_u * diff_v
        sum_sq_u += diff_u ** 2
        sum_sq_v += diff_v ** 2

    denominador = math.sqrt(sum_sq_u) * math.sqrt(sum_sq_v)

    if denominador == 0:
        return None

    return numerador / denominador

def calcular_similitudes(conn, usuarios):
    """
    Calcula la similitud de Pearson entre cada par de usuarios.
    Devuelve una lista de tuplas (usuario1, usuario2, similitud).
    """
    print(f"Calculando similitudes entre {len(usuarios)} usuarios...")

    # precargamos los ratings de todos los usuarios
    ratings = {}
    for uid in usuarios:
        ratings[uid] = obtener_ratings_usuario(conn, uid)

    similitudes = []
    total_pares = len(usuarios) * (len(usuarios) - 1) // 2
    procesados = 0

    for u, v in combinations(usuarios, 2):
        pc = pearson_correlation(ratings[u], ratings[v])
        if pc is not None:  # solo guardamos si tienen artículos en común
            similitudes.append((u, v, round(pc, 4)))
        procesados += 1
        if procesados % 100 == 0:
            print(f"  {procesados}/{total_pares} pares procesados...")

    print(f"Similitudes calculadas: {len(similitudes)} pares con artículos en común")
    return similitudes

def cargar_similitudes_neo4j(driver, usuarios, similitudes):
    """Carga los usuarios como nodos y las similitudes como enlaces en Neo4J"""
    limpiar_neo4j(driver)

    with driver.session() as session:
        # creamos los nodos de usuarios
        for uid in usuarios:
            session.run(
                "CREATE (u:Usuario {reviewerID: $rid})",
                rid=uid
            )

        # creamos las relaciones de similitud (bidireccional)
        for u, v, sim in similitudes:
            session.run("""
                MATCH (u1:Usuario {reviewerID: $uid1})
                MATCH (u2:Usuario {reviewerID: $uid2})
                CREATE (u1)-[:SIMILITUD {valor: $sim}]->(u2)
            """, uid1=u, uid2=v, sim=sim)

    print(f"Cargados {len(usuarios)} nodos y {len(similitudes)} relaciones en Neo4J")

def mostrar_usuario_mas_vecinos(driver):
    """Consulta Neo4J para mostrar el usuario con más vecinos (más relaciones)"""
    with driver.session() as session:
        resultado = session.run("""
            MATCH (u:Usuario)-[:SIMILITUD]-()
            RETURN u.reviewerID AS usuario, COUNT(*) AS vecinos
            ORDER BY vecinos DESC
            LIMIT 1
        """)
        record = resultado.single()
        if record:
            print(f"\nUsuario con más vecinos: {record['usuario']} ({record['vecinos']} vecinos)")
        else:
            print("No se encontraron resultados")

def opcion_similitudes():
    """Ejecuta toda la funcionalidad del apartado 4.1"""
    print("\n" + "=" * 60)
    print("4.1 - SIMILITUDES ENTRE USUARIOS (PEARSON)")
    print("=" * 60)

    conn = conectar_mysql()
    driver = conectar_neo4j()

    usuarios = obtener_top_usuarios(conn, TOP_N_USUARIOS)
    print(f"Top {TOP_N_USUARIOS} usuarios obtenidos")

    similitudes = calcular_similitudes(conn, usuarios)
    cargar_similitudes_neo4j(driver, usuarios, similitudes)
    mostrar_usuario_mas_vecinos(driver)

    print("\nPuedes consultar el grafo en Neo4J Browser (http://localhost:7474)")

    conn.close()
    driver.close()


#==================================================================
# 4.2 Artículos aleatorios y sus usuarios

def pedir_categoria(conn):
    """Pide al usuario que elija una de las categorías existentes en la base de datos"""
    categorias = obtener_categorias(conn)
    print("\nCategorías disponibles:")
    for i, cat in enumerate(categorias, 1):
        print(f"  {i}. {cat}")

    while True:
        try:
            opcion = int(input("Selecciona categoría: "))
            if 1 <= opcion <= len(categorias):
                return categorias[opcion - 1]
            print("Opción no válida")
        except ValueError:
            print("Introduce un número")

def obtener_articulos_aleatorios(conn, categoria, n):
    """Obtiene n artículos aleatorios de la categoría indicada"""
    cursor = conn.cursor()
    sql = """
        SELECT DISTINCT asin
        FROM reviews
        WHERE categoria = %s
    """
    cursor.execute(sql, (categoria,))
    todos = [row[0] for row in cursor.fetchall()]
    cursor.close()

    if len(todos) < n:
        print(f"Solo hay {len(todos)} artículos de {categoria}, se usarán todos")
        return todos

    return random.sample(todos, n)

def obtener_usuarios_articulo(conn, asin):
    """Devuelve los usuarios que han puntuado un artículo con su nota y timestamp"""
    cursor = conn.cursor()
    sql = """
        SELECT reviewerID, overall, unixReviewTime
        FROM reviews
        WHERE asin = %s
    """
    cursor.execute(sql, (asin,))
    resultados = cursor.fetchall()
    cursor.close()
    return resultados  # lista de (reviewerID, overall, unixReviewTime)

def cargar_articulos_usuarios_neo4j(driver, articulos_datos):
    """
    Carga en Neo4J los artículos y sus usuarios.
    articulos_datos es un dict {asin: [(reviewerID, overall, unixReviewTime), ...]}
    """
    limpiar_neo4j(driver)

    with driver.session() as session:
        usuarios_creados = set()

        for asin, reviews in articulos_datos.items():
            # creamos el nodo del artículo
            session.run("CREATE (a:Articulo {asin: $asin})", asin=asin)

            for reviewer_id, overall, unix_time in reviews:
                # creamos el nodo del usuario si no existe
                if reviewer_id not in usuarios_creados:
                    session.run(
                        "CREATE (u:Usuario {reviewerID: $rid})",
                        rid=reviewer_id
                    )
                    usuarios_creados.add(reviewer_id)

                # creamos la relación usuario -> artículo con propiedades
                session.run("""
                    MATCH (u:Usuario {reviewerID: $rid})
                    MATCH (a:Articulo {asin: $asin})
                    CREATE (u)-[:HA_PUNTUADO {nota: $nota, timestamp: $ts}]->(a)
                """, rid=reviewer_id, asin=asin, nota=float(overall), ts=unix_time)

    total_relaciones = sum(len(v) for v in articulos_datos.values())
    print(f"Cargados {len(articulos_datos)} artículos y {len(usuarios_creados)} usuarios ({total_relaciones} relaciones)")

def opcion_articulos_aleatorios():
    """Ejecuta toda la funcionalidad del apartado 4.2"""
    print("\n" + "=" * 60)
    print("4.2 - ARTÍCULOS ALEATORIOS Y SUS USUARIOS")
    print("=" * 60)

    conn = conectar_mysql()
    driver = conectar_neo4j()

    categoria = pedir_categoria(conn)

    while True:
        try:
            n = int(input("Número de artículos aleatorios a seleccionar: "))
            if n > 0:
                break
            print("Debe ser mayor que 0")
        except ValueError:
            print("Introduce un número válido")

    articulos = obtener_articulos_aleatorios(conn, categoria, n)
    print(f"Artículos seleccionados: {articulos}")

    # obtenemos los usuarios de cada artículo
    articulos_datos = {}
    for asin in articulos:
        articulos_datos[asin] = obtener_usuarios_articulo(conn, asin)

    cargar_articulos_usuarios_neo4j(driver, articulos_datos)

    print("\nCarga en Neo4J finalizada. Puedes consultar los datos en Neo4J Browser")

    conn.close()
    driver.close()


#==================================================================
# 4.3 Usuarios con reviews en más de un tipo de artículo

def obtener_usuarios_multi_categoria(conn, n_usuarios=400):
    """
    Selecciona los primeros n_usuarios ordenados por nombre y filtra los que
    han puntuado artículos de más de un tipo distinto.
    Devuelve un dict {reviewerID: {categoria: count, ...}}
    """
    cursor = conn.cursor()

    # primeros 400 usuarios ordenados por nombre (reviewerName)
    sql = """
        SELECT reviewerID
        FROM usuarios
        WHERE reviewerName IS NOT NULL AND reviewerName != ''
        ORDER BY reviewerName
        LIMIT %s
    """
    cursor.execute(sql, (n_usuarios,))
    ids_usuarios = [row[0] for row in cursor.fetchall()]

    if not ids_usuarios:
        cursor.close()
        return {}

    # para cada usuario, obtenemos las categorías y el conteo
    resultado = {}
    placeholders = ",".join(["%s"] * len(ids_usuarios))
    sql = f"""
        SELECT reviewerID, categoria, COUNT(*) AS total
        FROM reviews
        WHERE reviewerID IN ({placeholders})
        GROUP BY reviewerID, categoria
    """
    cursor.execute(sql, ids_usuarios)

    datos_por_usuario = {}
    for rid, cat, total in cursor.fetchall():
        if rid not in datos_por_usuario:
            datos_por_usuario[rid] = {}
        datos_por_usuario[rid][cat] = total

    cursor.close()

    # filtramos solo los que tienen más de un tipo de categoría
    for rid, cats in datos_por_usuario.items():
        if len(cats) >= 2:
            resultado[rid] = cats

    return resultado

def cargar_usuarios_tipos_neo4j(driver, usuarios_categorias):
    """
    Carga en Neo4J nodos de usuarios y nodos de tipo de artículo,
    con enlaces indicando el número de artículos consumidos de ese tipo.
    """
    limpiar_neo4j(driver)

    with driver.session() as session:
        tipos_creados = set()

        for rid, categorias in usuarios_categorias.items():
            # nodo usuario
            session.run("CREATE (u:Usuario {reviewerID: $rid})", rid=rid)

            for cat, count in categorias.items():
                # nodo tipo de artículo (si no existe)
                if cat not in tipos_creados:
                    session.run("CREATE (t:TipoArticulo {nombre: $nombre})", nombre=cat)
                    tipos_creados.add(cat)

                # relación con propiedad de cantidad
                session.run("""
                    MATCH (u:Usuario {reviewerID: $rid})
                    MATCH (t:TipoArticulo {nombre: $cat})
                    CREATE (u)-[:HA_CONSUMIDO {cantidad: $cnt}]->(t)
                """, rid=rid, cat=cat, cnt=count)

    print(f"Cargados {len(usuarios_categorias)} usuarios y {len(tipos_creados)} tipos de artículo")

def opcion_usuarios_multi_categoria():
    """Ejecuta toda la funcionalidad del apartado 4.3"""
    print("\n" + "=" * 60)
    print("4.3 - USUARIOS CON REVIEWS EN MÁS DE UN TIPO DE ARTÍCULO")
    print("=" * 60)

    conn = conectar_mysql()
    driver = conectar_neo4j()

    usuarios_cats = obtener_usuarios_multi_categoria(conn, 400)
    print(f"Usuarios con reviews en más de un tipo: {len(usuarios_cats)}")

    cargar_usuarios_tipos_neo4j(driver, usuarios_cats)

    print("\nCarga en Neo4J finalizada. Puedes consultar los datos en Neo4J Browser")

    conn.close()
    driver.close()


#==================================================================
# 4.4 Artículos populares (<40 reviews) y artículos en común


def obtener_articulos_populares(conn, top=5, max_reviews=40):
    """Obtiene los top artículos más populares con menos de max_reviews reviews"""
    cursor = conn.cursor()
    sql = """
        SELECT asin, COUNT(*) AS total
        FROM reviews
        GROUP BY asin
        HAVING total < %s
        ORDER BY total DESC
        LIMIT %s
    """
    cursor.execute(sql, (max_reviews, top))
    articulos = [row[0] for row in cursor.fetchall()]
    cursor.close()
    return articulos

def obtener_usuarios_y_reviews_articulos(conn, articulos):
    """
    Para una lista de artículos, devuelve:
    - articulos_usuarios: {asin: [reviewerID, ...]}
    - usuarios_articulos: {reviewerID: set(asin, ...)} (para calcular comunes)
    """
    cursor = conn.cursor()
    articulos_usuarios = {}
    usuarios_articulos = {}

    for asin in articulos:
        cursor.execute("SELECT reviewerID FROM reviews WHERE asin = %s", (asin,))
        users = [row[0] for row in cursor.fetchall()]
        articulos_usuarios[asin] = users

        for uid in users:
            if uid not in usuarios_articulos:
                usuarios_articulos[uid] = set()
            usuarios_articulos[uid].add(asin)

    cursor.close()
    return articulos_usuarios, usuarios_articulos

def cargar_populares_neo4j(driver, articulos, articulos_usuarios, usuarios_articulos):
    """
    Carga en Neo4J los artículos populares, sus usuarios y los enlaces entre
    usuarios indicando cuántos artículos han puntuado en común.
    """
    limpiar_neo4j(driver)

    with driver.session() as session:
        # nodos de artículos
        for asin in articulos:
            session.run("CREATE (a:Articulo {asin: $asin})", asin=asin)

        # nodos de usuarios y relaciones con artículos
        todos_usuarios = set()
        for asin, users in articulos_usuarios.items():
            for uid in users:
                if uid not in todos_usuarios:
                    session.run("CREATE (u:Usuario {reviewerID: $rid})", rid=uid)
                    todos_usuarios.add(uid)

                session.run("""
                    MATCH (u:Usuario {reviewerID: $rid})
                    MATCH (a:Articulo {asin: $asin})
                    CREATE (u)-[:HA_PUNTUADO]->(a)
                """, rid=uid, asin=asin)

        # enlaces entre usuarios con artículos en común
        usuarios_lista = list(todos_usuarios)
        relaciones_creadas = 0

        for i in range(len(usuarios_lista)):
            for j in range(i + 1, len(usuarios_lista)):
                u1 = usuarios_lista[i]
                u2 = usuarios_lista[j]
                comunes = usuarios_articulos.get(u1, set()) & usuarios_articulos.get(u2, set())

                if len(comunes) > 0:
                    session.run("""
                        MATCH (u1:Usuario {reviewerID: $uid1})
                        MATCH (u2:Usuario {reviewerID: $uid2})
                        CREATE (u1)-[:ARTICULOS_COMUNES {cantidad: $cnt}]->(u2)
                    """, uid1=u1, uid2=u2, cnt=len(comunes))
                    relaciones_creadas += 1

    print(f"Cargados {len(articulos)} artículos, {len(todos_usuarios)} usuarios, {relaciones_creadas} relaciones entre usuarios")

def opcion_articulos_populares():
    """Ejecuta toda la funcionalidad del apartado 4.4"""
    print("\n" + "=" * 60)
    print("4.4 - ARTÍCULOS POPULARES Y ARTÍCULOS EN COMÚN")
    print("=" * 60)

    conn = conectar_mysql()
    driver = conectar_neo4j()

    articulos = obtener_articulos_populares(conn, top=5, max_reviews=40)
    print(f"5 artículos más populares con <40 reviews: {articulos}")

    articulos_usuarios, usuarios_articulos = obtener_usuarios_y_reviews_articulos(conn, articulos)
    cargar_populares_neo4j(driver, articulos, articulos_usuarios, usuarios_articulos)

    print("\nCarga en Neo4J finalizada. Puedes consultar los datos en Neo4J Browser")

    conn.close()
    driver.close()


# Menú principal
def mostrar_menu():
    """Muestra las opciones del menú de Neo4J"""
    print("\n" + "=" * 55)
    print("  MENÚ NEO4J - PROYECTO BBDD")
    print("=" * 55)
    print("  1. Similitudes entre usuarios (Pearson)")
    print("  2. Artículos aleatorios y sus usuarios")
    print("  3. Usuarios con reviews en más de un tipo")
    print("  4. Artículos populares y artículos en común")
    print("  5. Salir")
    print("=" * 55)


def main():
    while True:
        mostrar_menu()
        opcion = input("Selecciona una opción: ").strip()

        try:
            if opcion == "1":
                opcion_similitudes()
            elif opcion == "2":
                opcion_articulos_aleatorios()
            elif opcion == "3":
                opcion_usuarios_multi_categoria()
            elif opcion == "4":
                opcion_articulos_populares()
            elif opcion == "5":
                print("Saliendo del menú de Neo4J...")
                break
            else:
                print("Opción no válida, introduce un número del 1 al 5")
        except Exception as e:
            print(f"Error al ejecutar la opción: {e}")


if __name__ == "__main__":
    main()
