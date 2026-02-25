# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime
import json
import sys

# Forzar UTF-8 para evitar errores de codificación en Windows
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app) # Permitir que el frontend (JS) llame a esta API

# --- CONEXIÓN MONGODB ---
URI = "mongodb+srv://admin_stitch:daniel1315@cluster0.e1mh2za.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
client = MongoClient(URI)
db = client['StitchFinance']

# Helper para convertir ObjectId a String para JSON
def parse_json(data):
    return json.loads(json.dumps(data, default=str))

# --- RUTAS API ---

@app.route('/')
def home():
    return app.send_static_file('index.html')

@app.route('/api/clients', methods=['GET'])
def get_clients():
    user_id = request.headers.get('X-User-ID')
    if not user_id: return jsonify({"error": "No User ID"}), 401
    try:
        clients = list(db.clients.find({"userId": user_id}))
        return jsonify(parse_json(clients))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/clients', methods=['POST'])
def add_client():
    user_id = request.headers.get('X-User-ID')
    if not user_id: return jsonify({"error": "No User ID"}), 401
    try:
        data = request.json
        new_client = {
            "userId": user_id,
            "name": data.get('name'),
            "lastname": data.get('lastname'),
            "idCard": data.get('idCard'),
            "phone": data.get('phone'),
            "address": data.get('address', ''),
            "status": data.get('status', 'paid'),
            "totalDebt": float(data.get('totalDebt', 0)),
            "createdAt": datetime.now()
        }
        result = db.clients.insert_one(new_client)
        new_client['_id'] = result.inserted_id
        return jsonify(parse_json(new_client))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/payments', methods=['GET'])
def get_payments():
    user_id = request.headers.get('X-User-ID')
    if not user_id: return jsonify({"error": "No User ID"}), 401
    try:
        payments = list(db.payments.find({"userId": user_id}))
        return jsonify(parse_json(payments))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/payments', methods=['POST'])
def add_payment():
    user_id = request.headers.get('X-User-ID')
    if not user_id: return jsonify({"error": "No User ID"}), 401
    try:
        data = request.json
        new_payment = {
            "userId": user_id,
            "clientId": data.get('clientId'),
            "amount": float(data.get('amount')),
            "date": data.get('date', datetime.now().isoformat()),
            "method": data.get('method'),
            "createdAt": datetime.now()
        }
        result = db.payments.insert_one(new_payment)
        
        # Actualizar deuda del cliente en la DB verificando userId
        db.clients.update_one(
            {"idCard": data.get('clientIdCard'), "userId": user_id}, 
            {"$inc": {"totalDebt": -float(data.get('amount'))}}
        )

        new_payment['_id'] = result.inserted_id
        return jsonify(parse_json(new_payment))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/clients/<idCard>', methods=['DELETE'])
def delete_client(idCard):
    user_id = request.headers.get('X-User-ID')
    if not user_id: return jsonify({"error": "No User ID"}), 401
    try:
        db.clients.delete_one({"idCard": idCard, "userId": user_id})
        db.payments.delete_many({"clientId": idCard, "userId": user_id})
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/clients/<idCard>', methods=['PUT'])
def update_client(idCard):
    user_id = request.headers.get('X-User-ID')
    if not user_id: return jsonify({"error": "No User ID"}), 401
    try:
        data = request.json
        update_data = {
            "name": data.get('name'),
            "lastname": data.get('lastname'),
            "totalDebt": float(data.get('totalDebt', 0)),
            "status": "pending" if float(data.get('totalDebt', 0)) > 0 else "paid"
        }
        db.clients.update_one(
            {"idCard": idCard, "userId": user_id},
            {"$set": update_data}
        )
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("🚀 SERVIDOR STITCH FINANCE API")
    print("Acceso Local: http://localhost:5000")
    print("Acceso Red (Celular): http://192.168.0.106:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)
