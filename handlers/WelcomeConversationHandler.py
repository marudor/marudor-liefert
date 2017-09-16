from telegram.bot import Bot
from telegram.ext.commandhandler import CommandHandler
from telegram.ext.conversationhandler import ConversationHandler
from telegram.ext.filters import Filters
from telegram.ext.messagehandler import MessageHandler
from telegram.parsemode import ParseMode
from telegram.replykeyboardremove import ReplyKeyboardRemove
from telegram.update import Update

from decorators import marudor_only
from models import User, Opportunity
from tools import get_city


class WelcomeConversationHandler(ConversationHandler):
    WAIT_FOR_HOMETOWN = 0

    def __init__(self, app):
        self.app = app

        super().__init__(
            entry_points=[
                CommandHandler("start", self.command_start),
                CommandHandler("changehometown", self.command_changehometown)
            ],
            states={
                self.WAIT_FOR_HOMETOWN: [
                    MessageHandler(Filters.text, self.handle_hometown),
                    MessageHandler(Filters.location, self.handle_hometown)
                ],
            },
            fallbacks=[

            ]
        )

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
                                  reply_markup=self.app.generate_cities_keyboard(with_current_location=True))

        return self.WAIT_FOR_HOMETOWN

    def command_changehometown(self, bot: Bot, update: Update):
        update.message.reply_text(
            "Sag mir wo du wohnst, damit ich dich benachrichtigen kann, wenn @marudor in deine Stadt kommt.",
            reply_markup=self.app.generate_cities_keyboard(with_current_location=True))
        return self.WAIT_FOR_HOMETOWN

    def handle_hometown(self, bot: Bot, update: Update):
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
        opportunities = Opportunity.for_me(user)
        if opportunities.count() == 0:
            text += "Aktuell sind keine Bestellmöglichkeiten verfügbar. Ich werde dich benachrichtigen, wenn es soweit ist."
        else:
            text += "@marudor kommt an folgenden Tagen in deine Stadt:\n"

        for op in opportunities:
            text += "<strong>%s</strong>: Bestelle mit /order_%s\n" % (op.date.strftime("%d.%m.%Y"), op.id)

        update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
