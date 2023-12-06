import logging
import g4f
from viberbot import Api
from viberbot.api.bot_configuration import BotConfiguration
from viberbot.api.messages import TextMessage
from viberbot.api.viber_requests import ViberMessageRequest
from config import VIBER_AUTH_TOKEN

logging.basicConfig(level=logging.INFO)


viber = Api(BotConfiguration(
    name='ChatGPTPersonalBotbyVM',
    avatar='https://dl-media.viber.com/1/share/2/long/vibes/icon/image/0x0/7a08/3c87d21eceedb833743a81c19b74cea8c1c3e4ef66e7c86b71d82d16c1147a08.jpg',
    auth_token=VIBER_AUTH_TOKEN
))

conversation_history = {}

def trim_history(history, max_length=4096):
    current_length = sum(len(message["content"]) for message in history)
    while history and current_length > max_length:
        removed_message = history.pop(0)
        current_length -= len(removed_message["content"])
    return history

def message_received_callback(viber_request):
    if isinstance(viber_request, ViberMessageRequest):
        user_id = viber_request.sender.id
        user_input = viber_request.message.text

        viber.send_messages(user_id, [TextMessage(text="Подождите пожалуйста, я обрабатываю ваш запрос...")])

        if user_id not in conversation_history:
            conversation_history[user_id] = []

        conversation_history[user_id].append({"role": "user", "content": user_input})
        conversation_history[user_id] = trim_history(conversation_history[user_id])

        chat_history = conversation_history[user_id]

        try:
            response = g4f.ChatCompletion.create(
                model=g4f.models.default,
                messages=chat_history,
                provider=g4f.Provider.GeekGpt,
            )
            chat_gpt_response = response
        except Exception as e:
            print(f"{g4f.Provider.GeekGpt.__name__}:", e)
            chat_gpt_response = "Извините, произошла ошибка."

        conversation_history[user_id].append({"role": "assistant", "content": chat_gpt_response})
        print(conversation_history)
        length = sum(len(message["content"]) for message in conversation_history[user_id])
        print(length)

        viber.send_messages(user_id, [TextMessage(text=chat_gpt_response)])

if __name__ == '__main__':
    viber.set_webhook('https://worker-production-2716.up.railway.app')

