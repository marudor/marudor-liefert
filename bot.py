import json
import logging

import yaml
from orator.database_manager import DatabaseManager
from orator.orm.model import Model
from telegram.bot import Bot
from telegram.error import TelegramError
from telegram.ext.dispatcher import Dispatcher
from telegram.ext.filters import Filters
from telegram.ext.messagehandler import MessageHandler
from telegram.ext.updater import Updater
from telegram.keyboardbutton import KeyboardButton
from telegram.parsemode import ParseMode
from telegram.replykeyboardmarkup import ReplyKeyboardMarkup
from telegram.update import Update

from handlers.ManageOpsConversationHandler import ManageOpsConversationHandler
from handlers.OrderConversationHandler import OrderConversationHandler
from handlers.WelcomeConversationHandler import WelcomeConversationHandler
from models import Opportunity

"""
Commands:
changehometown - Ändere deinen Wohnort
newop - Trage neue Reise ein (marudor-only)
cancel - Bricht die aktuelle Aktion ab

Todo:
- /deleteop (marudor-only)
- /listorders (marudor-only)
- /myorders
- /notify (marudor-only) (Benachrichtigt alle Nutzer in einer Stadt)
- Bestellschluss
- Send location for detecting hometown
"""

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


def load_db():
    config = yaml.load(open("orator.yaml"))
    db = DatabaseManager(config["databases"])
    Model.set_connection_resolver(db)
    return db


class MarudorLiefertBot:
    def __init__(self):
        self.config = json.load(open("config.json"))

        self.db = load_db()

        updater = Updater(self.config["api_token"])
        dp = updater.dispatcher  # type: Dispatcher

        dp.add_handler(WelcomeConversationHandler(self))
        dp.add_handler(ManageOpsConversationHandler(self, updater.bot))
        dp.add_handler(OrderConversationHandler(self))

        dp.add_handler(MessageHandler(Filters.text, self.handle_fetch_op))

        dp.add_error_handler(self.handle_error)

        updater.start_polling()
        updater.idle()

    def generate_cities_keyboard(self, with_current_location=False):
        # select distinct hometown as city from users union select distinct city from opportunities order by city asc;
        op_cities = self.db.table("opportunities").distinct().select("city")
        cities = self.db.table("users").distinct().select("hometown as city") \
            .union(op_cities).order_by("city", "asc").get()

        keyboard = []

        for c in cities:
            keyboard.append([KeyboardButton(c.city)])

        return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)

    def handle_fetch_op(self, bot: Bot, update: Update):
        city = update.message.text
        opportunities = Opportunity.where_city(city).in_future().get()

        if opportunities.count() > 0:
            text = "@marudor kommt an folgenden Tagen nach <strong>%s</strong>:\n" % city
        else:
            text = "@marudor kommt in nächster Zeit nicht nach <strong>%s</strong>" % city

        for op in opportunities:
            text += "\n%s: Bestelle mit /order_%u" % (op.date.strftime("%d.%m.%Y"), op.id)

        update.message.reply_text(text, parse_mode=ParseMode.HTML)

    def handle_error(self, bot: Bot, update: Update, error: TelegramError):
        raise error


if __name__ == "__main__":
    MarudorLiefertBot()
