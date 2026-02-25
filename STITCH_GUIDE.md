# Stitch Finance - Configuración del Dashboard

Este proyecto está diseñado para integrarse directamente con **MongoDB Atlas Charts**. Sigue estos pasos para importar tu dashboard:

## 1. Crear el Dashboard en MongoDB Atlas
1. Inicia sesión en [MongoDB Atlas](https://cloud.mongodb.com/).
2. Ve a la sección **Charts** en el menú lateral izquierdo.
3. Crea un nuevo Dashboard y añade los gráficos basados en tus colecciones de `clientes` y `pagos`.

## 2. Obtener el código de inserción (Embed)
1. En tu dashboard de Charts, haz clic en el botón **Dashboards** (icono de tablero) y luego en los tres puntos `...` de tu dashboard específico.
2. Selecciona **Embed Dashboard**.
3. Activa la opción **Enable authenticated access** (recomendado para producción) o **Unauthenticated** para pruebas rápidas.
4. Copia la **Base URL** y el **Dashboard ID**.

## 3. Integración en el Código
En el archivo `app.js`, dentro de la función `renderDashboard`, puedes reemplazar el `chart-placeholder` con el siguiente código de IFrame:

```html
<iframe 
    style="background: #21313C; border: none; border-radius: 16px; box-shadow: 0 2px 10px 0 rgba(70, 76, 79, .2);" 
    width="100%" 
    height="480" 
    src="TU_URL_DE_STITCH_AQUI">
</iframe>
```

## 4. Uso en Móviles (PWA)
Esta herramienta es una **PWA (Progressive Web App)**, lo que significa que puedes instalarla en tu celular sin ir a la App Store.

### Cómo instalarla en tu celular:
1. **Publicar la app:** Debes subir estos archivos a un servidor (ver sección "Despliegue").
2. **Abrir en el móvil:** Entra a la URL de tu app desde Chrome (Android) o Safari (iPhone).
3. **Instalar:**
   - **Android:** Toca los tres puntos `...` y selecciona **"Instalar aplicación"** o **"Añadir a pantalla de inicio"**.
   - **iPhone:** Toca el botón de compartir (el cuadrado con la flecha hacia arriba) y selecciona **"Añadir a pantalla de inicio"**.

## 5. Despliegue (Para Sincronización Real)
Para que los datos se sincronicen entre tu laptop y tu celular en tiempo real, la app debe estar en internet.

**Opciones recomendadas:**
- **Netlify (Gratis y Fácil):** Arrastra la carpeta de este proyecto a [Netlify Drop](https://app.netlify.com/drop). Te dará una URL instantánea.
- **GitHub Pages:** Si usas Git, puedes publicarla directamente desde tu repositorio.

## 7. Sincronización Total con MongoDB Cloud
Dado que MongoDB Atlas requiere una conexión segura que no se puede hacer directamente desde el navegador de forma simple, hemos creado un **Servidor Puente (Bridge)** en Python.

### Cómo poner a funcionar la nube:
1.  **Inicia el servidor:** Abre una terminal y ejecuta:
    ```powershell
    python server.py
    ```
    *Deberías ver un mensaje: "Servidor Stitch Finance API corriendo en http://localhost:5000"*

2.  **Usa la App:** Ahora, cuando guardes un cliente o un pago en `index.html`, los datos viajarán así:
    `App Web` -> `Servidor Python (API)` -> `MongoDB Atlas (Nube)` -> `Stitch Charts`

3.  **Beneficio:** Ahora puedes registrar datos desde cualquier lugar y tus gráficos de Charts se actualizarán al instante.

### Requisitos:
- Librerías necesarias (ya instaladas): `pymongo`, `flask`, `flask-cors`.
- Mantener la terminal de `server.py` abierta mientras uses la aplicación.
