from flask import Flask, render_template, request, redirect, session, send_file
import os
import re
from datetime import datetime

from PIL import Image
import pytesseract
import openpyxl

from database import (
    init_db,
    crear_usuario,
    buscar_usuario,
    insert_movimiento,
    get_movimientos
)

# =====================================================
# CONFIG APP
# =====================================================

app = Flask(__name__)
app.secret_key = "clave_super_segura"

UPLOAD_FOLDER = "uploads"

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# =====================================================
# OCR TESSERACT
# =====================================================

# SOLO PARA WINDOWS LOCAL
# En Render normalmente NO existe Tesseract
TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

if os.path.exists(TESSERACT_PATH):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

# =====================================================
# INICIAR DB
# =====================================================

init_db()

# =====================================================
# FUNCIONES AUXILIARES
# =====================================================

def safe_float(valor):

    if valor is None:
        return 0.0

    texto = str(valor)

    texto = texto.replace("€", "")
    texto = texto.replace("EUR", "")
    texto = texto.replace(" ", "")

    # ---------------------------------------------
    # CASOS:
    # 127.000,00
    # 1.250,50
    # 999,99
    # ---------------------------------------------

    if "." in texto and "," in texto:

        # europeo: 127.000,00
        texto = texto.replace(".", "")
        texto = texto.replace(",", ".")

    elif "," in texto:

        # 250,50
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

    if not valores:
        return 0.0

    return max(valores)


def clasificar(texto):

    t = texto.lower()

    # ---------------------------------------------
    # INGRESOS
    # ---------------------------------------------

    palabras_ingreso = [
        "factura emitida",
        "factura venta",
        "cliente",
        "cobro",
        "ingreso",
        "venta",
        "base imponible"
    ]

    # ---------------------------------------------
    # GASTOS
    # ---------------------------------------------

    palabras_gasto = [
        "factura recibida",
        "proveedor",
        "compra",
        "ticket",
        "gasto",
        "pagado"
    ]

    for p in palabras_ingreso:
        if p in t:
            return "INGRESO"

    for p in palabras_gasto:
        if p in t:
            return "GASTO"

    # ---------------------------------------------
    # HEURÍSTICA SIMPLE
    # ---------------------------------------------

    if "cliente" in t:
        return "INGRESO"

    if "proveedor" in t:
        return "GASTO"

    return "DESCONOCIDO"

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

        return "❌ Usuario o contraseña incorrectos"

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
# DASHBOARD CONTABILIDAD
# =====================================================

@app.route("/contabilidad")
def contabilidad():

    if "user_id" not in session:
        return redirect("/login")

    movimientos = get_movimientos(session["user_id"])

    ingresos = 0.0
    gastos = 0.0

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
# UPLOAD + OCR
# =====================================================

@app.route("/upload", methods=["POST"])
def upload_file():

    if "user_id" not in session:
        return redirect("/login")

    if "file" not in request.files:
        return "❌ No se encontró archivo"

    file = request.files["file"]

    if file.filename == "":
        return "❌ Archivo vacío"

    filepath = os.path.join(
        app.config["UPLOAD_FOLDER"],
        file.filename
    )

    file.save(filepath)

    fecha = datetime.now().strftime("%Y-%m-%d")

    try:

        # =========================================
        # OCR
        # =========================================

        img = Image.open(filepath).convert("L")

        texto = pytesseract.image_to_string(img)

        # =========================================
        # EXTRAER TOTAL
        # =========================================

        total = extraer_total(texto)

        # =========================================
        # CLASIFICAR
        # =========================================

        tipo = clasificar(texto)

        # =========================================
        # GUARDAR
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

        return f"ERROR OCR: {e}"

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