import logging
import os
import requests
import telegram
import exceptions

from time import time, sleep
from http import HTTPStatus
from json.decoder import JSONDecodeError
from dotenv import load_dotenv

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_STATUSES = {
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.',
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
}

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())


def send_message(bot, message):
    """Функция отправляет сообщение в Telegram чат.
    Определяемый переменной окружения TELEGRAM_CHAT_ID.
    Принимает на вход два параметра: экземпляр
    класса Bot и строку с текстом сообщения.
    """
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message
        )
        logger.info(f'Отправлено сообщение: {message}')
    except telegram.TelegramError:
        raise telegram.TelegramError('Ошибка в отправке сообщения!')


def get_api_answer(current_timestamp):
    """Функция делает запрос к единственному эндпоинту API-сервиса.
    В качестве параметра функция получает
    временную метку. В случае успешного запроса
    должна вернуть ответ API, преобразовав
    его из формата JSON к типам данных Python.
    """
    timestamp = current_timestamp or int(time())
    requests_params = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': {'from_date': timestamp},
    }
    try:
        response = requests.get(**requests_params)
        logger.info(f'[Запрос к API] статуc (HTTP): {response.status_code}')
        if response.status_code != HTTPStatus.OK:
            logger.error(
                f'[Запрос к API] Ошибка при получении ответа с сервера.'
                f'Статус ответа сервера {response.status_code}'
            )
            raise exceptions.ErrorMessage(
                f'[Запрос к API]'
                f'Статус, отличный от HTTP 200:{response.status_code}'
            )
        return response.json()
    except JSONDecodeError:
        logger.error('Запрос к API вернулся не в формате JSON')
        raise JSONDecodeError('Запрос к API вернулся не в формате JSON')
    except Exception as error:
        raise Exception(
            f'[Запрос к API] Статус: {response.status_code},'
            f'Получена ошибка: {error}'
        )


def check_response(response):
    """Функция проверяет ответ API на корректность.
    В качестве параметра функция получает ответ API, приведенный к
    типам данных Python. Если ответ API соответствует ожиданиям,
    то функция должна вернуть список домашних работ
    (он может быть и пустым), доступный в ответе API по ключу 'homeworks'.
    """
    try:
        homeworks = response['homeworks']
    except KeyError as error:
        raise KeyError(f'[Корректность] ошибка ключа: {error}')
    if not homeworks:
        logger.debug('[Корректность] Список домашних работ пуст')
    if not isinstance(homeworks, list):
        raise TypeError('[Корректность] Ошибка типа.')
    return homeworks


def parse_status(homework):
    """Функция извлекает из информации.
    Конкретной домашней работе статус этой работы.
    В качестве параметра функция получает только один элемент
    из списка домашних работ. В случае успеха, функция
    возвращает подготовленную для отправки в Telegram строку,
    содержащую один из вердиктов словаря HOMEWORK_STATUSES.
    """
    try:
        if len(homework) == 0:
            message = f'[Статус] Проект не на проверке: {homework}'
            logger.info(message)
            return message
        else:
            homework_name = homework['homework_name']
            homework_status = homework['status']
            if homework_status in HOMEWORK_STATUSES:
                verdict = HOMEWORK_STATUSES[homework_status]
                mes_verdict = (
                    f'Изменился статус проверки работы "{homework_name}".'
                    f'{verdict}'
                )
                logger.info(mes_verdict)
                return mes_verdict
            raise KeyError('[Статус] шибка статуса (ключа) homework')
    except KeyError:
        raise KeyError('[Статус] ERROR: Ошибка ключа')


def check_tokens():
    """Функция проверяет доступность переменных окружения.
    Которые необходимы для работы программы.
    Если отсутствует хотя бы одна переменная окружения — функция должна
    вернуть False, иначе — True.
    """
    try:
        tokens = {
            'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
            'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
            'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
        }
        for key, value in tokens.items():
            if not value:
                logger.critical(
                    f'Отсутствует ключ/значение для токенов: {value} для {key}'
                )
                return False
        return True
    except NameError:
        message = 'Ошибка доступности токенов. Остановка программы'
        logger.critical(message)


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
    current_timestamp = int(time())
    status_non = None
    status_ok = None
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if len(homeworks) == 0:
                if parse_status(homeworks) != status_non:
                    status_non = parse_status(homeworks)
                    send_message(bot, f'Работа не на проверке: {homeworks}')
                else:
                    logger.debug('Без обновлений')
            else:
                if homeworks[0]['status'] in HOMEWORK_STATUSES:
                    if homeworks[0]['status'] != status_ok:
                        status_ok = homeworks[0]['status']
                        parse_status(homeworks[0])
                        send_message(bot, HOMEWORK_STATUSES[status_ok])
                    else:
                        logger.debug('Без обновлений')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            send_message(bot, message)
        finally:
            sleep(RETRY_TIME)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        filename='Jurgen.log',
        format='%(asctime)s, %(levelname)s, %(message)s,'
               '%(funcName)s, %(lineno)s',
        filemode='w',
    )
    main()
