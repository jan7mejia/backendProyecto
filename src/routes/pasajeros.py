from flask import Blueprint, jsonify, request
import mysql.connector
from src.database import get_db_connection
from datetime import datetime

pasajeros_bp = Blueprint('pasajeros', __name__)

# ======================================
# NUEVO ENDPOINT: MONITOREO EN TIEMPO REAL PARA EL CHOFER
# ======================================
@pasajeros_bp.route('/api/chofer/monitoreo/<int:id_chofer>', methods=['GET'])
def monitoreo_chofer(id_chofer):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # 1. Obtener la unidad activa (Línea y Placa) asignada a este chofer
        query_unidad_fija = """
            SELECT CONCAT(l.nombre_linea, ' - ', v.placa) AS unidad 
            FROM asignaciones a
            JOIN vehiculos v ON a.id_vehiculo = v.id_vehiculo
            JOIN lineas l ON a.id_linea = l.id_linea
            WHERE a.id_chofer = %s AND a.estado = 'activo'
            LIMIT 1
        """
        
        try:
            cursor.execute(query_unidad_fija, (id_chofer,))
            unidad_resultado = cursor.fetchone()
        except mysql.connector.Error:
            unidad_resultado = {"unidad": "Línea Cercado (Activa)"}

        unidad_info = unidad_resultado["unidad"] if unidad_resultado else "Sin Unidad Asignada"

        # 2. Calcular la recaudación total acumulada del día de hoy para este chofer
        hoy = datetime.now().strftime('%Y-%m-%d')
        query_ingresos = """
            SELECT SUM(monto) AS total 
            FROM pagos 
            WHERE id_chofer = %s AND DATE(fecha_pago) = %s
        """
        cursor.execute(query_ingresos, (id_chofer, hoy))
        ingresos_resultado = cursor.fetchone()
        ingresos_hoy = float(ingresos_resultado["total"]) if ingresos_resultado and ingresos_resultado["total"] else 0.00

        # 3. Obtener el flujo de pasajeros entrantes con datos detallados (Nombre, Categoría, CI, Hora)
        query_pagos = """
            SELECT 
                p.id_pago AS id,
                CONCAT(u.nombre, ' ', IFNULL(u.apellido, '')) AS pasajero,
                u.ci,
                cp.nombre_categoria AS tipo_pasajero,
                p.metodo_pago AS metodo,
                p.monto,
                TIME(p.fecha_pago) AS hora
            FROM pagos p
            JOIN usuarios u ON p.id_usuario = u.id_usuario
            LEFT JOIN categorias_pasajero cp ON u.id_categoria = cp.id_categoria
            WHERE p.id_chofer = %s AND DATE(p.fecha_pago) = %s
            ORDER BY p.fecha_pago DESC
        """
        cursor.execute(query_pagos, (id_chofer, hoy))
        alertas_pagos = cursor.fetchall()

        # Formatear tipos de datos nativos para JSON
        for pago in alertas_pagos:
            pago['monto'] = float(pago['monto'])
            if pago['hora']:
                total_segundos = int(pago['hora'].total_seconds())
                horas = total_segundos // 3600
                minutos = (total_segundos % 3600) // 60
                segundos = total_segundos % 60
                pago['hora'] = f"{horas:02d}:{minutos:02d}:{segundos:02d}"
            else:
                pago['hora'] = datetime.now().strftime('%H:%M:%S')

        cursor.close()
        conn.close()

        return jsonify({
            "success": True,
            "unidad": unidad_info,
            "ingresosHoy": ingresos_hoy,
            "alertasPagos": alertas_pagos
        }), 200

    except mysql.connector.Error as err:
        return jsonify({'success': False, 'error': str(err)}), 500


# ======================================
# ENDPOINT: OBTENER TARIFA DINÁMICA DESDE LA BD
# ======================================
@pasajeros_bp.route('/api/tarifa', methods=['GET'])
def obtener_tarifa():
    id_categoria = request.args.get('id_categoria')
    id_linea = request.args.get('id_linea', 1) 

    if not id_categoria:
        return jsonify({"success": False, "error": "Falta especificar la categoría"}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        query = "SELECT monto FROM tarifas WHERE id_categoria = %s AND id_linea = %s"
        cursor.execute(query, (id_categoria, id_linea))
        resultado = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if resultado:
            return jsonify({
                "success": True, 
                "monto": float(resultado['monto'])
            }), 200
        else:
            return jsonify({
                "success": False, 
                "error": "Tarifa no configurada en el sistema para este trayecto"
            }), 404
            
    except mysql.connector.Error as err:
        return jsonify({'success': False, 'error': str(err)}), 500


# ======================================
# ENDPOINT: VER MOVIMIENTOS E INFORMACIÓN COMPLETA DEL USUARIO
# ======================================
@pasajeros_bp.route('/api/movimientos/<int:id_usuario>', methods=['GET'])
def ver_movimientos(id_usuario):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT id_usuario, nombre, id_categoria, id_rol FROM usuarios WHERE id_usuario = %s", (id_usuario,))
        info_usuario = cursor.fetchone()

        cursor.execute("SELECT codigo, saldo, estado FROM tarjetas_rfid WHERE id_usuario = %s LIMIT 1", (id_usuario,))
        tarjeta = cursor.fetchone()
        if tarjeta:
            tarjeta['saldo'] = float(tarjeta['saldo'])

        query_historial = """
            SELECT 
                h.id_historial, 
                h.tipo, 
                h.monto, 
                h.fecha,
                v.placa,
                l.nombre_linea,
                CONCAT(u_chofer.nombre, ' ', IFNULL(u_chofer.apellido, '')) AS nombre_chofer,
                IF(h.tipo='recarga', 'Recarga de Saldo - Llajtabus', 'Cobro de Pasaje Electrónico') as detalle
            FROM historial h
            LEFT JOIN pagos p ON h.id_usuario = p.id_usuario 
                             AND h.id_vehiculo = p.id_vehiculo 
                             AND h.monto = p.monto
                             AND ABS(TIMESTAMPDIFF(SECOND, h.fecha, p.fecha_pago)) < 10
            LEFT JOIN vehiculos v ON p.id_vehiculo = v.id_vehiculo
            LEFT JOIN lineas l ON v.id_linea = l.id_linea
            LEFT JOIN usuarios u_chofer ON p.id_chofer = u_chofer.id_usuario
            WHERE h.id_usuario = %s 
            ORDER BY h.fecha DESC
        """
        cursor.execute(query_historial, (id_usuario,))
        movimientos = cursor.fetchall()
        
        for m in movimientos:
            m['monto'] = float(m['monto'])
            m['fecha'] = m['fecha'].isoformat()

        cursor.execute("SELECT nombre_linea as linea, descripcion as recorrido, estado FROM lineas")
        rutas = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return jsonify({
            "success": True, 
            "usuario": info_usuario,
            "movimientos": movimientos, 
            "rutas": rutas,
            "tarjeta_rfid": tarjeta
        }), 200
    except mysql.connector.Error as err:
        return jsonify({'success': False, 'error': str(err)}), 500


# ======================================
# ENDPOINT OPTIMIZADO: OBTENER LÍNEAS ACTIVAS CON TARIFA DINÁMICA POR CATEGORÍA
# ======================================
@pasajeros_bp.route('/api/lineas', methods=['GET'])
@pasajeros_bp.route('/api/lineas/activas', methods=['GET']) # Cubre ambas rutas por consistencia del Front
def obtener_lineas_activas():
    # CAPTURAMOS EL ID DE CATEGORÍA DESDE LOS PARÁMETROS DE LA PETICIÓN
    id_categoria = request.args.get('id_categoria')
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        if id_categoria:
            # Hacemos un LEFT JOIN con la tabla de tarifas usando la categoría del pasajero logueado
            query = """
                SELECT 
                    l.id_linea, 
                    l.nombre_linea, 
                    l.descripcion, 
                    l.estado,
                    IFNULL(t.monto, 2.0) AS tarifa_personalizada
                FROM lineas l
                LEFT JOIN tarifas t ON l.id_linea = t.id_linea AND t.id_categoria = %s
                WHERE l.estado = 'activa'
            """
            cursor.execute(query, (id_categoria,))
        else:
            query = "SELECT id_linea, nombre_linea, descripcion, estado, 2.0 AS tarifa_personalizada FROM lineas WHERE estado = 'activa'"
            cursor.execute(query)
            
        lineas = cursor.fetchall()
        
        # Formatear la tarifa para JSON
        for linea in lineas:
            linea['tarifa_personalizada'] = float(linea['tarifa_personalizada'])
        
        cursor.close()
        conn.close()
        
        return jsonify({
            "success": True,
            "lineas": lineas
        }), 200
    except mysql.connector.Error as err:
        return jsonify({'success': False, 'error': str(err)}), 500