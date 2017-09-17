from telegram.ext.conversationhandler import ConversationHandler


class marudor_only:
    def __init__(self, method):
        self.method = method

    def __get__(self, instance, owner):
        self.instance = instance
        return self

    def __call__(self, *args, **kwargs):
        update = args[1]  # type: Update
        if marudor_only.is_marudor(update.effective_user.username):
            return self.method(self.instance, *args, **kwargs)

        else:
            update.message.reply_text(
                "Dieser Befehl ist nur für @marudor... Oder willst du auch anfangen Franzbrötchen in die Welt zu liefern? ;)")
            return ConversationHandler.END

    @classmethod
    def is_marudor(cls, username):
        return username == "marudor" or username == "TiiRex9"
