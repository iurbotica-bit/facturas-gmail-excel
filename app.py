import streamlit as st
import os
import pandas as pd
from datetime import datetime
import traceback

import security
import extractor
import excel_handler

# Configuración de página
st.set_page_config(
    page_title="Control de Gastos Trimestrales - Automático",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilo personalizado premium (CSS)
st.markdown("""
    <style>
    .main {
        background-color: #0f172a;
        color: #f8fafc;
    }
    .stButton>button {
        background-color: #3b82f6;
        color: white;
        border-radius: 8px;
        padding: 0.5rem 1.5rem;
        font-weight: 600;
        border: none;
        transition: all 0.3s;
    }
    .stButton>button:hover {
        background-color: #2563eb;
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
    }
    .sidebar .sidebar-content {
        background-color: #1e293b;
    }
    .card {
        background-color: #1e293b;
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #334155;
        margin-bottom: 20px;
    }
    .header-title {
        font-size: 2.2rem;
        font-weight: 700;
        background: linear-gradient(90deg, #3b82f6, #60a5fa);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 10px;
    }
    </style>
""", unsafe_allow_html=True)

# Inicializar estados de sesión
if 'logs' not in st.session_state:
    st.session_state.logs = []
if 'running' not in st.session_state:
    st.session_state.running = False

def add_log(message: str, type: str = "info"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    st.session_state.logs.append(f"[{timestamp}] [{type.upper()}] {message}")

# Carga inicial de configuración
config = security.load_config()

# Sidebar: Configuración de Credenciales
st.sidebar.markdown("<h2 style='color:#60a5fa;'>⚙️ Configuración</h2>", unsafe_allow_html=True)
st.sidebar.write("Introduce tus datos. Se guardarán encriptados de forma segura localmente.")

# Formulario de configuración
with st.sidebar.form("config_form"):
    email_input = st.text_input("Correo Gmail", value=config.get("gmail_email", ""))
    password_input = st.text_input(
        "Contraseña de Aplicación (16 caracteres)", 
        value=config.get("gmail_password", ""), 
        type="password",
        help="Obtenla en tu cuenta de Google -> Seguridad -> Contraseñas de aplicación."
    )
    api_key_input = st.text_input(
        "API Key de Gemini", 
        value=config.get("gemini_api_key", ""), 
        type="password",
        help="Obtenla gratis en Google AI Studio."
    )
    
    # Ruta del archivo Excel por defecto en la carpeta del proyecto
    default_excel = config.get("excel_path", "")
    if not default_excel:
        default_excel = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Gastos_Facturas.xlsx")
        
    excel_path_input = st.text_input("Ruta de la Plantilla Excel", value=default_excel)
    
    submitted = st.form_submit_button("💾 Guardar Configuración")
    
    if submitted:
        try:
            security.save_config(email_input, password_input, api_key_input, excel_path_input)
            st.sidebar.success("¡Configuración guardada y cifrada correctamente!")
            # Recargar configuración
            config = security.load_config()
        except Exception as e:
            st.sidebar.error(f"Error al guardar la configuración: {str(e)}")

# Estado de la configuración actual
st.sidebar.markdown("---")
st.sidebar.markdown("### 🔍 Estado del Sistema")
if config.get("gmail_email") and config.get("gmail_password"):
    st.sidebar.markdown("🟢 Gmail Configurado")
else:
    st.sidebar.markdown("🔴 Gmail No Configurado")

if config.get("gemini_api_key"):
    st.sidebar.markdown("🟢 Gemini API Habilitada")
else:
    st.sidebar.markdown("🔴 Gemini API Pendiente")

if os.path.exists(config.get("excel_path", "")):
    st.sidebar.markdown("🟢 Archivo Excel Detectado")
else:
    st.sidebar.markdown("🟡 Archivo Excel se creará al sincronizar")

# Cuerpo principal de la aplicación
st.markdown("<div class='header-title'>📊 Gestión de Gastos Automática</div>", unsafe_allow_html=True)
st.write("Esta herramienta escanea tu correo Gmail buscando facturas adjuntas en tus correos no leídos, extrae los importes con IA (Gemini) y los añade a tu Excel trimestral.")

# Botones de Acción
col1, col2 = st.columns([1, 3])
with col1:
    btn_sincronizar = st.button("🚀 Sincronizar Gmail", disabled=st.session_state.running)
with col2:
    if st.button("🧹 Limpiar Consola"):
        st.session_state.logs = []
        st.rerun()

# Proceso de Sincronización
if btn_sincronizar:
    # Validaciones previas
    if not config.get("gmail_email") or not config.get("gmail_password") or not config.get("gemini_api_key"):
        st.error("Por favor, introduce y guarda todas tus credenciales en el menú lateral izquierdo antes de iniciar la sincronización.")
    else:
        st.session_state.running = True
        st.session_state.logs = [] # Limpiar logs anteriores
        add_log("Iniciando proceso de escaneo y extracción...", "info")
        
        # Contenedor de progreso dinámico
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            # Conexión a Gmail
            status_text.text("Conectando con Gmail...")
            progress_bar.progress(10)
            mail = extractor.connect_gmail(config["gmail_email"], config["gmail_password"])
            add_log("Conectado con éxito a Gmail.", "success")
            
            # Buscar correos con facturas
            status_text.text("Buscando correos con facturas...")
            progress_bar.progress(30)
            uids = extractor.search_invoice_emails(mail, unread_only=True)
            
            if not uids:
                add_log("No se encontraron correos no leídos con facturas adjuntas.", "info")
                progress_bar.progress(100)
                status_text.text("Proceso finalizado. Sin facturas nuevas.")
            else:
                add_log(f"Se detectaron {len(uids)} correo(s) para procesar.", "info")
                total_emails = len(uids)
                processed_count = 0
                
                for idx, uid in enumerate(uids):
                    status_text.text(f"Procesando correo {idx+1} de {total_emails}...")
                    # Calcular progreso relativo entre 30% y 90%
                    rel_prog = int(30 + (idx / total_emails) * 60)
                    progress_bar.progress(rel_prog)
                    
                    attachments = extractor.get_attachments(mail, uid)
                    if not attachments:
                        add_log(f"Correo UID {uid}: No contenía adjuntos compatibles (PDF/Imagen).", "warning")
                        # Marcar correo como leído de todos modos para no atascarlo
                        extractor.mark_email_as_read(mail, uid)
                        continue
                    
                    for filename, file_bytes, mime_type in attachments:
                        add_log(f"Extrayendo datos de: '{filename}'...", "info")
                        try:
                            # Procesar con Gemini API
                            extracted_data = extractor.extract_invoice_data(
                                config["gemini_api_key"], 
                                file_bytes, 
                                mime_type
                            )
                            
                            # Guardar en Excel
                            excel_handler.save_to_excel(config["excel_path"], extracted_data, filename)
                            
                            emisor = extracted_data.get('emisor', 'Desconocido')
                            total = extracted_data.get('total', 0.0)
                            add_log(f"Factura de '{emisor}' por un total de {total}€ guardada correctamente.", "success")
                            
                        except Exception as ex:
                            add_log(f"Error procesando el archivo '{filename}': {str(ex)}", "error")
                            
                    # Marcar el correo como leído tras procesar sus adjuntos
                    extractor.mark_email_as_read(mail, uid)
                    processed_count += 1
                
                progress_bar.progress(100)
                status_text.text("Sincronización completada con éxito.")
                add_log(f"Sincronización finalizada. Procesados {processed_count} correo(s).", "success")
                
            mail.logout()
            
        except Exception as e:
            add_log(f"Error crítico en el proceso: {str(e)}", "error")
            st.error("Ocurrió un error inesperado durante la ejecución. Revisa la consola de logs para más detalles.")
            st.code(traceback.format_exc())
            
        st.session_state.running = False

# Layout Principal: Consola de Logs e Informes
col_left, col_right = st.columns([1, 1])

with col_left:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.subheader("📟 Registro de Actividad")
    if st.session_state.logs:
        # Mostramos los logs del revés para ver los últimos arriba
        log_text = "\n".join(reversed(st.session_state.logs))
        st.text_area("Logs de ejecución", value=log_text, height=350, disabled=True)
    else:
        st.info("La consola está vacía. Haz clic en 'Sincronizar Gmail' para iniciar el proceso.")
    st.markdown("</div>", unsafe_allow_html=True)

with col_right:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.subheader("📂 Vista Previa del Excel")
    
    excel_file = config.get("excel_path", "")
    if os.path.exists(excel_file):
        try:
            # Leer las pestañas del Excel para mostrarlas en un selector
            xl = pd.ExcelFile(excel_file)
            sheets = xl.sheet_names
            if sheets:
                selected_sheet = st.selectbox("Seleccionar Trimestre:", sheets)
                df = pd.read_excel(excel_file, sheet_name=selected_sheet)
                st.dataframe(df, use_container_width=True)
                
                # Resumen de gastos en la pestaña seleccionada
                if "Total (€)" in df.columns:
                    # Intentar convertir a numérico por seguridad
                    totals = pd.to_numeric(df["Total (€)"], errors='coerce')
                    total_gastado = totals.sum()
                    st.metric(label=f"Total Gastado en {selected_sheet}", value=f"{total_gastado:,.2f} €")
                
                # Botón para descargar el archivo Excel
                with open(excel_file, "rb") as f:
                    st.download_button(
                        label="📥 Descargar Excel de Gastos",
                        data=f.read(),
                        file_name=os.path.basename(excel_file),
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
            else:
                st.warning("El archivo Excel no contiene ninguna pestaña de datos.")
        except Exception as e:
            st.error(f"No se pudo cargar la vista previa del Excel: {str(e)}")
    else:
        st.info("Aún no se ha creado el archivo Excel de salida. Se creará automáticamente al procesar la primera factura.")
    st.markdown("</div>", unsafe_allow_html=True)
