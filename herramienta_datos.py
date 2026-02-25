# -*- coding: utf-8 -*-
from pymongo import MongoClient
from datetime import datetime
import json
import sys

# Forzar salida en UTF-8
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

class StitchFinanceData:
    def __init__(self, uri):
        self.client = MongoClient(uri)
        self.db = self.client['StitchFinance']
        self.clients_col = self.db['clients']
        self.payments_col = self.db['payments']

    def listar_clientes(self):
        print("\n--- LISTA DE CLIENTES EN MONGODB ---")
        clientes = list(self.clients_col.find())
        for c in clientes:
            status_str = "SOLVENTE" if c.get('status') == 'paid' else "DEUDOR"
            print(f"[{c.get('idCard')}] {c.get('name')} {c.get('lastname')} - Deuda: ${c.get('totalDebt')} ({status_str})")
        return clientes

    def registrar_pago(self, idCard, monto, metodo="Efectivo"):
        # 1. Registrar el pago
        pago = {
            "clientId": idCard,
            "amount": float(monto),
            "date": datetime.now().isoformat(),
            "method": metodo,
            "createdAt": datetime.now()
        }
        res_pago = self.payments_col.insert_one(pago)
        
        # 2. Actualizar la deuda del cliente
        self.clients_col.update_one(
            {"idCard": idCard},
            {"$inc": {"totalDebt": -float(monto)}}
        )
        
        # 3. Verificar si ya pagó todo para cambiar status
        cliente = self.clients_col.find_one({"idCard": idCard})
        if cliente and cliente.get('totalDebt', 0) <= 0:
            self.clients_col.update_one({"idCard": idCard}, {"$set": {"status": "paid", "totalDebt": 0}})
        
        print(f"✅ Pago de ${monto} registrado para {idCard}")
        return res_pago.inserted_id

# --- CONFIGURACIÓN ---
URI = "mongodb+srv://admin_stitch:daniel1315@cluster0.e1mh2za.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"

if __name__ == "__main__":
    app_data = StitchFinanceData(URI)
    
    while True:
        print("\n=== HERRAMIENTA PYTHON STITCH FINANCE ===")
        print("1. Ver Clientes")
        print("2. Registrar Pago")
        print("3. Exportar Datos a JSON")
        print("4. Salir")
        
        opcion = input("Elige una opción: ")
        
        if opcion == "1":
            app_data.listar_clientes()
        elif opcion == "2":
            cedula = input("Cédula del cliente: ")
            monto = input("Monto del pago ($): ")
            metodo = input("Método (Efectivo/Zelle/Móvil): ")
            app_data.registrar_pago(cedula, monto, metodo)
        elif opcion == "3":
            clientes = list(app_data.clients_col.find({}, {'_id': 0}))
            with open('export_datos.json', 'w', encoding='utf-8') as f:
                json.dump(clientes, f, indent=4, default=str)
            print("💾 Datos exportados a export_datos.json")
        elif opcion == "4":
            print("¡Hasta luego!")
            break
        else:
            print("Opción no válida.")
