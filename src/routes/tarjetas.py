from flask import Blueprint, request, jsonify
import mysql.connector
from src.database import get_db_connection

tarjetas_bp = Blueprint('tarjetas', __name__)

# ======================================
# ENDPOINT: CONSULTAR ASOCIACIÓN DE TARJETA
# ======================================
@tarjetas_bp.route('/api/tarjeta-rfid/<int:id_usuario>', methods=['GET'])
def obtener_tarjeta_rfid(id_usuario):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT codigo, saldo, estado FROM tarjetas_rfid WHERE id_usuario = %s LIMIT 1", (id_usuario,))
        tarjeta = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if tarjeta:
            tarjeta['saldo'] = float(tarjeta['saldo'])
            return jsonify({"success": True, "tiene_tarjeta": True, "tarjeta": tarjeta}), 200
        else:
            return jsonify({"success": True, "tiene_tarjeta": False, "message": "No hay tarjeta vinculada"}), 200
    except mysql.connector.Error as err:
        return jsonify({'success': False, 'error': str(err)}), 500

# ======================================
# ENDPOINT: VINCULAR TARJETA FÍSICA ESCRIBIENDO SU UID
# ======================================
@tarjetas_bp.route('/api/tarjeta-rfid/vincular', methods=['POST'])
def vincular_tarjeta():
    data = request.json or {}
    id_usuario = data.get('id_usuario')
    codigo_rfid = data.get('codigo_rfid')

    if not id_usuario or not codigo_rfid:
        return jsonify({'success': False, 'error': 'ID de usuario y Código RFID requeridos'}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT id_usuario FROM tarjetas_rfid WHERE codigo = %s", (codigo_rfid,))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Esta tarjeta ya se encuentra vinculada a otro usuario'}), 400

        cursor.execute("""
            INSERT INTO tarjetas_rfid (codigo, id_usuario, saldo, estado)
            VALUES (%s, %s, 10.00, 'activa')
            ON DUPLICATE KEY UPDATE codigo = %s, estado = 'activa'
        """, (codigo_rfid, id_usuario, codigo_rfid))
        
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"success": True, "message": "¡Tarjeta Llajtabus vinculada con éxito con un saldo promocional de Bs. 10!"}), 200
    except mysql.connector.Error as err:
        return jsonify({'success': False, 'error': str(err)}), 500

# ======================================
# ENDPOINT: TRASPASAR SALDO DIGITAL DE LA APP HACIA EL PLÁSTICO RFID
# ======================================
@tarjetas_bp.route('/api/tarjeta-rfid/recargar', methods=['POST'])
def recargar_tarjeta_desde_app():
    data = request.json or {}
    id_usuario = data.get('id_usuario')
    monto = data.get('monto')

    if not id_usuario or not monto or float(monto) <= 0:
        return jsonify({'success': False, 'error': 'Monto inválido para la transferencia de fondos'}), 400

    try:
        monto_float = float(monto)
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT saldo FROM usuarios WHERE id_usuario = %s", (id_usuario,))
        usuario = cursor.fetchone()
        
        if not usuario or float(usuario['saldo']) < monto_float:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Saldo insuficiente en tu cuenta digital de la aplicación'}), 400
            
        cursor.execute("UPDATE usuarios SET saldo = saldo - %s WHERE id_usuario = %s", (monto_float, id_usuario))
        cursor.execute("UPDATE tarjetas_rfid SET saldo = saldo + %s WHERE id_usuario = %s", (monto_float, id_usuario))
        cursor.execute("INSERT INTO historial (id_usuario, id_vehiculo, tipo, monto) VALUES (%s, NULL, 'recarga', %s)", (id_usuario, monto_float))
        
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"success": True, "message": "Saldo transferido a tu tarjeta física correctamente"}), 200
    except mysql.connector.Error as err:
        return jsonify({'success': False, 'error': str(err)}), 500