from flask import Flask, render_template, request, redirect
import sqlite3
from datetime import datetime

app = Flask(__name__)

def unir_bd():
    with sqlite3.connect("visitas.db") as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS visitas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT,
                apellido TEXT,
                dni TEXT,
                motivo TEXT,
                persona_visita TEXT,
                hora_ingreso TEXT
            )
        """)
unir_bd()

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        nombre = request.form["nombre"]
        apellido = request.form["apellido"]
        dni = request.form["dni"]
        motivo = request.form["motivo"]
        persona_visita = request.form["persona_visita"]
        hora_ingreso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with sqlite3.connect("visitas.db") as conn:
            conn.execute("INSERT INTO visitas (nombre, apellido, dni, motivo, persona_visita, hora_ingreso) VALUES (?, ?, ?, ?, ?, ?)",
                         (nombre, apellido, dni, motivo, persona_visita, hora_ingreso))
        return redirect("/")

    # Para GET: obtener todas las visitas y enviarlas al template
    with sqlite3.connect("visitas.db") as conn:
        cursor = conn.execute("SELECT nombre, apellido, dni, motivo, persona_visita, hora_ingreso FROM visitas ORDER BY id DESC")
        visitas = cursor.fetchall()

    return render_template("index.html", visitas=visitas)


if __name__ == "__main__":
    app.run(debug=True)
