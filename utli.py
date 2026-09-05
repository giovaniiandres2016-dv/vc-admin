from datetime import datetime
from zoneinfo import ZoneInfo

def hora_colombia():
    # Obtiene la hora actual en Colombia y le quita la zona horaria para guardarla limpia en la BD
    return datetime.now(ZoneInfo("America/Bogota")).replace(tzinfo=None)