import os
import subprocess
import logging
from PIL import Image
from pypdf import PdfReader
from logging.handlers import TimedRotatingFileHandler
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ConversationHandler, ContextTypes

# --- CONFIGURACIÓN DE LOGS (Cero emojis aquí) ---
rotador = TimedRotatingFileHandler(
    filename='inprint.log',
    when='D',
    interval=30,
    backupCount=6, 
    encoding='utf-8'
)
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s', datefmt='%Y-%m-%d %H:%M:%S', handlers=[rotador])
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)

# --- CARGAR CONFIGURACIÓN ---
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")
USUARIOS_PERMITIDOS = [int(uid.strip()) for uid in os.getenv("USUARIOS_PERMITIDOS").split(",")]
ADMIN_ID = int(os.getenv("ADMIN_ID"))
PRINTER_IP = os.getenv("PRINTER_IP", "192.168.1.80")

COLOR, DUPLEX, PAGINAS, COPIAS, REINTENTO = range(5)

# --- COMANDOS Y MENSAJES GLOBALES (Con Emojis) ---
async def comando_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mensaje = (
        "👋 ¡Hola! Soy tu asistente automatizado de impresión 🖨️✨\n\n"
        "📄 Para empezar, simplemente envíame un documento (PDF, Word, Excel) o una 🖼️ imagen.\n"
        "🤖 Yo me encargaré de guiarte paso a paso y mandar tu trabajo directo a la máquina. ¡Facilito!"
    )
    await update.message.reply_text(mensaje)

async def mensaje_desconocido(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mensaje = (
        "😅 ¡Ups! No sé qué hacer con mensajes de texto normales.\n\n"
        "📂 Por favor, envíame directamente el archivo o la foto que necesitas imprimir y yo me encargo del resto 🚀"
    )
    await update.message.reply_text(mensaje)

# --- FUNCIÓN DE CANCELACIÓN Y LIMPIEZA ---
async def cancelar_operacion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        
    usuario = context.user_data.get('usuario', 'Desconocido')
    archivo_log = context.user_data.get('nombre_archivo', 'Desconocido')
    
    logging.info(f"CANCELADO | User: {usuario} | Doc: {archivo_log}")
    
    if query:
        await query.edit_message_text("❌ Operación cancelada. No se imprimió nada.")
    else:
        await update.message.reply_text("❌ Operación cancelada. No se imprimió nada.")
        
    ruta = context.user_data.get('ruta')
    ruta_original = context.user_data.get('ruta_original')
    if ruta and os.path.exists(ruta):
        os.remove(ruta)
    if ruta_original and os.path.exists(ruta_original):
        os.remove(ruta_original)
        
    return ConversationHandler.END

# --- LÓGICA PRINCIPAL ---
async def recibir_documento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_name = update.message.from_user.first_name
    
    if user_id not in USUARIOS_PERMITIDOS:
        logging.warning(f"INTENTO NO AUTORIZADO | ID: {user_id} | Nombre: {user_name}")
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"⚠️ ALERTA DE SEGURIDAD:\nAlguien no autorizado intentó usar el bot.\nNombre: {user_name}\nID: {user_id}")
        await update.message.reply_text("⛔ Acceso denegado.")
        return ConversationHandler.END

    if update.message.document:
        file_id = update.message.document.file_id
        nombre_original = update.message.document.file_name
    elif update.message.photo:
        foto = update.message.photo[-1]
        file_id = foto.file_id
        nombre_original = f"imagen_{foto.file_unique_id}.jpg"
    else:
        return ConversationHandler.END

    ruta_original = f"./{nombre_original}"
    context.user_data['usuario_id'] = user_id
    context.user_data['usuario'] = user_name
    context.user_data['nombre_archivo'] = nombre_original
    
    msg = await update.message.reply_text("📥 Descargando archivo...")
    
    file = await context.bot.get_file(file_id)
    await file.download_to_drive(ruta_original)
    
    ext = os.path.splitext(nombre_original)[1].lower()
    saltar_paginas = False 
    
    if ext in ['.docx', '.doc', '.xlsx', '.xls', '.pptx', '.ppt']:
        await msg.edit_text("🔄 Archivo de Office detectado. Convirtiendo a PDF...")
        try:
            subprocess.run(["libreoffice", "--headless", "--convert-to", "pdf", ruta_original, "--outdir", "./"], check=True, stderr=subprocess.DEVNULL)
            ruta_pdf = f"./{os.path.splitext(nombre_original)[0]}.pdf"
            context.user_data['ruta'] = ruta_pdf
            context.user_data['ruta_original'] = ruta_original 
        except Exception as e:
            logging.error(f"ERROR CONVERSIÓN OFFICE | Usuario: {user_name} | Archivo: {nombre_original} | Detalle: {e}")
            await context.bot.send_message(chat_id=ADMIN_ID, text=f"🚨 ERROR AL CONVERTIR OFFICE:\nUsuario: {user_name}\nArchivo: {nombre_original}\nFallo: {e}")
            await msg.edit_text("❌ Error al convertir el archivo.")
            return ConversationHandler.END
            
    elif ext in ['.jpg', '.jpeg', '.png', '.webp']:
        saltar_paginas = True 
        await msg.edit_text("🖼️ Imagen detectada. Ajustando formato para la impresora...")
        try:
            imagen = Image.open(ruta_original)
            imagen_rgb = imagen.convert('RGB')
            ruta_pdf = f"./{os.path.splitext(nombre_original)[0]}.pdf"
            imagen_rgb.save(ruta_pdf)
            context.user_data['ruta'] = ruta_pdf
            context.user_data['ruta_original'] = ruta_original
        except Exception as e:
            logging.error(f"ERROR CONVERSIÓN IMAGEN | Usuario: {user_name} | Archivo: {nombre_original} | Detalle: {e}")
            await msg.edit_text("❌ Error al procesar la imagen.")
            return ConversationHandler.END
    else:
        context.user_data['ruta'] = ruta_original
        context.user_data['ruta_original'] = None

    if not saltar_paginas:
        try:
            reader = PdfReader(context.user_data['ruta'])
            if len(reader.pages) <= 1:
                saltar_paginas = True 
        except Exception:
            pass 

    context.user_data['saltar_paginas'] = saltar_paginas

    teclado = [
        [InlineKeyboardButton("⚫ Blanco y Negro", callback_data='Gray')],
        [InlineKeyboardButton("🔴 Color", callback_data='RGB')],
        [InlineKeyboardButton("❌ Cancelar", callback_data='cancelar')]
    ]
    await msg.edit_text("📄 Documento listo.\n\n🎨 ¿A color o blanco y negro?", reply_markup=InlineKeyboardMarkup(teclado))
    return COLOR

async def preguntar_duplex(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['color'] = query.data 

    teclado = [
        [InlineKeyboardButton("📄 Una sola cara", callback_data='None')],
        [InlineKeyboardButton("📖 Doble cara", callback_data='DuplexNoTumble')],
        [InlineKeyboardButton("❌ Cancelar", callback_data='cancelar')]
    ]
    await query.edit_message_text(text="🖨️ ¿Impresión normal o doble cara?", reply_markup=InlineKeyboardMarkup(teclado))
    return DUPLEX

async def preguntar_paginas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['duplex'] = query.data

    if context.user_data.get('saltar_paginas'):
        context.user_data['paginas'] = 'all'
        
        teclado = [
            [InlineKeyboardButton("1", callback_data='1'), InlineKeyboardButton("2", callback_data='2')],
            [InlineKeyboardButton("3", callback_data='3'), InlineKeyboardButton("4", callback_data='4')],
            [InlineKeyboardButton("5", callback_data='5'), InlineKeyboardButton("10", callback_data='10')],
            [InlineKeyboardButton("❌ Cancelar", callback_data='cancelar')]
        ]
        await query.edit_message_text(text="📋 ¿Cuántas copias quieres?", reply_markup=InlineKeyboardMarkup(teclado))
        return COPIAS
    
    mensaje = "🔢 ¿Qué páginas quieres imprimir?\n\nEscribe tu respuesta en el chat. Ejemplos:\n• Todas\n• 1-5 (Intervalo de páginas)\n• 1,3,5 (Páginas salteadas)"
    teclado = [
        [InlineKeyboardButton("Todas las páginas", callback_data='all')],
        [InlineKeyboardButton("❌ Cancelar", callback_data='cancelar')]]
    await query.edit_message_text(text=mensaje, reply_markup=InlineKeyboardMarkup(teclado))
    return PAGINAS

async def recibir_paginas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip().lower()
    
    if texto == 'cancelar':
        return await cancelar_operacion(update, context)
    
    if texto == 'todas' or texto == 'todo':
        context.user_data['paginas'] = 'all'
    else:
        context.user_data['paginas'] = texto

    teclado = [
        [InlineKeyboardButton("1", callback_data='1'), InlineKeyboardButton("2", callback_data='2')],
        [InlineKeyboardButton("3", callback_data='3'), InlineKeyboardButton("4", callback_data='4')],
        [InlineKeyboardButton("5", callback_data='5'), InlineKeyboardButton("10", callback_data='10')],
        [InlineKeyboardButton("❌ Cancelar", callback_data='cancelar')]
    ]
    await update.message.reply_text("📋 ¿Cuántas copias quieres?", reply_markup=InlineKeyboardMarkup(teclado))
    return COPIAS

async def recibir_paginas_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['paginas'] = 'all'

    teclado = [
        [InlineKeyboardButton("1", callback_data='1'), InlineKeyboardButton("2", callback_data='2')],
        [InlineKeyboardButton("3", callback_data='3'), InlineKeyboardButton("4", callback_data='4')],
        [InlineKeyboardButton("5", callback_data='5'), InlineKeyboardButton("10", callback_data='10')],
        [InlineKeyboardButton("❌ Cancelar", callback_data='cancelar')]
    ]
    await query.edit_message_text("📋 ¿Cuántas copias quieres?", reply_markup=InlineKeyboardMarkup(teclado))
    return COPIAS

async def ejecutar_impresion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data != 'reintentar':
        context.user_data['copias'] = query.data
        
    copias = context.user_data['copias']
    ruta = context.user_data['ruta']
    ruta_original = context.user_data.get('ruta_original')
    color = context.user_data['color']
    duplex = context.user_data['duplex']
    paginas = context.user_data['paginas']
    usuario = context.user_data['usuario']
    usuario_id = context.user_data['usuario_id']
    archivo_log = context.user_data['nombre_archivo']

    await query.edit_message_text(text="⏳ Verificando conexión con la impresora...")

    ping = subprocess.run(["ping", "-c", "1", "-W", "2", PRINTER_IP], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    if ping.returncode != 0:
        logging.error(f"IMPRESORA APAGADA | User: {usuario} | Doc: {archivo_log}")
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"🚨 **IMPRESORA DESCONECTADA**\nUsuario: {usuario} intentó imprimir pero la IP {PRINTER_IP} no responde.\nCheca si está prendida.", parse_mode='Markdown')
        
        teclado = [
            [InlineKeyboardButton("🔄 Reintentar", callback_data='reintentar')],
            [InlineKeyboardButton("❌ Cancelar", callback_data='cancelar')]
        ]
        
        mensaje_error = (
            "🔌 ¡Aviso! No logro hacer conexión con la impresora.\n\n"
            "⚠️ Puede que esté apagada o desconectada del WiFi.\n"
            "👉 Enciéndela, espera unos 15 segundos a que conecte y presiona el botón de abajo para intentarlo de nuevo."
        )
        await query.edit_message_text(text=mensaje_error, reply_markup=InlineKeyboardMarkup(teclado))
        return REINTENTO

    comando = [
        "lp", "-d", "Brother", 
        "-n", copias, 
        "-o", f"ColorModel={color}", 
        "-o", f"Duplex={duplex}"
    ]
    if paginas != 'all':
        comando.extend(["-P", paginas])
    comando.append(ruta)

    try:
        subprocess.run(comando, check=True)
        logging.info(f"IMPRESIÓN | User: {usuario} | Doc: {archivo_log} | Copias: {copias} | Páginas: {paginas} | Color: {color} | Dúplex: {duplex}")
        
        if usuario_id != ADMIN_ID:
            tipo_color = "Color 🔴" if color == 'RGB' else "B/N ⚫"
            await context.bot.send_message(chat_id=ADMIN_ID, text=f"✅ **VENTA EXITOSA**\n{usuario} imprimió:\n📄 `{archivo_log}`\n🖨️ {copias} copias a {tipo_color}", parse_mode='Markdown')

        await query.message.reply_text("✅ ¡Listo! Documento enviado a la impresora.")
        
        if os.path.exists(ruta):
            os.remove(ruta)
        if ruta_original and os.path.exists(ruta_original):
            os.remove(ruta_original)
            
        return ConversationHandler.END
        
    except subprocess.CalledProcessError as e:
        logging.error(f"ERROR CUPS | User: {usuario} | Doc: {archivo_log} | Fallo: {e}")
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"🚨 **ERROR DEL SISTEMA**\nUsuario: {usuario}\nFallo interno de CUPS.\nDetalle: `{e}`", parse_mode='Markdown')
        
        teclado = [
            [InlineKeyboardButton("🔄 Reintentar", callback_data='reintentar')],
            [InlineKeyboardButton("❌ Cancelar", callback_data='cancelar')]
        ]
        await query.edit_message_text("❌ Ocurrió un error interno al mandar el documento.\n\n¿Deseas intentarlo de nuevo?", reply_markup=InlineKeyboardMarkup(teclado))
        return REINTENTO

def main():
    app = Application.builder().token(TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Document.ALL | filters.PHOTO, recibir_documento)],
        states={
            COLOR: [
                CallbackQueryHandler(cancelar_operacion, pattern='^cancelar$'),
                CallbackQueryHandler(preguntar_duplex)
            ],
            DUPLEX: [
                CallbackQueryHandler(cancelar_operacion, pattern='^cancelar$'),
                CallbackQueryHandler(preguntar_paginas)
            ],
            PAGINAS: [
                CallbackQueryHandler(cancelar_operacion, pattern='^cancelar$'),
                CallbackQueryHandler(recibir_paginas_callback, pattern='^all$'),
                MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_paginas)
            ],
            COPIAS: [
                CallbackQueryHandler(cancelar_operacion, pattern='^cancelar$'),
                CallbackQueryHandler(ejecutar_impresion)
            ],
            REINTENTO: [
                CallbackQueryHandler(cancelar_operacion, pattern='^cancelar$'),
                CallbackQueryHandler(ejecutar_impresion, pattern='^reintentar$')
            ]
        },
        fallbacks=[]
    )
    
    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("start", comando_start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, mensaje_desconocido))
    
    print("🤖 Bot activo: Con textos de Bienvenida/Error amigables y Logs intactos...")
    app.run_polling()

if __name__ == '__main__':
    main()