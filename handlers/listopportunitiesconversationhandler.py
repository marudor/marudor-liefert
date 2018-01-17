from telegram.bot import Bot
from telegram.ext.callbackqueryhandler import CallbackQueryHandler
from telegram.ext.commandhandler import CommandHandler
from telegram.ext.conversationhandler import ConversationHandler
from telegram.ext.regexhandler import RegexHandler
from telegram.inline.inlinekeyboardbutton import InlineKeyboardButton
from telegram.inline.inlinekeyboardmarkup import InlineKeyboardMarkup
from telegram.parsemode import ParseMode
from telegram.update import Update
from decorators import MarudorOnly

from models import Opportunity


class ListOpportunitiesConversationHandler(ConversationHandler):
    CONFIRM_DELETION = 0

    def __init__(self, app):
        self.app = app

        super().__init__(
            entry_points=[
                CommandHandler("listops", self.command_listops),
                RegexHandler("/showorders_(\d+)", self.command_showorders, pass_groups=True),
                RegexHandler("/deleteop_(\d+)", self.command_deleteop, pass_groups=True, pass_user_data=True)
            ],
            states={
                self.CONFIRM_DELETION: [
                    CallbackQueryHandler(self.handle_delete_confirmation, pattern="deleteop_", pass_user_data=True)
                ]
            },
            fallbacks=[
            ]
        )

    @MarudorOnly
    def command_listops(self, bot: Bot, update: Update):
        opportunities = Opportunity.in_future_or_today().get()

        if opportunities.count() == 0:
            text = "Es gibt aktuell keine eingetragenen Reisen."
        else:
            text = "Welche Bestellungen möchtest du einsehen?"

        for op in opportunities:
            text += "\n\nAm %s nach <strong>%s</strong>" \
                    "\n<em>Zeige Bestellungen</em>: /showorders_%u" \
                    "\n<em>Lösche Reise</em>: /deleteop_%u" % (
                        op.date.strftime("%d.%m.%Y"),
                        op.city,
                        op.id,
                        op.id
                    )

        update.message.reply_text(text, parse_mode=ParseMode.HTML)

    @MarudorOnly
    def command_showorders(self, bot: Bot, update: Update, groups):
        opportunity_id = groups[0]

        opportunity = Opportunity.find(opportunity_id)
        orders = opportunity.orders

        if orders.count() == 0:
            text = "Bisher gibt es keine Bestellungen für deine Reise am %s nach <strong>%s</strong>" % (
                opportunity.date_readable(),
                opportunity.city
            )
        else:
            text = "Bestellungen für deine Reise am %s nach <strong>%s</strong>\n" % (
                opportunity.date_readable(),
                opportunity.city
            )

        for order in orders:
            text += "\n▶︎ @%s: %s" % (
                order.user.telegram_username,
                order.order_text
            )

        update.message.reply_text(text, parse_mode=ParseMode.HTML)

    def command_deleteop(self, bot: Bot, update: Update, groups, user_data):
        opportunity_id = groups[0]

        opportunity = Opportunity.find(opportunity_id)

        if not opportunity:
            update.message.reply_text("Es gibt keine Reise mit dieser ID.")
            return self.END

        user_data["delete_opportunity_id"] = opportunity_id

        text = "Bist du dir sicher, dass du deine Reise am %s nach <strong>%s</strong> absagen möchtest?" % (
            opportunity.date_readable(),
            opportunity.city
        )

        reply = update.message.reply_text(text,
                                          parse_mode=ParseMode.HTML,
                                          reply_markup=InlineKeyboardMarkup(
                                              [[InlineKeyboardButton("Ja, sage die Reise ab",
                                                                     callback_data="deleteop_confirm")],
                                               [InlineKeyboardButton("Nein", callback_data="deleteop_cancel")]])
                                          )

        user_data["message_id"] = reply.message_id

        return self.CONFIRM_DELETION

    def handle_delete_confirmation(self, bot: Bot, update: Update, user_data):
        if update.callback_query.data == "deleteop_confirm":
            opportunity_id = user_data["delete_opportunity_id"]

            opportunity = Opportunity.find(opportunity_id)

            # Benachrichtige Menschen, die bestellt haben
            text = "@marudor hat seine Reise am %s nach <strong>%s</strong> leider abgesagt.\nDeine Bestellung wurde storniert." % (
                opportunity.date_readable(),
                opportunity.city
            )

            for order in opportunity.orders:
                user_id = order.user.telegram_user_id
                bot.sendMessage(user_id, text, parse_mode=ParseMode.HTML)

            opportunity.orders().delete()
            opportunity.delete()

            bot.edit_message_text(chat_id=update.effective_chat.id, message_id=user_data["message_id"],
                                  text="Die Reise wurde entfernt.")
        else:
            bot.edit_message_text(chat_id=update.effective_chat.id, message_id=user_data["message_id"],
                                  text="Ich habe die Reise nicht entfernt.")

        return self.END
