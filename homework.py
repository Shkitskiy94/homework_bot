import requests
import os
import logging

from logging.handlers import RotatingFileHandler
from telegram import Bot
from time import time, sleep
from dotenv import load_dotenv
from http import HTTPStatus

load_dotenv()
logging.basicConfig(
    level=logging.DEBUG,
    filename='homework.log',
    filemode='w',
    format='%(asctime)s, %(levelname)s, %(message)s, %(lineno)s',
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = RotatingFileHandler('my_logger.log',
                              encoding='UTF-8',
                              maxBytes=50000000,
                              backupCount=5
                              )
logger.addHandler(handler)
formatter = logging.Formatter(
    '%(asctime)s, %(levelname)s, %(message)s, %(funcName)s, %(lineno)s'
)
handler.setFormatter(formatter)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
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
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info('Сообщение в чат {TELEGRAM_CHAT_ID}: {message}')
    except Exception:
        logger.error('Ошибка отправки сообщения в телеграм')


def get_api_answer(current_timestamp):
    """Функция делает запрос к единственному эндпоинту API-сервиса.
    В качестве параметра функция получает
    временную метку. В случае успешного запроса
    должна вернуть ответ API, преобразовав
    его из формата JSON к типам данных Python.
    """
    timestamp = current_timestamp or int(time())
    params = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
    except Exception as error:
        logging.error(f'Ошибка при запросе к основному API: {error}')
        raise Exception(f'Ошибка при запросе к основному API: {error}')
    if homework_statuses.status_code != HTTPStatus.OK:
        status_code = homework_statuses.status_code
        logging.error(f'Ошибка {status_code}')
        raise Exception(f'Ошибка {status_code}')
    try:
        return homework_statuses.json()
    except ValueError:
        logger.error('Ошибка парсинга ответа из формата json')
        raise ValueError('Ошибка парсинга ответа из формата json')


def check_response(response):
    """Функция проверяет ответ API на корректность.
    В качестве параметрафункция получает ответ API, приведенный к
    типам данных Python. Если ответ API соответствует ожиданиям,
    то функция должна вернуть список домашних работ
    (он может быть и пустым), доступный в ответе API по ключу 'homeworks'.
    """
    if type(response) is not dict:
        raise TypeError('Ответ API отличен от словаря')
    try:
        all_homeworks = response["homeworks"]
    except KeyError:
        logger.error('Ошибка словаря по ключу homeworks')
        raise KeyError('Ошибка словаря по ключу homeworks')
    try:
        homework = all_homeworks[0]
    except IndexError:
        logger.error('Список домашних работ пуст')
        raise IndexError('Список домашних работ пуст')
    return homework


def parse_status(homework):
    """Функция извлекает из информации.
    Конкретной домашней работе статус этой работы.
    В качестве параметра функция получает только один элемент
    из списка домашних работ. В случае успеха, функция
    возвращает подготовленную для отправки в Telegram строку,
    содержащую один из вердиктов словаря HOMEWORK_STATUSES.
    """
    if 'homework_name' not in homework:
        raise KeyError('Отсутствует ключ "homework_name" в ответе API')
    if 'status' not in homework:
        raise Exception('Отсутствует ключ "status" в ответе API')
    homework_name = homework["homework_name"]
    homework_status = homework["status"]
    if homework_status not in HOMEWORK_STATUSES:
        raise Exception(f'Неизвестный статус работы: {homework_status}')
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Функция проверяет доступность переменных окружения.
    Которые необходимы для работы программы.
    Если отсутствует хотя бы одна переменная окружения — функция должна
    вернуть False, иначе — True.
    """
    if (
        PRACTICUM_TOKEN is None
        or TELEGRAM_TOKEN is None
        or TELEGRAM_CHAT_ID is None
    ):
        return False
    return True


def main():
    """Основная логика работы бота. Делает запрос к API.
    Проверяет ответ, если есть обновления получает статус,
    работы из обновлений и отправляет сообщение в,
    Telegram и ждет некоторое время и делает новый запрос
    """
    bot = Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time())
    error_message = ""
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if len(homeworks) > 0:
                current_homework = homeworks[0]
                lesson_name = current_homework["lesson_name"]
                homework_status = parse_status(current_homework)
                send_message(bot, f"{lesson_name}, {homework_status}")
            else:
                logger.debug("Новые статусы отсутствуют.")
            current_timestamp = response.get("current_date")
            error_message = ""
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            current_error = str(error)
            if current_error != error_message:
                send_message(bot, message)
                error_message = error
            logger.error(message)
        sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
