from flask import Blueprint, request, jsonify
import mysql.connector
from src.database import get_db_connection

soporte_chofer_bp = Blueprint('soporte_chofer', __name__)

@soporte_chofer_bp.route('/api/chofer/soporte/reportar', methods=['POST'])
def reportar_soporte_chofer():
    data = request.get_json(silent=True) or request.json or {}
    
    id_usuario = data.get('id_usuario_emisor') or data.get('id_usuario')
    mensaje_original = data.get('mensaje', '')
    categoria = data.get('categoria', 'otros')

    if not id_usuario:
        return jsonify({'success': False, 'error': 'Identificador id_usuario_emisor ausente.'}), 400
    if not mensaje_original:
        return jsonify({'success': False, 'error': 'El cuerpo del reporte no puede estar vacío.'}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Sincronización estricta con el ENUM físico de la Base de Datos
        # Si la categoría enviada es administrativa (baja_linea/alta_linea), se encapsula limpiamente en 'otros'
        if categoria in ['falla_app', 'mal_servicio', 'problema_saldo', 'limpieza', 'otros']:
            categoria_db = categoria
            mensaje_final = mensaje_original
        else:
            categoria_db = 'otros'
            mensaje_final = f"[{categoria.upper().replace('_', ' ')}] - {mensaje_original}"

        # CLASIFICACIÓN AUTOMÁTICA DE DESTINATARIO
        id_linea_afectada = None
        # Solo buscamos la línea si el reporte NO es una falla de la app o problema de saldo general
        if categoria_db not in ['falla_app', 'problema_saldo']:
            cursor.execute("SELECT id_linea FROM asignaciones WHERE id_chofer = %s AND estado = 'activo' LIMIT 1", (int(id_usuario),))
            linea_res = cursor.fetchone()
            if linea_res:
                id_linea_afectada = linea_res[0]

        # ÚNICA INSERCIÓN: Registrar la fila en la tabla de reportes operativos
        query_reporte = """
            INSERT INTO reportes_soporte (id_usuario_emisor, id_linea_afectada, tipo_usuario_emisor, categoria, mensaje, estado) 
            VALUES (%s, %s, 'chofer', %s, %s, 'pendiente')
        """
        cursor.execute(query_reporte, (int(id_usuario), id_linea_afectada, categoria_db, str(mensaje_final).strip()))
        id_reporte = cursor.lastrowid
        
        conn.commit()
        cursor.close()
        conn.close()
        
        # Retorna el JSON limpio que procesará el único modal de confirmation en el Front
        return jsonify({
            'success': True, 
            'message': 'Reporte guardado correctamente en la central.',
            'id_reporte': id_reporte
        }), 201

    except mysql.connector.Error as err:
        print(f"❌ Error de MySQL en soporte_chofer: {err}")
        return jsonify({'success': False, 'error': f"Error de Base de Datos: {err.msg}"}), 500
    except Exception as e:
        print(f"❌ Error inesperado en soporte_chofer: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500