import sqlite3

# Conecta a la base de datos de tu proyecto
conexion = sqlite3.connect('vc_admin.db') # O 'database.db' si así se llama la tuya
cursor = conexion.cursor()

# Actualiza el nombre exactamente para el usuario administrador
cursor.execute("UPDATE usuarios SET nombre = 'Victor Caro' WHERE rol = 'admin' OR rol = 'ADMIN'")
conexion.commit()
conexion.close()

print("¡Nombre actualizado a Victor Caro en la base de datos con éxito!")