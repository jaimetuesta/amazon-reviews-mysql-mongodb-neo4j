"""
Proyecto Bases de Datos - Recomendaciones
Jaime Tuesta de Simón y Juan Tabuyo Castell

Implementa un mecanismo que, dado el identificador original de un usuario y una
categoría de artículo, devuelve los 10 artículos más populares que dicho usuario
no ha consumido todavía.
"""

import pymysql

from configuracion import (
    MYSQL_HOST,
    MYSQL_PORT,
    MYSQL_USER,
    MYSQL_PASSWORD,
    MYSQL_DB,
)


def conectar_mysql():
    """Crea y devuelve una conexión a MySQL."""
    return pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DB,
        charset="utf8mb4",
        autocommit=True,
    )


def obtener_categorias(conn):
    """Devuelve la lista de categorías disponibles en la base de datos."""
    with conn.cursor() as cursor:
        cursor.execute("SELECT DISTINCT categoria FROM articulos ORDER BY categoria")
        return [fila[0] for fila in cursor.fetchall()]


def usuario_existe(conn, reviewer_id):
    """Comprueba si el usuario existe en la base de datos."""
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) FROM usuarios WHERE reviewerID = %s",
            (reviewer_id,),
        )
        return cursor.fetchone()[0] > 0


def categoria_existe(conn, categoria):
    """Comprueba si la categoría existe en la base de datos."""
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) FROM articulos WHERE categoria = %s",
            (categoria,),
        )
        return cursor.fetchone()[0] > 0


def recomendar_top_10_no_consumidos(conn, reviewer_id, categoria, limite=10):
    """
    Devuelve los artículos más populares de una categoría que el usuario no ha
    consumido todavía.

    La popularidad se mide como el número de reviews del artículo en la
    categoría indicada. En caso de empate, se ordena por media de puntuación
    descendente y por asin ascendente para mantener un resultado estable.
    """
    sql = """
        SELECT
            r.asin,
            COUNT(*) AS num_reviews,
            ROUND(AVG(r.overall), 2) AS media_overall
        FROM reviews r
        WHERE r.categoria = %s
          AND NOT EXISTS (
              SELECT 1
              FROM reviews ru
              WHERE ru.reviewerID = %s
                AND ru.asin = r.asin
          )
        GROUP BY r.asin
        ORDER BY num_reviews DESC, media_overall DESC, r.asin ASC
        LIMIT %s
    """

    with conn.cursor() as cursor:
        cursor.execute(sql, (categoria, reviewer_id, limite))
        return cursor.fetchall()


def pedir_categoria(conn):
    """Muestra las categorías disponibles y permite elegir una."""
    categorias = obtener_categorias(conn)
    if not categorias:
        raise ValueError("No hay categorías disponibles en la base de datos.")

    print("\nCategorías disponibles:")
    for i, categoria in enumerate(categorias, start=1):
        print(f" {i}. {categoria}")

    while True:
        opcion = input("Selecciona una categoría por número: ").strip()
        try:
            opcion = int(opcion)
            if 1 <= opcion <= len(categorias):
                return categorias[opcion - 1]
            print("Opción no válida.")
        except ValueError:
            print("Introduce un número válido.")


def mostrar_recomendaciones(reviewer_id, categoria, recomendaciones):
    """Muestra por pantalla las recomendaciones obtenidas."""
    print("\n" + "=" * 70)
    print("RECOMENDACIONES")
    print("=" * 70)
    print(f"Usuario   : {reviewer_id}")
    print(f"Categoría : {categoria}")

    if not recomendaciones:
        print("\nNo hay artículos para recomendar en esa categoría.")
        print("Puede ocurrir porque el usuario ya ha consumido todos los artículos")
        print("de ese tipo o porque la categoría tiene muy pocos datos.")
        return

    print("\nTop artículos más populares no consumidos:")
    for posicion, (asin, num_reviews, media_overall) in enumerate(recomendaciones, start=1):
        print(
            f" {posicion:2d}. ASIN: {asin} | reviews: {num_reviews} | "
            f"media overall: {media_overall}"
        )


def main():
    """Punto de entrada del programa."""
    print("=" * 70)
    print("RECOMENDADOR DE ARTÍCULOS POPULARES NO CONSUMIDOS")
    print("=" * 70)

    conn = conectar_mysql()
    try:
        reviewer_id = input("Introduce el reviewerID original del usuario: ").strip()
        if not reviewer_id:
            print("Debes introducir un reviewerID no vacío.")
            return

        if not usuario_existe(conn, reviewer_id):
            print(f"El usuario '{reviewer_id}' no existe en la base de datos.")
            return

        categoria = pedir_categoria(conn)
        if not categoria_existe(conn, categoria):
            print(f"La categoría '{categoria}' no existe en la base de datos.")
            return

        recomendaciones = recomendar_top_10_no_consumidos(conn, reviewer_id, categoria)
        mostrar_recomendaciones(reviewer_id, categoria, recomendaciones)
    finally:
        conn.close()


if __name__ == "__main__":
    main()