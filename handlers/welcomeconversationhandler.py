from telegram.bot import Bot
from telegram.ext.commandhandler import CommandHandler
from telegram.ext.conversationhandler import ConversationHandler
from telegram.ext.filters import Filters
from telegram.ext.messagehandler import MessageHandler
from telegram.parsemode import ParseMode
from telegram.replykeyboardremove import ReplyKeyboardRemove
from telegram.update import Update
from decorators import MarudorOnly

from models import User, Opportunity
from tools import get_city


class WelcomeConversationHandler(ConversationHandler):
    WAIT_FOR_HOMETOWN = 0

    def __init__(self, app):
        self.app = app

        super().__init__(
            entry_points=[
                CommandHandler("start", self.command_start, pass_user_data=True),
                CommandHandler("changehometown", self.command_changehometown)
            ],
            states={
                self.WAIT_FOR_HOMETOWN: [
                    MessageHandler(Filters.text | Filters.location, self.handle_hometown, pass_user_data=True),
                ],
            },
            fallbacks=[

            ]
        )

    def command_start(self, bot: Bot, update: Update, user_data):
        t_user = update.effective_user
        if MarudorOnly.is_marudor(t_user.username):
            return self.start_marudor(bot, update)


        user = User.telegram(t_user.id)
        if user:
            return self.start_existing_user(bot, update, user)

        return self.start_new_user(bot, update, user_data)

    def start_marudor(self, bot: Bot, update: Update):
        text = "Hallo @marudor."
        text += self.generate_command_intro(is_marudor=True)

        update.message.reply_text(text, parse_mode=ParseMode.HTML)
        return self.END

    def start_existing_user(self, bot: Bot, update: Update, user):
        t_user = update.effective_user
        opportunities = Opportunity.for_city(user.hometown)
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

        text += self.generate_command_intro()

        update.message.reply_text(text, parse_mode=ParseMode.HTML)
        return self.END

    def start_new_user(self, bot: Bot, update: Update, user_data):
        update.message.reply_text("Willkommen bei @marudor's Franzbrötchen Lieferservice\n\n"
                                  "Sag mir wo du wohnst, damit ich dich benachrichtigen kann, wenn @marudor in deine Stadt kommt.\n"
                                  "Du kannst mir auch deinen aktuellen Standort schicken.",
                                  reply_markup=self.app.generate_cities_keyboard())
        user_data["new_user"] = True
        return self.WAIT_FOR_HOMETOWN


    def command_changehometown(self, bot: Bot, update: Update):
        update.message.reply_text(
            "Sag mir wo du wohnst, damit ich dich benachrichtigen kann, wenn @marudor in deine Stadt kommt.\n"
            "Du kannst mir auch deinen aktuellen Standort schicken.",
            reply_markup=self.app.generate_cities_keyboard())
        return self.WAIT_FOR_HOMETOWN

    def handle_hometown(self, bot: Bot, update: Update, user_data):
        message = update.message  # type: Message

        if message.location:
            hometown = get_city(message.location.latitude, message.location.longitude)
        else:
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

        text = "Okay. Du wohnst in <strong>%s</strong>.\n\n" % hometown
        opportunities = Opportunity.for_city(user.hometown)
        if opportunities.count() == 0:
            text += "Aktuell sind keine Bestellmöglichkeiten verfügbar. Ich werde dich benachrichtigen, wenn es soweit ist."
        else:
            text += "@marudor kommt an folgenden Tagen in deine Stadt:\n"

        for op in opportunities:
            text += "<strong>%s</strong>: Bestelle mit /order_%s\n" % (op.date.strftime("%d.%m.%Y"), op.id)

        if "new_user" in user_data:
            del user_data["new_user"]
            text += self.generate_command_intro()

        update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=ReplyKeyboardRemove())
        return self.END

    def generate_command_intro(self, is_marudor=False):
        text =  """

Du kannst folgende Befehle ausführen:
/changehometown - Ändert den Ort zu dem du benachrichtigt wirst."""

        if is_marudor:
            text += """

<strong>Für @marudor:</strong>
/newop - Trage eine neue Reise ein.
/listops - Liste ausstehende Reisen auf"""

        return text
