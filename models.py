from orator import Model
from orator.orm.utils import has_many, has_one


class Opportunity(Model):
    __fillable__ = ["city", "date"]
    __dates__ = ["date"]


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

    def opportunities(self):
        return Opportunity.where_city(self.hometown).all()
