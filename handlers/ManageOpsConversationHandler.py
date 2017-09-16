from datetime import datetime
from threading import Thread

from telegram.bot import Bot
from telegram.ext.callbackqueryhandler import CallbackQueryHandler
from telegram.ext.commandhandler import CommandHandler
from telegram.ext.conversationhandler import ConversationHandler
from telegram.ext.filters import Filters
from telegram.ext.messagehandler import MessageHandler
from telegram.inline.inlinekeyboardbutton import InlineKeyboardButton
from telegram.inline.inlinekeyboardmarkup import InlineKeyboardMarkup
from telegram.keyboardbutton import KeyboardButton
from telegram.parsemode import ParseMode
from telegram.replykeyboardmarkup import ReplyKeyboardMarkup
from telegram.replykeyboardremove import ReplyKeyboardRemove
from telegram.update import Update

from decorators import marudor_only
from models import Opportunity, User


class ManageOpsConversationHandler(ConversationHandler):
    WAIT_FOR_DATE, WAIT_FOR_CITY, CONFIRM_CITY, WHAT_TO_DO = range(4)

    NEXT_ACTION_KEYBOARD = {
        "NEUE_REISE": "Nächste Reise eintragen",
        "FERTIG": "Fertig"
    }

    def __init__(self, app):
        self.app = app

        super().__init__(
            entry_points=[
                CommandHandler("newop", self.command_newop),
            ],
            states={
                self.WAIT_FOR_DATE: [
                    MessageHandler(Filters.text, self.handle_newop_date, pass_user_data=True)
                ],
                self.WAIT_FOR_CITY: [
                    MessageHandler(Filters.text, self.handle_newop_city, pass_user_data=True)
                ],
                self.CONFIRM_CITY: [
                    CallbackQueryHandler(self.handle_newop_city_confirmation, pattern="city_", pass_user_data=True)
                ],
                self.WHAT_TO_DO: [
                    MessageHandler(Filters.text, self.handle_next_action, pass_user_data=True)
                ],
            },
            fallbacks=[
                CommandHandler("cancel", self.command_cancel, pass_user_data=True)
            ]
        )

    @marudor_only
    def command_newop(self, bot: Bot, update: Update):
        update.message.reply_text(
            "An welchem Tag bist du unterwegs? (Verwende das Format <em>dd.mm.yyyy</em>)",
            parse_mode=ParseMode.HTML)
        return self.WAIT_FOR_DATE

    def command_cancel(self, bot: Bot, update: Update, user_data):
        user_data.clear()
        update.message.reply_text("Okay, wir machen hier nicht weiter.",
                                  reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

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

        keyboard = self.app.generate_cities_keyboard()
        update.message.reply_text("In welche Stadt bist du am %s unterwegs?" % date.strftime("%d.%m.%Y"),
                                  reply_markup=keyboard)
        return self.WAIT_FOR_CITY

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
            return self.CONFIRM_CITY

        self.save_opportunity(user_data)

        text = "Deine Reise wurde gespeichert."
        if city_has_subscribers:
            text += "\nIch werde jetzt die %u Benutzer in diesem Ort benachrichtigen." % city_user_count

        text += "\n\nWas möchtest du als nächstes tun?"

        keyboard = self.generate_next_action_keyboard()
        update.message.reply_text(text, reply_markup=keyboard)

        return self.WHAT_TO_DO

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
            return self.WHAT_TO_DO

        elif query.data == "city_cancel":
            user_data.clear()
            bot.edit_message_text(chat_id=update.effective_chat.id, message_id=mid,
                                  text="Da niemand in diesem Ort wohnt, habe ich die Reise verworfen.")

            keyboard = self.generate_next_action_keyboard()
            bot.sendMessage(chat_id=update.effective_chat.id,
                            text="Was möchtest du als nächstes tun?",
                            reply_markup=keyboard)
            return self.WHAT_TO_DO

    def handle_next_action(self, bot: Bot, update: Update, user_data):
        if update.message.text == self.NEXT_ACTION_KEYBOARD["NEUE_REISE"]:
            update.message.reply_text("Okay, noch eine Reise.\n\n"
                                      "An welchem Tag bist du unterwegs? (Verwende nach Möglichkeit das Format <em>dd.mm.yyyy</em>)",
                                      parse_mode=ParseMode.HTML,
                                      reply_markup=ReplyKeyboardRemove())
            return self.WAIT_FOR_DATE

        elif update.message.text == self.NEXT_ACTION_KEYBOARD["FERTIG"]:
            update.message.reply_text("Okay, das war's dann.",
                                      reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END

    def save_opportunity(self, user_data):
        opportunity = user_data["newop"]
        opportunity.save()

        user_data.clear()

        Thread(target=self.notify_users, args=(opportunity,)).start()

    def notify_users(self, opportunity: Opportunity):
        users = User.where_hometown(opportunity.city).get()
        for u in users:
            self.bot.sendMessage(u.telegram_user_id,
                                 "@marudor ist am %s in %s.\n\n"
                                 "Wenn du eine Franzbrötchen Bestellung vornehmen möchtest, klicke hier: /order_%u" % (
                                     opportunity.date.strftime("%d.%m.%Y"), opportunity.city, opportunity.id))

    def generate_yesno_inlinekeyboard(self):
        keyboard = [[InlineKeyboardButton("Ja", callback_data="city_confirm"),
                     InlineKeyboardButton("Nein", callback_data="city_cancel")]]
        return InlineKeyboardMarkup(keyboard)

    def generate_next_action_keyboard(self):
        keyboard = [[KeyboardButton(self.NEXT_ACTION_KEYBOARD["NEUE_REISE"])],
                    [KeyboardButton(self.NEXT_ACTION_KEYBOARD["FERTIG"])]]
        return ReplyKeyboardMarkup(keyboard)
