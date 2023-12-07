# from datetime import datetime
# import logging
# import os
# import g4f
# from flask import Flask, request, Response
# from viberbot import Api
# from viberbot.api.bot_configuration import BotConfiguration
# from viberbot.api.messages import TextMessage
# from viberbot.api.viber_requests import ViberMessageRequest, ViberConversationStartedRequest, ViberFailedRequest, ViberSubscribedRequest
# from threading import Lock

# app = Flask(__name__)
# logging.basicConfig(level=logging.INFO)

# viber = Api(BotConfiguration(
#     name='Чат Йопите ГГТУ',
#     avatar='https://dl-media.viber.com/1/share/2/long/vibes/icon/image/0x0/7a08/3c87d21eceedb833743a81c19b74cea8c1c3e4ef66e7c86b71d82d16c1147a08.jpg',
#     auth_token="521050f57467dfbf-f45b9b21ace92422-5e8da79493cf619c"
# ))


# last_processed_message_token = None
# token_lock = Lock()  # Создаем блокировку для потоков

# @app.route('/viber-webhook', methods=['POST'])
# def incoming():
#     global last_processed_message_token
#     logging.debug(f"{datetime.now()}: received request. post data: {request.get_data()}")
    
#     if not viber.verify_signature(request.get_data(), request.headers.get('X-Viber-Content-Signature')):
#         logging.error("Invalid signature")
#         return Response(status=403)
    
#     viber_request = viber.parse_request(request.get_data())
#     message_token = getattr(viber_request, 'message_token', None)
    
#     if message_token and message_token == last_processed_message_token:
#         logging.info(f"{datetime.now()}: Duplicate message with token {message_token} received and ignored.")
#         return Response(status=200)
    
#     if isinstance(viber_request, ViberConversationStartedRequest):
#         viber.send_messages(viber_request.user.id, [
#             TextMessage(text="Салют! Это наш чат Йопите, ну ты понял/а) Чем я могу тебе помочь сегодня?")
#         ])
#     elif isinstance(viber_request, ViberSubscribedRequest):
#         viber.send_messages(viber_request.user.id, [
#             TextMessage(text="Thanks for subscribing!")
#         ])
#     elif isinstance(viber_request, ViberMessageRequest):
#         message_received_callback(viber_request)
#     elif isinstance(viber_request, ViberFailedRequest):
#         logging.error("Message failed")
    
#     last_processed_message_token = message_token
#     return Response(status=200)

# conversation_history = {}

# def trim_history(history, max_length=4096):
#     current_length = sum(len(message["content"]) for message in history)
#     while history and current_length > max_length:
#         removed_message = history.pop(0)
#         current_length -= len(removed_message["content"])
#     return history

# def message_received_callback(viber_request):
#     global last_processed_message_token
#     with token_lock:  # Используем блокировку для безопасного доступа к глобальной переменной
#         user_id = viber_request.sender.id
#         user_input = viber_request.message.text
#         message_token = getattr(viber_request, 'message_token', None)

#         logging.info(f"{datetime.now()}: Received message from {user_id}: {user_input}")

#         if message_token is None:
#             logging.error("No message_token found in the request")
#             return

#         if message_token == last_processed_message_token:
#             logging.info(f"{datetime.now()}: Duplicate message with token {message_token} received and ignored.")
#             return
    
#     if user_id not in conversation_history:
#         conversation_history[user_id] = []
    
#     conversation_history[user_id].append({"role": "user", "content": user_input})
#     conversation_history[user_id] = trim_history(conversation_history[user_id])

#     chat_history = conversation_history[user_id]

#     try:
#         response = g4f.ChatCompletion.create(
#             model=g4f.models.default,
#             messages=chat_history,
#             provider=g4f.Provider.GeekGpt,
#         )

#         logging.info(f"{datetime.now()}: g4f response: {response}")
        
#         if isinstance(response, dict) and 'choices' in response and response['choices']:
#             chat_gpt_response = response['choices'][0]['message']['content']
#         else:
#             if isinstance(response, str):
#                 chat_gpt_response = response
#             else:
#                 logging.error(f"{datetime.now()}: Unexpected response format or error: {response}")
#                 chat_gpt_response = "Извините, произошла ошибка."
#     except Exception as e:
#         logging.error(f"{datetime.now()}: Error while calling g4f API: {e}")
#         chat_gpt_response = "Извините, произошла ошибка при обработке вашего запроса."

#     last_processed_message_token = message_token

#     viber.send_messages(user_id, [TextMessage(text=chat_gpt_response)])
#     conversation_history[user_id].append({"role": "assistant", "content": chat_gpt_response})

#     logging.info(f"{datetime.now()}: Response sent for message token: {viber_request.message_token}")

# if __name__ == '__main__':
#     app.run(host='0.0.0.0', port=int(os.getenv('PORT', 8080)), debug=True)

from datetime import datetime
import logging
import os
import g4f
from flask import Flask, request, Response
from viberbot import Api
from viberbot.api.bot_configuration import BotConfiguration
from viberbot.api.messages import TextMessage
from viberbot.api.viber_requests import ViberMessageRequest, ViberConversationStartedRequest, ViberFailedRequest, ViberSubscribedRequest

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

viber = Api(BotConfiguration(
    name='Чат Йопите ГГТУ',
    avatar='https://dl-media.viber.com/1/share/2/long/vibes/icon/image/0x0/7a08/3c87d21eceedb833743a81c19b74cea8c1c3e4ef66e7c86b71d82d16c1147a08.jpg',
    auth_token="521050f57467dfbf-f45b9b21ace92422-5e8da79493cf619c"
))

# Глобальные переменные
conversation_history = {}
last_processed_message_token = None

@app.route('/viber-webhook', methods=['POST'])
def incoming():
    global last_processed_message_token
    logging.debug(f"{datetime.now()}: received request. post data: {request.get_data()}")
    
    if not viber.verify_signature(request.get_data(), request.headers.get('X-Viber-Content-Signature')):
        logging.error("Invalid signature")
        return Response(status=403)
    
    viber_request = viber.parse_request(request.get_data())
    message_token = getattr(viber_request, 'message_token', None)
    
    # Блокируем обработку дубликатов
    if message_token == last_processed_message_token:
        logging.info(f"{datetime.now()}: Duplicate message with token {message_token} received and ignored.")
        return Response(status=200)
    
    # Обновляем токен после проверки на дубликаты
    last_processed_message_token = message_token
    
    # Обработка разных типов запросов
    try:
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
    except Exception as e:
        logging.error(f"Error during message handling: {e}")
    
    return Response(status=200)

def trim_history(history, max_length=4096):
    current_length = sum(len(message["content"]) for message in history)
    while current_length > max_length and history:
        removed_message = history.pop(0)
        current_length -= len(removed_message["content"])
    return history

def message_received_callback(viber_request):
    global last_processed_message_token
    user_id = viber_request.sender.id
    user_input = viber_request.message.text
    message_token = viber_request.message_token  # Идентификатор сообщения от Viber

    logging.info(f"{datetime.now()}: Received message from {user_id}: {user_input}")

    # Проверка на дубликаты
    if message_token == last_processed_message_token:
        logging.info(f"{datetime.now()}: Duplicate message with token {message_token} received and ignored.")
        return

    # Обновление токена только если это не дубликат
    last_processed_message_token = message_token

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

        if isinstance(response, dict) and 'choices' in response:
            chat_gpt_response = response['choices'][0]['message']['content']
        else:
            chat_gpt_response = "Извините, произошла ошибка."

        conversation_history[user_id].append({"role": "assistant", "content": chat_gpt_response})

    except Exception as e:
        logging.error(f"Error in message_received_callback: {e}")
        chat_gpt_response = "Извините, произошла ошибка при обработке вашего запроса."

    # Отправка ответа пользователю
    viber.send_messages(user_id, [TextMessage(text=chat_gpt_response)])

    # Логгирование для отладки
    logging.info(f"{datetime.now()}: Sent response to user {user_id}. Message: {chat_gpt_response}")

# Функция main, если нужно запустить Flask напрямую
if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)
