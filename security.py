import os
import json
import binascii
import sys

# Detectar el sistema operativo
IS_WINDOWS = sys.platform.startswith('win')

# Variables globales para DPAPI en Windows
crypt32 = None
kernel32 = None

if IS_WINDOWS:
    try:
        import ctypes
        from ctypes import wintypes
        
        class DATA_BLOB(ctypes.Structure):
            _fields_ = [
                ("cbData", wintypes.DWORD),
                ("pbData", ctypes.POINTER(ctypes.c_ubyte))
            ]
            
        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
    except Exception:
        IS_WINDOWS = False

def encrypt_string(plain_text: str) -> str:
    """Cifra una cadena usando DPAPI en Windows, o devuelve texto plano en otros SO."""
    if not plain_text:
        return ""
    
    if IS_WINDOWS and crypt32 and kernel32:
        try:
            plain_bytes = plain_text.encode('utf-8')
            data_in = DATA_BLOB(
                len(plain_bytes),
                ctypes.cast(ctypes.create_string_buffer(plain_bytes), ctypes.POINTER(ctypes.c_ubyte))
            )
            data_out = DATA_BLOB()
            
            # CRYPTPROTECT_UI_FORBIDDEN = 1
            success = crypt32.CryptProtectData(
                ctypes.byref(data_in), None, None, None, None, 1, ctypes.byref(data_out)
            )
            
            if success:
                encrypted_bytes = ctypes.string_at(data_out.pbData, data_out.cbData)
                kernel32.LocalFree(data_out.pbData)
                return binascii.hexlify(encrypted_bytes).decode('utf-8')
        except Exception:
            pass
            
    # Fallback para no-Windows (Streamlit Cloud, etc.) o error
    # Añadimos un prefijo simple para saber que está en texto plano
    return f"plain:{plain_text}"

def decrypt_string(hex_text: str) -> str:
    """Descifra una cadena usando DPAPI de Windows, o la devuelve tal cual si es texto plano."""
    if not hex_text:
        return ""
        
    if hex_text.startswith("plain:"):
        return hex_text[6:]
        
    if IS_WINDOWS and crypt32 and kernel32:
        try:
            encrypted_bytes = binascii.unhexlify(hex_text.encode('utf-8'))
            data_in = DATA_BLOB(
                len(encrypted_bytes),
                ctypes.cast(ctypes.create_string_buffer(encrypted_bytes), ctypes.POINTER(ctypes.c_ubyte))
            )
            data_out = DATA_BLOB()
            
            success = crypt32.CryptUnprotectData(
                ctypes.byref(data_in), None, None, None, None, 1, ctypes.byref(data_out)
            )
            
            if success:
                decrypted_bytes = ctypes.string_at(data_out.pbData, data_out.cbData)
                kernel32.LocalFree(data_out.pbData)
                return decrypted_bytes.decode('utf-8')
        except Exception:
            pass
            
    # Si no es Windows o falló el descifrado (ej. se clonó en otra máquina),
    # intentamos devolverlo por si era texto plano sin prefijo
    return hex_text

# Ruta por defecto de configuración
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

def load_config() -> dict:
    """Carga la configuración. Prioriza Streamlit Secrets en producción Cloud, luego el archivo local."""
    config = {}
    
    # 1. Intentar cargar desde Streamlit Secrets (perfecto para Streamlit Community Cloud)
    try:
        import streamlit as st
        # Buscamos en st.secrets si están declarados
        if "gmail_email" in st.secrets:
            config["gmail_email"] = st.secrets["gmail_email"]
        if "gmail_password" in st.secrets:
            config["gmail_password"] = st.secrets["gmail_password"]
        if "gemini_api_key" in st.secrets:
            config["gemini_api_key"] = st.secrets["gemini_api_key"]
        if "excel_path" in st.secrets:
            config["excel_path"] = st.secrets["excel_path"]
            
        # Si logramos cargar las credenciales críticas, las devolvemos
        if "gmail_email" in config and "gmail_password" in config and "gemini_api_key" in config:
            return config
    except Exception:
        pass
        
    # 2. Cargar del archivo local si no estamos en la nube o faltan secretos
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                raw_config = json.load(f)
        except Exception:
            raw_config = {}
            
        for key in ["gmail_email", "gmail_password", "gemini_api_key"]:
            if key in raw_config:
                try:
                    # Si ya viene de st.secrets, no sobreescribir con datos locales vacíos
                    if key not in config or not config[key]:
                        config[key] = decrypt_string(raw_config[key])
                except Exception:
                    config[key] = ""
            elif key not in config:
                config[key] = ""
                
        if "excel_path" not in config or not config["excel_path"]:
            config["excel_path"] = raw_config.get("excel_path", "")
            
    # Rellenar valores vacíos por defecto si no existen
    for key in ["gmail_email", "gmail_password", "gemini_api_key", "excel_path"]:
        if key not in config:
            config[key] = ""
            
    return config

def save_config(gmail_email: str, gmail_password: str, gemini_api_key: str, excel_path: str):
    """Cifra y guarda la configuración localmente."""
    config_to_save = {
        "gmail_email": encrypt_string(gmail_email),
        "gmail_password": encrypt_string(gmail_password),
        "gemini_api_key": encrypt_string(gemini_api_key),
        "excel_path": excel_path
    }
    
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config_to_save, f, indent=4)
