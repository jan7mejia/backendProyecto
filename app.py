from flask import Flask, request, jsonify
from flask_cors import CORS
import mysql.connector
import re
from datetime import datetime, date

app = Flask(__name__)
CORS(app)

# Saltar advertencia de seguridad de la página de inicio de ngrok
@app.after_request
def add_ngrok_header(response):
    response.headers["ngrok-skip-browser-warning"] = "true"
    return response

# Configuración de base de datos exacta de Jan Alessi
db_config = {
    'user': 'root',
    'password': '123jan',  
    'host': '127.0.0.1',
    'database': 'transporte_cercado_final'
}

def get_db_connection():
    return mysql.connector.connect(**db_config)

def calcular_edad(fecha_nac_str):
    if not fecha_nac_str:
        return 0
    try:
        if "T" in fecha_nac_str:
            fecha_nac_str = fecha_nac_str.split("T")[0]
        nacimiento = datetime.strptime(fecha_nac_str, '%Y-%m-%d').date()
        hoy = date.today()
        return hoy.year - nacimiento.year - ((hoy.month, hoy.day) < (nacimiento.month, nacimiento.day))
    except Exception as e:
        print(f"Error calculando edad: {e}")
        return 0

# ======================================
# ENDPOINT: OBTENER USUARIO POR ID 
# ======================================
@app.route('/api/usuarios/<int:id_usuario>', methods=['GET'])
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
        else:
            return jsonify({'success': False, 'error': 'Usuario no encontrado o inactivo'}), 404

    except mysql.connector.Error as err:
        return jsonify({'success': False, 'error': f"Error de BD: {str(err)}"}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': 'Error interno en el servidor'}), 500

# ======================================
# ENDPOINT DE INICIO DE SESIÓN
# ======================================
@app.route('/api/login', methods=['POST'])
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
            SELECT u.id_usuario, u.nombre, u.apellido, u.correo, u.ci, u.saldo, 
                   r.nombre_rol, cp.nombre_categoria
            FROM usuarios u
            JOIN roles r ON u.id_rol = r.id_rol
            LEFT JOIN categorias_pasajero cp ON u.id_categoria = cp.id_categoria
            WHERE (u.correo = %s OR u.ci = %s) AND u.password = %s AND u.estado = 'activo'
        """
        cursor.execute(query, (login_input, login_input, password))
        user = cursor.fetchone()
        
        cursor.close()
        conn.close()

        if user:
            return jsonify({
                'success': True,
                'message': f"Bienvenido {user['nombre']}",
                'user': {
                    'id_usuario': user['id_usuario'],
                    'nombre': user['nombre'],
                    'apellido': user['apellido'],
                    'correo': user['correo'],
                    'rol': user['nombre_rol'],
                    'saldo': float(user['saldo']),
                    'categoria': user['nombre_categoria'] if user['nombre_categoria'] else 'adulto'
                }
            }), 200
        else:
            return jsonify({'success': False, 'error': 'Credenciales incorrectas o usuario inactivo'}), 401

    except mysql.connector.Error as err:
        return jsonify({'success': False, 'error': f"Error de BD: {str(err)}"}), 500

# ======================================
# ENDPOINT DE REGISTRO
# ======================================
@app.route('/api/register', methods=['POST'])
def register():
    data = request.json or {}
    
    nombre = str(data.get('nombre', '')).strip()
    apellido = str(data.get('apellido', '')).strip()
    ci = str(data.get('ci', '')).strip()
    correo = str(data.get('correo', '')).strip().lower()
    telefono = str(data.get('telefono', '')).strip()
    password = str(data.get('password', '')).strip()
    rol_elegido = str(data.get('rol', '')).strip()
    categoria_elegida = data.get('categoria', '')
    fecha_nacimiento = data.get('fecha_nacimiento') 

    if not nombre or not apellido or not ci or not correo or not password or not rol_elegido or not fecha_nacimiento:
        return jsonify({'success': False, 'error': 'Faltan campos obligatorios en el formulario'}), 400

    edad = calcular_edad(fecha_nacimiento)

    if rol_elegido == 'chofer':
        if edad < 18:
            return jsonify({'success': False, 'error': 'Registro rechazado. Un chofer debe ser mayor de 18 años según SEGIP.'}), 400
            
    elif rol_elegido == 'pasajero':
        if categoria_elegida == 'universitario':
            uni_regex = r".+@(umss\.edu\.bo|upds\.net\.bo|upds\.edu\.bo|[a-zA-Z0-9.-]+\.edu\.bo)$"
            if not re.match(uni_regex, correo):
                return jsonify({'success': False, 'error': 'Usa un correo institucional válido (Ej: @umss.edu.bo o @upds.net.bo)'}), 400
                
        elif categoria_elegida == 'estudiante':
            if edad >= 19:
                return jsonify({'success': False, 'error': 'La categoría Estudiante (Colegio) es válida únicamente hasta los 18 años.'}), 400
                
        elif categoria_elegida == 'adulto_mayor':
            if edad < 60:
                return jsonify({'success': False, 'error': 'La categoría Adulto Mayor en Bolivia requiere un mínimo de 60 años cumplidos.'}), 400

    valor_telefono = telefono if telefono != '' else None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if rol_elegido == 'pasajero':
            mapping_cat = {
                'estudiante': 1,
                'universitario': 2,
                'adulto': 3,
                'adulto_mayor': 4
            }
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
            return jsonify({'success': False, 'error': 'El Carnet de Identidad (C.I.) o Correo ya existen en el sistema.'}), 400
        return jsonify({'success': False, 'error': f"Error interno del Servidor MySQL: {err.msg}"}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': 'Error interno en la ejecución del script Python.'}), 500

# ======================================
# CORRECCIÓN DE ENRUTAMIENTO: RECARGAR DINERO REAL
# ======================================
@app.route('/api/recargar', methods=['POST'])
@app.route('/api/Recharge/recargar', methods=['POST']) # Soporte para la ruta de tu front
def recargar_saldo():
    data = request.json or {}
    id_usuario = data.get('id_usuario')
    monto = data.get('monto')
    metodo = data.get('metodo', 'qr')

    if not id_usuario or not monto or float(monto) <= 0:
        return jsonify({'success': False, 'error': 'Datos de recarga inválidos'}), 400

    try:
        monto_float = float(monto)
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("UPDATE usuarios SET saldo = saldo + %s WHERE id_usuario = %s", (monto_float, id_usuario))
        cursor.execute("INSERT INTO recargas (id_usuario, monto, metodo) VALUES (%s, %s, %s)", (id_usuario, monto_float, metodo))
        cursor.execute("INSERT INTO historial (id_usuario, id_vehiculo, tipo, monto) VALUES (%s, NULL, 'recarga', %s)", (id_usuario, monto_float))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({"status": "success", "success": True, "message": "Recarga registrada con éxito"}), 200
    except mysql.connector.Error as err:
        return jsonify({'success': False, 'error': f"Error en BD al recargar: {str(err)}"}), 500

# ======================================
# CORRECCIÓN DE ENRUTAMIENTO: COBRO REAL CON QR 
# ======================================
@app.route('/api/pagar-qr', methods=['POST'])
@app.route('/api/ScanQR/pagar-qr', methods=['POST']) # Soporte para la ruta de tu front
def pagar_qr():
    data = request.json or {}
    id_usuario = data.get('id_usuario')
    id_vehiculo = data.get('id_vehiculo', 1) 

    if not id_usuario:
        return jsonify({'success': False, 'error': 'El ID del pasajero es requerido'}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT id_linea, placa FROM vehiculos WHERE id_vehiculo = %s", (id_vehiculo,))
        vehiculo = cursor.fetchone()
        if not vehiculo:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Vehículo / Micro no identificado en el sistema'}), 404
            
        id_linea = vehiculo['id_linea']

        cursor.execute("SELECT id_categoria, saldo FROM usuarios WHERE id_usuario = %s AND estado = 'activo'", (id_usuario,))
        usuario = cursor.fetchone()
        
        if not usuario:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Pasajero no encontrado en el padrón'}), 404

        id_cat = usuario['id_categoria'] if usuario['id_categoria'] else 3 

        query_tarifa = "SELECT monto FROM tarifas WHERE id_categoria = %s AND id_linea = %s"
        cursor.execute(query_tarifa, (id_cat, id_linea))
        tarifa_row = cursor.fetchone()
        
        if tarifa_row:
            tarifa = float(tarifa_row['monto'])
        else:
            if id_cat == 1: tarifa = 1.50   
            elif id_cat == 2: tarifa = 2.00 
            elif id_cat == 4: tarifa = 1.00 
            else: tarifa = 2.50             

        if float(usuario['saldo']) < tarifa:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': f"Saldo insuficiente. Tu pasaje cuesta Bs. {tarifa:.2f}"}), 400

        cursor.execute("UPDATE usuarios SET saldo = saldo - %s WHERE id_usuario = %s", (tarifa, id_usuario))
        cursor.execute("INSERT INTO pagos (id_usuario, id_vehiculo, metodo_pago, monto) VALUES (%s, %s, 'qr', %s)", (id_usuario, id_vehiculo, tarifa))
        cursor.execute("INSERT INTO historial (id_usuario, id_vehiculo, tipo, monto) VALUES (%s, %s, 'pago', %s)", (id_usuario, id_vehiculo, tarifa))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            "status": "success",
            "success": True, 
            "monto_descontado": tarifa, 
            "linea": f"Línea vinculada al Bus Interno (Placa: {vehiculo['placa']})"
        }), 200
        
    except mysql.connector.Error as err:
        return jsonify({'success': False, 'error': f"Fallo transaccional de BD: {str(err)}"}), 500

# ======================================
# CORRECCIÓN DE ENRUTAMIENTO: HISTORIAL Y RUTA DE BUSES
# ======================================
@app.route('/api/movimientos/<int:id_usuario>', methods=['GET'])
@app.route('/api/TravelHistory/movimientos/<int:id_usuario>', methods=['GET']) # Soporte por si tu front añade la subcarpeta
def ver_movimientos(id_usuario):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        query_historial = """
            SELECT id_historial, tipo, monto, fecha, 
            IF(tipo='recarga', 'Recarga de Saldo Digital - Llajtabus', 'Cobro de Pasaje Electrónico') as detalle
            FROM historial WHERE id_usuario = %s ORDER BY fecha DESC
        """
        cursor.execute(query_historial, (id_usuario,))
        movimientos = cursor.fetchall()
        
        for m in movimientos:
            m['monto'] = float(m['monto'])
            m['fecha'] = m['fecha'].strftime('%d/%m/%Y %H:%M')

        cursor.execute("SELECT nombre_linea as linea, descripcion as recorrido, estado FROM lineas")
        rutas = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return jsonify({
            "status": "success",
            "success": True,
            "movimientos": movimientos, 
            "rutas": rutas
        }), 200
    except mysql.connector.Error as err:
        return jsonify({'success': False, 'error': f"Error cargando movimientos de la BD: {str(err)}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)