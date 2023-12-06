import logging
import os
import g4f
from flask import Flask, request, Response
from viberbot import Api
from viberbot.api.bot_configuration import BotConfiguration
from viberbot.api.messages import TextMessage
from viberbot.api.viber_requests import ViberMessageRequest, ViberConversationStartedRequest, ViberFailedRequest
from viberbot.api.viber_requests import ViberSubscribedRequest, ViberUnsubscribedRequest

app = Flask(__name__)


logging.basicConfig(level=logging.INFO)


viber = Api(BotConfiguration(
    name='ChatGPTPersonalBotbyVM',
    avatar='https://dl-media.viber.com/1/share/2/long/vibes/icon/image/0x0/7a08/3c87d21eceedb833743a81c19b74cea8c1c3e4ef66e7c86b71d82d16c1147a08.jpg',
    auth_token="52100bf26727e139-ef744c60c27c6fe-6baa33f46d9d4d19"
))

@app.route('/viber-webhook', methods=['POST'])
def incoming():
    logging.debug("received request. post data: {0}".format(request.get_data()))
    
    if not viber.verify_signature(request.get_data(), request.headers.get('X-Viber-Content-Signature')):
        return Response(status=403)
    
    viber_request = viber.parse_request(request.get_data())

    if isinstance(viber_request, ViberMessageRequest):
        message = viber_request.message
        viber.send_messages(viber_request.sender.id, [message])
    elif isinstance(viber_request, ViberSubscribedRequest):
        viber.send_messages(viber_request.user.id, [
            TextMessage(text="Thanks for subscribing!")
        ])
    elif isinstance(viber_request, ViberUnsubscribedRequest):
        pass
    elif isinstance(viber_request, ViberConversationStartedRequest):
        pass
    elif isinstance(viber_request, ViberFailedRequest):
        pass
    
    return Response(status=200)

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
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 8080)), debug=True)
    viber.set_webhook('https://worker-production-2716.up.railway.app')

