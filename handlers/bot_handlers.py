import os
import shutil
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler, 
    filters, ConversationHandler, ContextTypes
)
from core.config import USUARIOS_PERMITIDOS, ADMIN_ID
from services.converter import preparar_archivo
from services.printer import verificar_impresora, enviar_a_cups

logger = logging.getLogger("InPrint")

COLOR, DUPLEX, PAGINAS, COPIAS, REINTENTO = range(5)

# --- COMANDOS Y MENSAJES GLOBALES ---
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
    
    logger.info(f"CANCELADO | User: {usuario} | Doc: {archivo_log}")
    
    if query:
        await query.edit_message_text("❌ Operación cancelada. No se imprimió nada.")
    else:
        await update.message.reply_text("❌ Operación cancelada. No se imprimió nada.")
        
    dir_temp = context.user_data.get('dir_temp')
    if dir_temp and os.path.exists(dir_temp):
        shutil.rmtree(dir_temp)
        
    return ConversationHandler.END

# --- LÓGICA PRINCIPAL (Integrando converter.py) ---
async def recibir_documento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_name = update.message.from_user.first_name
    
    if user_id not in USUARIOS_PERMITIDOS:
        logger.warning(f"INTENTO NO AUTORIZADO | ID: {user_id} | Nombre: {user_name}")
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

    context.user_data['usuario_id'] = user_id
    context.user_data['usuario'] = user_name
    context.user_data['nombre_archivo'] = nombre_original
    
    msg = await update.message.reply_text("📥 Descargando y procesando archivo...")
    
    file = await context.bot.get_file(file_id)
    file_bytes = await file.download_as_bytearray()
    
    try:
        # Llamamos al servicio modular de conversión y directorios temporales
        dir_temp, ruta_pdf, saltar_paginas = preparar_archivo(bytes(file_bytes), nombre_original)
        context.user_data['dir_temp'] = dir_temp
        context.user_data['ruta'] = ruta_pdf
    except Exception as e:
        logger.error(f"ERROR PROCESAMIENTO | Usuario: {user_name} | Archivo: {nombre_original} | Detalle: {e}")
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"🚨 ERROR AL PROCESAR ARCHIVO:\nUsuario: {user_name}\nArchivo: {nombre_original}\nFallo: {e}")
        await msg.edit_text("❌ Error al procesar o convertir el archivo.")
        return ConversationHandler.END

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
    
    mensaje = "🔢 ¿Qué páginas quieres imprimir?\n\nEscribe tu respuesta en el chat. Ejemplos:\n• 1-5 (Intervalo de páginas)\n• 1,3,5 (Páginas salteadas)"
    teclado = [
        [InlineKeyboardButton("📄 Todas las páginas", callback_data='all')],
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
    color = context.user_data['color']
    duplex = context.user_data['duplex']
    paginas = context.user_data['paginas']
    usuario = context.user_data['usuario']
    usuario_id = context.user_data['usuario_id']
    archivo_log = context.user_data['nombre_archivo']

    await query.edit_message_text(text="⏳ Verificando conexión con la impresora...")

    # Usamos el servicio modular de red (printer.py)
    if not verificar_impresora():
        logger.error(f"IMPRESORA APAGADA | User: {usuario} | Doc: {archivo_log}")
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"🚨 **IMPRESORA DESCONECTADA**\nUsuario: {usuario} intentó imprimir pero la impresora no responde.\nCheca si está prendida.", parse_mode='Markdown')
        
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

    try:
        # Mandamos a CUPS usando el servicio modular
        enviar_a_cups(ruta, copias, color, duplex, paginas)
        logger.info(f"IMPRESIÓN | User: {usuario} | Doc: {archivo_log} | Copias: {copias} | Páginas: {paginas} | Color: {color} | Dúplex: {duplex}")
        
        if usuario_id != ADMIN_ID:
            tipo_color = "Color 🔴" if color == 'RGB' else "B/N ⚫"
            await context.bot.send_message(chat_id=ADMIN_ID, text=f"✅ **VENTA EXITOSA**\n{usuario} imprimió:\n📄 `{archivo_log}`\n🖨️ {copias} copias a {tipo_color}", parse_mode='Markdown')

        await query.message.reply_text("✅ ¡Listo! Documento enviado a la impresora.")
        
        # Limpieza de la carpeta temporal del trabajo actual
        dir_temp = context.user_data.get('dir_temp')
        if dir_temp and os.path.exists(dir_temp):
            shutil.rmtree(dir_temp)
            
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"ERROR CUPS | User: {usuario} | Doc: {archivo_log} | Fallo: {e}")
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"🚨 **ERROR DEL SISTEMA**\nUsuario: {usuario}\nFallo interno de CUPS.\nDetalle: `{e}`", parse_mode='Markdown')
        
        teclado = [
            [InlineKeyboardButton("🔄 Reintentar", callback_data='reintentar')],
            [InlineKeyboardButton("❌ Cancelar", callback_data='cancelar')]
        ]
        await query.edit_message_text("❌ Ocurrió un error interno al mandar el documento.\n\n¿Deseas intentarlo de nuevo?", reply_markup=InlineKeyboardMarkup(teclado))
        return REINTENTO

def registrar_handlers(app: Application):
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