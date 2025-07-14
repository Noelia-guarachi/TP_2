from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import pandas as pd
import io

# Para la generación de PDF (ReportLab)
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors, units

# --- Configuración de la Aplicación Flask ---
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SECRET_KEY'] = 'una_clave_secreta_muy_segura_para_el_tp_2025' # ¡CAMBIA ESTO POR UNA CADENA MÁS COMPLEJA Y ÚNICA!
db = SQLAlchemy(app)

# --- Modelos de la Base de Datos ---
# Representan las tablas en tu base de datos SQLite

class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(50), nullable=False, default='personal') # Ejemplo: 'admin', 'personal'

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<Usuario {self.username}>'

class Visita(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    dni_visitante = db.Column(db.String(20), nullable=False, index=True)
    nombre_visitante = db.Column(db.String(100), nullable=False)
    apellido_visitante = db.Column(db.String(100), nullable=True) # Campo opcional
    motivo = db.Column(db.String(255))
    persona_visitada = db.Column(db.String(100)) # A quién visita dentro del edificio
    fecha_ingreso = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_egreso = db.Column(db.DateTime, nullable=True)
    estado = db.Column(db.String(10), default='Ingresado') # 'Ingresado' o 'Egreso'

    def __repr__(self):
        return f'<Visita {self.nombre_visitante} - DNI: {self.dni_visitante}>'

# --- Inicialización de la Base de Datos y Creación de Usuario Admin ---
# Esta función se ejecuta una sola vez cuando la aplicación se inicia por primera vez.
@app.before_first_request
def create_tables_and_admin():
    db.create_all() # Crea todas las tablas definidas en los modelos
    # Crea un usuario administrador por defecto si no existe
    if not Usuario.query.filter_by(username='admin').first():
        admin_user = Usuario(username='admin', role='admin')
        admin_user.set_password('admin123') # ¡IMPORTANTE: CAMBIA ESTA CONTRASEÑA EN UN ENTORNO REAL!
        db.session.add(admin_user)
        db.session.commit()
        print("Usuario 'admin' creado con contraseña 'admin123'. ¡Cámbiala en una aplicación real!")

    # Opcional: Agregar algunos datos de visita de ejemplo si la tabla está vacía
    if Visita.query.count() == 0:
        visits_to_add = [
            Visita(dni_visitante="12345678", nombre_visitante="Juan", apellido_visitante="Pérez", motivo="Reunión", persona_visitada="Ana Gómez", fecha_ingreso=datetime(2024, 7, 10, 9, 0), fecha_egreso=datetime(2024, 7, 10, 10, 30), estado="Egreso"),
            Visita(dni_visitante="87654321", nombre_visitante="María", apellido_visitante="López", motivo="Entrega", persona_visitada="Recepción", fecha_ingreso=datetime(2024, 7, 11, 14, 0), estado="Ingresado"),
            Visita(dni_visitante="11223344", nombre_visitante="Carlos", apellido_visitante="Ruiz", motivo="Mantenimiento", persona_visitada="Sistemas", fecha_ingreso=datetime(2024, 7, 12, 8, 30), fecha_egreso=datetime(2024, 7, 12, 10, 0), estado="Egreso"),
            Visita(dni_visitante="12345678", nombre_visitante="Juan", apellido_visitante="Pérez", motivo="Consulta", persona_visitada="Ana Gómez", fecha_ingreso=datetime(2024, 7, 13, 11, 0), estado="Ingresado"),
        ]
        db.session.add_all(visits_to_add)
        db.session.commit()
        print("Datos de visitas de ejemplo agregados.")


# --- Rutas de la Aplicación ---

@app.route('/')
def index():
    # Redirige al login si el usuario no ha iniciado sesión
    if 'user_id' not in session:
        return redirect(url_for('login'))
    # Si está logueado, redirige a la página de listar visitas
    return redirect(url_for('listar_visitas'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = Usuario.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            flash('¡Inicio de sesión exitoso!', 'success')
            return redirect(url_for('listar_visitas'))
        else:
            flash('Usuario o contraseña incorrectos.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    session.pop('role', None)
    flash('Has cerrado sesión.', 'info')
    return redirect(url_for('login'))

# --- TU CÓDIGO: Listado, Búsqueda y Filtrado de Visitas ---

@app.route('/visitas', methods=['GET'])
def listar_visitas():
    # Asegúrate de que solo los usuarios logueados puedan acceder
    if 'user_id' not in session:
        flash('Debes iniciar sesión para ver esta página.', 'warning')
        return redirect(url_for('login'))

    # Inicializa la consulta para obtener todas las visitas
    query = Visita.query

    # --- Obtener parámetros de filtro del formulario GET ---
    dni_search = request.args.get('dni_search', '').strip()
    nombre_search = request.args.get('nombre_search', '').strip()
    estado_filter = request.args.get('estado_filter', 'all').strip() # 'all' para todos los estados
    fecha_inicio_filter = request.args.get('fecha_inicio_filter', '').strip()
    fecha_fin_filter = request.args.get('fecha_fin_filter', '').strip()

    # --- Aplicar filtros a la consulta de la base de datos ---

    # 1. Filtro por DNI
    if dni_search:
        query = query.filter(Visita.dni_visitante == dni_search)

    # 2. Filtro por Nombre o Apellido (búsqueda parcial e insensible a mayúsculas/minúsculas)
    if nombre_search:
        # Busca en nombre O apellido
        query = query.filter(
            (Visita.nombre_visitante.ilike(f'%{nombre_search}%')) |
            (Visita.apellido_visitante.ilike(f'%{nombre_search}%'))
        )

    # 3. Filtro por Estado (Ingresado/Egreso)
    if estado_filter != 'all':
        query = query.filter(Visita.estado == estado_filter)

    # 4. Filtro por Rango de Fechas de Ingreso
    if fecha_inicio_filter:
        try:
            start_date = datetime.strptime(fecha_inicio_filter, '%Y-%m-%d')
            query = query.filter(Visita.fecha_ingreso >= start_date)
        except ValueError:
            flash('Formato de fecha de inicio inválido. Use AAAA-MM-DD.', 'danger')

    if fecha_fin_filter:
        try:
            # Sumamos un día para incluir todo el día final en el rango
            end_date = datetime.strptime(fecha_fin_filter, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(Visita.fecha_ingreso < end_date)
        except ValueError:
            flash('Formato de fecha de fin inválido. Use AAAA-MM-DD.', 'danger')

    # Ordenar los resultados (ej. por fecha de ingreso, las más recientes primero)
    visitas = query.order_by(Visita.fecha_ingreso.desc()).all()

    # Renderiza la plantilla HTML, pasando las visitas filtradas y los valores de filtro para que se mantengan en los campos
    return render_template('listar_visitas.html',
                           visitas=visitas,
                           dni_search=dni_search,
                           nombre_search=nombre_search,
                           estado_filter=estado_filter,
                           fecha_inicio_filter=fecha_inicio_filter,
                           fecha_fin_filter=fecha_fin_filter)

# --- TU CÓDIGO: Exportación a CSV ---

@app.route('/exportar_csv', methods=['GET'])
def exportar_csv():
    if 'user_id' not in session:
        flash('Debes iniciar sesión para exportar datos.', 'warning')
        return redirect(url_for('login'))

    # Reutiliza la misma lógica de filtrado que en listar_visitas
    # Esto asegura que el CSV contenga los datos exactamente como se muestran filtrados
    query = Visita.query

    dni_search = request.args.get('dni_search', '').strip()
    nombre_search = request.args.get('nombre_search', '').strip()
    estado_filter = request.args.get('estado_filter', 'all').strip()
    fecha_inicio_filter = request.args.get('fecha_inicio_filter', '').strip()
    fecha_fin_filter = request.args.get('fecha_fin_filter', '').strip()

    if dni_search:
        query = query.filter(Visita.dni_visitante == dni_search)
    if nombre_search:
        query = query.filter(
            (Visita.nombre_visitante.ilike(f'%{nombre_search}%')) |
            (Visita.apellido_visitante.ilike(f'%{nombre_search}%'))
        )
    if estado_filter != 'all':
        query = query.filter(Visita.estado == estado_filter)
    if fecha_inicio_filter:
        try:
            start_date = datetime.strptime(fecha_inicio_filter, '%Y-%m-%d')
            query = query.filter(Visita.fecha_ingreso >= start_date)
        except ValueError:
            pass
    if fecha_fin_filter:
        try:
            end_date = datetime.strptime(fecha_fin_filter, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(Visita.fecha_ingreso < end_date)
        except ValueError:
            pass

    visitas_a_exportar = query.order_by(Visita.fecha_ingreso.desc()).all()

    # Prepara los datos en un formato de lista de diccionarios para pandas
    data_for_df = []
    for visita in visitas_a_exportar:
        data_for_df.append({
            'ID': visita.id,
            'DNI': visita.dni_visitante,
            'Nombre': visita.nombre_visitante,
            'Apellido': visita.apellido_visitante if visita.apellido_visitante else '',
            'Motivo': visita.motivo if visita.motivo else '',
            'Persona Visitada': visita.persona_visitada if visita.persona_visitada else '',
            'Fecha Ingreso': visita.fecha_ingreso.strftime('%Y-%m-%d %H:%M:%S'),
            'Fecha Egreso': visita.fecha_egreso.strftime('%Y-%m-%d %H:%M:%S') if visita.fecha_egreso else 'N/A',
            'Estado': visita.estado
        })

    # Crea un DataFrame de pandas con los datos
    df = pd.DataFrame(data_for_df)

    # Crea un buffer en memoria para guardar el contenido CSV
    output = io.StringIO()
    # Exporta el DataFrame a CSV, sin el índice y con codificación UTF-8
    df.to_csv(output, index=False, encoding='utf-8')
    output.seek(0) # Mueve el cursor al inicio del buffer

    # Envía el archivo CSV al navegador para su descarga
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')), # Flask send_file necesita bytes
        mimetype='text/csv',
        as_attachment=True,
        download_name='visitas_filtradas.csv'
    )

# --- TU CÓDIGO: Exportación a PDF ---

@app.route('/exportar_pdf', methods=['GET'])
def exportar_pdf():
    if 'user_id' not in session:
        flash('Debes iniciar sesión para exportar datos.', 'warning')
        return redirect(url_for('login'))

    # Reutiliza la misma lógica de filtrado
    query = Visita.query

    dni_search = request.args.get('dni_search', '').strip()
    nombre_search = request.args.get('nombre_search', '').strip()
    estado_filter = request.args.get('estado_filter', 'all').strip()
    fecha_inicio_filter = request.args.get('fecha_inicio_filter', '').strip()
    fecha_fin_filter = request.args.get('fecha_fin_filter', '').strip()

    if dni_search:
        query = query.filter(Visita.dni_visitante == dni_search)
    if nombre_search:
        query = query.filter(
            (Visita.nombre_visitante.ilike(f'%{nombre_search}%')) |
            (Visita.apellido_visitante.ilike(f'%{nombre_search}%'))
        )
    if estado_filter != 'all':
        query = query.filter(Visita.estado == estado_filter)
    if fecha_inicio_filter:
        try:
            start_date = datetime.strptime(fecha_inicio_filter, '%Y-%m-%d')
            query = query.filter(Visita.fecha_ingreso >= start_date)
        except ValueError:
            pass
    if fecha_fin_filter:
        try:
            end_date = datetime.strptime(fecha_fin_filter, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(Visita.fecha_ingreso < end_date)
        except ValueError:
            pass

    visitas_a_exportar = query.order_by(Visita.fecha_ingreso.desc()).all()

    # --- Lógica de generación de PDF con ReportLab ---
    buffer = io.BytesIO() # Buffer en memoria para guardar el PDF
    # Configuración del documento PDF
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            rightMargin=units.inch/2, leftMargin=units.inch/2,
                            topMargin=units.inch/2, bottomMargin=units.inch/2)
    styles = getSampleStyleSheet()
    elements = []

    # Título y metadata del reporte
    elements.append(Paragraph("<b>Reporte de Visitas Filtradas</b>", styles['h1']))
    elements.append(Spacer(1, 0.2 * units.inch))
    elements.append(Paragraph(f"Generado el: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
    elements.append(Spacer(1, 0.4 * units.inch))

    # Encabezados de la tabla para el PDF
    headers = ['DNI', 'Nombre Completo', 'Motivo', 'Persona Visitada', 'Fecha Ingreso', 'Fecha Egreso', 'Estado']
    # Prepara los datos para la tabla del PDF
    data = [headers]
    for visita in visitas_a_exportar:
        data.append([
            visita.dni_visitante,
            f"{visita.nombre_visitante} {visita.apellido_visitante or ''}",
            visita.motivo or '',
            visita.persona_visitada or '',
            visita.fecha_ingreso.strftime('%Y-%m-%d %H:%M'),
            visita.fecha_egreso.strftime('%Y-%m-%d %H:%M') if visita.fecha_egreso else 'N/A',
            visita.estado
        ])

    # Crea la tabla y aplica estilos
    # Los colWidths son estimaciones, ajústalos según necesites
    table = Table(data, colWidths=[0.8*units.inch, 1.5*units.inch, 1.5*units.inch, 1.2*units.inch, 1.5*units.inch, 1.5*units.inch, 0.8*units.inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#007bff')), # Azul de Bootstrap
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONTSIZE', (0,0), (-1,-1), 8) # Tamaño de fuente para el contenido
    ]))
    elements.append(table)

    doc.build(elements) # Construye el documento PDF

    buffer.seek(0) # Mueve el cursor al inicio del buffer para leerlo
    # Envía el archivo PDF al navegador para su descarga
    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name='visitas_filtradas.pdf'
    )

# --- Ruta para registrar una nueva visita (ejemplo básico, puedes expandirlo) ---
@app.route('/registrar_visita', methods=['GET', 'POST'])
def registrar_visita():
    if 'user_id' not in session:
        flash('Debes iniciar sesión para registrar visitas.', 'warning')
        return redirect(url_for('login'))

    if request.method == 'POST':
        dni = request.form['dni']
        nombre = request.form['nombre']
        apellido = request.form.get('apellido', '') # .get para campos opcionales
        motivo = request.form['motivo']
        persona_visitada = request.form['persona_visitada']

        if not dni or not nombre or not motivo or not persona_visitada:
            flash('Por favor, completa todos los campos obligatorios.', 'danger')
        else:
            # Crea una nueva visita y guárdala
            nueva_visita = Visita(
                dni_visitante=dni,
                nombre_visitante=nombre,
                apellido_visitante=apellido,
                motivo=motivo,
                persona_visitada=persona_visitada,
                fecha_ingreso=datetime.utcnow(),
                estado='Ingresado'
            )
            db.session.add(nueva_visita)
            db.session.commit()
            flash('Visita registrada exitosamente como "Ingresado".', 'success')
            return redirect(url_for('listar_visitas'))
    
    return render_template('registrar_visita.html') # Necesitarás crear este HTML

# --- Ruta para registrar egreso de una visita (ejemplo básico) ---
@app.route('/registrar_egreso/<int:visita_id>', methods=['POST'])
def registrar_egreso(visita_id):
    if 'user_id' not in session:
        flash('Debes iniciar sesión para registrar egresos.', 'warning')
        return redirect(url_for('login'))
    
    visita = Visita.query.get_or_404(visita_id)
    if visita.estado == 'Ingresado':
        visita.fecha_egreso = datetime.utcnow()
        visita.estado = 'Egreso'
        db.session.commit()
        flash(f'Egreso de {visita.nombre_visitante} registrado exitosamente.', 'success')
    else:
        flash('La visita ya ha egresado o no está en estado "Ingresado".', 'warning')
    
    return redirect(url_for('listar_visitas'))

# --- Iniciar la Aplicación ---
if __name__ == '__main__':
    # Esto es crucial para Replit: le dice a Flask que escuche en todas las interfaces
    # y en el puerto que Replit le asigna.
    app.run(host='0.0.0.0', port=8080, debug=True)