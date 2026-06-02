from flask import Blueprint, request, jsonify
import mysql.connector
import re
from src.database import get_db_connection
from src.utils import calcular_edad

auth_bp = Blueprint('auth', __name__)

# ======================================
# ENDPOINT: OBTENER USUARIO POR ID (Sincronización en Tiempo Real)
# ======================================
@auth_bp.route('/api/usuarios/<int:id_usuario>', methods=['GET'])
def obtener_usuario(id_usuario):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT u.id_usuario, u.nombre, u.apellido, u.correo, u.saldo, cp.nombre_categoria 
            FROM usuarios u 
            LEFT JOIN categorias_pasajero cp ON u.id_categoria = cp.id_categoria 
            WHERE u.id_usuario = %s AND u.estado = 'activo'
        """
        cursor.execute(query, (id_usuario,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if row:
            return jsonify({
                "success": True,
                "user": {
                    "id_usuario": str(row['id_usuario']),
                    "nombre": row['nombre'],
                    "apellido": row['apellido'],
                    "correo": row['correo'],
                    "saldo": float(row['saldo']),
                    "categoria": row['nombre_categoria'] if row['nombre_categoria'] else 'adulto'
                }
            }), 200
        return jsonify({'success': False, 'error': 'Usuario no encontrado o inactivo'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ======================================
# ENDPOINT DE INICIO DE SESIÓN
# ======================================
@auth_bp.route('/api/login', methods=['POST'])
def login():
    data = request.json or {}
    login_input = str(data.get('loginInput', '')).strip()
    password = str(data.get('password', '')).strip()

    if not login_input or not password:
        return jsonify({'success': False, 'error': 'Por favor, llena todos los campos'}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT u.id_usuario, u.nombre, u.apellido, u.correo, u.ci, u.saldo, r.nombre_rol, cp.nombre_categoria
            FROM usuarios u
            JOIN roles r ON u.id_rol = r.id_rol
            LEFT JOIN categorias_pasajero cp ON u.id_categoria = cp.id_categoria
            WHERE (u.correo = %s OR u.ci = %s) AND u.password = %s AND u.estado = 'activo'
        """
        cursor.execute(query, (login_input, login_input, password))
        user = cursor.fetchone()

        if user:
            # MEJORA CRÍTICA: Detectar subtipo de administrador si el rol es 'admin'
            sub_rol = None
            if user['nombre_rol'] == 'admin':
                query_sub_rol = "SELECT id_linea FROM admin_lineas WHERE id_admin = %s LIMIT 1"
                cursor.execute(query_sub_rol, (user['id_usuario'],))
                es_admin_linea = cursor.fetchone()
                if es_admin_linea:
                    sub_rol = 'admin_linea'
                else:
                    sub_rol = 'admin_general'

            cursor.close()
            conn.close()

            return jsonify({
                'success': True,
                'message': f"Bienvenido {user['nombre']}",
                'user': {
                    'id_usuario': user['id_usuario'],
                    'nombre': user['nombre'],
                    'apellido': user['apellido'],
                    'correo': user['correo'],
                    'rol': user['nombre_rol'],
                    'sub_rol': sub_rol, # Retorna 'admin_general', 'admin_linea' o None
                    'saldo': float(user['saldo']),
                    'categoria': user['nombre_categoria'] if user['nombre_categoria'] else 'adulto'
                }
            }), 200
            
        cursor.close()
        conn.close()
        return jsonify({'success': False, 'error': 'Credenciales incorrectas o usuario inactivo'}), 401
    except mysql.connector.Error as err:
        return jsonify({'success': False, 'error': f"Error de BD: {str(err)}"}), 500

# ======================================
# ENDPOINT DE REGISTRO
# ======================================
@auth_bp.route('/api/register', methods=['POST'])
def register():
    data = request.json or {}
    nombre = str(data.get('nombre', '')).strip()
    apellido = str(data.get('apellido', '')).strip()
    ci = str(data.get('ci', '')).strip()
    correo = str(data.get('correo', '')).strip().lower()
    telefono = str(data.get('telefono', '')).strip()
    password = str(data.get('password', '')).strip()
    rol_elegido = str(data.get('rol', '')).strip()
    categoria_elegida = str(data.get('categoria', '')).strip()
    fecha_nacimiento = data.get('fecha_nacimiento') 

    if not nombre or not apellido or not ci or not correo or not password or not rol_elegido or not fecha_nacimiento:
        return jsonify({'success': False, 'error': 'Faltan campos obligatorios en el formulario'}), 400

    edad = calcular_edad(fecha_nacimiento)

    if rol_elegido == 'chofer' and edad < 18:
        return jsonify({'success': False, 'error': 'Registro rechazado. Un chofer debe ser mayor de 18 años según SEGIP.'}), 400
            
    if rol_elegido == 'pasajero':
        if categoria_elegida == 'universitario':
            uni_regex = r".+@(umss\.edu\.bo|upds\.net\.bo|upds\.edu\.bo|[a-zA-Z0-9.-]+\.edu\.bo)$"
            if not re.match(uni_regex, correo):
                return jsonify({'success': False, 'error': 'Usa un correo institucional válido (Ej: @umss.edu.bo)'}), 400
        elif categoria_elegida == 'estudiante' and edad >= 19:
            return jsonify({'success': False, 'error': 'La categoría Estudiante (Colegio) es válida únicamente hasta los 18 años.'}), 400
        elif categoria_elegida == 'adulto_mayor' and edad < 60:
            return jsonify({'success': False, 'error': 'La categoría Adulto Mayor en Bolivia requiere un mínimo de 60 años cumplidos.'}), 400

    valor_telefono = telefono if telefono != '' else None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if rol_elegido == 'pasajero':
            mapping_cat = {'estudiante': 1, 'universitario': 2, 'adulto': 3, 'adulto_mayor': 4}
            id_categoria = mapping_cat.get(categoria_elegida, 3)
            query = """
                INSERT INTO usuarios (nombre, apellido, ci, correo, telefono, password, fecha_nacimiento, id_rol, id_categoria, saldo, estado)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 1, %s, 0.00, 'activo')
            """
            valores = (nombre, apellido, ci, correo, valor_telefono, password, fecha_nacimiento, id_categoria)
        else:
            query = """
                INSERT INTO usuarios (nombre, apellido, ci, correo, telefono, password, fecha_nacimiento, id_rol, id_categoria, saldo, estado)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 2, NULL, 0.00, 'activo')
            """
            valores = (nombre, apellido, ci, correo, valor_telefono, password, fecha_nacimiento)

        cursor.execute(query, valores)
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'success': True, 'message': '¡Usuario creado exitosamente!'}), 201
    except mysql.connector.Error as err:
        if err.errno == 1062:
            return jsonify({'success': False, 'error': 'El Carnet de Identidad (C.I.) o Correo ya existen.'}), 400
        return jsonify({'success': False, 'error': f"Error interno del Servidor MySQL: {err.msg}"}), 500