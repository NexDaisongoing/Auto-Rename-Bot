import logging
from helper.database import madflixbotz as db
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from config import Txt

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Default metadata value
DEFAULT_METADATA = "@Anime_Onsen | @Matrix_Bots"

@Client.on_message(filters.command("metadata"))
async def show_metadata_help(client, message):
    try:
        help_text = """
**📝 Metadata Commands Guide**

1. Set All File Metadata:
`/setallfilemetadata AudioTitle | Artist | Album | Genre | Author | VideoTitle | VideoName | AudioName | Subtitles`

2. Set Audio Metadata:
`/setaudiometadata Title | Artist | Album | Genre | Author`

3. Set Video Metadata:
`/setvideometadata VideoTitle | VideoName | AudioName | Subtitles`

**Note:**
• All fields are optional
• Default value if not specified: @Anime_Onsen | @Matrix_Bots
• Supported audio formats: .mp3, .m4a, .ogg, .wav, .eac3, .opus, .vorbis
• Supported video formats: .mkv, .mp4, .mov, .avi

**Examples:**
• `/setallfilemetadata My Song | Artist Name | Album Name | Pop | Author Name | My Video | Video Name | Audio Track | English`
• `/setaudiometadata My Song | Artist Name | Album Name | Pop | Author Name`
• `/setvideometadata My Video | Video Name | Audio Track | English`
"""
        await message.reply_text(
            text=help_text,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Home", callback_data="start")]
            ])
        )
    except Exception as e:
        logger.exception("Error in metadata help command:")
        await message.reply_text("An error occurred. Please try again later.")

@Client.on_message(filters.command("setaudiometadata"))
async def set_audio_metadata(client, message):
    try:
        if len(message.command) == 1:
            return await message.reply_text(
                "**Please provide audio metadata:\n\n"
                "Format: /setaudiometadata Title | Artist | Album | Genre | Author**"
            )
        
        metadata = message.text.split(" ", 1)[1].split("|")
        metadata = [m.strip() if m.strip() else DEFAULT_METADATA for m in metadata + [''] * 5][:5]
        
        user_id = message.from_user.id
        await db.set_atitle(user_id, metadata[0])
        await db.set_artist(user_id, metadata[1])
        await db.set_aalbum(user_id, metadata[2])  # Using audio field for album
        await db.set_agenre(user_id, metadata[3])  # Using subtitle field for genre
        await db.set_aauthor(user_id, metadata[4])
        
        await message.reply_text("**✅ Audio Metadata Saved Successfully**")
    except Exception as e:
        logger.exception("Error in setaudiometadata command:")
        await message.reply_text("An error occurred while setting audio metadata.")

@Client.on_message(filters.command("setvideometadata"))
async def set_video_metadata(client, message):
    try:
        if len(message.command) == 1:
            return await message.reply_text(
                "**Please provide video metadata:\n\n"
                "Format: /setvideometadata VideoTitle | VideoName | AudioName | Subtitles**"
            )
        
        metadata = message.text.split(" ", 1)[1].split("|")
        metadata = [m.strip() if m.strip() else DEFAULT_METADATA for m in metadata + [''] * 4][:4]
        
        user_id = message.from_user.id
        await db.set_title(user_id, metadata[5])
        await db.set_video(user_id, metadata[6])
        await db.set_audio(user_id, metadata[7])
        await db.set_subtitle(user_id, metadata[8])
        
        await message.reply_text("**✅ Video Metadata Saved Successfully**")
    except Exception as e:
        logger.exception("Error in setvideometadata command:")
        await message.reply_text("An error occurred while setting video metadata.")

@Client.on_message(filters.command("setallfilemetadata"))
async def set_all_metadata(client, message):
    try:
        if len(message.command) == 1:
            return await message.reply_text(
                "**Please provide all metadata:\n\n"
                "Format: /setallfilemetadata AudioTitle | Artist | Album | Genre | Author | "
                "VideoTitle | VideoName | AudioName | Subtitles**"
            )
        
        metadata = message.text.split(" ", 1)[1].split("|")
        metadata = [m.strip() if m.strip() else DEFAULT_METADATA for m in metadata + [''] * 9][:9]
        
        user_id = message.from_user.id
        # Audio metadata
        await db.set_atitle(user_id, metadata[0])
        await db.set_artist(user_id, metadata[1])
        await db.set_aalbum(user_id, metadata[2])  # Using audio field for album
        await db.set_agenre(user_id, metadata[3])  # Using subtitle field for genre
        await db.set_aauthor(user_id, metadata[4])
        # Video metadata
        await db.set_title(user_id, metadata[5])
        await db.set_video(user_id, metadata[6])
        await db.set_audio(user_id, metadata[7])
        await db.set_subtitle(user_id, metadata[8])
        
        await message.reply_text("**✅ All Metadata Saved Successfully**")
    except Exception as e:
        logger.exception("Error in setallfilemetadata command:")
        await message.reply_text("An error occurred while setting all metadata.")
