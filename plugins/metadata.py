import logging
from helper.database import madflixbotz as db
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from config import Txt

# Set up logging to log exceptions and errors.
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@Client.on_message(filters.command("metadata"))
async def metadata(client, message):
    try:
        user_id = message.from_user.id

        # Fetch user metadata from the database
        current = await db.get_metadata(user_id)
        title = await db.get_title(user_id)
        author = await db.get_author(user_id)
        artist = await db.get_artist(user_id)
        video = await db.get_video(user_id)
        audio = await db.get_audio(user_id)
        subtitle = await db.get_subtitle(user_id)

        # Display the current metadata
        text = f"""
**㊋ Yᴏᴜʀ Mᴇᴛᴀᴅᴀᴛᴀ ɪꜱ ᴄᴜʀʀᴇɴᴛʟʏ: {current}**

**◈ Tɪᴛʟᴇ ▹** `{title if title else 'Nᴏᴛ ꜰᴏᴜɴᴅ'}`
**◈ Aᴜᴛʜᴏʀ ▹** `{author if author else 'Nᴏᴛ ꜰᴏᴜɴᴅ'}`
**◈ Aʀᴛɪꜱᴛ ▹** `{artist if artist else 'Nᴏᴛ ꜰᴏᴜɴᴅ'}`
**◈ Aᴜᴅɪᴏ ▹** `{audio if audio else 'Nᴏᴛ ꜰᴏᴜɴᴅ'}`
**◈ Sᴜʙᴛɪᴛʟᴇ ▹** `{subtitle if subtitle else 'Nᴏᴛ ꜰᴏᴜɴᴅ'}`
**◈ Vɪᴅᴇᴏ ▹** `{video if video else 'Nᴏᴛ ꜰᴏᴜɴᴅ'}`
        """

        # Inline buttons to toggle metadata
        buttons = [
            [
                InlineKeyboardButton(f"On{' ✅' if current == 'On' else ''}", callback_data='on_metadata'),
                InlineKeyboardButton(f"Off{' ✅' if current == 'Off' else ''}", callback_data='off_metadata')
            ],
            [
                InlineKeyboardButton("How to Set Metadata", callback_data="metainfo")
            ]
        ]
        keyboard = InlineKeyboardMarkup(buttons)

        await message.reply_text(text=text, reply_markup=keyboard, disable_web_page_preview=True)
    except Exception as e:
        logger.exception("Error in metadata command:")
        await message.reply_text("An error occurred while fetching your metadata. Please try again later.")


@Client.on_callback_query(filters.regex(r"on_metadata|off_metadata|metainfo"))
async def metadata_callback(client, query: CallbackQuery):
    try:
        user_id = query.from_user.id
        data = query.data

        if data == "on_metadata":
            await db.set_metadata(user_id, "On")
        elif data == "off_metadata":
            await db.set_metadata(user_id, "Off")
        elif data == "metainfo":
            await query.message.edit_text(
                text=Txt.META_TXT,
                disable_web_page_preview=True,
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("Hᴏᴍᴇ", callback_data="start"),
                        InlineKeyboardButton("Bᴀᴄᴋ", callback_data="commands")
                    ]
                ])
            )
            return

        # Fetch updated metadata after toggling
        current = await db.get_metadata(user_id)
        title = await db.get_title(user_id)
        author = await db.get_author(user_id)
        artist = await db.get_artist(user_id)
        video = await db.get_video(user_id)
        audio = await db.get_audio(user_id)
        subtitle = await db.get_subtitle(user_id)

        # Updated metadata message after toggle
        text = f"""
**㊋ Yᴏᴜʀ Mᴇᴛᴀᴅᴀᴛᴀ ɪꜱ ᴄᴜʀʀᴇɴᴛʟʏ: {current}**

**◈ Tɪᴛʟᴇ ▹** `{title if title else 'Nᴏᴛ ꜰᴏᴜɴᴅ'}`
**◈ Aᴜᴛʜᴏʀ ▹** `{author if author else 'Nᴏᴛ ꜰᴏᴜɴᴅ'}`
**◈ Aʀᴛɪꜱᴛ ▹** `{artist if artist else 'Nᴏᴛ ꜰᴏᴜɴᴅ'}`
**◈ Aᴜᴅɪᴏ ▹** `{audio if audio else 'Nᴏᴛ ꜰᴏᴜɴᴅ'}`
**◈ Sᴜʙᴛɪᴛʟᴇ ▹** `{subtitle if subtitle else 'Nᴏᴛ ꜰᴏᴜɴᴅ'}`
**◈ Vɪᴅᴇᴏ ▹** `{video if video else 'Nᴏᴛ ꜰᴏᴜɴᴅ'}`
        """

        # Update inline buttons
        buttons = [
            [
                InlineKeyboardButton(f"On{' ✅' if current == 'On' else ''}", callback_data='on_metadata'),
                InlineKeyboardButton(f"Off{' ✅' if current == 'Off' else ''}", callback_data='off_metadata')
            ],
            [
                InlineKeyboardButton("How to Set Metadata", callback_data="metainfo")
            ]
        ]
        await query.message.edit_text(
            text=text,
            reply_markup=InlineKeyboardMarkup(buttons),
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.exception("Error in metadata callback:")
        await query.answer("An error occurred while processing your request.", show_alert=True)


@Client.on_message(filters.private & filters.command('settitle'))
async def title(client, message):
    try:
        if len(message.command) == 1:
            return await message.reply_text(
                "**Gɪᴠᴇ Tʜᴇ Tɪᴛʟᴇ\n\nExᴀᴍᴩʟᴇ: /settitle Encoded By @Animes_Cruise**"
            )
        title_text = message.text.split(" ", 1)[1]
        await db.set_title(message.from_user.id, title=title_text)
        await message.reply_text("**✅ Tɪᴛʟᴇ Sᴀᴠᴇᴅ**")
    except Exception as e:
        logger.exception("Error in settitle command:")
        await message.reply_text("An error occurred while setting your title. Please try again later.")


@Client.on_message(filters.private & filters.command('setauthor'))
async def author(client, message):
    try:
        if len(message.command) == 1:
            return await message.reply_text(
                "**Gɪᴠᴇ Tʜᴇ Aᴜᴛʜᴏʀ\n\nExᴀᴍᴩʟᴇ: /setauthor @Animes_Cruise**"
            )
        author_text = message.text.split(" ", 1)[1]
        await db.set_author(message.from_user.id, author=author_text)
        await message.reply_text("**✅ Aᴜᴛʜᴏʀ Sᴀᴠᴇᴅ**")
    except Exception as e:
        logger.exception("Error in setauthor command:")
        await message.reply_text("An error occurred while setting your author. Please try again later.")


@Client.on_message(filters.private & filters.command('setartist'))
async def artist(client, message):
    try:
        if len(message.command) == 1:
            return await message.reply_text(
                "**Gɪᴠᴇ Tʜᴇ Aʀᴛɪꜱᴛ\n\nExᴀᴍᴩʟᴇ: /setartist @Animes_Cruise**"
            )
        artist_text = message.text.split(" ", 1)[1]
        await db.set_artist(message.from_user.id, artist=artist_text)
        await message.reply_text("**✅ Aʀᴛɪꜱᴛ Sᴀᴠᴇᴅ**")
    except Exception as e:
        logger.exception("Error in setartist command:")
        await message.reply_text("An error occurred while setting your artist. Please try again later.")


@Client.on_message(filters.private & filters.command('setaudio'))
async def audio(client, message):
    try:
        if len(message.command) == 1:
            return await message.reply_text(
                "**Gɪᴠᴇ Tʜᴇ Aᴜᴅɪᴏ Tɪᴛʟᴇ\n\nExᴀᴍᴩʟᴇ: /setaudio @Animes_Cruise**"
            )
        audio_text = message.text.split(" ", 1)[1]
        await db.set_audio(message.from_user.id, audio=audio_text)
        await message.reply_text("**✅ Aᴜᴅɪᴏ Sᴀᴠᴇᴅ**")
    except Exception as e:
        logger.exception("Error in setaudio command:")
        await message.reply_text("An error occurred while setting your audio. Please try again later.")


@Client.on_message(filters.private & filters.command('setsubtitle'))
async def subtitle(client, message):
    try:
        if len(message.command) == 1:
            return await message.reply_text(
                "**Gɪᴠᴇ Tʜᴇ Sᴜʙᴛɪᴛʟᴇ Tɪᴛʟᴇ\n\nExᴀᴍᴩʟᴇ: /setsubtitle @Animes_Cruise**"
            )
        subtitle_text = message.text.split(" ", 1)[1]
        await db.set_subtitle(message.from_user.id, subtitle=subtitle_text)
        await message.reply_text("**✅ Sᴜʙᴛɪᴛʟᴇ Sᴀᴠᴇᴅ**")
    except Exception as e:
        logger.exception("Error in setsubtitle command:")
        await message.reply_text("An error occurred while setting your subtitle. Please try again later.")


@Client.on_message(filters.private & filters.command('setvideo'))
async def video(client, message):
    try:
        if len(message.command) == 1:
            return await message.reply_text(
                "**Gɪᴠᴇ Tʜᴇ Vɪᴅᴇᴏ Tɪᴛʟᴇ\n\nExᴀᴍᴩʟᴇ: /setvideo Encoded by @Animes_Cruise**"
            )
        video_text = message.text.split(" ", 1)[1]
        await db.set_video(message.from_user.id, video=video_text)
        await message.reply_text("**✅ Vɪᴅᴇᴏ Sᴀᴠᴇᴅ**")
    except Exception as e:
        logger.exception("Error in setvideo command:")
        await message.reply_text("An error occurred while setting your video. Please try again later.")
