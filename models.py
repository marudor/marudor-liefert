import yaml
from orator import Model
from orator.database_manager import DatabaseManager
from orator.orm.utils import has_many, has_one, scope, belongs_to


def get_db():
    config = yaml.load(open("orator.yaml"))
    return DatabaseManager(config["databases"])


Model.set_connection_resolver(get_db())


class Opportunity(Model):
    __fillable__ = ["city", "date"]
    __dates__ = ["date"]

    @scope
    def in_future(self, query):
        return query.where_raw("date >= datetime('now')").order_by("date", "asc")

    @scope
    def in_future_or_today(self, query):
        return query.where_raw("date >= date('now')").order_by("date", "asc")

    @classmethod
    def for_city(cls, city):
        return cls.where_city(city).in_future().get()

    def date_readable(self):
        return self.date.strftime("%d.%m.%Y")

    @has_many
    def orders(self):
        return Order


class Order(Model):
    __fillable__ = ["user_id", "opportunity_id", "order_text"]

    @scope
    def is_open(self, query):
        return query.where_has("opportunity", lambda q: q.where_raw("date >= date('now')"))

    @belongs_to
    def user(self):
        return User

    @belongs_to
    def opportunity(self):
        return Opportunity


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
