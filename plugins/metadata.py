from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.handlers import MessageHandler
from helper.database import madflixbotz
from config import Txt, Config
import asyncio

# Custom message collector class to replace pyromod's ask functionality
class MessageCollector:
    def __init__(self, client, chat_id, timeout):
        self.client = client
        self.chat_id = chat_id
        self.timeout = timeout
        self.response = None
        self._response_event = asyncio.Event()

    async def handler(self, client, message):
        self.response = message
        self._response_event.set()

    async def wait_for_response(self):
        try:
            await asyncio.wait_for(self._response_event.wait(), timeout=self.timeout)
            return self.response
        except asyncio.TimeoutError:
            raise TimeoutError("Request timed out")

async def ask(client, chat_id, text, timeout=60, filters=None):
    """
    Custom ask function that properly handles filters
    """
    # Create a base filter for the chat
    base_filter = filters.chat(chat_id)
    
    # If additional filters are provided, combine them with the chat filter
    if filters:
        final_filter = base_filter & filters
    else:
        final_filter = base_filter

    collector = MessageCollector(client, chat_id, timeout)
    
    # Add the handler with the final filter
    handler = client.add_handler(
        MessageHandler(
            collector.handler,
            filters=final_filter
        )
    )

    await client.send_message(
        chat_id,
        text,
        disable_web_page_preview=True
    )

    try:
        response = await collector.wait_for_response()
        return response
    finally:
        client.remove_handler(handler)
ON = [
    [InlineKeyboardButton('ᴍᴇᴛᴀᴅᴀᴛᴀ ᴏɴ', callback_data='metadata_1'), 
     InlineKeyboardButton('✅', callback_data='metadata_1')],
    [InlineKeyboardButton('Sᴇᴛ Cᴜsᴛᴏᴍ Mᴇᴛᴀᴅᴀᴛᴀ', callback_data='custom_metadata')]
]

OFF = [
    [InlineKeyboardButton('ᴍᴇᴛᴀᴅᴀᴛᴀ ᴏғғ', callback_data='metadata_0'), 
     InlineKeyboardButton('❌', callback_data='metadata_0')],
    [InlineKeyboardButton('Sᴇᴛ Cᴜsᴛᴏᴍ Mᴇᴛᴀᴅᴀᴛᴀ', callback_data='custom_metadata')]
]

@Client.on_message(filters.private & filters.command("metadata"))
async def handle_metadata(bot: Client, message: Message):
    ms = await message.reply_text("Wait A Second...", reply_to_message_id=message.id)
    bool_metadata = await madflixbotz.get_metadata(message.from_user.id)
    user_metadata = await madflixbotz.get_metadata_code(message.from_user.id)
    await ms.delete()

    if bool_metadata:
        await message.reply_text(
            f"<b>ʏᴏᴜʀ ᴄᴜʀʀᴇɴᴛ ᴍᴇᴛᴀᴅᴀᴛᴀ:</b>\n\n➜ `{user_metadata}` ",
            reply_markup=InlineKeyboardMarkup(ON),
        )
    else:
        await message.reply_text(
            f"<b>ʏᴏᴜʀ ᴄᴜʀʀᴇɴᴛ ᴍᴇᴛᴀᴅᴀᴛᴀ:</b>\n\n➜ `{user_metadata}` ",
            reply_markup=InlineKeyboardMarkup(OFF),
        )

@Client.on_callback_query(filters.regex(r".?(custom_metadata|metadata).?"))
async def query_metadata(bot: Client, query: CallbackQuery):
    data = query.data

    if data.startswith("metadata_"):
        _bool = data.split("_")[1] == '1'
        user_metadata = await madflixbotz.get_metadata_code(query.from_user.id)

        if _bool:
            await madflixbotz.set_metadata(query.from_user.id, bool_meta=False)
            await query.message.edit(
                f"<b>ʏᴏᴜʀ ᴄᴜʀʀᴇɴᴛ ᴍᴇᴛᴀᴅᴀᴛᴀ:</b>\n\n➜ `{user_metadata}` ",
                reply_markup=InlineKeyboardMarkup(OFF),
            )
        else:
            await madflixbotz.set_metadata(query.from_user.id, bool_meta=True)
            await query.message.edit(
                f"<b>ʏᴏᴜʀ ᴄᴜʀʀᴇɴᴛ ᴍᴇᴛᴀᴅᴀᴛᴀ:</b>\n\n➜ `{user_metadata}` ",
                reply_markup=InlineKeyboardMarkup(ON),
            )

 elif data == "custom_metadata":
    await query.message.delete()
    try:
        user_metadata = await madflixbotz.get_metadata_code(query.from_user.id)
        metadata_message = f"""
<b>--Metadata Settings:--</b>

➜ <b>ᴄᴜʀʀᴇɴᴛ ᴍᴇᴛᴀᴅᴀᴛᴀ:</b> {user_metadata}

<b>Description</b> : Metadata will change MKV video files including all audio, streams, and subtitle titles.

<b>➲ Send metadata title. Timeout: 60 sec</b>
"""
        try:
            # Note the change here - we're passing filters.text as is
            metadata = await ask(
                bot,
                query.from_user.id,
                metadata_message,
                timeout=60,
                filters=filters.text
            )
            
            if metadata:
                ms = await query.message.reply_text(
                    "**Wait A Second...**",
                    reply_to_message_id=metadata.id
                )
                await madflixbotz.set_metadata_code(
                    query.from_user.id,
                    metadata_code=metadata.text
                )
                await ms.edit("**Your Metadata Code Set Successfully ✅**")
            else:
                await query.message.reply_text(
                    "No metadata received. Please try again using /metadata"
                )
                
        except TimeoutError:
            await query.message.reply_text(
                "⚠️ Error!!\n\nRequest timed out.\nRestart by using /metadata",
                reply_to_message_id=query.message.id,
            )
            return
            
    except Exception as e:
        await query.message.reply_text(f"**Error Occurred:** {str(e)}")
