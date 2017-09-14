import json
import logging
from datetime import datetime
from threading import Thread

import yaml
from orator.database_manager import DatabaseManager
from orator.orm.model import Model
from telegram.bot import Bot
from telegram.callbackquery import CallbackQuery
from telegram.error import TelegramError
from telegram.ext.callbackqueryhandler import CallbackQueryHandler
from telegram.ext.commandhandler import CommandHandler
from telegram.ext.conversationhandler import ConversationHandler
from telegram.ext.dispatcher import Dispatcher
from telegram.ext.filters import Filters
from telegram.ext.messagehandler import MessageHandler
from telegram.ext.regexhandler import RegexHandler
from telegram.ext.updater import Updater
from telegram.inline.inlinekeyboardbutton import InlineKeyboardButton
from telegram.inline.inlinekeyboardmarkup import InlineKeyboardMarkup
from telegram.keyboardbutton import KeyboardButton
from telegram.parsemode import ParseMode
from telegram.replykeyboardmarkup import ReplyKeyboardMarkup
from telegram.replykeyboardremove import ReplyKeyboardRemove
from telegram.update import Update

from models import User, Opportunity, Order

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


class marudor_only:
    def __init__(self, method):
        self.method = method

    def __get__(self, instance, owner):
        self.instance = instance
        return self

    def __call__(self, *args, **kwargs):
        update = args[1]  # type: Update
        if marudor_only.is_marudor(update.effective_user.username) or update.effective_user.username == "TiiRex9":
            return self.method(self.instance, *args, **kwargs)
        else:
            update.message.reply_text(
                "Dieser Befehl ist nur für @marudor... Oder willst du auch anfangen Franzbrötchen in die Welt zu liefern? ;)")
            return ConversationHandler.END

    @classmethod
    def is_marudor(cls, username):
        return username == "marudor"


class CreateUserConversation:
    WAIT_FOR_HOMETOWN = 0


class CreateOpConversation:
    WAIT_FOR_DATE = 1
    WAIT_FOR_CITY = 2
    CONFIRM_CITY = 3
    WHAT_TO_DO = 4


class OrderConversation:
    WAIT_FOR_ORDER_TEXT = 5


class NextActionKeyboard:
    NEUE_REISE = "Nächste Reise eintragen"
    FERTIG = "Fertig"


class MarudorLiefertBot:
    def __init__(self):
        self.config = json.load(open("config.json"))

        self.db = load_db()

        updater = Updater(self.config["api_token"])
        self.bot = updater.bot
        dp = updater.dispatcher  # type: Dispatcher

        dp.add_handler(ConversationHandler(
            entry_points=[
                CommandHandler("start", self.command_start),
                CommandHandler("changehometown", self.command_changehometown),
                CommandHandler("newop", self.command_newop),
                RegexHandler("/order_(\d+)", self.command_order, pass_groups=True, pass_user_data=True),
                MessageHandler(Filters.text, self.handle_fetch_op)
            ],
            states={
                CreateUserConversation.WAIT_FOR_HOMETOWN: [
                    MessageHandler(Filters.text, self.handle_hometown)
                ],

                CreateOpConversation.WAIT_FOR_DATE: [
                    MessageHandler(Filters.text, self.handle_newop_date, pass_user_data=True)
                ],
                CreateOpConversation.WAIT_FOR_CITY: [
                    MessageHandler(Filters.text, self.handle_newop_city, pass_user_data=True)
                ],
                CreateOpConversation.CONFIRM_CITY: [
                    CallbackQueryHandler(self.handle_newop_city_confirmation, pattern="city_", pass_user_data=True)
                ],
                CreateOpConversation.WHAT_TO_DO: [
                    MessageHandler(Filters.text, self.handle_next_action, pass_user_data=True)
                ],

                OrderConversation.WAIT_FOR_ORDER_TEXT: [
                    MessageHandler(Filters.text, self.handle_neworder_text, pass_user_data=True)
                ]
            },
            fallbacks=[
                CommandHandler("cancel", self.command_cancel, pass_user_data=True)
            ]
        ))

        dp.add_error_handler(self.handle_error)

        updater.start_polling()
        updater.idle()

    def command_start(self, bot: Bot, update: Update):
        t_user = update.effective_user
        if marudor_only.is_marudor(t_user.username):
            update.message.reply_text("Hallo @marudor. Was kann ich für dich tun?")
            return ConversationHandler.END

        user = User.telegram(t_user.id)
        if user:
            opportunities = Opportunity.for_me(user)
            if (t_user.username):
                text = "Willkommen zurück, @%s\n\n" % t_user.username
            else:
                text = "Willkommen zurück.\n\n"

            if opportunities.count() > 0:
                text += "@marudor kommt an folgenden Tagen in deine Stadt:"
            else:
                text += "@marudor hat keine Besuche in <strong>%s</strong> für die nächste Zeit geplant." % user.hometown

            for op in opportunities:
                text += "\n%s - Bestelle mit /order_%u" % (op.date.strftime("%d.%m.%Y"), op.id)

            update.message.reply_text(text, parse_mode=ParseMode.HTML)
            return ConversationHandler.END

        update.message.reply_text("Willkommen bei @marudor's Franzbrötchen Lieferservice\n\n"
                                  "Sag mir wo du wohnst, damit ich dich benachrichtigen kann, wenn @marudor in deine Stadt kommt.",
                                  reply_markup=self.generate_cities_keyboard())

        return CreateUserConversation.WAIT_FOR_HOMETOWN

    def handle_hometown(self, bot: Bot, update: Update):
        message = update.message  # type: Message
        hometown = message.text

        user = User.update_or_create(
            attributes={
                "telegram_user_id": message.from_user.id
            },
            values={
                "telegram_username": message.from_user.username,
                "hometown": hometown
            }
        )

        text = "Deine Daten wurden gespeichert.\n\n"
        opportunities = Opportunity.for_me(user)
        if opportunities.count() == 0:
            text += "Aktuell sind keine Bestellmöglichkeiten verfügbar. Ich werde dich benachrichtigen, wenn es soweit ist."
        else:
            text += "@marudor kommt an folgenden Tagen in deine Stadt:\n"

        for op in opportunities:
            text += "<strong>%s</strong>: Bestelle mit /order_%s\n" % (op.date.strftime("%d.%m.%Y"), op.id)

        update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    def command_changehometown(self, bot: Bot, update: Update):
        update.message.reply_text(
            "Sag mir wo du wohnst, damit ich dich benachrichtigen kann, wenn @marudor in deine Stadt kommt.",
            reply_markup=self.generate_cities_keyboard())
        return CreateUserConversation.WAIT_FOR_HOMETOWN

    @marudor_only
    def command_newop(self, bot: Bot, update: Update):
        update.message.reply_text(
            "An welchem Tag bist du unterwegs? (Verwende das Format <em>dd.mm.yyyy</em>)",
            parse_mode=ParseMode.HTML)
        return CreateOpConversation.WAIT_FOR_DATE

    def handle_newop_date(self, bot: Bot, update: Update, user_data):
        text = update.message.text  # type: str

        today = datetime.now()

        segments = text.strip(".").split(".", 2)
        valid_date = True
        try:
            day = int(segments[0])
        except IndexError:
            day = today.day
        except ValueError:
            valid_date = False

        try:
            month = int(segments[1])
        except IndexError:
            month = today.month if day >= today.day else today.month + 1
        except ValueError:
            valid_date = False

        try:
            year = segments[2]
            if len(year) == 2:
                year = int("20%s" % year)
        except IndexError:
            year = today.year
        except ValueError:
            valid_date = False

        if not valid_date:
            update.message.reply_text(
                "Ich hab keine Ahnung wovon du redest. Dir ist schon klar, dass ich ein Datum von dir wollte, oder? Probier's bitte nochmal!")
            return

        date = datetime(year, month, day)

        if date < today:
            update.message.reply_text(
                "Solange noch keine Zeitmaschinen erfunden wurden, kannst du keine Reisen in der Vergangenheit anlegen.")
            return

        user_data["newop"] = Opportunity(
            date=date
        )

        keyboard = self.generate_cities_keyboard()
        update.message.reply_text("In welche Stadt bist du am %s unterwegs?" % date.strftime("%d.%m.%Y"),
                                  reply_markup=keyboard)
        return CreateOpConversation.WAIT_FOR_CITY

    def generate_cities_keyboard(self):
        # select distinct hometown as city from users union select distinct city from opportunities order by city asc;
        op_cities = self.db.table("opportunities").distinct().select("city")
        cities = self.db.table("users").distinct().select("hometown as city").union(op_cities).order_by("city",
                                                                                                        "asc").get()

        keyboard = []
        for c in cities:
            keyboard.append([KeyboardButton(c.city)])

        return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)

    def handle_newop_city(self, bot: Bot, update: Update, user_data):
        text = update.message.text

        user_data["newop"].city = text

        city_user_count = User.where_hometown(text).count()
        city_has_subscribers = city_user_count == 0
        if city_has_subscribers:
            reply = update.message.reply_text(
                "Niemand wohnt in diesem Ort. Möchtest du die Reise trotzdem eintragen?",
                reply_markup=self.generate_yesno_inlinekeyboard())
            user_data["confirm_city_mid"] = reply.message_id
            return CreateOpConversation.CONFIRM_CITY

        self.save_opportunity(user_data)

        text = "Deine Reise wurde gespeichert."
        if city_has_subscribers:
            text += "\nIch werde jetzt die %u Benutzer in diesem Ort benachrichtigen." % city_user_count

        text += "\n\nWas möchtest du als nächstes tun?"

        keyboard = self.generate_next_action_keyboard()
        update.message.reply_text(text, reply_markup=keyboard)
        return CreateOpConversation.WHAT_TO_DO

    def save_opportunity(self, user_data):
        opportunity = user_data["newop"]
        opportunity.save()

        user_data.clear()

        Thread(target=self.notify_users, args=(opportunity,)).start()

    def generate_yesno_inlinekeyboard(self):
        keyboard = [[InlineKeyboardButton("Ja", callback_data="city_confirm"),
                     InlineKeyboardButton("Nein", callback_data="city_cancel")]]
        return InlineKeyboardMarkup(keyboard)

    def handle_newop_city_confirmation(self, bot: Bot, update: Update, user_data):
        mid = user_data["confirm_city_mid"]
        query = update.callback_query  # type: CallbackQuery
        query.answer()

        if query.data == "city_confirm":
            self.save_opportunity(user_data)

            bot.edit_message_text(chat_id=update.effective_user.id, message_id=mid,
                                  text="Deine Reise wurde gespeichert.")

            keyboard = self.generate_next_action_keyboard()
            bot.sendMessage(chat_id=update.effective_chat.id,
                            text="Was möchtest du als nächstes tun?",
                            reply_markup=keyboard)
            return CreateOpConversation.WHAT_TO_DO

        elif query.data == "city_cancel":
            user_data.clear()
            bot.edit_message_text(chat_id=update.effective_chat.id, message_id=mid,
                                  text="Da niemand in diesem Ort wohnt, habe ich die Reise verworfen.")

            keyboard = self.generate_next_action_keyboard()
            bot.sendMessage(chat_id=update.effective_chat.id,
                            text="Was möchtest du als nächstes tun?",
                            reply_markup=keyboard)
            return CreateOpConversation.WHAT_TO_DO

    def generate_next_action_keyboard(self):
        keyboard = [[KeyboardButton(NextActionKeyboard.NEUE_REISE)],
                    [KeyboardButton(NextActionKeyboard.FERTIG)]]
        return ReplyKeyboardMarkup(keyboard)

    def handle_next_action(self, bot: Bot, update: Update, user_data):
        if update.message.text == NextActionKeyboard.NEUE_REISE:
            update.message.reply_text("Okay, noch eine Reise.\n\n"
                                      "An welchem Tag bist du unterwegs? (Verwende nach Möglichkeit das Format <em>dd.mm.yyyy</em>)",
                                      parse_mode=ParseMode.HTML,
                                      reply_markup=ReplyKeyboardRemove())
            return CreateOpConversation.WAIT_FOR_DATE

        elif update.message.text == NextActionKeyboard.FERTIG:
            update.message.reply_text("Okay, das war's dann.",
                                      reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END

    def notify_users(self, opportunity: Opportunity):
        users = User.where_hometown(opportunity.city).get()
        for u in users:
            self.bot.sendMessage(u.telegram_user_id,
                                 "@marudor ist am %s in %s.\n\n"
                                 "Wenn du eine Franzbrötchen Bestellung vornehmen möchtest, klicke hier: /order_%u" % (
                                     opportunity.date.strftime("%d.%m.%Y"), opportunity.city, opportunity.id))

    def command_order(self, bot: Bot, update: Update, groups, user_data):
        opportunity_id = groups[0]

        user = User.where_telegram_user_id(update.effective_user.id).first()
        if not user:
            return

        opportunity = Opportunity.find(opportunity_id)
        if not opportunity:
            return

        user_data["neworder"] = Order.first_or_new(
            user_id=update.effective_user.id,
            opportunity_id=opportunity_id
        )

        update.message.reply_text("Du möchtest eine Bestellung für den %s für %s machen.\n\n"
                                  "Was möchtest du bestellen?" % (
                                      opportunity.date.format("%d.%m.%Y"), opportunity.city))
        return OrderConversation.WAIT_FOR_ORDER_TEXT

    def handle_neworder_text(self, bot: Bot, update: Update, user_data):
        order = user_data["neworder"]
        order.order_text = update.message.text
        order.save()

        user_data.clear()

        update.message.reply_text("Deine Bestellung wurde gespeichert.")
        return ConversationHandler.END

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

    def command_cancel(self, bot: Bot, update: Update, user_data):
        user_data.clear()
        update.message.reply_text("Okay, wir machen hier nicht weiter.",
                                  reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    def handle_error(self, bot: Bot, update: Update, error: TelegramError):
        raise error


if __name__ == "__main__":
    MarudorLiefertBot()
