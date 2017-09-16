import yaml
from orator import Model
from orator.database_manager import DatabaseManager
from orator.orm.utils import has_many, has_one, scope


def get_db():
    config = yaml.load(open("orator.yaml"))
    return DatabaseManager(config["databases"])


Model.set_connection_resolver(get_db())


class Opportunity(Model):
    __fillable__ = ["city", "date"]
    __dates__ = ["date"]

    @scope
    def in_future(self, query):
        return query.where_raw("date >= datetime('now')")

    @classmethod
    def for_city(cls, city):
        return cls.where_city(city).in_future().get()


class Order(Model):
    __fillable__ = ["user_id", "opportunity_id", "order_text"]

    @has_one
    def user(self):
        return User


class User(Model):
    __fillable__ = ["telegram_user_id", "telegram_username", "hometown"]

    @has_many
    def orders(self):
        return Order

    @classmethod
    def telegram(cls, telegram_user_id):
        return cls.where_telegram_user_id(telegram_user_id).first()

    def opportunities(self):
        return Opportunity.where_city(self.hometown).all()
