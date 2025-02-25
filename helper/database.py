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
            # Audio metadata fields
            audio_title=None,
            audio_artist=None,
            audio_album=None,
            audio_genre=None,
            audio_author=None,
            # Video metadata fields
            video_title=None,
            video_name=None,
            video_audio_name=None,
            video_subtitles=None,
            # Default metadata value
            default_metadata="@Anime_Onsen | @RDS_BOTS"
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

    # Basic file operations remain unchanged
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
        
    async def set_media_preference(self, id, media_type):
        await self.col.update_one({'_id': int(id)}, {'$set': {'media_type': media_type}})
        
    async def get_media_preference(self, id):
        user = await self.col.find_one({'_id': int(id)})
        return user.get('media_type', None)        

    async def set_format_template(self, id, format_template):
        await self.col.update_one({'_id': int(id)}, {'$set': {'format_template': format_template}})

    async def get_format_template(self, id):
        user = await self.col.find_one({'_id': int(id)})
        return user.get('format_template', None)

    # Enhanced metadata operations for audio files
    async def set_audio_metadata(self, user_id, title=None, artist=None, album=None, genre=None, author=None):
        default = await self.get_default_metadata(user_id)
        update_data = {
            'audio_title': title if title else default,
            'audio_artist': artist if artist else default,
            'audio_album': album if album else default,
            'audio_genre': genre if genre else default,
            'audio_author': author if author else default
        }
        await self.col.update_one({'_id': int(user_id)}, {'$set': update_data}, upsert=True)

    async def get_audio_metadata(self, user_id):
        user = await self.col.find_one({'_id': int(user_id)})
        default = await self.get_default_metadata(user_id)
        return {
            'title': user.get('audio_title', default),
            'artist': user.get('audio_artist', default),
            'album': user.get('audio_album', default),
            'genre': user.get('audio_genre', default),
            'author': user.get('audio_author', default)
        }

    # Enhanced metadata operations for video files
    async def set_video_metadata(self, user_id, title=None, name=None, audio_name=None, subtitles=None):
        default = await self.get_default_metadata(user_id)
        update_data = {
            'video_title': title if title else default,
            'video_name': name if name else default,
            'video_audio_name': audio_name if audio_name else default,
            'video_subtitles': subtitles if subtitles else default
        }
        await self.col.update_one({'_id': int(user_id)}, {'$set': update_data}, upsert=True)

    async def get_video_metadata(self, user_id):
        user = await self.col.find_one({'_id': int(user_id)})
        default = await self.get_default_metadata(user_id)
        return {
            'title': user.get('video_title', default),
            'name': user.get('video_name', default),
            'audio_name': user.get('video_audio_name', default),
            'subtitles': user.get('video_subtitles', default)
        }

    # Default metadata value management
    async def set_default_metadata(self, user_id, value):
        await self.col.update_one(
            {'_id': int(user_id)},
            {'$set': {'default_metadata': value}},
            upsert=True
        )

    async def get_default_metadata(self, user_id):
        user = await self.col.find_one({'_id': int(user_id)})
        return user.get('default_metadata', "@Anime_Onsen | @Matrix_Bots")

    # New methods for compatibility with metadata.py
    async def set_atitle(self, user_id, title):
        await self.col.update_one({'_id': int(user_id)}, {'$set': {'audio_title': title}}, upsert=True)

    async def get_atitle(self, user_id):
        user = await self.col.find_one({'_id': int(user_id)})
        return user.get('audio_title', await self.get_default_metadata(user_id))

    async def set_aalbum(self, user_id, album):
        await self.col.update_one({'_id': int(user_id)}, {'$set': {'audio_album': album}}, upsert=True)

    async def get_aalbum(self, user_id):
        user = await self.col.find_one({'_id': int(user_id)})
        return user.get('audio_album', await self.get_default_metadata(user_id))

    async def set_agenre(self, user_id, genre):
        await self.col.update_one({'_id': int(user_id)}, {'$set': {'audio_genre': genre}}, upsert=True)

    async def get_agenre(self, user_id):
        user = await self.col.find_one({'_id': int(user_id)})
        return user.get('audio_genre', await self.get_default_metadata(user_id))

    async def set_aauthor(self, user_id, author):
        await self.col.update_one({'_id': int(user_id)}, {'$set': {'audio_author': author}}, upsert=True)

    async def get_aauthor(self, user_id):
        user = await self.col.find_one({'_id': int(user_id)})
        return user.get('audio_author', await self.get_default_metadata(user_id))

    # Existing methods remain unchanged
    async def set_video(self, user_id, video):
        await self.set_video_metadata(user_id, name=video)

    async def get_video(self, user_id):
        video_meta = await self.get_video_metadata(user_id)
        return video_meta['name']

    async def set_audio(self, user_id, audio):
        await self.set_video_metadata(user_id, audio_name=audio)

    async def get_audio(self, user_id):
        video_meta = await self.get_video_metadata(user_id)
        return video_meta['audio_name']

    async def set_subtitle(self, user_id, subtitle):
        await self.set_video_metadata(user_id, subtitles=subtitle)

    async def get_subtitle(self, user_id):
        video_meta = await self.get_video_metadata(user_id)
        return video_meta['subtitles']
        
    async def set_title(self, user_id, title):
        await self.col.update_one({'_id': int(user_id)}, {'$set': {'video_title': title}}, upsert=True)

    async def get_title(self, user_id):
        user = await self.col.find_one({'_id': int(user_id)})
        return user.get('video_title', await self.get_default_metadata(user_id))

madflixbotz = Database(Config.DB_URL, Config.DB_NAME)
