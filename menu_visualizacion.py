"""
Proyecto Bases de Datos - Menú de visualización
Juan Tabuyo Castell y Jaime Tuesta de Simón
"""

import pymysql
import pymongo
import matplotlib.pyplot as plt
from wordcloud import WordCloud

from configuracion import (
    MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB,
    MONGO_URI, MONGO_DB, MONGO_COLECCION)

CATEGORIAS_VALIDAS = []


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

def conectar_mongo():
    """Crea y devuelve la colección de MongoDB"""
    cliente = pymongo.MongoClient(MONGO_URI)
    return cliente, cliente[MONGO_DB][MONGO_COLECCION]

def obtener_categorias():
    """Obtiene las categorías disponibles directamente de la base de datos"""
    conn = conectar_mysql()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT categoria FROM reviews ORDER BY categoria")
    categorias = [row[0] for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return categorias

def pedir_categoria(permitir_todo=True):
    """
    Pide al usuario que elija una categoría.
    Si permitir_todo=True, permite elegir 'todo' para no filtrar.
    """
    print("\nCategorías disponibles:")
    for i, cat in enumerate(CATEGORIAS_VALIDAS, 1):
        print(f"  {i}. {cat}")
    if permitir_todo:
        print(f"  {len(CATEGORIAS_VALIDAS) + 1}. Todo (todas las categorías)")

    while True:
        try:
            opcion = int(input("Selecciona una opción: "))
            if 1 <= opcion <= len(CATEGORIAS_VALIDAS):
                return CATEGORIAS_VALIDAS[opcion - 1]
            elif permitir_todo and opcion == len(CATEGORIAS_VALIDAS) + 1:
                return None  # None = todas las categorías
            else:
                print("Opción no válida")
        except ValueError:
            print("Introduce un número válido")
            

def construir_where_categoria(categoria, alias="r"):
    """Devuelve la cláusula WHERE para filtrar por categoría, o vacío si es None"""
    if categoria:
        return f" WHERE {alias}.categoria = %s ", (categoria,)
    return " ", ()

def evolucion_reviews_anios():
    """Histograma con el número de reviews por año"""
    categoria = pedir_categoria(permitir_todo=True)
    conn = conectar_mysql()
    cursor = conn.cursor()

    if categoria:
        sql = """
            SELECT YEAR(reviewTime) AS anio, COUNT(*) AS total
            FROM reviews
            WHERE categoria = %s AND reviewTime IS NOT NULL
            GROUP BY anio
            ORDER BY anio
        """
        cursor.execute(sql, (categoria,))
        titulo = f"Reviews por año de {categoria}"
    else:
        sql = """
            SELECT YEAR(reviewTime) AS anio, COUNT(*) AS total
            FROM reviews
            WHERE reviewTime IS NOT NULL
            GROUP BY anio
            ORDER BY anio
        """
        cursor.execute(sql)
        titulo = "Reviews por año de todos los productos"

    resultados = cursor.fetchall()
    cursor.close()
    conn.close()

    if not resultados:
        print("No se encontraron datos")
        return

    anios = [row[0] for row in resultados]
    totales = [row[1] for row in resultados]

    plt.figure(figsize=(10, 6))
    plt.bar(anios, totales, color="steelblue")
    plt.xlabel("Años")
    plt.ylabel("Número de reviews")
    plt.title(titulo)
    plt.xticks(anios, rotation=45)
    plt.tight_layout()
    plt.show()

def evolucion_popularidad():
    """Curva de artículos ordenados de mayor a menor popularidad (nº reviews)"""
    categoria = pedir_categoria(permitir_todo=True)
    conn = conectar_mysql()
    cursor = conn.cursor()

    if categoria:
        sql = """
            SELECT asin, COUNT(*) AS total
            FROM reviews
            WHERE categoria = %s
            GROUP BY asin
            ORDER BY total DESC
        """
        cursor.execute(sql, (categoria,))
        titulo = f"Evolución de popularidad de {categoria}"
    else:
        sql = """
            SELECT asin, COUNT(*) AS total
            FROM reviews
            GROUP BY asin
            ORDER BY total DESC
        """
        cursor.execute(sql)
        titulo = "Evolución de popularidad de todos los productos"

    resultados = cursor.fetchall()
    cursor.close()
    conn.close()

    if not resultados:
        print("No se encontraron datos")
        return

    popularidades = [row[1] for row in resultados]

    plt.figure(figsize=(10, 6))
    plt.plot(range(len(popularidades)), popularidades, color="steelblue", linewidth=0.8)
    plt.xlabel("Artículos")
    plt.ylabel("Número de reviews")
    plt.title(titulo)
    plt.tight_layout()
    plt.show()

def histograma_por_nota():
    """Histograma con el número de reviews por nota (overall). Permite filtrar por categoría o artículo individual"""
    print("\n¿Filtrar por categoría o por artículo individual?")
    print("  1. Por categoría (o todos)")
    print("  2. Por artículo individual (asin)")

    opcion = input("Selecciona: ").strip()

    conn = conectar_mysql()
    cursor = conn.cursor()

    if opcion == "2":
        asin = input("Introduce el asin del artículo: ").strip()
        sql = "SELECT COUNT(*) FROM articulos WHERE asin = %s"
        cursor.execute(sql, (asin,))
        if cursor.fetchone()[0] == 0:
            print(f"El artículo '{asin}' no existe en la base de datos")
            cursor.close()
            conn.close()
            return

        sql = """
            SELECT overall, COUNT(*) AS total
            FROM reviews
            WHERE asin = %s
            GROUP BY overall
            ORDER BY overall
        """
        cursor.execute(sql, (asin,))
        titulo = f"Reviews por nota del artículo {asin}"
    else:
        categoria = pedir_categoria(permitir_todo=True)
        if categoria:
            sql = """
                SELECT overall, COUNT(*) AS total
                FROM reviews
                WHERE categoria = %s
                GROUP BY overall
                ORDER BY overall
            """
            cursor.execute(sql, (categoria,))
            titulo = f"Reviews por nota de {categoria}"
        else:
            sql = """
                SELECT overall, COUNT(*) AS total
                FROM reviews
                GROUP BY overall
                ORDER BY overall
            """
            cursor.execute(sql)
            titulo = "Reviews por nota de todos los productos"

    resultados = cursor.fetchall()
    cursor.close()
    conn.close()

    if not resultados:
        print("No se encontraron datos")
        return

    notas = [float(row[0]) for row in resultados]
    totales = [row[1] for row in resultados]

    plt.figure(figsize=(8, 6))
    plt.bar(notas, totales, color="steelblue", width=0.6)
    plt.xlabel("Nota")
    plt.ylabel("Número de reviews")
    plt.title(titulo)
    plt.xticks(notas)
    plt.tight_layout()
    plt.show()

def evolucion_reviews_tiempo():
    """Evolución acumulada de reviews a lo largo del tiempo para cada categoría"""
    conn = conectar_mysql()
    cursor = conn.cursor()

    plt.figure(figsize=(12, 6))

    for categoria in CATEGORIAS_VALIDAS:
        sql = """
            SELECT unixReviewTime
            FROM reviews
            WHERE categoria = %s AND unixReviewTime IS NOT NULL
            ORDER BY unixReviewTime
        """
        cursor.execute(sql, (categoria,))
        timestamps = [row[0] for row in cursor.fetchall()]

        if timestamps:
            acumulado = list(range(1, len(timestamps) + 1))  # 1, 2, 3, ...
            plt.plot(timestamps, acumulado, label=categoria, linewidth=1)

    cursor.close()
    conn.close()

    plt.xlabel("Tiempo")
    plt.ylabel("Número de reviews hasta ese momento")
    plt.title("Evolución de las reviews a lo largo del tiempo")
    plt.legend()
    plt.tight_layout()
    plt.show()

def histograma_reviews_usuario():
    """Histograma donde eje x = nº reviews, eje y = nº usuarios con esa cantidad"""
    conn = conectar_mysql()
    cursor = conn.cursor()

    sql = """
        SELECT reviews_count, COUNT(*) AS num_usuarios
        FROM (
            SELECT reviewerID, COUNT(*) AS reviews_count
            FROM reviews
            GROUP BY reviewerID
        ) AS sub
        GROUP BY reviews_count
        ORDER BY reviews_count
    """
    cursor.execute(sql)
    resultados = cursor.fetchall()
    cursor.close()
    conn.close()

    if not resultados:
        print("No se encontraron datos")
        return

    num_reviews = [row[0] for row in resultados]
    num_usuarios = [row[1] for row in resultados]

    plt.figure(figsize=(10, 6))
    plt.bar(num_reviews, num_usuarios, color="steelblue", width=1.0)
    plt.xlabel("Número de reviews")
    plt.ylabel("Número de usuarios")
    plt.title("Reviews por usuario")
    plt.tight_layout()
    plt.show()

def nube_palabras():
    """Genera una nube de palabras a partir del campo summary de MongoDB (por categoría)"""
    categoria = pedir_categoria(permitir_todo=False)  # no se permite "todo"

    cliente, coleccion = conectar_mongo()

    # obtenemos todos los summaries de esa categoría
    cursor_mongo = coleccion.find(
        {"categoria": categoria},
        {"summary": 1, "_id": 0}
    )

    texto = ""
    for doc in cursor_mongo:
        summary = doc.get("summary", "")
        if summary:
            # solo palabras de longitud > 3
            palabras = [p for p in summary.split() if len(p) > 3]
            texto += " ".join(palabras) + " "

    cliente.close()

    if not texto.strip():
        print("No se encontraron datos de texto para esa categoría")
        return

    wc = WordCloud(width=800, height=400, background_color="white", max_words=200)
    wc.generate(texto)

    plt.figure(figsize=(12, 6))
    plt.imshow(wc, interpolation="bilinear")
    plt.axis("off")
    plt.title(f"Nube de palabras - {categoria}")
    plt.tight_layout()
    plt.show()

def top_usuarios_reviews():
    """Gráfica de barras horizontales con los 15 usuarios con más reviews"""
    conn = conectar_mysql()
    cursor = conn.cursor()

    sql = """
        SELECT u.reviewerName, COUNT(*) AS total
        FROM reviews r
        JOIN usuarios u ON u.reviewerID = r.reviewerID
        WHERE u.reviewerName IS NOT NULL AND u.reviewerName != ''
        GROUP BY r.reviewerID, u.reviewerName
        ORDER BY total DESC
        LIMIT 15
    """
    cursor.execute(sql)
    resultados = cursor.fetchall()
    cursor.close()
    conn.close()

    if not resultados:
        print("No se encontraron datos")
        return

    nombres = [row[0][:25] for row in resultados]  # recortamos nombres largos
    totales = [row[1] for row in resultados]

    nombres.reverse()
    totales.reverse()

    plt.figure(figsize=(10, 7))
    plt.barh(nombres, totales, color="steelblue")
    plt.xlabel("Número de reviews")
    plt.ylabel("Usuario")
    plt.title("Top 15 usuarios con más reviews")
    plt.tight_layout()
    plt.show()


def mostrar_menu():
    """Muestra las opciones del menú"""
    print("\n" + "=" * 55)
    print("  MENÚ DE VISUALIZACIÓN - PROYECTO BBDD")
    print("=" * 55)
    print("  1. Evolución de reviews por años")
    print("  2. Evolución de la popularidad de los artículos")
    print("  3. Histograma por nota")
    print("  4. Evolución de reviews a lo largo del tiempo")
    print("  5. Histograma de reviews por usuario")
    print("  6. Nube de palabras (por categoría)")
    print("  7. Top 15 usuarios con más reviews")
    print("  8. Salir")
    print("=" * 55)


def main():
    global CATEGORIAS_VALIDAS
    try:
        CATEGORIAS_VALIDAS = obtener_categorias()
    except Exception as e:
        print(f"[ERROR] No se pudo conectar a la base de datos: {e}")
        return

    while True:
        mostrar_menu()
        opcion = input("Selecciona una opción: ").strip()

        try:
            if opcion == "1":
                evolucion_reviews_anios()
            elif opcion == "2":
                evolucion_popularidad()
            elif opcion == "3":
                histograma_por_nota()
            elif opcion == "4":
                evolucion_reviews_tiempo()
            elif opcion == "5":
                histograma_reviews_usuario()
            elif opcion == "6":
                nube_palabras()
            elif opcion == "7":
                top_usuarios_reviews()
            elif opcion == "8":
                print("Saliendo del menú de visualización...")
                break
            else:
                print("Opción no válida, introduce un número del 1 al 8")
        except Exception as e:
            print(f"Error al ejecutar la opción: {e}")


if __name__ == "__main__":
    main()
