from core.config import TOKEN
from core.logger import setup_logger
from handlers.bot_handlers import registrar_handlers
from telegram.ext import Application

def main():
    setup_logger()
    app = Application.builder().token(TOKEN).build()
    
    registrar_handlers(app)
    
    print("🤖 Bot modular activo...")
    app.run_polling()

if __name__ == '__main__':
    main()