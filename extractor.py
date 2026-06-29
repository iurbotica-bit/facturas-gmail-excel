import imaplib
import email
from email.header import decode_header
import os
import re
import json
from google import genai
from google.genai import types
from typing import List, Dict, Any, Tuple

def connect_gmail(email_address: str, password: str) -> imaplib.IMAP4_SSL:
    """Se conecta a Gmail utilizando IMAP SSL."""
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(email_address, password)
        return mail
    except Exception as e:
        raise ConnectionError(f"Error de conexión a Gmail: {str(e)}")

def search_invoice_emails(mail: imaplib.IMAP4_SSL, unread_only: bool = True) -> List[str]:
    """Busca correos en Gmail que contengan facturas adjuntas usando el buscador de Gmail X-GM-RAW."""
    mail.select("inbox")
    
    # Construcción de la consulta de búsqueda de Gmail
    query = 'has:attachment (subject:factura OR factura OR subject:invoice OR invoice OR subject:recibo OR recibo)'
    if unread_only:
        query = f'is:unread {query}'
        
    status, response = mail.uid('search', 'X-GM-RAW', f'"{query}"')
    if status != 'OK':
        return []
    
    # Devuelve la lista de IDs únicos (UID) de los mensajes
    email_uids = response[0].split()
    return [uid.decode('utf-8') for uid in email_uids]

def get_attachments(mail: imaplib.IMAP4_SSL, uid: str) -> List[Tuple[str, bytes, str]]:
    """Descarga los adjuntos válidos (PDFs e imágenes) de un correo específico por su UID."""
    status, response = mail.uid('fetch', uid, '(RFC822)')
    if status != 'OK':
        return []
    
    raw_email = response[0][1]
    msg = email.message_from_bytes(raw_email)
    
    attachments = []
    
    for part in msg.walk():
        if part.get_content_maintype() == 'multipart':
            continue
        if part.get('Content-Disposition') is None:
            continue
            
        filename = part.get_filename()
        if filename:
            # Decodificar el nombre del archivo
            decode_result = decode_header(filename)[0]
            if isinstance(decode_result[0], bytes):
                try:
                    encoding = decode_result[1] or 'utf-8'
                    filename = decode_result[0].decode(encoding)
                except Exception:
                    filename = decode_result[0].decode('utf-8', errors='ignore')
            else:
                filename = decode_result[0]
                
            # Limpiar nombre
            filename = re.sub(r'[\r\n\t]', '', filename)
            
            # Filtro por tipo de archivo
            mime_type = part.get_content_type()
            is_pdf = mime_type == 'application/pdf' or filename.lower().endswith('.pdf')
            is_image = mime_type.startswith('image/') or filename.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))
            
            if is_pdf or is_image:
                payload = part.get_payload(decode=True)
                if payload:
                    # Deducir MIME type real basado en la extensión si es genérico
                    fn_lower = filename.lower()
                    if fn_lower.endswith('.pdf'):
                        actual_mime = 'application/pdf'
                    elif fn_lower.endswith(('.jpg', '.jpeg')):
                        actual_mime = 'image/jpeg'
                    elif fn_lower.endswith('.png'):
                        actual_mime = 'image/png'
                    elif fn_lower.endswith('.webp'):
                        actual_mime = 'image/webp'
                    else:
                        actual_mime = mime_type
                        
                    attachments.append((filename, payload, actual_mime))
                    
    return attachments

def extract_invoice_data(api_key: str, file_bytes: bytes, mime_type: str) -> Dict[str, Any]:
    """Usa la API de Gemini (SDK moderno google-genai) para extraer los datos de la factura como JSON estructurado."""
    client = genai.Client(api_key=api_key)
    
    prompt = """
    Analiza esta factura o recibo (puede ser un PDF o una imagen) y extrae los siguientes datos clave de facturación en formato JSON.
    Usa estrictamente la siguiente estructura JSON:
    {
      "fecha": "YYYY-MM-DD" (si no se encuentra, usa null. Intenta interpretar formatos españoles como DD/MM/AAAA o de texto),
      "emisor": "Nombre o Razón Social del emisor/proveedor" (cadena de texto, si no se encuentra usa null),
      "cif_emisor": "NIF/CIF del emisor" (cadena de texto, ej. B12345678, si no se encuentra usa null),
      "numero_factura": "Número o referencia de la factura" (cadena de texto, si no se encuentra usa null),
      "base_imponible": 0.00 (Número decimal representing la base imponible total sin impuestos, usa null si no se puede deducir),
      "iva_porcentaje": 0.00 (Porcentaje de IVA dominante, por ejemplo 21.0 o 10.0, usa null si no aplica),
      "iva_importe": 0.00 (Importe total del IVA en euros, usa null si no aplica o no se encuentra),
      "total": 0.00 (Importe total a pagar, número decimal. Este campo es obligatorio si existe en el documento)
    }
    Devuelve ÚNICAMENTE el código JSON limpio, sin bloques markdown de código ```json o explicaciones adicionales.
    """
    
    # Estructura del contenido para el nuevo SDK google-genai
    contents = [
        types.Part.from_bytes(
            data=file_bytes,
            mime_type=mime_type
        ),
        prompt
    ]
    
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=contents,
        config={
            "response_mime_type": "application/json",
            "temperature": 0.1
        }
    )
    
    try:
        data = json.loads(response.text.strip())
        return data
    except Exception as e:
        raise ValueError(f"Error al decodificar la respuesta JSON de Gemini: {str(e)}\nRespuesta obtenida: {response.text}")

def mark_email_as_read(mail: imaplib.IMAP4_SSL, uid: str):
    """Marca un correo como leído para evitar procesarlo de nuevo en la siguiente ejecución."""
    mail.uid('store', uid, '+FLAGS', '\\Seen')
