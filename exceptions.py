class NotSendMessageError(Exception):
    """Ошибка отправки сообщения."""

    pass


class NonStatusCodeError(Exception):
    """Исключение отсутствия ответа от сервера."""

    pass


class WrongStatusCodeError(Exception):
    """Исключение не совпадения ответа от сервера."""

    pass


class NonTokenError(Exception):
    """Исключение отсутствия Токена."""

    pass


class JSonDecoderError(Exception):
    """Ошибка преобразования в JSON."""

    pass