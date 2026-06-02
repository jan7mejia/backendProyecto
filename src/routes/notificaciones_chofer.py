from flask import Blueprint, request, jsonify
import mysql.connector
from src.database import get_db_connection

notificaciones_chofer_bp = Blueprint('notificaciones_chofer', __name__)

# OBTENER NOTIFICACIONES DEL CHOFER
@notificaciones_chofer_bp.route('/api/chofer/notificaciones/<int:id_chofer>', methods=['GET'])
def obtener_notificaciones_chofer(id_chofer):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        query = """
            SELECT id_notificacion, id_usuario, titulo, mensaje, leido, fecha 
            FROM notificaciones 
            WHERE id_usuario = %s
            ORDER BY fecha DESC
        """
        cursor.execute(query, (id_chofer,))
        notificaciones = cursor.fetchall() or []
        
        for n in notificaciones:
            n['leido'] = bool(n['leido'])
            n['fecha'] = n['fecha'].strftime('%d/%m/%Y %H:%M') if n['fecha'] else 'Reciente'
            
        cursor.close()
        conn.close()
        return jsonify({'success': True, 'notificaciones': notificaciones}), 200
        
    except mysql.connector.Error as err:
        print(f"❌ Error MySQL en notificaciones_chofer: {err}")
        return jsonify({'success': False, 'notificaciones': [], 'error': str(err)}), 500
    except Exception as e:
        return jsonify({'success': False, 'notificaciones': [], 'error': str(e)}), 500

# MARCAR UNA NOTIFICACIÓN COMO LEÍDA INDIVIDUAL
@notificaciones_chofer_bp.route('/api/chofer/notificaciones/leer/<int:id_notificacion>', methods=['PUT'])
def marcar_leida_individual_chofer(id_notificacion):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE notificaciones SET leido = TRUE WHERE id_notificacion = %s", (id_notificacion,))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'success': True, 'message': 'Notificación marcada como leída.'}), 200
    except mysql.connector.Error as err:
        return jsonify({'success': False, 'error': str(err)}), 500

# LIMPIAR/LEER TODAS LAS NOTIFICACIONES DE UN CHOFER
@notificaciones_chofer_bp.route('/api/chofer/notificaciones/limpiar/<int:id_chofer>', methods=['POST'])
def limpiar_todas_notificaciones_chofer(id_chofer):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE notificaciones SET leido = TRUE WHERE id_usuario = %s", (id_chofer,))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'success': True, 'message': 'Bandeja marcada como leída.'}), 200
    except mysql.connector.Error as err:
        return jsonify({'success': False, 'error': str(err)}), 500

# ELIMINAR FÍSICAMENTE UNA NOTIFICACIÓN
@notificaciones_chofer_bp.route('/api/chofer/notificaciones/eliminar/<int:id_notificacion>', methods=['DELETE'])
def eliminar_notificacion_chofer(id_notificacion):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM notificaciones WHERE id_notificacion = %s", (id_notificacion,))
        conn.commit()
        filas = cursor.rowcount
        cursor.close()
        conn.close()
        
        if filas > 0:
            return jsonify({'success': True, 'message': 'Notificación eliminada.'}), 200
        return jsonify({'success': False, 'error': 'No se encontró la notificación.'}), 404
    except mysql.connector.Error as err:
        return jsonify({'success': False, 'error': str(err)}), 500