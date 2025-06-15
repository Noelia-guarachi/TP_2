
import mysql.connector
from datetime import datetime
import sys

dni = sys.argv[1]  

def marcar_salida_por_dni(dni):
    try:
        conexion = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="registro_visitas"
        )

        cursor = conexion.cursor()

       
        cursor.execute("""
            SELECT id, hora_egreso FROM visitas 
            WHERE dni = %s 
            ORDER BY hora_ingreso DESC LIMIT 1
        """, (dni,))
        resultado = cursor.fetchone()

        if resultado is None:
            print("No se encontró ninguna visita pendiente de salida para el DNI ingresado.")
            return

        visita_id, hora_egreso = resultado

        if hora_egreso is not None:
            print("La salida ya fue registrada anteriormente.")
            return

        hora_actual = datetime.now()
        cursor.execute("UPDATE visitas SET hora_egreso = %s WHERE id = %s", (hora_actual, visita_id))
        conexion.commit()

        print(f"✅ Salida registrada correctamente a las {hora_actual.strftime('%H:%M:%S')}.")

    except mysql.connector.Error as error:
        print(f"❌ Error al conectar o actualizar la base de datos: {error}")
    finally:
        if conexion.is_connected():
            cursor.close()
            conexion.close()

marcar_salida_por_dni(dni)
