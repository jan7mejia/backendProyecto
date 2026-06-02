from flask import Blueprint, request, jsonify
import mysql.connector
from src.database import get_db_connection

soporte_bp = Blueprint('soporte', __name__)

@soporte_bp.route('/api/soporte/reportar', methods=['POST'])
def reportar_soporte():
    data = request.json or {}
    id_usuario = data.get('id_usuario')
    mensaje = data.get('mensaje')
    
    # MEJORA/ACOPLE: Captura el parámetro enviado desde el frontend con el nombre exacto
    id_linea = data.get('id_linea_afectada') or data.get('id_linea')
    
    tipo_emisor = data.get('tipo_emisor', 'pasajero')
    categoria = data.get('categoria', 'otros')

    if not id_usuario or not mensaje:
        return jsonify({'success': False, 'error': 'Datos de soporte incompletos'}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # CLASIFICACIÓN INTERCEPTORA AUTOMÁTICA
        # Si es un problema técnico global del sistema, va directo al Admin General (id_linea = None)
        if categoria in ['falla_app', 'problema_saldo']:
            valor_linea = None
        else:
            # Si es mal servicio, limpieza u otros operativos, se asocia a la línea enviada
            valor_linea = id_linea if (id_linea != '' and id_linea is not None) else None

        query = """
            INSERT INTO reportes_soporte (id_usuario_emisor, id_linea_afectada, tipo_usuario_emisor, categoria, mensaje, estado) 
            VALUES (%s, %s, %s, %s, %s, 'pendiente')
        """
        cursor.execute(query, (id_usuario, valor_linea, tipo_emisor, categoria, mensaje))
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Tu reporte ha sido despachado con éxito.'}), 200
    except mysql.connector.Error as err:
        return jsonify({'success': False, 'error': str(err)}), 500