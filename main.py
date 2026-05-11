from flask import Flask, render_template, request, redirect, session, send_file
import os
import re
import requests
from datetime import datetime

import openpyxl

from database import (
    init_db,
    crear_usuario,
    buscar_usuario,
    insert_movimiento,
    get_movimientos
)

# =====================================================
# CONFIG
# =====================================================

app = Flask(__name__)
app.secret_key = "clave_super_segura"

UPLOAD_FOLDER = "uploads"

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# =====================================================
# OCR API KEY
# =====================================================

OCR_API_KEY = K87458836088957

# =====================================================
# INIT DB
# =====================================================

init_db()

# =====================================================
# FUNCIONES
# =====================================================

def safe_float(valor):

    if valor is None:
        return 0.0

    texto = str(valor)

    texto = texto.replace("€", "")
    texto = texto.replace("EUR", "")
    texto = texto.replace(" ", "")

    # ---------------------------------------------
    # 127.000,00
    # ---------------------------------------------

    if "." in texto and "," in texto:

        texto = texto.replace(".", "")
        texto = texto.replace(",", ".")

    elif "," in texto:

        texto = texto.replace(",", ".")

    try:
        return float(texto)

    except:
        return 0.0


def extraer_total(texto):

    numeros = re.findall(r"\d+[.,]?\d*[.,]?\d*", texto)

    valores = []

    for n in numeros:

        valor = safe_float(n)

        if valor > 0:
            valores.append(valor)

    if not valores:
        return 0.0

    return max(valores)


def clasificar(texto):

    t = texto.lower()

    palabras_ingreso = [
        "cliente",
        "factura emitida",
        "venta",
        "ingreso",
        "cobro"
    ]

    palabras_gasto = [
        "proveedor",
        "factura recibida",
        "compra",
        "ticket",
        "gasto"
    ]

    for p in palabras_ingreso:
        if p in t:
            return "INGRESO"

    for p in palabras_gasto:
        if p in t:
            return "GASTO"

    return "DESCONOCIDO"


def hacer_ocr(filepath):

    with open(filepath, "rb") as f:

        response = requests.post(
            "https://api.ocr.space/parse/image",
            files={"filename": f},
            data={
                "apikey": OCR_API_KEY,
                "language": "spa",
                "isOverlayRequired": False
            }
        )

    resultado = response.json()

    if resultado.get("IsErroredOnProcessing"):
        return ""

    texto = resultado["ParsedResults"][0]["ParsedText"]

    return texto

# =====================================================
# HOME
# =====================================================

@app.route("/")
def home():

    if "user_id" not in session:
        return redirect("/login")

    return redirect("/contabilidad")

# =====================================================
# LOGIN
# =====================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        usuario = buscar_usuario(username, password)

        if usuario:

            session["user_id"] = usuario[0]

            return redirect("/contabilidad")

        return "Usuario incorrecto"

    return render_template("login.html")

# =====================================================
# REGISTER
# =====================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        crear_usuario(username, password)

        return redirect("/login")

    return render_template("register.html")

# =====================================================
# LOGOUT
# =====================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/login")

# =====================================================
# CONTABILIDAD
# =====================================================

@app.route("/contabilidad")
def contabilidad():

    if "user_id" not in session:
        return redirect("/login")

    movimientos = get_movimientos(session["user_id"])

    ingresos = 0
    gastos = 0

    for m in movimientos:

        importe = safe_float(m[3])
        tipo = m[4]

        if tipo == "INGRESO":
            ingresos += importe

        elif tipo == "GASTO":
            gastos += importe

    beneficio = ingresos - gastos

    return render_template(
        "dashboard.html",
        movimientos=movimientos,
        ingresos=round(ingresos, 2),
        gastos=round(gastos, 2),
        beneficio=round(beneficio, 2)
    )

# =====================================================
# UPLOAD + OCR CLOUD
# =====================================================

@app.route("/upload", methods=["POST"])
def upload_file():

    if "user_id" not in session:
        return redirect("/login")

    if "file" not in request.files:
        return "No file"

    file = request.files["file"]

    if file.filename == "":
        return "Archivo vacío"

    filepath = os.path.join(
        app.config["UPLOAD_FOLDER"],
        file.filename
    )

    file.save(filepath)

    fecha = datetime.now().strftime("%Y-%m-%d")

    try:

        # =========================================
        # OCR CLOUD
        # =========================================

        texto = hacer_ocr(filepath)

        # =========================================
        # EXTRAER TOTAL
        # =========================================

        total = extraer_total(texto)

        # =========================================
        # CLASIFICAR
        # =========================================

        tipo = clasificar(texto)

        # =========================================
        # GUARDAR DB
        # =========================================

        insert_movimiento(
            session["user_id"],
            texto,
            total,
            tipo,
            fecha
        )

        return redirect("/contabilidad")

    except Exception as e:

        return f"ERROR OCR CLOUD: {e}"

# =====================================================
# EXPORTAR EXCEL
# =====================================================

@app.route("/exportar_excel")
def exportar_excel():

    if "user_id" not in session:
        return redirect("/login")

    movimientos = get_movimientos(session["user_id"])

    wb = openpyxl.Workbook()

    ws = wb.active

    ws.title = "Contabilidad"

    ws.append([
        "Fecha",
        "Tipo",
        "Importe"
    ])

    for m in movimientos:

        ws.append([
            m[5],
            m[4],
            m[3]
        ])

    archivo = "contabilidad.xlsx"

    wb.save(archivo)

    return send_file(
        archivo,
        as_attachment=True
    )

# =====================================================
# MAIN
# =====================================================

if __name__ == "__main__":
    app.run()