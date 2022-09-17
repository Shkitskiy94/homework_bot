import json
import logging
import os
import time
from typing import Dict

import requests
import telegram

from dotenv import load_dotenv
from http import HTTPStatus
import exceptions

logging.basicConfig(
    level=logging.INFO,
    filename='Jurgen.log',
    format='%(asctime)s, %(levelname)s, %(message)s,'
           '%(funcName)s, %(lineno)s',
    filemode='a',
)
logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 3
# TWO_WEEKS = 1209600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Функция отправляет сообщение в Telegram чат.
    Определяемый переменной окружения TELEGRAM_CHAT_ID.
    Принимает на вход два параметра: экземпляр
    класса Bot и строку с текстом сообщения.
    """
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.info('Сообщение отправлено!')
    except telegram.error.TelegramError as error:
        logger.error(f'Ошибка: {error}')
        message = 'Ошибка отправки сообщения!'
        raise exceptions.NotSendMessageError(message)


def get_api_answer(current_timestamp):
    """Функция делает запрос к единственному эндпоинту API-сервиса.
    В качестве параметра функция получает
    временную метку. В случае успешного запроса
    должна вернуть ответ API, преобразовав
    его из формата JSON к типам данных Python.
    """
    params = {'from_date': current_timestamp}
    try:
        response = requests.get(url=ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != HTTPStatus.OK:
            message = 'Ошибка при получении ответа с сервера'
            raise exceptions.NonStatusCodeError(message)
        logger.info('Соединение с сервером установлено!')
        return response.json()
    except json.decoder.JSONDecodeError:
        raise exceptions.JSonDecoderError('Ошибка преобразования в JSON')
    except requests.RequestException as request_error:
        message = f'Код ответа API (RequestException): {request_error}'
        raise exceptions.WrongStatusCodeError(message)
    except ValueError as value_error:
        message = f'Код ответа API (ValueError): {value_error}'
        raise exceptions.WrongStatusCodeError(message)


def check_response(response):
    """Функция проверяет ответ API на корректность.
    В качестве параметра функция получает ответ API, приведенный к
    типам данных Python. Если ответ API соответствует ожиданиям,
    то функция должна вернуть список домашних работ
    (он может быть и пустым), доступный в ответе API по ключу 'homeworks'.
    """
    try:
        homeworks = response['homeworks']
    except KeyError:
        logger.error('Отсутствует ключ у homeworks')
        raise KeyError('Отсутствует ключ у homeworks')
    if homeworks is None:
        raise KeyError("Не содержит ключ или пустое значение")
    if not isinstance(homeworks, list):
        raise TypeError("Неверный формат homework")
    if not homeworks:
        return False
    return homeworks


def parse_status(homework):
    """Функция извлекает из информации.
    Конкретной домашней работе статус этой работы.
    В качестве параметра функция получает только один элемент
    из списка домашних работ. В случае успеха, функция
    возвращает подготовленную для отправки в Telegram строку,
    содержащую один из вердиктов словаря HOMEWORK_STATUSES.
    """
    if not isinstance(homework, Dict):
        raise TypeError("homework не является словарем!")
    homework_name = homework.get('homework_name')
    if homework_name is None:
        raise KeyError('У homework нет имени')
    homework_status = homework.get('status')
    if homework_status is None:
        raise KeyError('У homework нет статуса')
    verdict = HOMEWORK_STATUSES.get(homework_status)
    if verdict is None:
        raise KeyError(f'Ошибка статуса homework : {verdict}')
    logging.info(f'Новый статус {verdict}')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Функция проверяет доступность переменных окружения.
    Которые необходимы для работы программы.
    Если отсутствует хотя бы одна переменная окружения — функция должна
    вернуть False, иначе — True.
    """
    if all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
        return True
    elif PRACTICUM_TOKEN is None:
        logger.info('Отсутствует PRACTICUM_TOKEN')
        return False
    elif TELEGRAM_TOKEN is None:
        logger.info('Отсутствует TELEGRAM_TOKEN')
        return False
    elif TELEGRAM_CHAT_ID is None:
        logger.info('Отсутствует TELEGRAM_CHAT_ID')
        return False


def main():
    """Основная логика работы бота. Делает запрос к API.
    Проверяет ответ, если есть обновления получает статус,
    работы из обновлений и отправляет сообщение в,
    Telegram и ждет некоторое время и делает новый запрос
    """
    if not check_tokens():
        message = 'Отсутствуют токены чата (id чата, бота или Практикума)'
        logger.critical(message)
        raise exceptions.NonTokenError(message)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    error_message = ''
    while True:
        try:
            response = get_api_answer(current_timestamp)
            statuses = check_response(response)
            for status in statuses:
                message = parse_status(status)
                send_message(bot, message)
            current_timestamp = response.get('current_date', current_timestamp)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(error)
            if message != error_message:
                send_message(bot, message)
                error_message = message
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
