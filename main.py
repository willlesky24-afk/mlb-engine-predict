# --- PARTE 1: IMPORTACIONES ---
from server import app  # Importante para que Render encuentre la app
from pymongo import MongoClient
from datetime import datetime
import sys

# Forzar salida en UTF-8 para evitar errores con iconos en Windows
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# --- PARTE 2: CONEXIÓN ---
# 1. Tu enlace real de MongoDB Atlas
URI = "mongodb+srv://admin_stitch:daniel1315@cluster0.e1mh2za.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"

# 2. Cliente de MongoDB
client = MongoClient(URI)

# 3. Acceso a la base de datos
db = client['StitchFinance']

# --- PARTE 3: DEFINICIÓN DE FUNCIONES ---
def registrar_cliente(nombre, apellido, cedula, telefono, deuda_inicial):
    col_clientes = db['clients']
    nuevo_cliente = {
        "name": nombre,      # Coincide con app.js
        "lastname": apellido, # Coincide con app.js
        "idCard": cedula,     # Coincide con app.js
        "phone": telefono, 
        "totalDebt": float(deuda_inicial),
        "status": "pending" if float(deuda_inicial) > 0 else "paid",
        "createdAt": datetime.now()
    }
    resultado = col_clientes.insert_one(nuevo_cliente)
    return resultado.inserted_id

# --- PARTE 4: EJECUCIÓN ---
if __name__ == "__main__":
    try:
        # Verificar conexión
        client.admin.command('ping')
        print("CONEXION EXITOSA A MONGODB ATLAS")
        
        print("Registrando cliente de prueba (Pedro Perez)...")
        id_nuevo = registrar_cliente("Pedro", "Perez", "V-000000", "0414-000000", 500.0)
        print(f"EXITO. Cliente registrado con ID: {id_nuevo}")
        
    except Exception as e:
        print(f"ERROR DE CONEXION: {e}")
        print("\nRECUERDA:")
        print("1. El password 'daniel1315' debe ser el correcto para el usuario admin_stitch.")
        print("2. Debes autorizar tu IP en MongoDB Atlas (Network Access -> Allow Access from Anywhere).")