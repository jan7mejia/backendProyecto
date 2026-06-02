from flask import Flask
from flask_cors import CORS

def create_app():
    app = Flask(__name__)
    CORS(app)  # Habilitar CORS para la conexión con React Native

    # ======================================
    # IMPORTAR BLUEPRINTS ORIGINALES Y MEJORAS
    # ======================================
    from src.routes.auth import auth_bp
    from src.routes.pasajeros import pasajeros_bp
    from src.routes.tarjetas import tarjetas_bp
    from src.routes.cobros import cobros_bp
    from src.routes.soporte import soporte_bp
    from src.routes.notificaciones import notificaciones_bp
    from src.routes.choferes import choferes_bp
    from src.routes.notificaciones_chofer import notificaciones_chofer_bp
    from src.routes.soporte_chofer import soporte_chofer_bp
    from src.routes.admin_general import admin_gen_bp  # <-- MEJORA: Importar Administrador General
    from src.routes.admin_linea import admin_linea_bp  # <-- NUEVA MEJORA: Importar Administrador de Línea

    # ======================================
    # REGISTRAR BLUEPRINTS (SIN PREFIJOS INTERFERENTES)
    # ======================================
    app.register_blueprint(auth_bp)
    app.register_blueprint(pasajeros_bp)
    app.register_blueprint(tarjetas_bp)
    app.register_blueprint(cobros_bp)
    app.register_blueprint(soporte_bp)
    app.register_blueprint(notificaciones_bp)
    app.register_blueprint(choferes_bp)
    app.register_blueprint(notificaciones_chofer_bp)
    app.register_blueprint(soporte_chofer_bp)
    
    # MEJORA: Registrar Administrador General con su prefijo de ruta correspondiente
    app.register_blueprint(admin_gen_bp, url_prefix='/api/admin-general')

    # NUEVA MEJORA: Registrar Administrador de Línea con su prefijo operativo
    app.register_blueprint(admin_linea_bp, url_prefix='/api/admin-linea')

    return app