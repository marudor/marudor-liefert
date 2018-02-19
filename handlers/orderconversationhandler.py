
from telegram.bot import Bot
from telegram.ext.conversationhandler import ConversationHandler
from telegram.ext.filters import Filters
from telegram.ext.messagehandler import MessageHandler
from telegram.ext.regexhandler import RegexHandler
from telegram.update import Update

from models import User, Opportunity, Order


class OrderConversationHandler(ConversationHandler):
    WAIT_FOR_ORDER_TEXT = range(1)

    def __init__(self, app):
        self.app = app

        super().__init__(
            entry_points=[
                RegexHandler("/order_(\d+)", self.command_order, pass_groups=True, pass_user_data=True),
            ],
            states={
                self.WAIT_FOR_ORDER_TEXT: [
                    MessageHandler(Filters.text, self.handle_neworder_text, pass_user_data=True)
                ]
            },
            fallbacks=[

            ]
        )

    def command_order(self, bot: Bot, update: Update, groups, user_data):
        opportunity_id = groups[0]

        user = User.where_telegram_user_id(update.effective_user.id).first()
        if not user:
            return

        opportunity = Opportunity.find(opportunity_id)
        if not opportunity:
            return

        user_data["neworder"] = Order.first_or_new(
            user_id=user.id,
            opportunity_id=opportunity_id
        )

        update.message.reply_text("Du möchtest eine Bestellung für den %s für %s machen.\n\n"
                                  "Wieviele - und welche - Franzbrötchen möchtest du bestellen?" % (
                                      opportunity.date.format("%d.%m.%Y"), opportunity.city))
        update.message.reply_text("Spendenempfehlung sind 1,5€ für ein normales Franzbrötchen. 2€ für ein Special Franzbrötchen.\n"
                                  "Gerne per https://www.paypal.me/marudor überweisen!")
        return self.WAIT_FOR_ORDER_TEXT

    def handle_neworder_text(self, bot: Bot, update: Update, user_data):
        order = user_data["neworder"]
        order.order_text = update.message.text
        order.save()

        user_data.clear()

        update.message.reply_text("Deine Bestellung wurde gespeichert.")
        return self.END
