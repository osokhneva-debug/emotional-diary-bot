# main.py
import os
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List
import json

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode
from telegram.error import BadRequest, Forbidden
from sqlalchemy import text

from db import init_db, User, Entry, Schedule, UserSettings, get_session
from scheduler import EmotionScheduler
from analysis import EmotionAnalyzer
from i18n import TEXTS, EMOTION_CATEGORIES
from security import sanitize_input, RateLimiter
from rate_limiter import rate_limit, rate_limit_emotion_entry, rate_limit_summary, rate_limit_export

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot configuration
BOT_TOKEN = os.getenv('BOT_TOKEN') or os.getenv('TELEGRAM_BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("Bot token not found. Set BOT_TOKEN or TELEGRAM_BOT_TOKEN environment variable")

WEBHOOK_URL = os.getenv('WEBHOOK_URL')
PORT = int(os.getenv('PORT', 8080))

class EmotionalDiaryBot:
    def __init__(self):
        self.app = None
        self.scheduler = EmotionScheduler()
        self.analyzer = EmotionAnalyzer()
        self.rate_limiter = RateLimiter()
        
    async def setup(self):
        """Initialize bot application"""
        # ИСПРАВЛЕНО: Создаем Application и инициализируем его
        self.app = Application.builder().token(BOT_TOKEN).build()
        
        # ВАЖНО: Инициализируем Application
        await self.app.initialize()
        
        # Command handlers
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("note", self.note_command))
        self.app.add_handler(CommandHandler("summary", self.summary_command))
        self.app.add_handler(CommandHandler("export", self.export_command))
        self.app.add_handler(CommandHandler("timezone", self.timezone_command))
        self.app.add_handler(CommandHandler("pause", self.pause_command))
        self.app.add_handler(CommandHandler("resume", self.resume_command))
        self.app.add_handler(CommandHandler("delete_me", self.delete_me_command))
        self.app.add_handler(CommandHandler("help", self.help_command))
        
        # Callback handlers
        self.app.add_handler(CallbackQueryHandler(self.handle_callback))
        
        # Message handlers
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Initialize database and scheduler
        await init_db()
        
        # Set scheduler callbacks
        self.scheduler.set_callbacks(
            self.send_daily_ping,
            self.send_weekly_summary
        )
        
        await self.scheduler.start()
        
        logger.info("Bot setup completed")

    @rate_limit
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command with onboarding"""
        user = update.effective_user
        chat_id = update.effective_chat.id
        
        with get_session() as session:
            # Check if user exists
            existing_user = session.query(User).filter(User.chat_id == chat_id).first()
            
            if not existing_user:
                # Create new user
                new_user = User(
                    chat_id=chat_id,
                    username=user.username,
                    first_name=user.first_name,
                    timezone='Europe/Moscow'  # Default timezone
                )
                session.add(new_user)
                session.commit()
                
                # Send welcome message with scientific explanation
                await update.message.reply_text(
                    TEXTS['onboarding_welcome'],
                    parse_mode=ParseMode.HTML
                )
                
                # Setup timezone
                keyboard = self.get_timezone_keyboard()
                await update.message.reply_text(
                    TEXTS['setup_timezone'],
                    reply_markup=keyboard,
                    parse_mode=ParseMode.HTML
                )
                
            else:
                await update.message.reply_text(
                    TEXTS['welcome_back'].format(name=user.first_name or ""),
                    parse_mode=ParseMode.HTML
                )

    @rate_limit_emotion_entry
    async def note_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /note command - start emotion logging process"""
        chat_id = update.effective_chat.id
        
        with get_session() as session:
            user = session.query(User).filter(User.chat_id == chat_id).first()
            if not user:
                await update.message.reply_text(TEXTS['not_registered'])
                return
                
        # Show emotion categories
        keyboard = self.get_emotion_categories_keyboard()
        await update.message.reply_text(
            TEXTS['choose_emotion_category'],
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )

    @rate_limit_summary
    async def summary_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /summary command"""
        chat_id = update.effective_chat.id
        
        with get_session() as session:
            user = session.query(User).filter(User.chat_id == chat_id).first()
            if not user:
                await update.message.reply_text(TEXTS['not_registered'])
                return
        
        keyboard = self.get_summary_period_keyboard()
        await update.message.reply_text(
            TEXTS['choose_summary_period'],
            reply_markup=keyboard
        )

    @rate_limit_export
    async def export_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /export command"""
        chat_id = update.effective_chat.id
        
        with get_session() as session:
            user = session.query(User).filter(User.chat_id == chat_id).first()
            if not user:
                await update.message.reply_text(TEXTS['not_registered'])
                return
            
            entries = session.query(Entry).filter(Entry.user_id == user.id).all()
            
            if not entries:
                await update.message.reply_text(TEXTS['no_data_to_export'])
                return
        
        # Generate CSV
        csv_data = self.analyzer.generate_csv_export(entries)
        
        # Send as document
        await update.message.reply_document(
            document=csv_data,
            filename=f"emotional_diary_{datetime.now().strftime('%Y%m%d')}.csv",
            caption=TEXTS['export_complete']
        )

    @rate_limit
    async def timezone_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /timezone command"""
        keyboard = self.get_timezone_keyboard()
        await update.message.reply_text(
            TEXTS['change_timezone'],
            reply_markup=keyboard
        )

    @rate_limit
    async def pause_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /pause command"""
        chat_id = update.effective_chat.id
        
        with get_session() as session:
            user = session.query(User).filter(User.chat_id == chat_id).first()
            if not user:
                await update.message.reply_text(TEXTS['not_registered'])
                return
            
            user.paused = True
            session.commit()
        
        await update.message.reply_text(TEXTS['notifications_paused'])

    @rate_limit
    async def resume_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /resume command"""
        chat_id = update.effective_chat.id
        
        with get_session() as session:
            user = session.query(User).filter(User.chat_id == chat_id).first()
            if not user:
                await update.message.reply_text(TEXTS['not_registered'])
                return
            
            user.paused = False
            session.commit()
        
        await update.message.reply_text(TEXTS['notifications_resumed'])

    @rate_limit
    async def delete_me_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /delete_me command"""
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(TEXTS['confirm_delete'], callback_data="confirm_delete"),
                InlineKeyboardButton(TEXTS['cancel'], callback_data="cancel_delete")
            ]
        ])
        
        await update.message.reply_text(
            TEXTS['confirm_data_deletion'],
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        await update.message.reply_text(TEXTS['help_message'], parse_mode=ParseMode.HTML)

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle all callback queries"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        chat_id = query.message.chat_id
        
        # Store user context for multi-step processes
        if not hasattr(context, 'user_data'):
            context.user_data = {}
        if chat_id not in context.user_data:
            context.user_data[chat_id] = {}
        
        # Handle different callback types
        if data.startswith("emotion_category_"):
            await self.handle_emotion_category_selection(query, context)
        elif data.startswith("emotion_"):
            await self.handle_emotion_selection(query, context)
        elif data.startswith("valence_"):
            await self.handle_valence_selection(query, context)
        elif data.startswith("arousal_"):
            await self.handle_arousal_selection(query, context)
        elif data.startswith("summary_"):
            await self.handle_summary_request(query, context)
        elif data.startswith("timezone_"):
            await self.handle_timezone_selection(query, context)
        elif data == "confirm_delete":
            await self.handle_data_deletion(query, context)
        elif data == "cancel_delete":
            await query.edit_message_text(TEXTS['deletion_cancelled'])
        elif data == "skip_cause":
            await self.handle_skip_cause(query, context)
        elif data == "finish_entry":
            await self.handle_finish_entry(query, context)

    async def handle_emotion_category_selection(self, query, context):
        """Handle emotion category selection"""
        category = query.data.replace("emotion_category_", "")
        chat_id = query.message.chat_id
        
        context.user_data[chat_id]['selected_category'] = category
        
        # Show emotions in selected category
        keyboard = self.get_emotions_keyboard(category)
        
        await query.edit_message_text(
            f"{TEXTS['selected_category']} <b>{category}</b>\n\n{TEXTS['choose_specific_emotion']}",
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )

    async def handle_emotion_selection(self, query, context):
        """Handle specific emotion selection"""
        emotion = query.data.replace("emotion_", "")
        chat_id = query.message.chat_id
        
        context.user_data[chat_id]['selected_emotion'] = emotion
        
        # Ask for valence (positive/negative)
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("😊 Приятная", callback_data="valence_positive"),
                InlineKeyboardButton("😔 Неприятная", callback_data="valence_negative"),
                InlineKeyboardButton("😐 Нейтральная", callback_data="valence_neutral")
            ]
        ])
        
        await query.edit_message_text(
            f"{TEXTS['selected_emotion']} <b>{emotion}</b>\n\n{TEXTS['rate_valence']}",
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )

    async def handle_valence_selection(self, query, context):
        """Handle valence selection"""
        valence = query.data.replace("valence_", "")
        chat_id = query.message.chat_id
        
        context.user_data[chat_id]['valence'] = valence
        
        # Ask for arousal (energy level)
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("⚡ Высокая", callback_data="arousal_high"),
                InlineKeyboardButton("🌊 Средняя", callback_data="arousal_medium"),
                InlineKeyboardButton("😴 Низкая", callback_data="arousal_low")
            ]
        ])
        
        await query.edit_message_text(
            f"{TEXTS['selected_valence']} <b>{TEXTS[f'valence_{valence}']}</b>\n\n{TEXTS['rate_arousal']}",
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )

    async def handle_arousal_selection(self, query, context):
        """Handle arousal selection and ask for cause"""
        arousal = query.data.replace("arousal_", "")
        chat_id = query.message.chat_id
        
        context.user_data[chat_id]['arousal'] = arousal
        context.user_data[chat_id]['step'] = 'cause'
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(TEXTS['skip_cause_btn'], callback_data="skip_cause")]
        ])
        
        await query.edit_message_text(
            f"{TEXTS['selected_arousal']} <b>{TEXTS[f'arousal_{arousal}']}</b>\n\n{TEXTS['ask_cause']}",
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )

    async def handle_skip_cause(self, query, context):
        """Handle skipping cause input"""
        chat_id = query.message.chat_id
        context.user_data[chat_id]['step'] = 'notes'
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(TEXTS['finish_entry_btn'], callback_data="finish_entry")]
        ])
        
        await query.edit_message_text(
            TEXTS['ask_additional_notes'],
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )

    async def handle_finish_entry(self, query, context):
        """Finish emotion entry"""
        chat_id = query.message.chat_id
        user_data = context.user_data.get(chat_id, {})
        
        # Save entry to database
        await self.save_emotion_entry(chat_id, user_data)
        
        # Clear user data
        context.user_data[chat_id] = {}
        
        await query.edit_message_text(
            TEXTS['entry_saved'],
            parse_mode=ParseMode.HTML
        )

    async def handle_summary_request(self, query, context):
        """Handle summary period selection"""
        period = query.data.replace("summary_", "")
        chat_id = query.message.chat_id
        
        with get_session() as session:
            user = session.query(User).filter(User.chat_id == chat_id).first()
            if not user:
                await query.edit_message_text(TEXTS['not_registered'])
                return
            
            # Generate summary
            summary = await self.analyzer.generate_summary(user.id, period)
            
            # Add action buttons
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("📊 Другой период", callback_data="back_to_summary"),
                    InlineKeyboardButton("💾 Экспорт", callback_data="export_data")
                ]
            ])
            
            await query.edit_message_text(
                summary,
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML
            )

    async def handle_timezone_selection(self, query, context):
        """Handle timezone selection"""
        timezone_str = query.data.replace("timezone_", "").replace("_", "/")
        chat_id = query.message.chat_id
        
        with get_session() as session:
            user = session.query(User).filter(User.chat_id == chat_id).first()
            if user:
                user.timezone = timezone_str
                session.commit()
                
                await query.edit_message_text(
                    f"{TEXTS['timezone_updated']} <b>{timezone_str}</b>",
                    parse_mode=ParseMode.HTML
                )

    async def handle_data_deletion(self, query, context):
        """Handle confirmed data deletion"""
        chat_id = query.message.chat_id
        
        with get_session() as session:
            user = session.query(User).filter(User.chat_id == chat_id).first()
            if user:
                # Delete all user data
                session.query(Entry).filter(Entry.user_id == user.id).delete()
                session.query(Schedule).filter(Schedule.user_id == user.id).delete()
                session.query(UserSettings).filter(UserSettings.user_id == user.id).delete()
                session.delete(user)
                session.commit()
        
        await query.edit_message_text(TEXTS['data_deleted'])

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages during emotion logging process"""
        chat_id = update.effective_chat.id
        message_text = sanitize_input(update.message.text)
        
        if not hasattr(context, 'user_data') or chat_id not in context.user_data:
            await update.message.reply_text(TEXTS['no_active_session'])
            return
        
        user_data = context.user_data[chat_id]
        step = user_data.get('step')
        
        if step == 'cause':
            user_data['cause'] = message_text
            user_data['step'] = 'notes'
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(TEXTS['finish_entry_btn'], callback_data="finish_entry")]
            ])
            
            await update.message.reply_text(
                TEXTS['ask_additional_notes'],
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML
            )
            
        elif step == 'notes':
            user_data['notes'] = message_text
            
            # Save entry
            await self.save_emotion_entry(chat_id, user_data)
            
            # Clear user data
            context.user_data[chat_id] = {}
            
            await update.message.reply_text(
                TEXTS['entry_saved'],
                parse_mode=ParseMode.HTML
            )

    async def save_emotion_entry(self, chat_id: int, user_data: Dict):
        """Save emotion entry to database"""
        with get_session() as session:
            user = session.query(User).filter(User.chat_id == chat_id).first()
            if not user:
                return
            
            # Convert valence and arousal to numeric values
            valence_map = {'positive': 1, 'neutral': 0, 'negative': -1}
            arousal_map = {'high': 2, 'medium': 1, 'low': 0}
            
            entry = Entry(
                user_id=user.id,
                timestamp=datetime.now(timezone.utc),
                emotions=json.dumps([user_data.get('selected_emotion', '')]),
                category=user_data.get('selected_category', ''),
                valence=valence_map.get(user_data.get('valence'), 0),
                arousal=arousal_map.get(user_data.get('arousal'), 0),
                cause=user_data.get('cause', ''),
                notes=user_data.get('notes', '')
            )
            
            session.add(entry)
            session.commit()

    def get_emotion_categories_keyboard(self) -> InlineKeyboardMarkup:
        """Generate emotion categories keyboard"""
        buttons = []
        for category, info in EMOTION_CATEGORIES.items():
            buttons.append([InlineKeyboardButton(
                f"{info['emoji']} {category}",
                callback_data=f"emotion_category_{category}"
            )])
        
        return InlineKeyboardMarkup(buttons)

    def get_emotions_keyboard(self, category: str) -> InlineKeyboardMarkup:
        """Generate emotions keyboard for specific category"""
        emotions = EMOTION_CATEGORIES[category]['emotions']
        buttons = []
        
        # Create rows of 2 emotions each
        for i in range(0, len(emotions), 2):
            row = []
            for j in range(i, min(i + 2, len(emotions))):
                row.append(InlineKeyboardButton(
                    emotions[j],
                    callback_data=f"emotion_{emotions[j]}"
                ))
            buttons.append(row)
        
        # Add back button
        buttons.append([InlineKeyboardButton("⬅️ Назад", callback_data="back_to_categories")])
        
        return InlineKeyboardMarkup(buttons)

    def get_summary_period_keyboard(self) -> InlineKeyboardMarkup:
        """Generate summary period selection keyboard"""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📅 7 дней", callback_data="summary_7"),
                InlineKeyboardButton("📊 14 дней", callback_data="summary_14")
            ],
            [
                InlineKeyboardButton("📈 30 дней", callback_data="summary_30"),
                InlineKeyboardButton("📉 90 дней", callback_data="summary_90")
            ]
        ])

    def get_timezone_keyboard(self) -> InlineKeyboardMarkup:
        """Generate timezone selection keyboard"""
        timezones = [
            ('Europe/Moscow', '🇷🇺 Москва (UTC+3)'),
            ('Europe/Kiev', '🇺🇦 Киев (UTC+2)'),
            ('Europe/Minsk', '🇧🇾 Минск (UTC+3)'),
            ('Asia/Almaty', '🇰🇿 Алматы (UTC+6)'),
            ('Asia/Tashkent', '🇺🇿 Ташкент (UTC+5)'),
            ('Europe/Berlin', '🇩🇪 Берлин (UTC+1)'),
            ('America/New_York', '🇺🇸 Нью-Йорк (UTC-5)'),
        ]
        
        buttons = []
        for tz_code, tz_name in timezones:
            buttons.append([InlineKeyboardButton(
                tz_name,
                callback_data=f"timezone_{tz_code.replace('/', '_')}"
            )])
        
        return InlineKeyboardMarkup(buttons)

    async def send_daily_ping(self, chat_id: int):
        """Send daily emotion check-in"""
        with get_session() as session:
            user = session.query(User).filter(User.chat_id == chat_id).first()
            if not user or user.paused:
                return
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✨ Записать эмоцию", callback_data="start_entry")],
            [
                InlineKeyboardButton("⏰ Отложить на 15 мин", callback_data="postpone_15"),
                InlineKeyboardButton("🛑 Пропустить сегодня", callback_data="skip_today")
            ]
        ])
        
        try:
            await self.app.bot.send_message(
                chat_id=chat_id,
                text=TEXTS['daily_ping'],
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML
            )
        except (BadRequest, Forbidden) as e:
            logger.warning(f"Could not send daily ping to {chat_id}: {e}")

    async def send_weekly_summary(self, chat_id: int):
        """Send weekly emotional summary"""
        with get_session() as session:
            user = session.query(User).filter(User.chat_id == chat_id).first()
            if not user or user.paused:
                return
        
        try:
            summary = await self.analyzer.generate_summary(user.id, "7")
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📊 Подробная сводка", callback_data="summary_7")],
                [InlineKeyboardButton("💾 Экспорт данных", callback_data="export_data")]
            ])
            
            await self.app.bot.send_message(
                chat_id=chat_id,
                text=f"🌸 <b>Еженедельная сводка</b>\n\n{summary}",
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML
            )
        except (BadRequest, Forbidden) as e:
            logger.warning(f"Could not send weekly summary to {chat_id}: {e}")

    async def run_polling(self):
        """Run bot with polling (for development)"""
        await self.setup()
        await self.app.run_polling(drop_pending_updates=True)
    
    async def shutdown(self):
        """Shutdown bot properly"""
        try:
            if self.scheduler:
                await self.scheduler.stop()
            if self.app:
                await self.app.shutdown()
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

# Health check endpoint for monitoring
from aiohttp import web, web_runner
import aiohttp_cors

async def health_check(request):
    """Health check endpoint"""
    try:
        # Check database connection
        with get_session() as session:
            session.execute(text("SELECT 1"))
        
        # Check scheduler status  
        scheduler_running = hasattr(bot, 'scheduler') and bot.scheduler.scheduler.running
        
        health_data = {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "database": "connected",
            "scheduler": "running" if scheduler_running else "stopped",
            "version": "1.0.0"
        }
        
        return web.json_response(health_data)
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return web.json_response(
            {"status": "unhealthy", "error": str(e)},
            status=500
        )

async def webhook_handler(request):
    """Handle incoming webhooks"""
    try:
        update_data = await request.json()
        update = Update.de_json(update_data, bot.app.bot)
        await bot.app.process_update(update)
        return web.Response(text="OK")
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return web.Response(text="Error", status=500)

async def setup_web_server():
    """Setup web server for webhooks and health checks"""
    app = web.Application()
    
    # Setup CORS
    cors = aiohttp_cors.setup(app, defaults={
        "*": aiohttp_cors.ResourceOptions(
            allow_credentials=True,
            expose_headers="*",
            allow_headers="*",
            allow_methods="*"
        )
    })
    
    # Add routes
    app.router.add_get('/', lambda r: web.Response(text="Emotional Diary Bot is running"))
    app.router.add_get('/health', health_check)
    app.router.add_post('/webhook', webhook_handler)
    
    # Add CORS to all routes
    for route in list(app.router.routes()):
        cors.add(route)
    
    return app

# Main execution
if __name__ == "__main__":
    bot = EmotionalDiaryBot()
    
    if WEBHOOK_URL:
        async def main():
            try:
                # Setup bot
                await bot.setup()
                
                # Setup web server
                web_app = await setup_web_server()
                runner = web_runner.AppRunner(web_app)
                await runner.setup()
                
                site = web_runner.TCPSite(runner, '0.0.0.0', PORT)
                await site.start()
                
                # Set webhook
                webhook_url = f"{WEBHOOK_URL}/webhook"
                await bot.app.bot.set_webhook(
                    url=webhook_url,
                    drop_pending_updates=True
                )
                
                logger.info(f"Bot started with webhook on port {PORT}")
                logger.info(f"Webhook URL set to: {webhook_url}")
                logger.info(f"Health check available at: {WEBHOOK_URL}/health")
                logger.info(f"Root endpoint available at: {WEBHOOK_URL}/")
                
                # Keep running
                try:
                    while True:
                        await asyncio.sleep(1)
                except KeyboardInterrupt:
                    logger.info("Shutting down...")
                    await bot.shutdown()
                    await runner.cleanup()
                    
            except Exception as e:
                logger.error(f"Error in main: {e}")
                await bot.shutdown()
                raise
        
        asyncio.run(main())
    else:
        logger.info("No WEBHOOK_URL provided, running in polling mode")
        asyncio.run(bot.run_polling())
