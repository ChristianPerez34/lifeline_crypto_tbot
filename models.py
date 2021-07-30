from decimal import Decimal

from pony import orm

db = orm.Database()


class TelegramGroupMember(db.Entity):
    id = orm.PrimaryKey(int, auto=True)
    kucoin_api_key = orm.Optional(str)
    kucoin_api_secret = orm.Optional(str)
    kucoin_api_passphrase = orm.Optional(str)

    bsc = orm.Optional(lambda: BinanceChain)

    @staticmethod
    def get_or_none(primary_key: int) -> db.Entity:
        with orm.db_session:
            try:
                return (
                    orm.select(
                        member
                        for member in TelegramGroupMember
                        if member.id == primary_key
                    )
                    .prefetch(BinanceChain)
                    .first()
                )
            except orm.ObjectNotFound:
                return None

    @orm.db_session
    def create_or_update(self, data: dict) -> db.Entity:
        _id = data.get("id")
        member = self.get_or_none(primary_key=_id)

        if member:
            bsc_data = data.pop("bsc")
            bsc = BinanceChain(**bsc_data)
            data["bsc"] = bsc
            member.set(**data)
        else:
            member = TelegramGroupMember(**data)
        return member


class BinanceChain(db.Entity):
    id = orm.PrimaryKey(int, auto=True)
    address = orm.Required(str)
    private_key = orm.Required(str)

    telegram_group_member = orm.Required(lambda: TelegramGroupMember)


class CryptoAlert(db.Entity):
    id = orm.PrimaryKey(int, auto=True)
    symbol = orm.Required(str)
    sign = orm.Required(str)
    price = orm.Required(Decimal, 36, 18)

    @staticmethod
    def create(data: dict) -> db.Entity:
        with orm.db_session:
            return CryptoAlert(**data)

    @staticmethod
    def all() -> list:
        with orm.db_session:
            return list(CryptoAlert.select())

    @orm.db_session
    def remove(self) -> None:
        CryptoAlert[self.id].delete()
