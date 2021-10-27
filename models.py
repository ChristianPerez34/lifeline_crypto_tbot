from decimal import Decimal

from pony import orm

from app import logger

db = orm.Database()


class TelegramGroupMember(db.Entity):  # type: ignore
    id = orm.PrimaryKey(int, auto=True)
    kucoin_api_key = orm.Optional(str)
    kucoin_api_secret = orm.Optional(str)
    kucoin_api_passphrase = orm.Optional(str)

    bsc = orm.Optional(lambda: BinanceNetwork)
    eth = orm.Optional(lambda: EthereumNetwork)
    matic = orm.Optional(lambda: MaticNetwork)
    orders = orm.Set(lambda: Order)

    @staticmethod
    def get_or_none(primary_key: int) -> db.Entity:  # type: ignore
        with orm.db_session:
            try:
                return (
                    orm.select(
                        member
                        for member in TelegramGroupMember  # type: ignore
                        if member.id == primary_key
                    )
                    .prefetch(BinanceNetwork)
                    .prefetch(EthereumNetwork)
                    .prefetch(MaticNetwork)
                    .first()
                )
            except orm.ObjectNotFound:
                return None

    @staticmethod
    def create_or_update(data: dict) -> db.Entity:  # type: ignore
        _id = data.get("id")
        bsc_data = data.pop("bsc")
        eth_data = data.pop("eth")
        matic_data = data.pop("matic")

        with orm.db_session:
            member = TelegramGroupMember.get_or_none(primary_key=_id)  # type: ignore
            if member:
                data.pop("id")
                if bsc_data:
                    bsc = BinanceNetwork.get_by_telegram_member_id(
                        telegram_member_id=member.id
                    )
                    if bsc:
                        bsc_data.pop("id")
                        bsc.set(**bsc_data)
                    else:
                        bsc = BinanceNetwork(**bsc_data)
                    data["bsc"] = bsc
                elif eth_data:
                    eth = EthereumNetwork.get_by_telegram_member_id(
                        telegram_member_id=member.id
                    )
                    if eth:
                        eth_data.pop("id")
                        eth.set(**eth_data)
                    else:
                        eth = EthereumNetwork(**eth_data)
                    data["eth"] = eth
                elif matic_data:
                    matic = MaticNetwork.get_by_telegram_member_id(
                        telegram_member_id=member.id
                    )
                    if matic:
                        matic_data.pop("id")
                        matic.set(**matic_data)
                    else:
                        matic = MaticNetwork(**matic_data)
                    data["matic"] = matic
                member.set(**data)
            else:
                member = TelegramGroupMember(**data)
                member.bsc = BinanceNetwork(**bsc_data)

        return member


class BinanceNetwork(db.Entity):  # type: ignore
    id = orm.PrimaryKey(int, auto=True)
    address = orm.Required(str)
    private_key = orm.Required(str)

    telegram_group_member = orm.Required(lambda: TelegramGroupMember)

    @staticmethod
    def get_by_telegram_member_id(telegram_member_id: int) -> db.Entity:  # type: ignore
        with orm.db_session:
            try:
                return orm.select(
                    bsc
                    for bsc in BinanceNetwork  # type: ignore
                    if bsc.telegram_group_member.id == telegram_member_id
                ).first()
            except orm.ObjectNotFound:
                return None


class EthereumNetwork(db.Entity):  # type: ignore
    id = orm.PrimaryKey(int, auto=True)
    address = orm.Required(str)
    private_key = orm.Required(str)

    telegram_group_member = orm.Required(lambda: TelegramGroupMember)

    @staticmethod
    def get_by_telegram_member_id(telegram_member_id: int) -> db.Entity:  # type: ignore
        with orm.db_session:
            try:
                return orm.select(
                    eth
                    for eth in EthereumNetwork  # type: ignore
                    if eth.telegram_group_member.id == telegram_member_id
                ).first()
            except orm.ObjectNotFound:
                return None


class MaticNetwork(db.Entity):  # type: ignore
    id = orm.PrimaryKey(int, auto=True)
    address = orm.Required(str)
    private_key = orm.Required(str)

    telegram_group_member = orm.Required(lambda: TelegramGroupMember)

    @staticmethod
    def get_by_telegram_member_id(telegram_member_id: int) -> db.Entity:  # type: ignore
        with orm.db_session:
            try:
                return orm.select(
                    matic
                    for matic in MaticNetwork  # type: ignore
                    if matic.telegram_group_member.id == telegram_member_id
                ).first()
            except orm.ObjectNotFound:
                return None


class CryptoAlert(db.Entity):  # type: ignore
    id = orm.PrimaryKey(int, auto=True)
    symbol = orm.Required(str)
    coin_id = orm.Required(str)
    sign = orm.Required(str)
    price = orm.Required(Decimal, 36, 18)

    @staticmethod
    def create(data: dict) -> db.Entity:  # type: ignore
        with orm.db_session:
            return CryptoAlert(**data)

    @staticmethod
    def all() -> list:
        with orm.db_session:
            return list(CryptoAlert.select())

    @orm.db_session
    def remove(self) -> None:
        CryptoAlert[self.id].delete()  # type: ignore


class Order(db.Entity):  # type: ignore
    id = orm.PrimaryKey(int, auto=True)
    trade_direction = orm.Required(str)
    address = orm.Required(str)
    target_price = orm.Required(Decimal, 36, 18)
    bnb_amount = orm.Required(Decimal, 36, 18)

    telegram_group_member = orm.Required(lambda: TelegramGroupMember)

    @staticmethod
    def get_or_none(primary_key: int) -> db.Entity:  # type: ignore
        logger.info("Retrieving order with id: %d", primary_key)
        with orm.db_session:
            try:
                return (
                    orm.select(order for order in Order if order.id == primary_key)  # type: ignore
                    .prefetch(TelegramGroupMember)
                    .prefetch(TelegramGroupMember.bsc)
                    .prefetch(TelegramGroupMember.eth)
                    .prefetch(TelegramGroupMember.matic)
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
                        for order in Order  # type: ignore
                        if order.telegram_group_member.id == telegram_group_member_id
                    )
                    .prefetch(TelegramGroupMember)
                    .prefetch(TelegramGroupMember.bsc)
                    .prefetch(TelegramGroupMember.eth)
                    .prefetch(TelegramGroupMember.matic)
                )
            )

    @staticmethod
    # @orm.db_session
    def create(data: dict) -> db.Entity:  # type: ignore
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
                .prefetch(TelegramGroupMember.eth)
                .prefetch(TelegramGroupMember.matic)
            )

    @orm.db_session
    def remove(self) -> None:
        logger.info("Deleting order with id: %d", self.id)
        Order[self.id].delete()  # type: ignore
