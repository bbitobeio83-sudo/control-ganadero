"""
Carga datos de demostración en la base de datos.
Ejecutar una sola vez: python cargar_datos_demo.py
"""
import sqlite3
import random
from datetime import date, timedelta

DB = 'ganado.db'

def run():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    # Animales
    animales = [
        ('001', 'Paloma',   'Holstein',      'hembra', '2019-03-15', 520.0, 'leche'),
        ('002', 'Estrella', 'Suizo Pardo',   'hembra', '2020-06-20', 480.0, 'leche'),
        ('003', 'Luna',     'Holstein',      'hembra', '2018-11-05', 550.0, 'leche'),
        ('004', 'Canela',   'Jersey',        'hembra', '2021-02-10', 390.0, 'leche'),
        ('005', 'Violeta',  'Simmental',     'hembra', '2020-08-30', 510.0, 'doble_proposito'),
        ('006', 'Rosa',     'Suizo Pardo',   'hembra', '2019-05-12', 490.0, 'leche'),
        ('007', 'Nube',     'Holstein',      'hembra', '2022-01-18', 420.0, 'leche'),
        ('008', 'Dulce',    'Jersey',        'hembra', '2021-09-25', 380.0, 'leche'),
        ('T01', 'Titan',    'Angus',         'macho',  '2017-04-08', 780.0, 'reproduccion'),
        ('T02', 'Zeus',     'Simmental',     'macho',  '2018-07-22', 820.0, 'reproduccion'),
        ('100', None,       'Cruza',         'hembra', '2024-02-14', 180.0, 'cria'),
        ('101', None,       'Holstein',      'macho',  '2024-03-20', 210.0, 'carne'),
        ('102', None,       'Suizo Pardo',   'hembra', '2024-04-05', 165.0, 'cria'),
    ]

    ids = {}
    for arete, nombre, raza, sexo, fn, peso, proposito in animales:
        try:
            c.execute('''INSERT INTO animales (arete, nombre, raza, sexo, fecha_nacimiento, peso_actual, proposito, estado)
                         VALUES (?,?,?,?,?,?,?,'activo')''',
                      (arete, nombre, raza, sexo, fn, peso, proposito))
            ids[arete] = c.lastrowid
        except sqlite3.IntegrityError:
            row = conn.execute("SELECT id FROM animales WHERE arete=?", (arete,)).fetchone()
            if row:
                ids[arete] = row[0]

    conn.commit()

    # Producción de leche últimos 14 días
    vacas_leche = [('001', 18), ('002', 15), ('003', 20), ('004', 12),
                   ('005', 14), ('006', 16), ('007', 11), ('008', 10)]
    hoy = date.today()
    for dias in range(14, 0, -1):
        fecha = (hoy - timedelta(days=dias)).isoformat()
        for arete, base in vacas_leche:
            if arete not in ids:
                continue
            manana = round(base * 0.6 + random.uniform(-1.5, 1.5), 1)
            tarde  = round(base * 0.4 + random.uniform(-1.0, 1.0), 1)
            total  = round(manana + tarde, 1)
            try:
                c.execute('''INSERT INTO produccion_leche (animal_id, fecha, manana, tarde, total)
                             VALUES (?,?,?,?,?)''',
                          (ids[arete], fecha, manana, tarde, total))
            except Exception:
                pass

    # Sanidad
    registros_salud = [
        ('001', '2026-05-01', 'vacuna',         'Vacuna antiaftosa',         'Aftovaxpur',    '5 ml',  'Dr. García',  120.0, '2026-11-01'),
        ('002', '2026-05-01', 'vacuna',         'Vacuna antiaftosa',         'Aftovaxpur',    '5 ml',  'Dr. García',  120.0, '2026-11-01'),
        ('003', '2026-04-15', 'desparasitacion','Desparasitación interna',   'Ivermectina',   '10 ml', 'Dr. García',   85.0, '2026-10-15'),
        ('001', '2026-03-10', 'tratamiento',    'Mastitis leve cuarto DI',   'Oxitetraciclina','10 ml','Dr. Pérez',   200.0, None),
        ('T01', '2026-05-20', 'revision',       'Chequeo reproductivo',      None,             None,   'Dr. García',  150.0, '2026-11-20'),
        ('007', '2026-06-10', 'vacuna',         'Triple viral bovina',       'Bovilis MH+LH', '2 ml',  'Dr. García',   95.0, '2026-12-10'),
    ]
    for arete, fecha, tipo, desc, med, dosis, vet, costo, prox in registros_salud:
        if arete in ids:
            try:
                c.execute('''INSERT INTO salud (animal_id, fecha, tipo, descripcion, medicamento,
                             dosis, veterinario, costo, proxima_cita) VALUES (?,?,?,?,?,?,?,?,?)''',
                          (ids[arete], fecha, tipo, desc, med, dosis, vet, costo, prox))
            except Exception:
                pass

    # Reproducción
    repros = [
        ('001', 'T01', '2025-09-15', 'monta_natural',         '2026-07-22', None,         0, None, None, 'gestacion'),
        ('002', 'T02', '2025-10-01', 'monta_natural',         '2026-08-07', None,         0, None, None, 'gestacion'),
        ('003', None,  '2025-06-10', 'inseminacion_artificial','2026-04-17','2026-04-20', 1, 'hembra', 35.0, 'parto'),
        ('005', 'T01', '2025-05-20', 'monta_natural',         '2026-03-26','2026-03-28', 1, 'macho',  40.0, 'parto'),
    ]
    for vaca, toro, fs, tipo, fpe, fpr, nc, sx, pn, estado in repros:
        if vaca in ids:
            try:
                c.execute('''INSERT INTO reproduccion (vaca_id, toro_arete, fecha_servicio, tipo_servicio,
                             fecha_parto_esperado, fecha_parto_real, num_crias, sexo_cria, peso_nacimiento, estado)
                             VALUES (?,?,?,?,?,?,?,?,?,?)''',
                          (ids[vaca], toro, fs, tipo, fpe, fpr, nc, sx, pn, estado))
            except Exception:
                pass

    # Finanzas
    finanzas = [
        ('2026-06-01', 'ingreso', 'Venta de leche',     'Venta 280 L',        5600.0, None),
        ('2026-06-02', 'ingreso', 'Venta de leche',     'Venta 275 L',        5500.0, None),
        ('2026-05-31', 'ingreso', 'Venta de leche',     'Venta 260 L',        5200.0, None),
        ('2026-06-01', 'gasto',   'Alimentación',       'Alimento balanceado', 3200.0, None),
        ('2026-06-01', 'gasto',   'Medicamentos',       'Antibióticos vaca 001', 200.0, '001'),
        ('2026-05-15', 'gasto',   'Vacunas',            'Antiaftosa lote',     480.0, None),
        ('2026-05-10', 'ingreso', 'Venta de crías',     'Becerro macho 101',  8000.0, '101'),
        ('2026-05-01', 'gasto',   'Mano de obra',       'Pago quincenal',    4500.0, None),
        ('2026-04-30', 'ingreso', 'Venta de leche',     'Mes abril',        15000.0, None),
        ('2026-04-30', 'gasto',   'Alimentación',       'Forraje abril',     6000.0, None),
    ]
    for fecha, tipo, cat, desc, monto, arete in finanzas:
        animal_id = ids.get(arete) if arete else None
        try:
            c.execute('''INSERT INTO finanzas (fecha, tipo, categoria, descripcion, monto, animal_id)
                         VALUES (?,?,?,?,?,?)''',
                      (fecha, tipo, cat, desc, monto, animal_id))
        except Exception:
            pass

    conn.commit()
    conn.close()
    print("OK: Datos de demostracion cargados correctamente.")
    print(f"  {len(animales)} animales, produccion 14 dias, sanidad, reproduccion y finanzas.")

if __name__ == '__main__':
    run()
