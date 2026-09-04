import sqlite3

# Conectamos directamente al archivo físico de la base de datos
conexion = sqlite3.connect("vc_admin.db")
cursor = conexion.cursor()

nombres = [
    "Sofía Martínez", "Carlos Pérez", "Valentina Gómez", "Andrés Restrepo",
    "Lucía Fernández", "Mateo Silva", "Camila Rúa", "Alejandro Morales",
    "Mariana Londoño", "Daniel Osorio", "Isabella Torres", "Felipe Castrillón",
    "Gabriela Ríos", "Santiago Henao", "Valeria Mejía", "David Echeverri",
    "Manuela Zuluaga", "Juan Esteban Arango", "Sara Palacio", "Lucas Betancur"
]

telefonos = [
    "3001234567", "3109876543", "3204567890", "3156781234",
    "3012345678", "3118765432", "3215439876", "3167892345",
    "3023456789", "3127654321", "3226543210", "3178903456",
    "3034567890", "3136543210", "3237654321", "3189014567",
    "3045678901", "3145432109", "3248765432", "3190125678"
]

contador = 0
for nombre, tel in zip(nombres, telefonos):
    try:
        # Cambiamos 'cliente' por 'clientes' (en plural)
        cursor.execute(
            "INSERT INTO clientes (nombre, telefono) VALUES (?, ?)", 
            (nombre, tel)
        )
        contador += 1
    except sqlite3.OperationalError as e:
        print(f"Error: {e}")
        break

conexion.commit()
conexion.close()

print(f"¡Listo! Se insertaron {contador} clientes en la base de datos con éxito.")