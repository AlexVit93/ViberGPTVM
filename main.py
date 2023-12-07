from datetime import datetime
import logging
import os
import g4f
from flask import Flask, request, Response
from viberbot import Api
from viberbot.api.bot_configuration import BotConfiguration
from viberbot.api.messages import TextMessage
from viberbot.api.viber_requests import ViberMessageRequest, ViberConversationStartedRequest, ViberFailedRequest
from viberbot.api.viber_requests import ViberSubscribedRequest

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

viber = Api(BotConfiguration(
    name='Чат Йопите ГГТУ',
    avatar='https://dl-media.viber.com/1/share/2/long/vibes/icon/image/0x0/7a08/3c87d21eceedb833743a81c19b74cea8c1c3e4ef66e7c86b71d82d16c1147a08.jpg',
    auth_token="521050f57467dfbf-f45b9b21ace92422-5e8da79493cf619c"
))

@app.route('/viber-webhook', methods=['POST'])
def incoming():
    logging.debug(f"{datetime.now()}: received request. post data: {request.get_data()}")
    global last_processed_message_token
    logging.debug("received request. post data: {0}".format(request.get_data()))
    
    if not viber.verify_signature(request.get_data(), request.headers.get('X-Viber-Content-Signature')):
        logging.error("Invalid signature")
        return Response(status=403)

    viber_request = viber.parse_request(request.get_data())

    # Получение message_token из запроса
    message_token = getattr(viber_request, 'message_token', None)
    
    # Проверяем, не было ли это сообщение уже обработано
    if message_token and message_token == last_processed_message_token:
        logging.info(f"Duplicate message with token {message_token} received and ignored.")
        return Response(status=200)

    # Сохраняем token последнего обработанного сообщения
    last_processed_message_token = message_token

    if isinstance(viber_request, ViberConversationStartedRequest):
        viber.send_messages(viber_request.user.id, [
            TextMessage(text="Салют! Это наш чат Йопите, ну ты понял/а) Чем я могу тебе помочь сегодня?")
        ])
    elif isinstance(viber_request, ViberSubscribedRequest):
        viber.send_messages(viber_request.user.id, [
            TextMessage(text="Thanks for subscribing!")
        ])
    elif isinstance(viber_request, ViberMessageRequest):
        message_received_callback(viber_request)
    elif isinstance(viber_request, ViberFailedRequest):
        logging.error("Message failed")

    return Response(status=200)

conversation_history = {}

def trim_history(history, max_length=4096):
    current_length = sum(len(message["content"]) for message in history)
    while history and current_length > max_length:
        removed_message = history.pop(0)
        current_length -= len(removed_message["content"])
    return history

last_processed_message_token = None

def message_received_callback(viber_request):
    global last_processed_message_token
    user_id = viber_request.sender.id
    user_input = viber_request.message.text
    message_token = viber_request.message_token  # Идентификатор сообщения от Viber

    logging.info(f"{datetime.now()}: Received message token: {message_token}")

    # Проверка на дубликаты
    if message_token == last_processed_message_token:
        logging.info(f"{datetime.now()}: Duplicate message with token {message_token} received and ignored.")
        return
    else:
        # Обновление токена только если это не дубликат
        last_processed_message_token = message_token

    logging.info(f"{datetime.now()}: Received message from {user_id}: {user_input}")


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

        logging.info(f"g4f response: {response}")

        # Предполагаем, что успешный ответ от g4f - это словарь с ключом 'choices'
        if isinstance(response, dict) and 'choices' in response and response['choices']:
            chat_gpt_response = response['choices'][0]['message']['content']
        else:
            # Если ответ API - строка, предполагаем, что это полезный ответ, и отправляем его пользователю
            if isinstance(response, str):
                chat_gpt_response = response
            else:
                logging.error(f"Unexpected response format or error: {response}")
                chat_gpt_response = "Извините, произошла ошибка."
    except Exception as e:
        logging.error(f"Error while calling g4f API: {e}")
        # Обработка ошибки Too Many Requests
        if e.response.status_code == 429:
            chat_gpt_response = "Извините, слишком много запросов. Попробуйте позже."
        else:
            chat_gpt_response = "Извините, произошла ошибка при обработке вашего запроса."

    # Отправка сообщения пользователю
    viber.send_messages(user_id, [TextMessage(text=chat_gpt_response)])
    # Добавление ответа в историю беседы
    conversation_history[user_id].append({"role": "assistant", "content": chat_gpt_response})

    last_processed_message_token = message_token
    logging.info(f"{datetime.now()}: Response sent for message token: {message_token}")


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 8080)), debug=True)

# viber.set_webhook('https://worker-production-2716.up.railway.app/viber-webhook')