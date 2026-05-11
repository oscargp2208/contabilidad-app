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
# APP
# =====================================================

app = Flask(__name__)
app.secret_key = "clave_super_segura"

UPLOAD_FOLDER = "uploads"

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# =====================================================
# OCR API
# =====================================================

OCR_API_KEY = "K87458836088957"

# =====================================================
# DB INIT
# =====================================================

init_db()

# =====================================================
# HELPERS
# =====================================================

def safe_float(valor):
    if valor is None:
        return 0.0

    texto = str(valor)

    texto = texto.replace("€", "")
    texto = texto.replace("EUR", "")
    texto = texto.replace(" ", "")

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
        v = safe_float(n)
        if v > 0:
            valores.append(v)

    return max(valores) if valores else 0.0


def clasificar(texto):
    t = texto.lower()

    ingresos = ["venta", "cliente", "factura emitida", "ingreso", "cobro"]
    gastos = ["proveedor", "compra", "gasto", "factura recibida", "ticket"]

    for i in ingresos:
        if i in t:
            return "INGRESO"

    for g in gastos:
        if g in t:
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

    data = response.json()

    if data.get("IsErroredOnProcessing"):
        return ""

    return data["ParsedResults"][0]["ParsedText"]

# =====================================================
# ROUTES
# =====================================================

@app.route("/")
def home():
    if "user_id" not in session:
        return redirect("/login")
    return redirect("/contabilidad")


@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        user = buscar_usuario(
            request.form["username"],
            request.form["password"]
        )

        if user:
            session["user_id"] = user[0]
            return redirect("/contabilidad")

        return "Login incorrecto"

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        crear_usuario(
            request.form["username"],
            request.form["password"]
        )

        return redirect("/login")

    return render_template("register.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# =====================================================
# DASHBOARD SAAS
# =====================================================

@app.route("/contabilidad")
def contabilidad():

    if "user_id" not in session:
        return redirect("/login")

    movimientos = get_movimientos(session["user_id"])

    ingresos = 0
    gastos = 0

    historial = []

    for m in movimientos:

        importe = safe_float(m[3])
        tipo = m[4]

        if tipo == "INGRESO":
            ingresos += importe
        elif tipo == "GASTO":
            gastos += importe

        historial.append({
            "fecha": m[5],
            "tipo": tipo,
            "importe": importe,
            "texto": m[2]
        })

    beneficio = ingresos - gastos

    return render_template(
        "dashboard.html",
        ingresos=round(ingresos, 2),
        gastos=round(gastos, 2),
        beneficio=round(beneficio, 2),
        movimientos=historial
    )

# =====================================================
# UPLOAD OCR
# =====================================================

@app.route("/upload", methods=["POST"])
def upload():

    if "user_id" not in session:
        return redirect("/login")

    file = request.files["file"]

    filepath = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
    file.save(filepath)

    texto = hacer_ocr(filepath)

    total = extraer_total(texto)
    tipo = clasificar(texto)

    insert_movimiento(
        session["user_id"],
        texto,
        total,
        tipo,
        datetime.now().strftime("%Y-%m-%d")
    )

    return redirect("/contabilidad")

# =====================================================
# EXPORT EXCEL
# =====================================================

@app.route("/exportar_excel")
def exportar_excel():

    if "user_id" not in session:
        return redirect("/login")

    movimientos = get_movimientos(session["user_id"])

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Contabilidad"

    ws.append(["Fecha", "Tipo", "Importe"])

    for m in movimientos:
        ws.append([m[5], m[4], m[3]])

    file = "contabilidad.xlsx"
    wb.save(file)

    return send_file(file, as_attachment=True)

# =====================================================
# RUN (RENDER COMPATIBLE)
# =====================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)