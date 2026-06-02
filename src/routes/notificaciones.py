from flask import Blueprint, request, jsonify
import mysql.connector
from src.database import get_db_connection

notificaciones_bp = Blueprint('notificaciones', __name__)

# ======================================
# ENDPOINT: OBTENER NOTIFICACIONES POR USUARIO
# ======================================
@notificaciones_bp.route('/api/notificaciones/<int:id_usuario>', methods=['GET'])
def obtener_notificaciones(id_usuario):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT id_notificacion, id_usuario, titulo, mensaje, leido, fecha 
            FROM notificaciones WHERE id_usuario = %s ORDER BY fecha DESC
        """
        cursor.execute(query, (id_usuario,))
        notificaciones = cursor.fetchall()
        
        for n in notificaciones:
            n['leido'] = bool(n['leido'])
            n['fecha'] = n['fecha'].strftime('%d/%m/%Y %H:%M') if n['fecha'] else 'Reciente'
            
        cursor.close()
        conn.close()
        return jsonify({'success': True, 'notificaciones': notificaciones}), 200
    except mysql.connector.Error as err:
        return jsonify({'success': False, 'error': f"Error de BD: {str(err)}"}), 500

# ======================================
# ENDPOINT: MARCAR NOTIFICACIÓN COMO LEÍDA
# ======================================
@notificaciones_bp.route('/api/notificaciones/leer/<int:id_notificacion>', methods=['PUT'])
def marcar_notificacion_leida(id_notificacion):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE notificaciones SET leido = TRUE WHERE id_notificacion = %s", (id_notificacion,))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'success': True, 'message': 'Notificación marcada como leída'}), 200
    except mysql.connector.Error as err:
        return jsonify({'success': False, 'error': f"Error de BD: {str(err)}"}), 500

# ======================================
# ENDPOINT: ELIMINAR NOTIFICACIÓN
# ======================================
@notificaciones_bp.route('/api/notificaciones/eliminar/<int:id_notificacion>', methods=['DELETE'])
def eliminar_notificacion(id_notificacion):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM notificaciones WHERE id_notificacion = %s", (id_notificacion,))
        conn.commit()
        
        filas_afectadas = cursor.rowcount
        cursor.close()
        conn.close()
        
        if filas_afectadas > 0:
            return jsonify({'success': True, 'message': 'Notificación eliminada exitosamente'}), 200
        else:
            return jsonify({'success': False, 'error': 'No se encontró la notificación especificada.'}), 404
            
    except mysql.connector.Error as err:
        return jsonify({'success': False, 'error': f"Error de BD al eliminar: {str(err)}"}), 500

# ======================================
# ENDPOINT BLINDADO DE SOPORTE
# ======================================
@notificaciones_bp.route('/api/soporte/reportar', methods=['POST'])
def crear_reporte_soporte():
    data = request.get_json(silent=True)
    
    print("\n========================================")
    print("MÉTODO POST DETECTADO EN /api/soporte/reportar")
    print(f"Diccionario JSON procesado: {data}")
    print("========================================\n")

    if data is None:
        return jsonify({
            'success': False,
            'error': 'El servidor recibió un cuerpo vacío o un JSON mal estructurado.'
        }), 400

    id_usuario_emisor = data.get('id_usuario_emisor') or data.get('id_usuario')
    id_linea_afectada = data.get('id_linea_afectada')
    tipo_usuario_emisor = data.get('tipo_usuario_emisor', 'pasajero')
    categoria = data.get('categoria', 'otros')
    mensaje = data.get('mensaje')

    mensaje_str = str(mensaje).strip() if mensaje is not None else ""

    if categoria == 'todos' or not categoria:
        categoria = 'otros'

    if not id_usuario_emisor or mensaje_str == "":
        return jsonify({
            'success': False,
            'error': f"Faltan campos obligatorios. id_usuario={id_usuario_emisor}"
        }), 400

    try:
        id_usuario_emisor = int(id_usuario_emisor)
        if id_linea_afectada is not None and str(id_linea_afectada).strip() != "" and str(id_linea_afectada).lower() != "null":
            id_linea_afectada = int(id_linea_afectada)
        else:
            id_linea_afectada = None
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'Los IDs deben ser numéricos.'}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        query_reporte = """
            INSERT INTO reportes_soporte (id_usuario_emisor, id_linea_afectada, tipo_usuario_emisor, categoria, mensaje, estado)
            VALUES (%s, %s, %s, %s, %s, 'pendiente')
        """
        cursor.execute(query_reporte, (id_usuario_emisor, id_linea_afectada, tipo_usuario_emisor, categoria, mensaje_str))
        id_nuevo_reporte = cursor.lastrowid

        titulos_cat = {
            'falla_app': 'Falla en Aplicación',
            'problema_saldo': 'Inconveniente de Saldo/RFID',
            'mal_servicio': 'Reclamo por Mal Servicio',
            'limpieza': 'Reporte de Limpieza',
            'otros': 'Soporte Técnico'
        }
        categoria_texto = titulos_cat.get(categoria, 'Soporte Técnico')

        query_notificacion = """
            INSERT INTO notificaciones (id_usuario, titulo, mensaje, leido)
            VALUES (%s, %s, %s, FALSE)
        """
        mensaje_notif = f"Tu reporte #{id_nuevo_reporte} sobre '{categoria_texto}' ha sido registrado. Estado: PENDIENTE."
        cursor.execute(query_notificacion, (id_usuario_emisor, 'Soporte Registrado', mensaje_notif))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'message': 'Reporte registrado exitosamente',
            'id_reporte': id_nuevo_reporte
        }), 201

    except mysql.connector.Error as err:
        return jsonify({'success': False, 'error': f"Error en MySQL: [{err.errno}] {err.msg}"}), 500

# ======================================
# ENDPOINT: OBTENER LÍNEAS ACTIVAS
# ======================================
@notificaciones_bp.route('/api/lineas/activas', methods=['GET'])
def obtener_lineas_activas():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        query = "SELECT id_linea, nombre_linea, descripcion FROM lineas WHERE estado = 'activa'"
        cursor.execute(query)
        lineas = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify({'success': True, 'lineas': lineas}), 200
    except mysql.connector.Error as err:
        return jsonify({'success': False, 'error': f"Error de BD al consultar líneas: {str(err)}"}), 500