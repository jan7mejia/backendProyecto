from flask import Blueprint, request, jsonify
from src.database import get_db_connection

admin_linea_bp = Blueprint('admin_linea', __name__)

def obtener_linea_admin(id_admin, connection):
    """Auxiliar para recuperar el id_linea gestionado por el usuario administrador"""
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT id_linea FROM admin_lineas WHERE id_admin = %s", (id_admin,))
    res = cursor.fetchone()
    cursor.close()
    return res['id_linea'] if res else None

# ======================================================================
# OBTENER REPORTES ESPECÍFICOS DE LA LÍNEA DEL ADMINISTRADOR
# ======================================================================
@admin_linea_bp.route('/reportes/<int:id_admin>', methods=['GET'])
def obtener_reportes(id_admin):
    try:
        connection = get_db_connection()
        id_linea = obtener_linea_admin(id_admin, connection)
        
        if not id_linea:
            connection.close()
            return jsonify([]), 200

        cursor = connection.cursor(dictionary=True)
        
        # FILTRADO CRÍTICO: Solo incidencias de su propia línea y excluye fallas de la app globales
        query = """
            SELECT r.id_reporte, r.id_usuario_emisor, r.id_linea_afectada, 
                   r.tipo_usuario_emisor, r.categoria, r.mensaje, r.estado, r.fecha_creacion,
                   u.nombre, u.apellido, u.correo
            FROM reportes_soporte r
            JOIN usuarios u ON r.id_usuario_emisor = u.id_usuario
            WHERE r.id_linea_afectada = %s AND r.categoria NOT IN ('falla_app', 'problema_saldo')
            ORDER BY r.fecha_creacion DESC
        """
        cursor.execute(query, (id_linea,))
        reportes = cursor.fetchall()
        
        cursor.close()
        connection.close()
        return jsonify(reportes), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ======================================================================
# ACCIÓN: CAMBIAR ESTADO DEL REPORTE (👁️ Leer / 🔄 Pendiente)
# ======================================================================
@admin_linea_bp.route('/reportes/<int:id_reporte>/estado', methods=['PUT'])
def cambiar_estado_reporte(id_reporte):
    try:
        data = request.json
        nuevo_estado = data.get('estado')

        connection = get_db_connection()
        cursor = connection.cursor()

        query = "UPDATE reportes_soporte SET estado = %s WHERE id_reporte = %s"
        cursor.execute(query, (nuevo_estado, id_reporte))
        connection.commit()

        cursor.close()
        connection.close()
        return jsonify({'message': 'Estado del reporte actualizado con éxito'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ======================================================================
# ACCIÓN: RESPONDER REPORTE (Inserta Alerta de Notificación al Pasajero/Chofer)
# ======================================================================
@admin_linea_bp.route('/reportes/responder', methods=['POST'])
def responder_reporte():
    try:
        data = request.json
        id_reporte = data.get('id_reporte')
        id_usuario_destino = data.get('id_usuario')
        mensaje_respuesta = data.get('mensaje')

        if not id_reporte or not id_usuario_destino or not mensaje_respuesta:
            return jsonify({'error': 'Parámetros insuficientes para procesar la respuesta'}), 400

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            "UPDATE reportes_soporte SET estado = 'resuelto' WHERE id_reporte = %s",
            (id_reporte,)
        )

        query_notificacion = """
            INSERT INTO notificaciones (id_usuario, titulo, mensaje, leido, fecha)
            VALUES (%s, 'Soporte Técnico de Línea', %s, FALSE, NOW())
        """
        cursor.execute(query_notificacion, (id_usuario_destino, mensaje_respuesta))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({'message': 'Respuesta registrada y notificación despachada al usuario'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ======================================================================
# ACCIÓN: ELIMINAR REPORTE
# ======================================================================
@admin_linea_bp.route('/reportes/<int:id_reporte>', methods=['DELETE'])
def borrar_reporte(id_reporte):
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("DELETE FROM reportes_soporte WHERE id_reporte = %s", (id_reporte,))
        connection.commit()

        cursor.close()
        connection.close()
        return jsonify({'message': 'Reporte eliminado permanentemente del sistema de control'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ======================================================================
# COMPONENTES Y REGISTROS ADICIONALES (VEHÍCULOS Y ASIGNACIONES)
# ======================================================================
@admin_linea_bp.route('/vehiculo', methods=['POST'])
def registrar_vehiculo():
    try:
        data = request.json
        placa = data.get('placa')
        modelo = data.get('modelo')
        id_linea = data.get('id_linea')

        if not placa or not modelo or not id_linea:
            return jsonify({'error': 'Parámetros incompletos'}), 400

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("SELECT id_vehiculo FROM vehiculos WHERE placa = %s", (placa,))
        if cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({'error': 'La unidad ya fue registrada previamente en el municipio'}), 400

        qr_codigo = f"PAYBUS_QR_{placa}"
        query = """
            INSERT INTO vehiculos (placa, modelo, qr_codigo, id_linea, estado)
            VALUES (%s, %s, %s, %s, 'activo')
        """
        cursor.execute(query, (placa, modelo, qr_codigo, id_linea))
        connection.commit()
        cursor.close()
        connection.close()
        return jsonify({'message': 'Vehículo añadido al sindicato'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_linea_bp.route('/componentes-asignacion/<int:id_admin>', methods=['GET'])
def obtener_componentes(id_admin):
    try:
        connection = get_db_connection()
        id_linea = obtener_linea_admin(id_admin, connection)
        
        cursor = connection.cursor(dictionary=True)
        query_choferes = """
            SELECT id_usuario, nombre, apellido FROM usuarios 
            WHERE id_rol = 2 AND estado = 'activo'
            AND id_usuario NOT IN (
                SELECT id_chofer FROM asignaciones WHERE estado = 'activo'
            )
        """
        cursor.execute(query_choferes)
        choferes = cursor.fetchall()
        
        cursor.execute("SELECT id_vehiculo, placa, modelo FROM vehiculos WHERE id_linea = %s AND estado = 'activo'", (id_linea,))
        vehiculos = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'id_linea': id_linea,
            'choferes': choferes,
            'vehiculos': vehiculos
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_linea_bp.route('/asignar', methods=['POST'])
def crear_asignacion():
    try:
        data = request.json
        id_chofer = data.get('id_chofer')
        id_linea = data.get('id_linea')
        id_vehiculo = data.get('id_vehiculo')
        turno = data.get('turno')

        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute(
            "UPDATE asignaciones SET estado = 'finalizado', fecha_fin = NOW() WHERE (id_chofer = %s OR id_vehiculo = %s) AND estado = 'activo'",
            (id_chofer, id_vehiculo)
        )
        
        query = """
            INSERT INTO asignaciones (id_chofer, id_linea, id_vehiculo, turno, fecha_inicio, estado)
            VALUES (%s, %s, %s, %s, NOW(), 'activo')
        """
        cursor.execute(query, (id_chofer, id_linea, id_vehiculo, turno))
        
        connection.commit()
        cursor.close()
        connection.close()
        return jsonify({'message': 'Asignación completada'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500