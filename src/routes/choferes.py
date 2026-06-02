from flask import Blueprint, jsonify, request
import mysql.connector
from src.database import get_db_connection

choferes_bp = Blueprint('choferes', __name__)

# ======================================
# ENDPOINT: FLUJO DE COBROS Y RECAUDACIÓN EN TIEMPO REAL
# ======================================
@choferes_bp.route('/api/chofer/monitoreo/<int:id_chofer>', methods=['GET'])
def monitoreo_chofer(id_chofer):
    rango = request.args.get('rango', 'hoy').lower().strip()

    conn   = None
    cursor = None
    try:
        id_chofer_int = int(id_chofer)
        conn   = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # 1. Asignación activa del chofer → obtenemos también id_linea e id_vehiculo
        cursor.execute("""
            SELECT a.id_linea, a.id_vehiculo, l.nombre_linea, v.placa
            FROM asignaciones a
            JOIN lineas  l ON a.id_linea    = l.id_linea
            JOIN vehiculos v ON a.id_vehiculo = v.id_vehiculo
            WHERE a.id_chofer = %s AND a.estado = 'activo'
            LIMIT 1
        """, (id_chofer_int,))
        asignacion = cursor.fetchone()

        nombre_linea   = asignacion['nombre_linea'] if asignacion and asignacion['nombre_linea'] else "Línea No Asignada"
        placa_vehiculo = asignacion['placa']         if asignacion and asignacion['placa'] else "S/N"
        id_linea       = asignacion['id_linea']      if asignacion else None
        id_vehiculo    = asignacion['id_vehiculo']   if asignacion else None

        # ─────────────────────────────────────────────────────────────────
        # 2. Recaudación de HOY — solo este chofer, solo hoy
        # ─────────────────────────────────────────────────────────────────
        cursor.execute("""
            SELECT IFNULL(SUM(p.monto), 0.00) AS total
            FROM pagos p
            WHERE (p.id_chofer = %s OR (p.id_vehiculo = %s AND p.id_linea = %s))
              AND DATE(p.fecha_pago) = CURDATE()
        """, (id_chofer_int, id_vehiculo, id_linea))
        total_hoy = float(cursor.fetchone()['total'])

        # ─────────────────────────────────────────────────────────────────
        # 3. Recaudación HISTÓRICA — Se mantiene fija internamente en la consulta base
        # ─────────────────────────────────────────────────────────────────
        cursor.execute("""
            SELECT IFNULL(SUM(p.monto), 0.00) AS total
            FROM pagos p
            WHERE p.id_chofer = %s 
               OR p.id_vehiculo IN (
                   SELECT DISTINCT id_vehiculo FROM asignaciones WHERE id_chofer = %s
               )
        """, (id_chofer_int, id_chofer_int))
        total_historico = float(cursor.fetchone()['total'])

        # ─────────────────────────────────────────────────────────────────
        # 4. Flujo de pasajeros estricto del día
        # ─────────────────────────────────────────────────────────────────
        query_pagos = """
            SELECT
                p.id_pago  AS id,
                CONCAT(u.nombre, ' ', IFNULL(u.apellido, '')) AS pasajero,
                u.ci,
                IFNULL(c.nombre_categoria, 'adulto') AS tipo_pasajero,
                p.monto,
                p.metodo_pago AS metodo,
                DATE_FORMAT(p.fecha_pago, '%%H:%%i:%%s') AS hora
            FROM pagos p
            JOIN usuarios u ON p.id_usuario = u.id_usuario
            LEFT JOIN categorias_pasajero c ON u.id_categoria = c.id_categoria
            WHERE (p.id_chofer = %s OR (p.id_vehiculo = %s AND p.id_linea = %s))
              AND DATE(p.fecha_pago) = CURDATE()
            ORDER BY p.id_pago DESC
        """
        params = [id_chofer_int, id_vehiculo, id_linea]

        cursor.execute(query_pagos, params)
        alertas_pagos = cursor.fetchall()

        for pago in alertas_pagos:
            pago['monto'] = float(pago['monto'])

        cursor.close()
        conn.close()

        # Forzamos que los ingresos calculados devuelvan siempre total_hoy
        ingresos_calculados = total_hoy

        # Si no se encontró asignación activa, definimos un texto por defecto claro
        if asignacion:
            unidad_string = f"{nombre_linea} (Placa: {placa_vehiculo})"
        else:
            unidad_string = "Sin Unidad Asignada"

        return jsonify({
            "success":            True,
            "unidad":             unidad_string,
            "ingresosCalculados": ingresos_calculados,
            "totalHoy":           total_hoy,
            "totalHistorico":     total_historico,
            "alertasPagos":       alertas_pagos
        }), 200

    except mysql.connector.Error as err:
        if cursor: cursor.close()
        if conn:   conn.close()
        return jsonify({'success': False, 'error': str(err)}), 500
    except Exception as e:
        if cursor: cursor.close()
        if conn:   conn.close()
        return jsonify({'success': False, 'error': str(e)}), 500