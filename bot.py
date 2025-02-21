from datetime import datetime
from pytz import timezone
from pyrogram import Client, __version__
from pyrogram.raw.all import layer
from config import Config
from aiohttp import web
import asyncio
import pyrogram.utils

pyrogram.utils.MIN_CHAT_ID = -999999999999
pyrogram.utils.MIN_CHANNEL_ID = -1009999999999

# Health check route handler
async def health_check(request):
    return web.Response(text="OK", status=200)

class Bot(Client):
    def __init__(self):
        super().__init__(
            name="renamer",
            api_id=Config.API_ID,
            api_hash=Config.API_HASH,
            bot_token=Config.BOT_TOKEN,
            workers=200,
            plugins={"root": "plugins"},
            sleep_threshold=15,
        )
        self.health_app = None
        self.runner = None

    async def start_health_server(self):
        """Start the health check server"""
        try:
            self.health_app = web.Application()
            self.health_app.router.add_get('/health', health_check)
            
            self.runner = web.AppRunner(self.health_app)
            await self.runner.setup()
            site = web.TCPSite(self.runner, "0.0.0.0", 8080)
            await site.start()
            print("Health check server started on port 8080")
        except Exception as e:
            print(f"Failed to start health server: {e}")

    async def stop_health_server(self):
        """Stop the health check server"""
        if self.runner:
            await self.runner.cleanup()

    async def start(self):
        await super().start()
        me = await self.get_me()
        self.mention = me.mention
        self.username = me.username
        self.uptime = Config.BOT_UPTIME

        # Start health check server regardless of webhook config
        await self.start_health_server()
            
        print(f"{me.first_name} Is Started.....✨️")
        for id in Config.ADMIN:
            try:
                await self.send_message(Config.LOG_CHANNEL, f"**{me.first_name} Is Started.....✨️**")
            except:
                pass
                
        if Config.LOG_CHANNEL:
            try:
                curr = datetime.now(timezone("Asia/Kolkata"))
                date = curr.strftime('%d %B, %Y')
                time = curr.strftime('%I:%M:%S %p')
                await self.send_message(
                    Config.LOG_CHANNEL,
                    f"**{me.mention} Is Restarted !!**\n\n"
                    f"📅 Date : `{date}`\n"
                    f"⏰ Time : `{time}`\n"
                    f"🌐 Timezone : `Asia/Kolkata`\n\n"
                    f"🉐 Version : `v{__version__} (Layer {layer})`</b>"
                )
            except:
                print("Please Make This Is Admin In Your Log Channel")

    async def stop(self):
        """Stop the bot and cleanup health check server"""
        await self.stop_health_server()
        await super().stop()

# Run the bot
app = Bot()
app.run()

# Jishu Developer 
# Don't Remove Credit 🥺
# Telegram Channel @Madflix_Bots
# Developer @JishuDeveloper
