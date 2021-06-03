from tortoise import fields
from tortoise.models import Model, MODEL


class TelegramGroupMember(Model):
    id = fields.IntField(pk=True)
    bsc_address = fields.TextField(null=True)
    bsc_private_key = fields.TextField(null=True)
    kucoin_api_key = fields.TextField(null=True)
    kucoin_api_secret = fields.TextField(null=True)
    kucoin_api_passphrase = fields.TextField(null=True)

    async def create_or_update(self, data: dict) -> MODEL:
        _id = data.get('id', None)
        member = await self.get_or_none(id=_id)

        if member:
            member = await member.update_from_dict(data=data)
            await member.save()
        else:
            member = await self.create(**data)
        return member
