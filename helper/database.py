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
            bool_metadata=False,     # Changed to match metadata.py
            metadata_code="Release Name"  # Default metadata code
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

    # Metadata methods exactly matching metadata.py requirements
    async def set_metadata(self, user_id, bool_meta):
        """Set metadata enabled/disabled status for a user"""
        await self.col.update_one(
            {'_id': int(user_id)},
            {'$set': {'bool_metadata': bool_meta}},  # Changed to bool_metadata to match usage
            upsert=True
        )

    async def get_metadata(self, user_id):
        """Get metadata status for a user"""
        user = await self.col.find_one({'_id': int(user_id)})
        if not user:
            user = self.new_user(user_id)
            await self.col.insert_one(user)
            return False
        return user.get('bool_metadata', False)  # Changed to bool_metadata to match usage

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

madflixbotz = Database(Config.DB_URL, Config.DB_NAME)

# Jishu Developer 
# Don't Remove Credit 🥺
# Telegram Channel @Madflix_Bots
# Developer @JishuDeveloper
