from flask import Blueprint, request, jsonify
from src.database import get_db_connection

admin_gen_bp = Blueprint('admin_general', __name__)

# 1. OBTENER REPORTES DE FALLA DE LA APP (Admin General)
@admin_gen_bp.route('/reportes/fallas', methods=['GET'])
def obtener_fallas_sistema():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT 
                r.id_reporte,
                r.id_usuario_emisor,
                r.id_linea_afectada,
                r.tipo_usuario_emisor,
                r.categoria,
                r.mensaje,
                r.estado,
                r.fecha_creacion,
                u.nombre, 
                u.apellido, 
                u.correo
            FROM reportes_soporte r
            JOIN usuarios u ON r.id_usuario_emisor = u.id_usuario
            ORDER BY r.fecha_creacion DESC
        """
        cursor.execute(query)
        reportes = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(reportes), 200
    except Exception as e:
        print(f"Error crítico en base de datos: {str(e)}")
        return jsonify([]), 200

# 2. CREAR NUEVA LÍNEA DE TRANSPORTE
@admin_gen_bp.route('/lineas', methods=['POST'])
def crear_linea():
    data = request.json
    nombre = data.get('nombre_linea')
    descripcion = data.get('descripcion')
    tarifa = data.get('tarifa_estandar')

    if not nombre or not tarifa:
        return jsonify({'error': 'Nombre y tarifa estándar son obligatorios'}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = "INSERT INTO lineas (nombre_linea, descripcion, tarifa_estandar, estado) VALUES (%s, %s, %s, 'activa')"
        cursor.execute(query, (nombre, descripcion, tarifa))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'message': 'Línea de transporte creada exitosamente'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 3. OBTENER TODAS LAS LÍNEAS (CORREGIDO: 'activa' según tu base de datos)
@admin_gen_bp.route('/lineas', methods=['GET'])
def obtener_lineas():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id_linea, nombre_linea FROM lineas WHERE estado = 'activa'")
        lineas = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(lineas), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 4. CAMBIAR ESTADO DEL REPORTE
@admin_gen_bp.route('/reportes/<int:id_reporte>/estado', methods=['PUT'])
def cambiar_estado_reporte(id_reporte):
    data = request.json
    nuevo_estado = data.get('estado')

    if nuevo_estado not in ['pendiente', 'en_revision', 'resuelto']:
        return jsonify({'error': 'Estado no válido'}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE reportes_soporte SET estado = %s WHERE id_reporte = %s", (nuevo_estado, id_reporte))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'message': 'Estado del reporte actualizado'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 5. RESPONDER AL REPORTE
@admin_gen_bp.route('/reportes/responder', methods=['POST'])
def responder_reporte():
    data = request.json
    id_usuario_destino = data.get('id_usuario')
    id_reporte = data.get('id_reporte')
    mensaje_respuesta = data.get('mensaje')

    if not id_usuario_destino or not mensaje_respuesta or not id_reporte:
        return jsonify({'error': 'Faltan datos obligatorios'}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query_notif = """
            INSERT INTO notificaciones (id_usuario, titulo, mensaje, leido) 
            VALUES (%s, 'Soporte Técnico - PayBus', %s, FALSE)
        """
        cursor.execute(query_notif, (id_usuario_destino, mensaje_respuesta))
        cursor.execute("UPDATE reportes_soporte SET estado = 'resuelto' WHERE id_reporte = %s", (id_reporte,))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'message': 'Respuesta enviada y reporte marcado como resuelto'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 6. BORRAR REPORTE FÍSICAMENTE
@admin_gen_bp.route('/reportes/<int:id_reporte>', methods=['DELETE'])
def eliminar_reporte(id_reporte):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM reportes_soporte WHERE id_reporte = %s", (id_reporte,))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'message': 'Reporte eliminado correctamente'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 7. OBTENER TARIFAS DE LÍNEA
@admin_gen_bp.route('/lineas/<string:id_linea>/tarifas', methods=['GET'])
def obtener_tarifas_linea(id_linea):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        id_linea_sanitizado = str(id_linea).strip().lower()
        
        if id_linea_sanitizado == "todos":
            query = "SELECT id_categoria, nombre_categoria, 0.00 as monto FROM categorias_pasajero"
            cursor.execute(query)
        else:
            id_linea_int = int(id_linea_sanitizado)
            query = """
                SELECT c.id_categoria, c.nombre_categoria, COALESCE(t.monto, 0.00) as monto
                FROM categorias_pasajero c
                LEFT JOIN tarifas t ON c.id_categoria = t.id_categoria AND t.id_linea = %s
            """
            cursor.execute(query, (id_linea_int,))
            
        tarifas = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(tarifas), 200
    except Exception as e:
        return jsonify({'error': f'Error interno al obtener tarifas: {str(e)}'}), 500

# 8. GUARDAR O ACTUALIZAR TARIFAS
@admin_gen_bp.route('/lineas/tarifas/guardar', methods=['POST'])
def guardar_tarifas_linea():
    data = request.json
    id_linea_raw = data.get('id_linea')
    lista_tarifas = data.get('tarifas')

    if id_linea_raw is None or not lista_tarifas:
        return jsonify({'error': 'Datos incompletos para actualizar tarifas'}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        ids_lineas_afectadas = []
        if str(id_linea_raw).strip().lower() == "todos":
            cursor.execute("SELECT id_linea FROM lineas WHERE estado = 'activa'")
            res = cursor.fetchall()
            ids_lineas_afectadas = [row[0] for row in res]
        else:
            ids_lineas_afectadas = [int(id_linea_raw)]

        for id_linea in ids_lineas_afectadas:
            for tarifa in lista_tarifas:
                id_cat = tarifa.get('id_categoria')
                monto = tarifa.get('monto')
                cursor.execute("SELECT id_tarifa FROM tarifas WHERE id_categoria = %s AND id_linea = %s", (id_cat, id_linea))
                existe = cursor.fetchone()
                if existe:
                    cursor.execute("UPDATE tarifas SET monto = %s WHERE id_categoria = %s AND id_linea = %s", (monto, id_cat, id_linea))
                else:
                    cursor.execute("INSERT INTO tarifas (id_categoria, id_linea, monto) VALUES (%s, %s, %s)", (id_cat, id_linea, monto))
                    
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'message': 'Tarifas actualizadas correctamente'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ======================================================================
# NUEVOS ENDPOINTS: GESTIÓN DE ALTA / BAJA ASIGNACIÓN DE CHOFERES
# ======================================================================

# 9. LISTAR TODOS LOS CHOFERES CON SUS ASIGNACIONES ACTUALES
@admin_gen_bp.route('/choferes/estado', methods=['GET'])
def obtener_estado_choferes():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT 
                u.id_usuario as id_chofer,
                u.nombre,
                u.apellido,
                u.ci,
                u.telefono,
                a.id_asignacion,
                l.id_linea,
                l.nombre_linea,
                v.id_vehiculo,
                v.placa,
                v.modelo
            FROM usuarios u
            JOIN roles r ON u.id_rol = r.id_rol
            LEFT JOIN asignaciones a ON u.id_usuario = a.id_chofer AND a.estado = 'activo'
            LEFT JOIN lineas l ON a.id_linea = l.id_linea
            LEFT JOIN vehiculos v ON a.id_vehiculo = v.id_vehiculo
            WHERE r.nombre_rol = 'chofer' AND u.estado = 'activo'
        """
        cursor.execute(query)
        choferes = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(choferes), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 10. OBTENER VEHÍCULOS DE UNA LÍNEA ESPECÍFICA
@admin_gen_bp.route('/lineas/<int:id_linea>/vehiculos', methods=['GET'])
def obtener_vehiculos_linea(id_linea):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id_vehiculo, placa, modelo FROM vehiculos WHERE id_linea = %s AND estado = 'activo'", (id_linea,))
        vehiculos = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(vehiculos), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 11. DAR DE BAJA (QUITAR LÍNEA Y VEHÍCULO)
@admin_gen_bp.route('/choferes/baja', methods=['POST'])
def dar_baja_chofer():
    data = request.json
    id_asignacion = data.get('id_asignacion')
    if not id_asignacion:
        return jsonify({'error': 'ID de asignación requerido'}), 400
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE asignaciones SET estado = 'finalizado', fecha_fin = NOW() WHERE id_asignacion = %s", (id_asignacion,))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'message': 'Chofer desvinculado con éxito (Baja procesada)'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 12. DAR DE ALTA (ASIGNAR LÍNEA Y VEHÍCULO)
@admin_gen_bp.route('/choferes/alta', methods=['POST'])
def dar_alta_chofer():
    data = request.json
    id_chofer = data.get('id_chofer')
    id_linea = data.get('id_linea')
    id_vehiculo = data.get('id_vehiculo')
    turno = data.get('turno', 'mañana')

    if not all([id_chofer, id_linea, id_vehiculo]):
        return jsonify({'error': 'Datos incompletos para procesar asignación'}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verificar que no tenga ya una asignación activa previa
        cursor.execute("SELECT id_asignacion FROM asignaciones WHERE id_chofer = %s AND estado = 'activo'", (id_chofer,))
        if cursor.fetchone():
            return jsonify({'error': 'El chofer ya cuenta con una línea y vehículo asignados activos'}), 400

        query = """
            INSERT INTO asignaciones (id_chofer, id_linea, id_vehiculo, turno, fecha_inicio, estado)
            VALUES (%s, %s, %s, %s, NOW(), 'activo')
        """
        cursor.execute(query, (id_chofer, id_linea, id_vehiculo, turno))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'message': 'Chofer asignado correctamente (Alta procesada)'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ======================================================================
# 13. CREAR NUEVO VEHÍCULO ASOCIADO A UNA LÍNEA (NUEVA MEJORA)
# ======================================================================
@admin_gen_bp.route('/vehiculos', methods=['POST'])
def crear_vehiculo():
    data = request.json
    placa = data.get('placa')
    modelo = data.get('modelo')
    id_linea = data.get('id_linea')
    
    if not placa or not id_linea:
        return jsonify({'error': 'La placa y la línea son obligatorias'}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Validación de Placa Única
        cursor.execute("SELECT id_vehiculo FROM vehiculos WHERE placa = %s", (placa,))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({'error': f'La placa {placa} ya está registrada en el sistema'}), 400
            
        # Generar un QR por defecto (puedes cambiar este texto según la lógica de tu app)
        qr_codigo = f"PAYBUS-VEHICULO-{placa}"
        
        query = """
            INSERT INTO vehiculos (placa, modelo, qr_codigo, id_linea, estado) 
            VALUES (%s, %s, %s, %s, 'activo')
        """
        cursor.execute(query, (placa, modelo, qr_codigo, int(id_linea)))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'message': f'Vehículo con placa {placa} registrado y asignado exitosamente'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500