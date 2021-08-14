from decimal import Decimal

from pony import orm

from app import logger

db = orm.Database()


class TelegramGroupMember(db.Entity):
    id = orm.PrimaryKey(int, auto=True)
    kucoin_api_key = orm.Optional(str)
    kucoin_api_secret = orm.Optional(str)
    kucoin_api_passphrase = orm.Optional(str)

    bsc = orm.Optional(lambda: BinanceNetwork)
    orders = orm.Set(lambda: Order)

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
                    .prefetch(BinanceNetwork)
                    .first()
                )
            except orm.ObjectNotFound:
                return None

    @staticmethod
    def create_or_update(data: dict) -> db.Entity:
        _id = data.get("id")
        bsc_data = data.pop("bsc")

        with orm.db_session:
            member = TelegramGroupMember.get_or_none(primary_key=_id)
            if member:
                data.pop("id")
                bsc = BinanceNetwork.get_by_telegram_member_id(
                    telegram_member_id=member.id
                )
                if bsc:
                    bsc_data.pop("id")
                    bsc.set(**bsc_data)
                else:
                    bsc = BinanceNetwork(**bsc_data)
                data["bsc"] = bsc
                member.set(**data)
            else:
                member = TelegramGroupMember(**data)
                member.bsc = BinanceNetwork(**bsc_data)

        return member


class BinanceNetwork(db.Entity):
    id = orm.PrimaryKey(int, auto=True)
    address = orm.Required(str)
    private_key = orm.Required(str)

    telegram_group_member = orm.Required(lambda: TelegramGroupMember)

    @staticmethod
    def get_by_telegram_member_id(telegram_member_id: int) -> db.Entity:
        with orm.db_session:
            try:
                return orm.select(
                    bsc
                    for bsc in BinanceNetwork
                    if bsc.telegram_group_member.id == telegram_member_id
                ).first()
            except orm.ObjectNotFound:
                return None


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


class Order(db.Entity):
    id = orm.PrimaryKey(int, auto=True)
    trade_direction = orm.Required(str)
    address = orm.Required(str)
    target_price = orm.Required(Decimal, 36, 18)
    bnb_amount = orm.Required(Decimal, 36, 18)

    telegram_group_member = orm.Required(lambda: TelegramGroupMember)

    @staticmethod
    def get_or_none(primary_key: int) -> db.Entity:
        logger.info("Retrieving order with id: %d", primary_key)
        with orm.db_session:
            try:
                return (
                    orm.select(order for order in Order if order.id == primary_key)
                    .prefetch(TelegramGroupMember)
                    .prefetch(TelegramGroupMember.bsc)
                    .first()
                )
            except orm.ObjectNotFound:
                return None

    @staticmethod
    def get_orders_by_member_id(telegram_group_member_id: int) -> list:
        logger.info(
            "Getting all orders for user with id: %d}", telegram_group_member_id
        )
        with orm.db_session:
            return list(
                (
                    orm.select(
                        order
                        for order in Order
                        if order.telegram_group_member.id == telegram_group_member_id
                    )
                    .prefetch(TelegramGroupMember)
                    .prefetch(TelegramGroupMember.bsc)
                )
            )

    @staticmethod
    # @orm.db_session
    def create(data: dict) -> db.Entity:
        logger.info("Creating Order")
        with orm.db_session:
            return Order(**data)

    @staticmethod
    def all() -> list:
        with orm.db_session:
            return list(
                Order.select()
                .prefetch(TelegramGroupMember)
                .prefetch(TelegramGroupMember.bsc)
            )

    @orm.db_session
    def remove(self) -> None:
        logger.info("Deleting order with id: %d", self.id)
        Order[self.id].delete()
