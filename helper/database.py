import motor.motor_asyncio
from config import Config
from .utils import send_log

class Database:

    def __init__(self, uri, database_name):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.madflixbotz = self._client[database_name]
        self.col = self.madflixbotz.user

    def new_user(self, id):
        return dict(
            _id=int(id),
            file_id=None,
            caption=None,
            format_template=None,
            bool_metadata="Off",  # Default to "Off" to match metadata.py
            metadata_code="Release Name",
            title=None,
            author=None,
            artist=None,
            video=None,
            audio=None,
            subtitle=None,
            audio_artist=None,
            audio_title=None,
            audio_genre=None,
            audio_album=None
        )

    async def add_user(self, b, m):
        u = m.from_user
        if not await self.is_user_exist(u.id):
            user = self.new_user(u.id)
            await self.col.insert_one(user)
            await send_log(b, u)

    async def is_user_exist(self, id):
        user = await self.col.find_one({'_id': int(id)})
        return bool(user)

    async def total_users_count(self):
        count = await self.col.count_documents({})
        return count

    async def get_all_users(self):
        all_users = self.col.find({})
        return all_users

    async def delete_user(self, user_id):
        await self.col.delete_many({'_id': int(user_id)})

    async def set_thumbnail(self, id, file_id):
        await self.col.update_one({'_id': int(id)}, {'$set': {'file_id': file_id}})

    async def get_thumbnail(self, id):
        user = await self.col.find_one({'_id': int(id)})
        return user.get('file_id', None)

    async def set_caption(self, id, caption):
        await self.col.update_one({'_id': int(id)}, {'$set': {'caption': caption}})

    async def get_caption(self, id):
        user = await self.col.find_one({'_id': int(id)})
        return user.get('caption', None)

    async def set_format_template(self, id, format_template):
        await self.col.update_one({'_id': int(id)}, {'$set': {'format_template': format_template}})

    async def get_format_template(self, id):
        user = await self.col.find_one({'_id': int(id)})
        return user.get('format_template', None)
        
    async def set_media_preference(self, id, media_type):
        await self.col.update_one({'_id': int(id)}, {'$set': {'media_type': media_type}})
        
    async def get_media_preference(self, id):
        user = await self.col.find_one({'_id': int(id)})
        return user.get('media_type', None)

    # Metadata functions updated to match metadata.py
    async def set_metadata(self, user_id, status):
        """Set metadata On or Off for a user"""
        await self.col.update_one(
            {'_id': int(user_id)},
            {'$set': {'bool_metadata': status}},  # Store as "On"/"Off"
            upsert=True
        )

    async def get_metadata(self, user_id):
        """Get metadata status for a user (On/Off)"""
        user = await self.col.find_one({'_id': int(user_id)})
        if not user:
            user = self.new_user(user_id)
            await self.col.insert_one(user)
            return "Off"  # Default to "Off"
        return user.get('bool_metadata', "Off")

    async def set_metadata_code(self, user_id, metadata_code):
        """Set custom metadata code for a user"""
        await self.col.update_one(
            {'_id': int(user_id)},
            {'$set': {'metadata_code': metadata_code}},
            upsert=True
        )

    async def get_metadata_code(self, user_id):
        """Get custom metadata code for a user"""
        user = await self.col.find_one({'_id': int(user_id)})
        if not user:
            user = self.new_user(user_id)
            await self.col.insert_one(user)
            return "Release Name"
        return user.get('metadata_code', "Release Name")

    # Additional metadata fields (Title, Author, Artist, Video, Audio, Subtitle)
    async def set_title(self, user_id, title):
        await self.col.update_one({'_id': int(user_id)}, {'$set': {'title': title}}, upsert=True)

    async def get_title(self, user_id):
        user = await self.col.find_one({'_id': int(user_id)})
        return user.get('title', None)

    async def set_author(self, user_id, author):
        await self.col.update_one({'_id': int(user_id)}, {'$set': {'author': author}}, upsert=True)

    async def get_author(self, user_id):
        user = await self.col.find_one({'_id': int(user_id)})
        return user.get('author', None)

    async def set_artist(self, user_id, artist):
        await self.col.update_one({'_id': int(user_id)}, {'$set': {'artist': artist}}, upsert=True)

    async def get_artist(self, user_id):
        user = await self.col.find_one({'_id': int(user_id)})
        return user.get('artist', None)

    async def set_video(self, user_id, video):
        await self.col.update_one({'_id': int(user_id)}, {'$set': {'video': video}}, upsert=True)

    async def get_video(self, user_id):
        user = await self.col.find_one({'_id': int(user_id)})
        return user.get('video', None)

    async def set_audio(self, user_id, audio):
        await self.col.update_one({'_id': int(user_id)}, {'$set': {'audio': audio}}, upsert=True)

    async def get_audio(self, user_id):
        user = await self.col.find_one({'_id': int(user_id)})
        return user.get('audio', None)

    async def set_subtitle(self, user_id, subtitle):
        await self.col.update_one({'_id': int(user_id)}, {'$set': {'subtitle': subtitle}}, upsert=True)

    async def get_subtitle(self, user_id):
        user = await self.col.find_one({'_id': int(user_id)})
        return user.get('subtitle', None)

    # Audio metadata fields (Artist, Title, Genre, Album)
    async def set_audio_info(self, user_id, artist, title, genre, album):
        """Set audio metadata for a user"""
        await self.col.update_one(
            {'_id': int(user_id)},
            {'$set': {
                'audio_artist': artist,
                'audio_title': title,
                'audio_genre': genre,
                'audio_album': album
            }},
            upsert=True
        )

    async def get_audio_info(self, user_id):
        """Get audio metadata for a user"""
        user = await self.col.find_one({'_id': int(user_id)})
        if not user:
            user = self.new_user(user_id)
            await self.col.insert_one(user)
            return None
        return {
            'artist': user.get('audio_artist', None),
            'title': user.get('audio_title', None),
            'genre': user.get('audio_genre', None),
            'album': user.get('audio_album', None)
        }

madflixbotz = Database(Config.DB_URL, Config.DB_NAME)
