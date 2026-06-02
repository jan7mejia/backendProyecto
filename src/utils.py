from datetime import datetime, date

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