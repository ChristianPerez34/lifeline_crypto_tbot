from tortoise import fields
from tortoise.models import Model


class TelegramGroupMember(Model):
    id = fields.IntField(pk=True)
    bsc_address = fields.TextField(null=True)
    bsc_private_key = fields.TextField(null=True)
    kucoin_api_key = fields.TextField(null=True)
    kucoin_api_secret = fields.TextField(null=True)
    kucoin_api_passphrase = fields.TextField(null=True)
