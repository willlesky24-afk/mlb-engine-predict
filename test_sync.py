# -*- coding: utf-8 -*-
import requests
import json
import time
import sys

# Forzar UTF-8
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

API_URL = "http://localhost:5000/api"

def test_api():
    print("--- INICIANDO PRUEBA DE SINCRONIZACION ---")
    
    try:
        print("1. Verificando servidor...")
        requests.get(f"{API_URL}/clients")
        print("SERVIDOR ACTIVO")
    except Exception as e:
        print(f"SERVIDOR NO RESPONDE: {e}")
        return

    print("2. Registrando cliente de prueba (Prueba Sincronizada)...")
    test_client = {
        "name": "Prueba",
        "lastname": "Sincronizada",
        "idCard": "V-TEST-99",
        "phone": "0000-0000000",
        "address": "Prueba de Servidor",
        "status": "pending",
        "totalDebt": 750.0
    }
    
    try:
        res = requests.post(f"{API_URL}/clients", json=test_client)
        if res.status_code == 200:
            client_id = res.json().get('_id')
            print(f"EXITO. Cliente registrado con ID: {client_id}")
        else:
            print(f"ERROR: {res.text}")
            return
            
        print("3. Registrando un pago de $250...")
        test_payment = {
            "clientId": client_id,
            "clientIdCard": "V-TEST-99",
            "amount": 250.0,
            "method": "Transferencia",
            "date": "2024-03-24"
        }
        res_pay = requests.post(f"{API_URL}/payments", json=test_payment)
        if res_pay.status_code == 200:
            print("PAGO REGISTRADO Y DEUDA ACTUALIZADA.")
        else:
            print(f"ERROR: {res_pay.text}")

        print("\n--- PRUEBA FINALIZADA CON EXITO ---")

    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    test_api()
