from tortoise import fields
from tortoise.models import Model


class TelegramGroupMember(Model):
    id = fields.IntField(pk=True)
    telegram_user_id = fields.IntField(unique=True)
    bsc_address = fields.TextField()
    bsc_private_key = fields.BinaryField()
