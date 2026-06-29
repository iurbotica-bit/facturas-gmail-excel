# 📊 Gestor de Gastos y Facturas Automático (Gmail a Excel)

Esta aplicación en Python/Streamlit se conecta de forma segura a tu bandeja de Gmail mediante IMAP, localiza correos no leídos con facturas o recibos adjuntos (PDFs e imágenes), extrae su información utilizando Inteligencia Artificial (**Gemini 2.5 Flash**) y la consolida automáticamente en una plantilla Excel clasificada por trimestres (1T, 2T, 3T, 4T).

El archivo Excel de gastos tiene un estilo estético profesional auto-ajustado y permite ser descargado directamente desde la web.

---

## 🛠️ Ejecución en Local

### 1. Requisitos previos
- Tener Python 3.9 o superior instalado.
- Generar una **Contraseña de aplicación** en tu cuenta de Google (Seguridad -> Verificación en 2 pasos -> Contraseñas de aplicación).
- Obtener una **API Key de Gemini** gratuita en [Google AI Studio](https://aistudio.google.com/).

### 2. Configurar entorno virtual e instalar dependencias
Abre tu consola o PowerShell en el directorio de la aplicación y ejecuta:

```bash
# Crear entorno virtual
python -m venv .venv

# Instalar dependencias
.venv/Scripts/pip.exe install -r requirements.txt
```

### 3. Ejecutar la aplicación
Lanza Streamlit desde la terminal:
```bash
.venv/Scripts/streamlit.exe run app.py
```

Introduce tus datos en el menú lateral y haz clic en **Guardar Configuración**. Los datos se guardarán localmente cifrados mediante DPAPI de Windows (exclusivos para tu usuario de Windows en este equipo).

---

## ☁️ Despliegue en Streamlit Community Cloud

Esta aplicación está completamente preparada para ejecutarse en la nube de Streamlit. Sigue estos pasos para desplegarla:

1. Inicia sesión en [Streamlit Community Cloud](https://share.streamlit.io/).
2. Haz clic en **"New app"** y selecciona este repositorio de GitHub (`iurbotica-bit/facturas-gmail-excel`), rama `main` y archivo principal `app.py`.
3. **CONFIGURACIÓN DE SECRETOS (CRÍTICO):** Antes de desplegar, expande la sección **Advanced settings...** y en el apartado **Secrets (TOML)** introduce tus credenciales de esta forma para no tener que escribirlas en la interfaz pública:

```toml
gmail_email = "tu-correo@gmail.com"
gmail_password = "tu-contrasenya-de-aplicacion-de-16-letras"
gemini_api_key = "tu-api-key-de-gemini"
excel_path = "Gastos_Facturas.xlsx"
```

4. Haz clic en **Deploy!** y tu aplicación estará lista y disponible en la web.
