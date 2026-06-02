import mysql.connector

db_config = {
    'user': 'root',
    'password': '123jan',  
    'host': '127.0.0.1',
    'database': 'transporte_cercado_final'
}

def get_db_connection():
    return mysql.connector.connect(**db_config)