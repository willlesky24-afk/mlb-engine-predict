# Estructura de Base de Datos para Stitch Finance

Para que tu aplicación funcione con MongoDB y los gráficos de Charts se vean correctamente, debes crear la siguiente estructura en tu clúster de MongoDB Atlas.

## 1. Crear Base de Datos
- **Nombre de la Base de Datos:** `StitchFinance`

## 2. Colecciones y Esquema (JSON)

Crea estas dos colecciones dentro de la base de datos `StitchFinance`:

### Colección: `clients`
Esta tabla guarda la información de tus clientes. Cada documento debe verse así:
```json
{
  "name": "Juan",
  "lastname": "Pérez",
  "idCard": "12345678",
  "phone": "0414-1234567",
  "address": "Calle 1, Caracas",
  "status": "pending", 
  "totalDebt": 100,
  "createdAt": { "$date": "2024-03-24T00:00:00Z" }
}
```

### Colección: `payments`
Esta tabla registra cada abono realizado. **Importante:** El campo `client_id` debe coincidir con el ID del cliente.
```json
{
  "client_id": "ID_DEL_CLIENTE_AQUÍ",
  "client_name": "Juan Pérez",
  "amount": 50,
  "date": { "$date": "2024-03-24T10:30:00Z" },
  "method": "Zelle",
  "receipt_nro": "0001"
}
```

---

## 3. Configuración en MongoDB Atlas (Paso a Paso)

1. **Data Services:** Ve a tu clúster y pulsa en **"Browse Collections"**.
2. **Create Database:** 
   - Database name: `StitchFinance`
   - Collection name: `clients`
3. **Add Collection:** Crea la segunda colección llamada `payments`.
4. **App Services (Cloud Sync):**
   - Ve a la pestaña **"App Services"** en el menú superior.
   - Crea una nueva aplicación llamada `FinanceApp`.
   - Activa **"Device Sync"** o **"Data Access"** para permitir que tu página web lea y escriba datos directamente sin necesidad de un servidor propio.

## 4. Conexión con Charts
Una vez tengas datos en estas colecciones:
1. Ve a **Charts**.
2. Añade un **Data Source** seleccionando tu clúster -> `StitchFinance` -> `payments`.
3. Crea tu dashboard y usa los campos `amount` (para el total recaudado) y `date` (para la línea de tiempo).
