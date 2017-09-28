from telegram.bot import Bot
from telegram.ext.commandhandler import CommandHandler
from telegram.ext.conversationhandler import ConversationHandler
from telegram.update import Update

from models import Opportunity


class ListOrderConversationHandler(ConversationHandler):
    def __init__(self, app):
        self.app = app

        super().__init__(
            entry_points=[
                CommandHandler("listorders", self.command_listorders)
            ],
            states={

            },
            fallbacks=[

            ]
        )

    def command_listorders(self, bot: Bot, update: Update):
        opportunities = Opportunity.in_future().get()

        if opportunities.count() == 0:
            text = "Es gibt aktuell keine eingetragenen Reisen."
        else:
            text = "Welche Bestellungen möchtest du einsehen?\n"

        for op in opportunities:
            text += "\n"