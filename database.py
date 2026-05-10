import sqlite3


def conectar():
    return sqlite3.connect("contabilidad.db")


def init_db():

    conn = conectar()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS movimientos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER,
        texto TEXT,
        importe TEXT,
        tipo TEXT,
        fecha TEXT
    )
    """)

    conn.commit()
    conn.close()


def crear_usuario(username, password):

    conn = conectar()
    c = conn.cursor()

    c.execute("""
    INSERT INTO usuarios (username, password)
    VALUES (?, ?)
    """, (username, password))

    conn.commit()
    conn.close()


def buscar_usuario(username, password):

    conn = conectar()
    c = conn.cursor()

    c.execute("""
    SELECT * FROM usuarios
    WHERE username=? AND password=?
    """, (username, password))

    user = c.fetchone()

    conn.close()
    return user


def insert_movimiento(usuario_id, texto, importe, tipo, fecha):

    conn = conectar()
    c = conn.cursor()

    c.execute("""
    INSERT INTO movimientos
    (usuario_id, texto, importe, tipo, fecha)
    VALUES (?, ?, ?, ?, ?)
    """, (usuario_id, texto, importe, tipo, fecha))

    conn.commit()
    conn.close()


def get_movimientos(usuario_id):

    conn = conectar()
    c = conn.cursor()

    c.execute("""
    SELECT * FROM movimientos
    WHERE usuario_id=?
    ORDER BY id DESC
    """, (usuario_id,))

    rows = c.fetchall()

    conn.close()
    return rows