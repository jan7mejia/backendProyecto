from flask import Blueprint, request, jsonify
import mysql.connector
from src.database import get_db_connection

cobros_bp = Blueprint('cobros', __name__)

# ======================================
# ENDPOINT: OBTENER VEHÍCULOS ACTIVOS (Para el Selector de la App)
# ======================================
@cobros_bp.route('/api/vehiculos-activos', methods=['GET'])
def obtener_vehiculos_activos():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT v.id_vehiculo, v.placa, v.modelo, l.nombre_linea 
            FROM vehiculos v
            INNER JOIN lineas l ON v.id_linea = l.id_linea
            WHERE v.estado = 'activo'
        """)
        vehiculos = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify({"success": True, "vehiculos": vehiculos}), 200
    except mysql.connector.Error as err:
        return jsonify({'success': False, 'error': str(err)}), 500

# ======================================
# ENDPOINT: RECARGAR SALDO DIGITAL / RFID
# ======================================
@cobros_bp.route('/api/recargar', methods=['POST'])
def recargar_saldo():
    data = request.json or {}
    id_usuario = data.get('id_usuario')
    monto = data.get('monto')
    metodo = data.get('metodo', 'qr')
    destino = data.get('destino', 'app')

    if not id_usuario or not monto or float(monto) <= 0:
        return jsonify({'success': False, 'error': 'Datos de recarga inválidos'}), 400

    try:
        monto_float = float(monto)
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if destino == 'rfid':
            cursor.execute("SELECT id_tarjeta FROM tarjetas_rfid WHERE id_usuario = %s AND estado = 'activa'", (id_usuario,))
            if not cursor.fetchone():
                cursor.close()
                conn.close()
                return jsonify({'success': False, 'error': 'No tienes una tarjeta RFID activa vinculada'}), 404
            cursor.execute("UPDATE tarjetas_rfid SET saldo = saldo + %s WHERE id_usuario = %s", (monto_float, id_usuario))
        else:
            cursor.execute("UPDATE usuarios SET saldo = saldo + %s WHERE id_usuario = %s", (monto_float, id_usuario))

        cursor.execute("INSERT INTO recargas (id_usuario, monto, metodo) VALUES (%s, %s, %s)", (id_usuario, monto_float, metodo))
        cursor.execute("INSERT INTO historial (id_usuario, id_vehiculo, tipo, monto) VALUES (%s, NULL, 'recarga', %s)", (id_usuario, monto_float))
        
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"success": True, "message": f"Recarga a {destino.upper()} registrada con éxito"}), 200
    except mysql.connector.Error as err:
        return jsonify({'success': False, 'error': str(err)}), 500

# ======================================
# ENDPOINT: PROCESAR COBRO QR REAL
# ======================================
@cobros_bp.route('/api/pagar-qr', methods=['POST'])
def pagar_qr():
    data = request.json or {}
    id_usuario = data.get('id_usuario')
    id_vehiculo = data.get('id_vehiculo') 

    if not id_usuario or not id_vehiculo:
        return jsonify({'success': False, 'error': 'El ID del pasajero y del vehículo son obligatorios'}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT v.id_linea, v.placa, l.nombre_linea FROM vehiculos v
            INNER JOIN lineas l ON v.id_linea = l.id_linea WHERE v.id_vehiculo = %s AND v.estado = 'activo'
        """, (id_vehiculo,))
        vehiculo = cursor.fetchone()
        if not vehiculo:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Vehículo inválido'}), 404
            
        id_linea = vehiculo['id_linea']

        cursor.execute("SELECT id_chofer FROM asignaciones WHERE id_vehiculo = %s AND estado = 'activo' LIMIT 1", (id_vehiculo,))
        asignacion = cursor.fetchone()
        id_chofer = asignacion['id_chofer'] if asignacion else 1

        cursor.execute("SELECT nombre, apellido FROM usuarios WHERE id_usuario = %s", (id_chofer,))
        datos_chofer = cursor.fetchone()
        nombre_chofer = f"{datos_chofer['nombre']} {datos_chofer['apellido'] or ''}".strip() if datos_chofer else "Conductor de Turno"

        cursor.execute("SELECT id_categoria, saldo FROM usuarios WHERE id_usuario = %s AND estado = 'activo'", (id_usuario,))
        usuario = cursor.fetchone()
        if not usuario:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Pasajero no encontrado'}), 404

        id_cat = usuario['id_categoria'] or 3
        cursor.execute("SELECT monto FROM tarifas WHERE id_categoria = %s AND id_linea = %s", (id_cat, id_linea))
        tarifa_row = cursor.fetchone()
        tarifa = float(tarifa_row['monto']) if tarifa_row else 2.00

        saldo_actual = float(usuario['saldo'])
        if saldo_actual < tarifa:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': f"Saldo insuficiente. Cuesta Bs. {tarifa:.2f}"}), 400

        cursor.execute("UPDATE usuarios SET saldo = %s WHERE id_usuario = %s", (saldo_actual - tarifa, id_usuario))
        cursor.execute("INSERT INTO pagos (id_usuario, id_vehiculo, id_chofer, metodo_pago, monto) VALUES (%s, %s, %s, 'qr', %s)", (id_usuario, id_vehiculo, id_chofer, tarifa))
        cursor.execute("INSERT INTO historial (id_usuario, id_vehiculo, tipo, monto) VALUES (%s, %s, 'pago', %s)", (id_usuario, id_vehiculo, tarifa))
        
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"success": True, "monto_descontado": tarifa, "nuevo_saldo": saldo_actual - tarifa, "linea": vehiculo['nombre_linea'], "chofer": nombre_chofer}), 200
    except mysql.connector.Error as err:
        return jsonify({'success': False, 'error': str(err)}), 500

# ======================================
# SIMULADOR: COBRO RFID VALIDADOR (Chofer / App)
# ======================================
@cobros_bp.route('/api/pagar-rfid', methods=['POST'])
@cobros_bp.route('/api/chofer/cobrar-rfid', methods=['POST'])
def pagar_rfid():
    data = request.json or {}
    codigo_rfid = data.get('codigo_rfid')
    id_vehiculo = data.get('id_vehiculo') 

    if not codigo_rfid or not id_vehiculo:
        return jsonify({'success': False, 'error': 'Datos incompletos'}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT t.id_tarjeta, t.saldo, t.estado, t.id_usuario, u.id_categoria FROM tarjetas_rfid t
            INNER JOIN usuarios u ON t.id_usuario = u.id_usuario WHERE t.codigo = %s
        """, (codigo_rfid,))
        tarjeta = cursor.fetchone()

        if not tarjeta or tarjeta['estado'] != 'activa':
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Tarjeta inválida o bloqueada'}), 404

        id_usuario = tarjeta['id_usuario']
        id_cat = tarjeta['id_categoria'] or 3
        saldo_tarjeta = float(tarjeta['saldo'])

        cursor.execute("SELECT id_linea FROM vehiculos WHERE id_vehiculo = %s", (id_vehiculo,))
        vehiculo = cursor.fetchone()
        id_linea = vehiculo['id_linea'] if vehiculo else 1

        cursor.execute("SELECT monto FROM tarifas WHERE id_categoria = %s AND id_linea = %s", (id_cat, id_linea))
        tarifa_row = cursor.fetchone()
        tarifa = float(tarifa_row['monto']) if tarifa_row else 2.00

        if saldo_tarjeta < tarifa:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Saldo insuficiente'}), 400

        cursor.execute("UPDATE tarjetas_rfid SET saldo = saldo - %s WHERE id_tarjeta = %s", (tarifa, tarjeta['id_tarjeta']))
        cursor.execute("INSERT INTO pagos (id_usuario, id_vehiculo, id_chofer, metodo_pago, monto) VALUES (%s, %s, 1, 'rfid', %s)", (id_usuario, id_vehiculo, tarifa))
        cursor.execute("INSERT INTO historial (id_usuario, id_vehiculo, tipo, monto) VALUES (%s, %s, 'pago', %s)", (id_usuario, id_vehiculo, tarifa))
        
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"success": True, "message": "Cobro RFID completado", "monto": tarifa}), 200
    except mysql.connector.Error as err:
        return jsonify({'success': False, 'error': str(err)}), 500

