from flask import Flask, render_template, request, redirect, session, send_file
import os
from PIL import Image
import pytesseract
import re
from datetime import datetime
import openpyxl

from database import (
    init_db,
    crear_usuario,
    buscar_usuario,
    insert_movimiento,
    get_movimientos
)

app = Flask(__name__)
app.secret_key = "clave_super_segura"

UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

init_db()

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


# =====================================================
# LOGIN
# =====================================================
@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        user = buscar_usuario(username, password)

        if user:
            session["user_id"] = user[0]
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
# HOME
# =====================================================
@app.route("/")
def home():

    if "user_id" not in session:
        return redirect("/login")

    return redirect("/contabilidad")


# =====================================================
# UPLOAD FACTURAS + OCR
# =====================================================
@app.route("/upload", methods=["POST"])
def upload_file():

    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    file = request.files["file"]

    filepath = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
    file.save(filepath)

    fecha = datetime.now().strftime("%Y-%m-%d")

    try:

        img = Image.open(filepath).convert("L")
        text = pytesseract.image_to_string(img)

        amounts = re.findall(r"\b\d+[.,]?\d*\b", text)

        total = max([safe_float(a) for a in amounts]) if amounts else 0.0
        tipo = clasificar(text)

        insert_movimiento(user_id, text, total, tipo, fecha)

        return redirect("/contabilidad")

    except Exception as e:
        return f"ERROR OCR: {e}"


# =====================================================
# DASHBOARD
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
        else:
            gastos += importe

    return render_template(
        "dashboard.html",
        ingresos=ingresos,
        gastos=gastos,
        beneficio=ingresos - gastos,
        movimientos=movimientos
    )


# =====================================================
# EXPORTAR EXCEL
# =====================================================
@app.route("/exportar_excel")
def exportar_excel():

    if "user_id" not in session:
        return redirect("/login")

    datos = get_movimientos(session["user_id"])

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Contabilidad"

    ws.append(["Fecha", "Tipo", "Importe"])

    for d in datos:
        ws.append([d[5], d[4], d[3]])

    archivo = "contabilidad.xlsx"
    wb.save(archivo)

    return send_file(archivo, as_attachment=True)


# =====================================================
# SAFE FLOAT
# =====================================================
def safe_float(v):

    if not v:
        return 0.0

    try:
        v = str(v).replace("€", "").replace(" ", "").replace(",", ".")
        return float(v)
    except:
        return 0.0


# =====================================================
# CLASIFICADOR
# =====================================================
def clasificar(texto):

    t = texto.lower()

    ingresos = ["venta", "cliente", "cobro", "factura"]
    gastos = ["compra", "proveedor", "ticket", "gasto"]

    if any(x in t for x in ingresos):
        return "INGRESO"

    if any(x in t for x in gastos):
        return "GASTO"

    return "DESCONOCIDO"


# =====================================================
# MAIN
# =====================================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)