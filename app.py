from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
import sqlite3
from datetime import datetime, date, timedelta
import os
import exportar
from PIL import Image as PILImage, ImageDraw, ImageFont
import io as _io

app = Flask(__name__)
app.secret_key = 'ganado_vacuno_2026'

_BASE    = os.path.dirname(os.path.abspath(__file__))
# En Android se sobreescribe con almacenamiento persistente via GANADO_DB
DATABASE = os.environ.get('GANADO_DB', os.path.join(_BASE, 'ganado.db'))

UPLOAD_DIR      = os.path.join(_BASE, 'static', 'uploads')
UPLOAD_ANIM_DIR = os.path.join(UPLOAD_DIR, 'animales')
ALLOWED_EXT      = {'jpg', 'jpeg', 'png', 'webp'}
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024  # 8 MB máximo

def _ext_ok(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT

def _save_img(stream, dest_path, max_px=900):
    """Abre, redimensiona y guarda como JPEG."""
    img = PILImage.open(stream)
    img.thumbnail((max_px, max_px), PILImage.LANCZOS)
    if img.mode not in ('RGB', 'L'):
        img = img.convert('RGB')
    img.save(dest_path, 'JPEG', quality=85, optimize=True)

# Filtro personalizado para Jinja2
app.jinja_env.filters['enumerate'] = enumerate


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()
    c.executescript('''
        CREATE TABLE IF NOT EXISTS animales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            arete TEXT UNIQUE NOT NULL,
            nombre TEXT,
            raza TEXT NOT NULL,
            sexo TEXT NOT NULL,
            fecha_nacimiento DATE,
            peso_actual REAL,
            madre_id INTEGER,
            padre_arete TEXT,
            estado TEXT DEFAULT 'activo',
            proposito TEXT DEFAULT 'doble_proposito',
            observaciones TEXT,
            fecha_ingreso DATE DEFAULT (date('now')),
            FOREIGN KEY (madre_id) REFERENCES animales(id)
        );

        CREATE TABLE IF NOT EXISTS salud (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            animal_id INTEGER NOT NULL,
            fecha DATE NOT NULL,
            tipo TEXT NOT NULL,
            descripcion TEXT,
            medicamento TEXT,
            dosis TEXT,
            via_administracion TEXT,
            veterinario TEXT,
            costo REAL DEFAULT 0,
            proxima_cita DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (animal_id) REFERENCES animales(id)
        );

        CREATE TABLE IF NOT EXISTS reproduccion (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vaca_id INTEGER NOT NULL,
            toro_arete TEXT,
            fecha_servicio DATE NOT NULL,
            tipo_servicio TEXT DEFAULT 'monta_natural',
            fecha_parto_esperado DATE,
            fecha_parto_real DATE,
            num_crias INTEGER DEFAULT 0,
            sexo_cria TEXT,
            peso_nacimiento REAL,
            estado TEXT DEFAULT 'gestacion',
            observaciones TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (vaca_id) REFERENCES animales(id)
        );

        CREATE TABLE IF NOT EXISTS produccion_leche (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            animal_id INTEGER NOT NULL,
            fecha DATE NOT NULL,
            manana REAL DEFAULT 0,
            tarde REAL DEFAULT 0,
            total REAL DEFAULT 0,
            observaciones TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (animal_id) REFERENCES animales(id)
        );

        CREATE TABLE IF NOT EXISTS pesos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            animal_id INTEGER NOT NULL,
            fecha DATE NOT NULL,
            peso REAL NOT NULL,
            condicion_corporal INTEGER,
            observaciones TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (animal_id) REFERENCES animales(id)
        );

        CREATE TABLE IF NOT EXISTS finanzas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha DATE NOT NULL,
            tipo TEXT NOT NULL,
            categoria TEXT NOT NULL,
            descripcion TEXT,
            monto REAL NOT NULL,
            animal_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (animal_id) REFERENCES animales(id)
        );

        CREATE TABLE IF NOT EXISTS alertas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            animal_id INTEGER,
            tipo TEXT NOT NULL,
            mensaje TEXT NOT NULL,
            fecha_alerta DATE NOT NULL,
            atendida INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (animal_id) REFERENCES animales(id)
        );

        CREATE TABLE IF NOT EXISTS configuracion (
            clave TEXT PRIMARY KEY,
            valor TEXT DEFAULT ''
        );
    ''')

    # Columna foto en animales (migración segura)
    try:
        conn.execute("ALTER TABLE animales ADD COLUMN foto TEXT")
    except sqlite3.OperationalError:
        pass  # Ya existe

    # Valores por defecto de la configuración (solo si no existen)
    defaults = [
        ('nombre_hacienda', 'Mi Rancho'),
        ('propietario',     ''),
        ('ubicacion',       ''),
        ('telefono',        ''),
        ('email',           ''),
        ('descripcion',     ''),
        ('logo_archivo',    ''),
    ]
    for clave, valor in defaults:
        conn.execute("INSERT OR IGNORE INTO configuracion (clave, valor) VALUES (?,?)",
                     (clave, valor))

    conn.commit()
    conn.close()


def get_config():
    """Devuelve la configuración como dict. Seguro si la tabla aún no existe."""
    try:
        conn = get_db()
        cfg = {r['clave']: r['valor']
               for r in conn.execute("SELECT clave, valor FROM configuracion").fetchall()}
        conn.close()
        return cfg
    except Exception:
        return {}


@app.context_processor
def inject_config():
    """Inyecta 'cfg' en todos los templates automáticamente."""
    return {'cfg': get_config()}


# ─── DASHBOARD ────────────────────────────────────────────────────────────────

@app.route('/')
def dashboard():
    conn = get_db()
    hoy = date.today().isoformat()

    stats = {
        'total_animales': conn.execute("SELECT COUNT(*) FROM animales WHERE estado='activo'").fetchone()[0],
        'vacas': conn.execute("SELECT COUNT(*) FROM animales WHERE sexo='hembra' AND estado='activo'").fetchone()[0],
        'toros': conn.execute("SELECT COUNT(*) FROM animales WHERE sexo='macho' AND estado='activo'").fetchone()[0],
        'terneros': conn.execute(
            "SELECT COUNT(*) FROM animales WHERE fecha_nacimiento >= date('now','-12 months') AND estado='activo'"
        ).fetchone()[0],
        'gestantes': conn.execute(
            "SELECT COUNT(*) FROM reproduccion WHERE estado='gestacion'"
        ).fetchone()[0],
        'leche_hoy': conn.execute(
            "SELECT COALESCE(SUM(total),0) FROM produccion_leche WHERE fecha=?", (hoy,)
        ).fetchone()[0],
        'proximas_vacunas': conn.execute(
            "SELECT COUNT(*) FROM salud WHERE proxima_cita BETWEEN ? AND date(?,'+7 days')",
            (hoy, hoy)
        ).fetchone()[0],
    }

    # Producción últimos 7 días
    leche_semana = conn.execute('''
        SELECT fecha, SUM(total) as litros
        FROM produccion_leche
        WHERE fecha >= date('now','-6 days')
        GROUP BY fecha ORDER BY fecha
    ''').fetchall()

    # Ingresos vs gastos mes actual
    balance = conn.execute('''
        SELECT tipo, SUM(monto) as total
        FROM finanzas
        WHERE strftime('%Y-%m', fecha) = strftime('%Y-%m', 'now')
        GROUP BY tipo
    ''').fetchall()

    # Próximos partos (30 días)
    proximos_partos = conn.execute('''
        SELECT r.*, a.arete, a.nombre
        FROM reproduccion r
        JOIN animales a ON r.vaca_id = a.id
        WHERE r.estado='gestacion' AND r.fecha_parto_esperado BETWEEN ? AND date(?,'+30 days')
        ORDER BY r.fecha_parto_esperado
        LIMIT 5
    ''', (hoy, hoy)).fetchall()

    # Próximas vacunas
    proximas_vacunas = conn.execute('''
        SELECT s.*, a.arete, a.nombre
        FROM salud s
        JOIN animales a ON s.animal_id = a.id
        WHERE s.proxima_cita BETWEEN ? AND date(?,'+14 days')
        ORDER BY s.proxima_cita
        LIMIT 5
    ''', (hoy, hoy)).fetchall()

    conn.close()
    return render_template('dashboard.html',
                           stats=stats,
                           leche_semana=leche_semana,
                           balance=balance,
                           proximos_partos=proximos_partos,
                           proximas_vacunas=proximas_vacunas)


# ─── ANIMALES ─────────────────────────────────────────────────────────────────

@app.route('/animales')
def animales():
    conn = get_db()
    filtro_estado = request.args.get('estado', 'activo')
    filtro_sexo = request.args.get('sexo', '')
    buscar = request.args.get('q', '')

    query = "SELECT * FROM animales WHERE estado=?"
    params = [filtro_estado]
    if filtro_sexo:
        query += " AND sexo=?"
        params.append(filtro_sexo)
    if buscar:
        query += " AND (arete LIKE ? OR nombre LIKE ?)"
        params += [f'%{buscar}%', f'%{buscar}%']
    query += " ORDER BY arete"

    lista = conn.execute(query, params).fetchall()
    madres = conn.execute("SELECT id, arete, nombre FROM animales WHERE sexo='hembra'").fetchall()
    conn.close()
    return render_template('animales.html', animales=lista, madres=madres,
                           filtro_estado=filtro_estado, filtro_sexo=filtro_sexo, buscar=buscar)


@app.route('/animales/nuevo', methods=['POST'])
def nuevo_animal():
    conn = get_db()
    try:
        conn.execute('''
            INSERT INTO animales (arete, nombre, raza, sexo, fecha_nacimiento, peso_actual,
                madre_id, padre_arete, estado, proposito, observaciones, fecha_ingreso)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (
            request.form['arete'].strip().upper(),
            request.form.get('nombre', '').strip() or None,
            request.form['raza'],
            request.form['sexo'],
            request.form.get('fecha_nacimiento') or None,
            float(request.form['peso_actual']) if request.form.get('peso_actual') else None,
            int(request.form['madre_id']) if request.form.get('madre_id') else None,
            request.form.get('padre_arete', '').strip().upper() or None,
            request.form.get('estado', 'activo'),
            request.form.get('proposito', 'doble_proposito'),
            request.form.get('observaciones', '').strip() or None,
            request.form.get('fecha_ingreso') or date.today().isoformat(),
        ))
        conn.commit()
        flash('Animal registrado correctamente.', 'success')
    except sqlite3.IntegrityError:
        flash(f'El arete {request.form["arete"]} ya existe.', 'danger')
    finally:
        conn.close()
    return redirect(url_for('animales'))


@app.route('/animales/<int:animal_id>')
def detalle_animal(animal_id):
    conn = get_db()
    animal = conn.execute("SELECT * FROM animales WHERE id=?", (animal_id,)).fetchone()
    if not animal:
        flash('Animal no encontrado.', 'danger')
        return redirect(url_for('animales'))

    madre = None
    if animal['madre_id']:
        madre = conn.execute("SELECT arete, nombre FROM animales WHERE id=?",
                             (animal['madre_id'],)).fetchone()

    historial_salud = conn.execute(
        "SELECT * FROM salud WHERE animal_id=? ORDER BY fecha DESC", (animal_id,)
    ).fetchall()
    historial_pesos = conn.execute(
        "SELECT * FROM pesos WHERE animal_id=? ORDER BY fecha DESC LIMIT 10", (animal_id,)
    ).fetchall()
    historial_leche = conn.execute(
        "SELECT * FROM produccion_leche WHERE animal_id=? ORDER BY fecha DESC LIMIT 10", (animal_id,)
    ).fetchall()
    historial_repro = conn.execute(
        "SELECT * FROM reproduccion WHERE vaca_id=? ORDER BY fecha_servicio DESC", (animal_id,)
    ).fetchall()

    conn.close()
    return render_template('detalle_animal.html',
                           animal=animal, madre=madre,
                           historial_salud=historial_salud,
                           historial_pesos=historial_pesos,
                           historial_leche=historial_leche,
                           historial_repro=historial_repro)


@app.route('/animales/<int:animal_id>/editar', methods=['POST'])
def editar_animal(animal_id):
    conn = get_db()
    conn.execute('''
        UPDATE animales SET nombre=?, raza=?, sexo=?, fecha_nacimiento=?,
            peso_actual=?, madre_id=?, padre_arete=?, estado=?, proposito=?, observaciones=?
        WHERE id=?
    ''', (
        request.form.get('nombre', '').strip() or None,
        request.form['raza'],
        request.form['sexo'],
        request.form.get('fecha_nacimiento') or None,
        float(request.form['peso_actual']) if request.form.get('peso_actual') else None,
        int(request.form['madre_id']) if request.form.get('madre_id') else None,
        request.form.get('padre_arete', '').strip().upper() or None,
        request.form.get('estado', 'activo'),
        request.form.get('proposito', 'doble_proposito'),
        request.form.get('observaciones', '').strip() or None,
        animal_id,
    ))
    conn.commit()
    conn.close()
    flash('Animal actualizado.', 'success')
    return redirect(url_for('detalle_animal', animal_id=animal_id))


@app.route('/animales/<int:animal_id>/eliminar', methods=['POST'])
def eliminar_animal(animal_id):
    conn = get_db()
    conn.execute("UPDATE animales SET estado='vendido' WHERE id=?", (animal_id,))
    conn.commit()
    conn.close()
    flash('Animal marcado como vendido/retirado.', 'info')
    return redirect(url_for('animales'))


# ─── SALUD ────────────────────────────────────────────────────────────────────

@app.route('/salud')
def salud():
    conn = get_db()
    hoy = date.today().isoformat()
    filtro_tipo = request.args.get('tipo', '')
    buscar = request.args.get('q', '')

    query = '''
        SELECT s.*, a.arete, a.nombre
        FROM salud s JOIN animales a ON s.animal_id = a.id
        WHERE 1=1
    '''
    params = []
    if filtro_tipo:
        query += " AND s.tipo=?"
        params.append(filtro_tipo)
    if buscar:
        query += " AND (a.arete LIKE ? OR a.nombre LIKE ? OR s.descripcion LIKE ?)"
        params += [f'%{buscar}%', f'%{buscar}%', f'%{buscar}%']
    query += " ORDER BY s.fecha DESC LIMIT 100"

    registros = conn.execute(query, params).fetchall()

    proximas = conn.execute('''
        SELECT s.*, a.arete, a.nombre
        FROM salud s JOIN animales a ON s.animal_id = a.id
        WHERE s.proxima_cita BETWEEN ? AND date(?,'+30 days')
        ORDER BY s.proxima_cita
    ''', (hoy, hoy)).fetchall()

    animales_lista = conn.execute(
        "SELECT id, arete, nombre FROM animales WHERE estado='activo' ORDER BY arete"
    ).fetchall()
    conn.close()
    return render_template('salud.html', registros=registros, proximas=proximas,
                           animales_lista=animales_lista, filtro_tipo=filtro_tipo, buscar=buscar)


@app.route('/salud/nuevo', methods=['POST'])
def nuevo_salud():
    conn = get_db()
    conn.execute('''
        INSERT INTO salud (animal_id, fecha, tipo, descripcion, medicamento, dosis,
            via_administracion, veterinario, costo, proxima_cita)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    ''', (
        int(request.form['animal_id']),
        request.form['fecha'],
        request.form['tipo'],
        request.form.get('descripcion', '').strip() or None,
        request.form.get('medicamento', '').strip() or None,
        request.form.get('dosis', '').strip() or None,
        request.form.get('via_administracion', '').strip() or None,
        request.form.get('veterinario', '').strip() or None,
        float(request.form['costo']) if request.form.get('costo') else 0,
        request.form.get('proxima_cita') or None,
    ))
    conn.commit()
    conn.close()
    flash('Registro sanitario guardado.', 'success')
    return redirect(url_for('salud'))


# ─── REPRODUCCIÓN ─────────────────────────────────────────────────────────────

@app.route('/reproduccion')
def reproduccion():
    conn = get_db()
    hoy = date.today().isoformat()

    gestantes_raw = conn.execute('''
        SELECT r.*, a.arete, a.nombre
        FROM reproduccion r JOIN animales a ON r.vaca_id = a.id
        WHERE r.estado='gestacion'
        ORDER BY r.fecha_parto_esperado
    ''').fetchall()

    hoy_date = date.today()
    gestantes = []
    for r in gestantes_raw:
        row = dict(r)
        if row.get('fecha_parto_esperado'):
            try:
                fpe = date.fromisoformat(row['fecha_parto_esperado'])
                row['dias_restantes'] = (fpe - hoy_date).days
            except Exception:
                row['dias_restantes'] = None
        else:
            row['dias_restantes'] = None
        gestantes.append(row)

    historial = conn.execute('''
        SELECT r.*, a.arete, a.nombre
        FROM reproduccion r JOIN animales a ON r.vaca_id = a.id
        WHERE r.estado != 'gestacion'
        ORDER BY r.fecha_servicio DESC LIMIT 50
    ''').fetchall()

    vacas = conn.execute(
        "SELECT id, arete, nombre FROM animales WHERE sexo='hembra' AND estado='activo' ORDER BY arete"
    ).fetchall()
    toros = conn.execute(
        "SELECT id, arete, nombre FROM animales WHERE sexo='macho' AND estado='activo' ORDER BY arete"
    ).fetchall()
    conn.close()
    return render_template('reproduccion.html', gestantes=gestantes,
                           historial=historial, vacas=vacas, toros=toros, hoy=hoy)


@app.route('/reproduccion/nuevo', methods=['POST'])
def nuevo_reproduccion():
    conn = get_db()
    fecha_servicio = request.form['fecha_servicio']
    # Calcular fecha parto esperado (280 días)
    try:
        fs = datetime.strptime(fecha_servicio, '%Y-%m-%d')
        fpe = (fs + timedelta(days=280)).strftime('%Y-%m-%d')
    except Exception:
        fpe = None

    conn.execute('''
        INSERT INTO reproduccion (vaca_id, toro_arete, fecha_servicio, tipo_servicio,
            fecha_parto_esperado, estado, observaciones)
        VALUES (?,?,?,?,?,?,?)
    ''', (
        int(request.form['vaca_id']),
        request.form.get('toro_arete', '').strip().upper() or None,
        fecha_servicio,
        request.form.get('tipo_servicio', 'monta_natural'),
        fpe,
        'gestacion',
        request.form.get('observaciones', '').strip() or None,
    ))
    conn.commit()
    conn.close()
    flash('Servicio registrado. Parto esperado calculado automáticamente (280 días).', 'success')
    return redirect(url_for('reproduccion'))


@app.route('/reproduccion/<int:rep_id>/parto', methods=['POST'])
def registrar_parto(rep_id):
    conn = get_db()
    conn.execute('''
        UPDATE reproduccion SET
            fecha_parto_real=?, num_crias=?, sexo_cria=?,
            peso_nacimiento=?, estado='parto', observaciones=?
        WHERE id=?
    ''', (
        request.form['fecha_parto_real'],
        int(request.form.get('num_crias', 1)),
        request.form.get('sexo_cria', ''),
        float(request.form['peso_nacimiento']) if request.form.get('peso_nacimiento') else None,
        request.form.get('observaciones', '').strip() or None,
        rep_id,
    ))
    conn.commit()
    conn.close()
    flash('Parto registrado correctamente.', 'success')
    return redirect(url_for('reproduccion'))


# ─── PRODUCCIÓN DE LECHE ──────────────────────────────────────────────────────

@app.route('/produccion')
def produccion():
    conn = get_db()
    hoy = date.today().isoformat()
    fecha = request.args.get('fecha', hoy)

    registros_dia = conn.execute('''
        SELECT p.*, a.arete, a.nombre
        FROM produccion_leche p JOIN animales a ON p.animal_id = a.id
        WHERE p.fecha=?
        ORDER BY a.arete
    ''', (fecha,)).fetchall()

    total_dia = conn.execute(
        "SELECT COALESCE(SUM(total),0) FROM produccion_leche WHERE fecha=?", (fecha,)
    ).fetchone()[0]

    # Producción últimos 30 días
    produccion_mensual = conn.execute('''
        SELECT fecha, SUM(total) as litros, COUNT(DISTINCT animal_id) as vacas
        FROM produccion_leche
        WHERE fecha >= date('now','-29 days')
        GROUP BY fecha ORDER BY fecha
    ''').fetchall()

    # Top productoras
    top_vacas = conn.execute('''
        SELECT a.arete, a.nombre, SUM(p.total) as total_litros
        FROM produccion_leche p JOIN animales a ON p.animal_id = a.id
        WHERE p.fecha >= date('now','-29 days')
        GROUP BY a.id ORDER BY total_litros DESC LIMIT 5
    ''').fetchall()

    vacas = conn.execute(
        "SELECT id, arete, nombre FROM animales WHERE sexo='hembra' AND estado='activo' ORDER BY arete"
    ).fetchall()
    conn.close()
    return render_template('produccion.html',
                           registros_dia=registros_dia, total_dia=total_dia,
                           produccion_mensual=produccion_mensual, top_vacas=top_vacas,
                           vacas=vacas, fecha=fecha, hoy=hoy)


@app.route('/produccion/nuevo', methods=['POST'])
def nuevo_produccion():
    conn = get_db()
    manana = float(request.form.get('manana', 0) or 0)
    tarde = float(request.form.get('tarde', 0) or 0)
    total = manana + tarde

    existing = conn.execute(
        "SELECT id FROM produccion_leche WHERE animal_id=? AND fecha=?",
        (request.form['animal_id'], request.form['fecha'])
    ).fetchone()

    if existing:
        conn.execute(
            "UPDATE produccion_leche SET manana=?, tarde=?, total=?, observaciones=? WHERE id=?",
            (manana, tarde, total, request.form.get('observaciones', '') or None, existing['id'])
        )
    else:
        conn.execute('''
            INSERT INTO produccion_leche (animal_id, fecha, manana, tarde, total, observaciones)
            VALUES (?,?,?,?,?,?)
        ''', (
            int(request.form['animal_id']),
            request.form['fecha'],
            manana, tarde, total,
            request.form.get('observaciones', '').strip() or None,
        ))

    # Actualizar peso si viene incluido
    if request.form.get('peso'):
        conn.execute(
            "INSERT INTO pesos (animal_id, fecha, peso) VALUES (?,?,?)",
            (int(request.form['animal_id']), request.form['fecha'], float(request.form['peso']))
        )
        conn.execute(
            "UPDATE animales SET peso_actual=? WHERE id=?",
            (float(request.form['peso']), int(request.form['animal_id']))
        )

    conn.commit()
    conn.close()
    flash('Producción registrada.', 'success')
    return redirect(url_for('produccion', fecha=request.form['fecha']))


# ─── PESOS ────────────────────────────────────────────────────────────────────

@app.route('/pesos')
def pesos():
    conn = get_db()
    registros = conn.execute('''
        SELECT p.*, a.arete, a.nombre, a.sexo
        FROM pesos p JOIN animales a ON p.animal_id = a.id
        ORDER BY p.fecha DESC LIMIT 100
    ''').fetchall()
    animales_lista = conn.execute(
        "SELECT id, arete, nombre FROM animales WHERE estado='activo' ORDER BY arete"
    ).fetchall()
    conn.close()
    return render_template('pesos.html', registros=registros, animales_lista=animales_lista)


@app.route('/pesos/nuevo', methods=['POST'])
def nuevo_peso():
    conn = get_db()
    animal_id = int(request.form['animal_id'])
    peso = float(request.form['peso'])
    conn.execute(
        "INSERT INTO pesos (animal_id, fecha, peso, condicion_corporal, observaciones) VALUES (?,?,?,?,?)",
        (animal_id, request.form['fecha'], peso,
         int(request.form['condicion_corporal']) if request.form.get('condicion_corporal') else None,
         request.form.get('observaciones', '').strip() or None)
    )
    conn.execute("UPDATE animales SET peso_actual=? WHERE id=?", (peso, animal_id))
    conn.commit()
    conn.close()
    flash('Peso registrado y animal actualizado.', 'success')
    return redirect(url_for('pesos'))


# ─── FINANZAS ─────────────────────────────────────────────────────────────────

@app.route('/finanzas')
def finanzas():
    conn = get_db()
    filtro_tipo = request.args.get('tipo', '')
    filtro_mes = request.args.get('mes', date.today().strftime('%Y-%m'))

    query = '''
        SELECT f.*, a.arete, a.nombre
        FROM finanzas f LEFT JOIN animales a ON f.animal_id = a.id
        WHERE strftime('%Y-%m', f.fecha) = ?
    '''
    params = [filtro_mes]
    if filtro_tipo:
        query += " AND f.tipo=?"
        params.append(filtro_tipo)
    query += " ORDER BY f.fecha DESC"

    registros = conn.execute(query, params).fetchall()

    resumen = conn.execute('''
        SELECT tipo, SUM(monto) as total
        FROM finanzas WHERE strftime('%Y-%m', fecha) = ?
        GROUP BY tipo
    ''', (filtro_mes,)).fetchall()

    por_categoria = conn.execute('''
        SELECT tipo, categoria, SUM(monto) as total
        FROM finanzas WHERE strftime('%Y-%m', fecha) = ?
        GROUP BY tipo, categoria ORDER BY tipo, total DESC
    ''', (filtro_mes,)).fetchall()

    animales_lista = conn.execute(
        "SELECT id, arete, nombre FROM animales WHERE estado='activo' ORDER BY arete"
    ).fetchall()
    conn.close()
    return render_template('finanzas.html', registros=registros, resumen=resumen,
                           por_categoria=por_categoria, animales_lista=animales_lista,
                           filtro_tipo=filtro_tipo, filtro_mes=filtro_mes)


@app.route('/finanzas/nuevo', methods=['POST'])
def nuevo_finanza():
    conn = get_db()
    conn.execute('''
        INSERT INTO finanzas (fecha, tipo, categoria, descripcion, monto, animal_id)
        VALUES (?,?,?,?,?,?)
    ''', (
        request.form['fecha'],
        request.form['tipo'],
        request.form['categoria'],
        request.form.get('descripcion', '').strip() or None,
        float(request.form['monto']),
        int(request.form['animal_id']) if request.form.get('animal_id') else None,
    ))
    conn.commit()
    conn.close()
    flash('Movimiento financiero registrado.', 'success')
    return redirect(url_for('finanzas'))


# ─── REPORTES ─────────────────────────────────────────────────────────────────

@app.route('/reportes')
def reportes():
    conn = get_db()

    inventario_raza = conn.execute('''
        SELECT raza, sexo, COUNT(*) as cantidad
        FROM animales WHERE estado='activo'
        GROUP BY raza, sexo ORDER BY raza
    ''').fetchall()

    leche_mensual = conn.execute('''
        SELECT strftime('%Y-%m', fecha) as mes, SUM(total) as litros, AVG(total) as promedio_dia
        FROM produccion_leche
        GROUP BY mes ORDER BY mes DESC LIMIT 12
    ''').fetchall()

    balance_mensual = conn.execute('''
        SELECT strftime('%Y-%m', fecha) as mes,
               SUM(CASE WHEN tipo='ingreso' THEN monto ELSE 0 END) as ingresos,
               SUM(CASE WHEN tipo='gasto' THEN monto ELSE 0 END) as gastos
        FROM finanzas
        GROUP BY mes ORDER BY mes DESC LIMIT 12
    ''').fetchall()

    partos_anno = conn.execute('''
        SELECT strftime('%Y-%m', fecha_parto_real) as mes, COUNT(*) as partos
        FROM reproduccion WHERE fecha_parto_real IS NOT NULL
        AND fecha_parto_real >= date('now','-12 months')
        GROUP BY mes ORDER BY mes
    ''').fetchall()

    top_productoras = conn.execute('''
        SELECT a.arete, a.nombre, a.raza,
               SUM(p.total) as total_litros,
               AVG(p.total) as promedio_dia,
               COUNT(p.id) as dias_ordenada
        FROM produccion_leche p JOIN animales a ON p.animal_id = a.id
        WHERE p.fecha >= date('now','-29 days')
        GROUP BY a.id ORDER BY total_litros DESC LIMIT 10
    ''').fetchall()

    conn.close()
    return render_template('reportes.html',
                           inventario_raza=inventario_raza,
                           leche_mensual=leche_mensual,
                           balance_mensual=balance_mensual,
                           partos_anno=partos_anno,
                           top_productoras=top_productoras)


# ─── API JSON (para gráficas) ─────────────────────────────────────────────────

@app.route('/api/leche_semana')
def api_leche_semana():
    conn = get_db()
    datos = conn.execute('''
        SELECT fecha, SUM(total) as litros
        FROM produccion_leche
        WHERE fecha >= date('now','-6 days')
        GROUP BY fecha ORDER BY fecha
    ''').fetchall()
    conn.close()
    return jsonify([dict(r) for r in datos])


@app.route('/api/pesos_animal/<int:animal_id>')
def api_pesos_animal(animal_id):
    conn = get_db()
    datos = conn.execute(
        "SELECT fecha, peso FROM pesos WHERE animal_id=? ORDER BY fecha DESC LIMIT 12",
        (animal_id,)
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in datos])


# ─── FOTOS DE ANIMALES ────────────────────────────────────────────────────────

@app.route('/animales/<int:animal_id>/subir-foto', methods=['POST'])
def subir_foto_animal(animal_id):
    f = request.files.get('foto')
    if not f or not f.filename:
        flash('No se seleccionó ningún archivo.', 'warning')
        return redirect(url_for('detalle_animal', animal_id=animal_id))
    if not _ext_ok(f.filename):
        flash('Formato no válido. Use JPG, PNG o WEBP.', 'danger')
        return redirect(url_for('detalle_animal', animal_id=animal_id))

    os.makedirs(UPLOAD_ANIM_DIR, exist_ok=True)
    dest = os.path.join(UPLOAD_ANIM_DIR, f'animal_{animal_id}.jpg')
    try:
        _save_img(f.stream, dest, max_px=900)
        ruta = f'animales/animal_{animal_id}.jpg'
        conn = get_db()
        conn.execute("UPDATE animales SET foto=? WHERE id=?", (ruta, animal_id))
        conn.commit()
        conn.close()
        flash('Foto guardada correctamente.', 'success')
    except Exception as e:
        flash(f'Error al procesar la imagen: {e}', 'danger')
    return redirect(url_for('detalle_animal', animal_id=animal_id))


@app.route('/animales/<int:animal_id>/eliminar-foto', methods=['POST'])
def eliminar_foto_animal(animal_id):
    conn = get_db()
    animal = conn.execute("SELECT foto FROM animales WHERE id=?", (animal_id,)).fetchone()
    if animal and animal['foto']:
        path = os.path.join(UPLOAD_DIR, animal['foto'])
        if os.path.exists(path):
            os.remove(path)
        conn.execute("UPDATE animales SET foto=NULL WHERE id=?", (animal_id,))
        conn.commit()
    conn.close()
    flash('Foto eliminada.', 'info')
    return redirect(url_for('detalle_animal', animal_id=animal_id))


# ─── LOGO DE LA HACIENDA ──────────────────────────────────────────────────────

@app.route('/configuracion/subir-logo', methods=['POST'])
def subir_logo():
    f = request.files.get('logo')
    if not f or not f.filename:
        flash('No se seleccionó ningún archivo.', 'warning')
        return redirect(url_for('configuracion'))
    if not _ext_ok(f.filename):
        flash('Formato no válido. Use JPG, PNG o WEBP.', 'danger')
        return redirect(url_for('configuracion'))

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    dest = os.path.join(UPLOAD_DIR, 'logo.jpg')
    try:
        _save_img(f.stream, dest, max_px=400)
        conn = get_db()
        conn.execute("INSERT OR REPLACE INTO configuracion (clave, valor) VALUES ('logo_archivo','logo.jpg')")
        conn.commit()
        conn.close()
        flash('Logo guardado correctamente.', 'success')
    except Exception as e:
        flash(f'Error al procesar la imagen: {e}', 'danger')
    return redirect(url_for('configuracion'))


@app.route('/configuracion/eliminar-logo', methods=['POST'])
def eliminar_logo():
    path = os.path.join(UPLOAD_DIR, 'logo.jpg')
    if os.path.exists(path):
        os.remove(path)
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO configuracion (clave, valor) VALUES ('logo_archivo','')")
    conn.commit()
    conn.close()
    flash('Logo eliminado.', 'info')
    return redirect(url_for('configuracion'))


# ─── CONFIGURACIÓN ────────────────────────────────────────────────────────────

@app.route('/configuracion')
def configuracion():
    cfg = get_config()
    return render_template('configuracion.html', cfg=cfg)


@app.route('/configuracion/guardar', methods=['POST'])
def guardar_configuracion():
    conn = get_db()
    campos = ['nombre_hacienda', 'propietario', 'ubicacion', 'telefono', 'email', 'descripcion']
    for campo in campos:
        valor = request.form.get(campo, '').strip()
        conn.execute("INSERT OR REPLACE INTO configuracion (clave, valor) VALUES (?,?)",
                     (campo, valor))
    conn.commit()
    conn.close()
    flash('Configuración de la hacienda guardada correctamente.', 'success')
    return redirect(url_for('configuracion'))


# ─── EXPORTACIONES ────────────────────────────────────────────────────────────

MIME_PDF  = 'application/pdf'
MIME_XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


def _send(buf, mime, filename):
    return send_file(buf, mimetype=mime, download_name=filename, as_attachment=True)


def _hoy_str():
    return date.today().strftime('%Y%m%d')


# ── Animales ──────────────────────────────────────────────────────────────────

@app.route('/exportar/animales.<fmt>')
def export_animales(fmt):
    conn = get_db()
    estado = request.args.get('estado', 'activo')
    rows = conn.execute(
        "SELECT * FROM animales WHERE estado=? ORDER BY arete", (estado,)
    ).fetchall()
    conn.close()
    data = [dict(r) for r in rows]
    cfg  = get_config()
    tag  = _hoy_str()
    if fmt == 'pdf':
        return _send(exportar.pdf_animales(data, cfg), MIME_PDF,
                     f'animales_{tag}.pdf')
    return _send(exportar.excel_animales(data, cfg), MIME_XLSX,
                 f'animales_{tag}.xlsx')


# ── Sanidad ───────────────────────────────────────────────────────────────────

@app.route('/exportar/salud.<fmt>')
def export_salud(fmt):
    conn = get_db()
    rows = conn.execute('''
        SELECT s.*, a.arete, a.nombre
        FROM salud s JOIN animales a ON s.animal_id = a.id
        ORDER BY s.fecha DESC
    ''').fetchall()
    conn.close()
    data = [dict(r) for r in rows]
    cfg  = get_config()
    tag  = _hoy_str()
    if fmt == 'pdf':
        return _send(exportar.pdf_salud(data, cfg), MIME_PDF,
                     f'sanidad_{tag}.pdf')
    return _send(exportar.excel_salud(data, cfg), MIME_XLSX,
                 f'sanidad_{tag}.xlsx')


# ── Producción de Leche ───────────────────────────────────────────────────────

@app.route('/exportar/produccion.<fmt>')
def export_produccion(fmt):
    conn = get_db()
    hoy = date.today().isoformat()
    fecha = request.args.get('fecha', hoy)

    registros_dia = [dict(r) for r in conn.execute('''
        SELECT p.*, a.arete, a.nombre
        FROM produccion_leche p JOIN animales a ON p.animal_id = a.id
        WHERE p.fecha=? ORDER BY a.arete
    ''', (fecha,)).fetchall()]

    total_dia = conn.execute(
        "SELECT COALESCE(SUM(total),0) FROM produccion_leche WHERE fecha=?", (fecha,)
    ).fetchone()[0]

    produccion_mensual = [dict(r) for r in conn.execute('''
        SELECT fecha, SUM(total) as litros, COUNT(DISTINCT animal_id) as vacas
        FROM produccion_leche WHERE fecha >= date('now','-29 days')
        GROUP BY fecha ORDER BY fecha
    ''').fetchall()]

    top_vacas = [dict(r) for r in conn.execute('''
        SELECT a.arete, a.nombre, SUM(p.total) as total_litros
        FROM produccion_leche p JOIN animales a ON p.animal_id = a.id
        WHERE p.fecha >= date('now','-29 days')
        GROUP BY a.id ORDER BY total_litros DESC LIMIT 5
    ''').fetchall()]
    conn.close()

    cfg = get_config()
    tag = fecha.replace('-', '')
    if fmt == 'pdf':
        return _send(exportar.pdf_produccion_dia(registros_dia, fecha, total_dia, cfg),
                     MIME_PDF, f'produccion_{tag}.pdf')
    return _send(exportar.excel_produccion(registros_dia, produccion_mensual,
                                           top_vacas, fecha, total_dia, cfg),
                 MIME_XLSX, f'produccion_{tag}.xlsx')


@app.route('/exportar/produccion_mensual.pdf')
def export_produccion_mensual_pdf():
    conn = get_db()
    produccion_mensual = [dict(r) for r in conn.execute('''
        SELECT fecha, SUM(total) as litros, COUNT(DISTINCT animal_id) as vacas
        FROM produccion_leche WHERE fecha >= date('now','-29 days')
        GROUP BY fecha ORDER BY fecha
    ''').fetchall()]
    conn.close()
    return _send(exportar.pdf_produccion_mensual(produccion_mensual, get_config()),
                 MIME_PDF, f'produccion_mensual_{_hoy_str()}.pdf')


# ── Finanzas ──────────────────────────────────────────────────────────────────

@app.route('/exportar/finanzas.<fmt>')
def export_finanzas(fmt):
    conn = get_db()
    filtro_mes = request.args.get('mes', date.today().strftime('%Y-%m'))

    registros = [dict(r) for r in conn.execute('''
        SELECT f.*, a.arete, a.nombre
        FROM finanzas f LEFT JOIN animales a ON f.animal_id = a.id
        WHERE strftime('%Y-%m', f.fecha) = ?
        ORDER BY f.fecha DESC
    ''', (filtro_mes,)).fetchall()]

    totales = conn.execute('''
        SELECT tipo, SUM(monto) as total FROM finanzas
        WHERE strftime('%Y-%m', fecha) = ? GROUP BY tipo
    ''', (filtro_mes,)).fetchall()
    conn.close()

    ingresos = next((r['total'] for r in totales if r['tipo'] == 'ingreso'), 0)
    gastos   = next((r['total'] for r in totales if r['tipo'] == 'gasto'), 0)
    cfg = get_config()
    tag = filtro_mes.replace('-', '')

    if fmt == 'pdf':
        return _send(exportar.pdf_finanzas(registros, filtro_mes, ingresos, gastos, cfg),
                     MIME_PDF, f'finanzas_{tag}.pdf')
    return _send(exportar.excel_finanzas(registros, filtro_mes, ingresos, gastos, cfg),
                 MIME_XLSX, f'finanzas_{tag}.xlsx')


# ── Reporte General ───────────────────────────────────────────────────────────

@app.route('/exportar/reporte.<fmt>')
def export_reporte(fmt):
    conn = get_db()

    inv_raza = [dict(r) for r in conn.execute('''
        SELECT raza, sexo, COUNT(*) as cantidad
        FROM animales WHERE estado='activo'
        GROUP BY raza, sexo ORDER BY raza
    ''').fetchall()]

    leche_mensual = [dict(r) for r in conn.execute('''
        SELECT strftime('%Y-%m', fecha) as mes, SUM(total) as litros,
               AVG(total) as promedio_dia
        FROM produccion_leche GROUP BY mes ORDER BY mes DESC LIMIT 12
    ''').fetchall()]

    balance_mensual = [dict(r) for r in conn.execute('''
        SELECT strftime('%Y-%m', fecha) as mes,
               SUM(CASE WHEN tipo='ingreso' THEN monto ELSE 0 END) as ingresos,
               SUM(CASE WHEN tipo='gasto'   THEN monto ELSE 0 END) as gastos
        FROM finanzas GROUP BY mes ORDER BY mes DESC LIMIT 12
    ''').fetchall()]

    top_productoras = [dict(r) for r in conn.execute('''
        SELECT a.arete, a.nombre, a.raza,
               SUM(p.total) as total_litros,
               AVG(p.total) as promedio_dia,
               COUNT(p.id) as dias_ordenada
        FROM produccion_leche p JOIN animales a ON p.animal_id = a.id
        WHERE p.fecha >= date('now','-29 days')
        GROUP BY a.id ORDER BY total_litros DESC LIMIT 10
    ''').fetchall()]

    partos_anno = [dict(r) for r in conn.execute('''
        SELECT strftime('%Y-%m', fecha_parto_real) as mes, COUNT(*) as partos
        FROM reproduccion WHERE fecha_parto_real IS NOT NULL
          AND fecha_parto_real >= date('now','-12 months')
        GROUP BY mes ORDER BY mes
    ''').fetchall()]
    conn.close()

    cfg = get_config()
    tag = _hoy_str()
    if fmt == 'pdf':
        return _send(exportar.pdf_reporte_general(
            inv_raza, leche_mensual, balance_mensual, top_productoras, partos_anno, cfg),
            MIME_PDF, f'reporte_general_{tag}.pdf')
    return _send(exportar.excel_reporte_general(
        inv_raza, leche_mensual, balance_mensual, top_productoras, partos_anno, cfg),
        MIME_XLSX, f'reporte_general_{tag}.xlsx')


# ══════════════════════════════════════════════════════════════════════════════
# ─── PWA ──────────────────────────────────────────────────────────────────────

@app.route('/sw.js')
def service_worker():
    resp = send_file(os.path.join(_BASE, 'static', 'sw.js'), mimetype='application/javascript')
    resp.headers['Service-Worker-Allowed'] = '/'
    resp.headers['Cache-Control'] = 'no-cache'
    return resp


@app.route('/manifest.json')
def pwa_manifest():
    resp = send_file(os.path.join(_BASE, 'static', 'manifest.json'), mimetype='application/manifest+json')
    resp.headers['Cache-Control'] = 'no-cache'
    return resp


@app.route('/offline')
def offline():
    return render_template('offline.html')


def _generate_pwa_icons():
    icons_dir = os.path.join(_BASE, 'static', 'icons')
    os.makedirs(icons_dir, exist_ok=True)

    for size in (192, 512):
        path = os.path.join(icons_dir, f'icon-{size}.png')
        if os.path.exists(path):
            continue

        img = PILImage.new('RGB', (size, size), '#1a3a2a')
        draw = ImageDraw.Draw(img)

        # Círculo verde interior
        m = size // 6
        draw.ellipse([m, m, size - m, size - m], fill='#2e7d32')

        # Letra "G" centrada
        font_size = int(size * 0.45)
        font = None
        for font_path in ('C:/Windows/Fonts/arialbd.ttf', 'C:/Windows/Fonts/arial.ttf'):
            try:
                font = ImageFont.truetype(font_path, font_size)
                break
            except OSError:
                pass
        if font is None:
            font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), 'G', font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text(((size - tw) // 2 - bbox[0], (size - th) // 2 - bbox[1]), 'G', fill='white', font=font)

        img.save(path, 'PNG')


# ══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    import socket
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    init_db()
    _generate_pwa_icons()
    # Obtener la IP local de la maquina
    try:
        ip_local = socket.gethostbyname(socket.gethostname())
    except Exception:
        ip_local = '0.0.0.0'
    print("\n" + "="*60)
    print("  SISTEMA DE CONTROL GANADERO - GANADO VACUNO")
    print("="*60)
    print(f"  En esta laptop:    http://localhost:5000")
    print(f"  Desde celular/otra laptop (misma WiFi):")
    print(f"  --> http://{ip_local}:5000")
    print("  Presionar Ctrl+C para detener")
    print("="*60 + "\n")
    app.run(debug=False, host='0.0.0.0', port=5000)
