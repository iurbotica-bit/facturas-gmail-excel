import streamlit as st
import os
import pandas as pd
from datetime import datetime
import traceback
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

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

# Función para enviar fotos al correo propio por SMTP
def send_image_to_gmail(email_address: str, password: str, image_bytes: bytes, filename: str) -> bool:
    try:
        # Configurar mensaje MIME
        msg = MIMEMultipart()
        msg['From'] = email_address
        msg['To'] = email_address
        msg['Subject'] = f"Factura: Foto Capturada {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        body = "Adjunto enviamos la foto de la factura capturada desde la aplicación web."
        msg.attach(MIMEText(body, 'plain'))
        
        # Adjunto
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(image_bytes)
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f"attachment; filename={filename}")
        msg.attach(part)
        
        # Conexión y envío por SMTP SSL (Gmail)
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(email_address, password)
        server.sendmail(email_address, email_address, msg.as_string())
        server.close()
        return True
    except Exception as e:
        raise RuntimeError(f"Error al enviar correo por SMTP: {str(e)}")

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
st.write("Sincroniza tus facturas desde Gmail a Excel o sube fotos instantáneas de tus tickets utilizando la cámara.")

# Crear las pestañas para organizar la interfaz de forma premium
tab_dashboard, tab_camera = st.tabs(["📊 Sincronización e Historial", "📷 Hacer Foto a Factura"])

# Pestaña 1: Sincronización e Historial (Excel editable)
with tab_dashboard:
    col_act, col_prev = st.columns([1, 1])
    
    with col_act:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader("🚀 Acciones")
        
        col_btn1, col_btn2 = st.columns([1, 1])
        with col_btn1:
            btn_sincronizar = st.button("🔌 Sincronizar Gmail", disabled=st.session_state.running, use_container_width=True)
        with col_btn2:
            if st.button("🧹 Limpiar Consola", use_container_width=True):
                st.session_state.logs = []
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        
        # Procesar Sincronización
        if btn_sincronizar:
            if not config.get("gmail_email") or not config.get("gmail_password") or not config.get("gemini_api_key"):
                st.error("Introduce y guarda todas tus credenciales en el menú lateral izquierdo antes de iniciar.")
            else:
                st.session_state.running = True
                st.session_state.logs = []
                add_log("Iniciando proceso de escaneo y extracción...", "info")
                
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                try:
                    status_text.text("Conectando con Gmail...")
                    progress_bar.progress(10)
                    mail = extractor.connect_gmail(config["gmail_email"], config["gmail_password"])
                    add_log("Conectado con éxito a Gmail.", "success")
                    
                    status_text.text("Buscando correos con facturas...")
                    progress_bar.progress(30)
                    uids = extractor.search_invoice_emails(mail, unread_only=True)
                    
                    if not uids:
                        add_log("No se encontraron correos nuevos con facturas adjuntas.", "info")
                        progress_bar.progress(100)
                        status_text.text("Proceso finalizado. Sin facturas nuevas.")
                    else:
                        add_log(f"Se detectaron {len(uids)} correo(s) para procesar.", "info")
                        total_emails = len(uids)
                        processed_count = 0
                        
                        for idx, uid in enumerate(uids):
                            status_text.text(f"Procesando correo {idx+1} de {total_emails}...")
                            rel_prog = int(30 + (idx / total_emails) * 60)
                            progress_bar.progress(rel_prog)
                            
                            attachments = extractor.get_attachments(mail, uid)
                            if not attachments:
                                add_log(f"Correo UID {uid}: No contenía adjuntos compatibles (PDF/Imagen).", "warning")
                                extractor.mark_email_as_read(mail, uid)
                                continue
                            
                            for filename, file_bytes, mime_type in attachments:
                                add_log(f"Extrayendo datos de: '{filename}'...", "info")
                                try:
                                    extracted_data = extractor.extract_invoice_data(
                                        config["gemini_api_key"], 
                                        file_bytes, 
                                        mime_type
                                    )
                                    
                                    excel_handler.save_to_excel(config["excel_path"], extracted_data, filename)
                                    
                                    emisor = extracted_data.get('emisor', 'Desconocido')
                                    total = extracted_data.get('total', 0.0)
                                    add_log(f"Factura de '{emisor}' por un total de {total}€ guardada.", "success")
                                    
                                except Exception as ex:
                                    add_log(f"Error procesando '{filename}': {str(ex)}", "error")
                                    
                            extractor.mark_email_as_read(mail, uid)
                            processed_count += 1
                        
                        progress_bar.progress(100)
                        status_text.text("Sincronización completada.")
                        add_log(f"Sincronización finalizada. Procesados {processed_count} correos.", "success")
                        
                    mail.logout()
                    
                except Exception as e:
                    add_log(f"Error crítico en el proceso: {str(e)}", "error")
                    st.error("Ocurrió un error inesperado durante la ejecución. Revisa los logs.")
                    st.code(traceback.format_exc())
                    
                st.session_state.running = False
                st.rerun()
                
        # Consola de logs
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader("📟 Registro de Actividad")
        if st.session_state.logs:
            log_text = "\n".join(reversed(st.session_state.logs))
            st.text_area("Logs de ejecución", value=log_text, height=300, disabled=True)
        else:
            st.info("Consola inactiva. Haz clic en 'Sincronizar Gmail' para escanear facturas.")
        st.markdown("</div>", unsafe_allow_html=True)

# Pestaña 2: Visualización y Edición
    with col_prev:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader("📂 Vista Previa y Edición de la Hoja de Gastos")
        
        excel_file = config.get("excel_path", "")
        if os.path.exists(excel_file):
            try:
                xl = pd.ExcelFile(excel_file)
                sheets = xl.sheet_names
                if sheets:
                    selected_sheet = st.selectbox("Seleccionar Trimestre:", sheets)
                    df = pd.read_excel(excel_file, sheet_name=selected_sheet)
                    
                    st.warning("⚠️ Puedes hacer doble clic en cualquier celda para corregir los datos directamente. Al terminar, recuerda guardar los cambios.")
                    
                    # EDITOR DE DATOS INTERACTIVO
                    edited_df = st.data_editor(
                        df, 
                        use_container_width=True, 
                        num_rows="dynamic",
                        key="excel_editor"
                    )
                    
                    # Comprobar si el usuario ha realizado modificaciones
                    if not edited_df.equals(df):
                        if st.button("💾 Guardar Cambios en el Excel", use_container_width=True):
                            try:
                                with pd.ExcelWriter(excel_file, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                                    edited_df.to_excel(writer, sheet_name=selected_sheet, index=False)
                                
                                # Re-aplicar los estilos estéticos premium
                                excel_handler.apply_excel_styling(excel_file)
                                st.success("¡Cambios guardados y formateados en el Excel con éxito!")
                                st.rerun()
                            except Exception as ex_save:
                                st.error(f"Error al guardar los cambios: {str(ex_save)}")
                    
                    # Métricas de Resumen
                    if "Total (€)" in df.columns:
                        totals = pd.to_numeric(df["Total (€)"], errors='coerce')
                        total_gastado = totals.sum()
                        st.metric(label=f"Total Gastado acumulado ({selected_sheet})", value=f"{total_gastado:,.2f} €")
                        
                    # Botón para descargar
                    with open(excel_file, "rb") as f:
                        st.download_button(
                            label="📥 Descargar Excel de Gastos",
                            data=f.read(),
                            file_name=os.path.basename(excel_file),
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True
                        )
                else:
                    st.warning("El archivo Excel no tiene hojas válidas.")
            except Exception as e:
                st.error(f"No se pudo cargar la hoja de gastos: {str(e)}")
        else:
            st.info("El archivo Excel se generará automáticamente en cuanto proceses tu primera factura.")
        st.markdown("</div>", unsafe_allow_html=True)

# Pestaña 2: Captura por Cámara
with tab_camera:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.subheader("📸 Capturar Ticket / Factura con la Cámara")
    st.write("Usa la cámara de tu móvil o portátil para hacer una foto a una factura física. Esta se auto-enviará por correo para ser procesada al sincronizar.")
    
    # Campo de captura de cámara
    img_file = st.camera_input("Haz la foto a la factura asegurando buena iluminación y enfoque:")
    
    if img_file is not None:
        # Obtener los bytes de la imagen capturada
        bytes_data = img_file.getvalue()
        
        # Mostrar vista previa
        st.image(img_file, caption="Vista previa de la factura capturada", width=350)
        
        btn_enviar = st.button("✉️ Enviar factura a mi Gmail para procesar", use_container_width=True)
        
        if btn_enviar:
            if not config.get("gmail_email") or not config.get("gmail_password"):
                st.error("Introduce y guarda tu correo y contraseña de aplicación en el menú lateral izquierdo para poder realizar el envío.")
            else:
                with st.spinner("Enviando foto por correo electrónico..."):
                    try:
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename = f"factura_foto_{timestamp}.jpg"
                        
                        send_image_to_gmail(
                            config["gmail_email"],
                            config["gmail_password"],
                            bytes_data,
                            filename
                        )
                        st.success(f"¡Factura enviada con éxito! Se ha mandado un correo a {config['gmail_email']} con el adjunto. Ahora puedes volver a la pestaña 'Sincronización' y pulsar en 'Sincronizar Gmail' para procesarla.")
                    except Exception as e_send:
                        st.error(f"Fallo al enviar el correo: {str(e_send)}")
    st.markdown("</div>", unsafe_allow_html=True)
