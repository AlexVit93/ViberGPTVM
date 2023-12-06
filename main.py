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
    name='Чат Йопите',
    avatar='https://dl-media.viber.com/1/share/2/long/vibes/icon/image/0x0/7a08/3c87d21eceedb833743a81c19b74cea8c1c3e4ef66e7c86b71d82d16c1147a08.jpg',
    auth_token="52100bf26727e139-ef744c60c27c6fe-6baa33f46d9d4d19"
))

@app.route('/viber-webhook', methods=['POST'])
def incoming():
    logging.debug("received request. post data: {0}".format(request.get_data()))
    
    if not viber.verify_signature(request.get_data(), request.headers.get('X-Viber-Content-Signature')):
        return Response(status=403)
    
    viber_request = viber.parse_request(request.get_data())

    if isinstance(viber_request, ViberConversationStartedRequest):
        viber.send_messages(viber_request.user.id, [
            TextMessage(text="Салют! Это наш чат Йопите, ну ты понял/а) Чем я могу тебе помочь сегодня?")
        ])
    elif isinstance(viber_request, ViberSubscribedRequest):
        viber.send_messages(viber_request.user.id, [
            TextMessage(text="Thanks for subscribing!")
        ])
    # Повторяющийся блок удалён
    elif isinstance(viber_request, ViberFailedRequest):
        pass
    
    return Response(status=200)

# Остальная часть кода без изменений...

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 8080)), debug=True)
    # Здесь должен быть код для установки webhook, если вы не делали это вручную через платформу Viber
