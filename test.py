from datetime import datetime

def datetime_str_to_int(date_input) -> int:
    """Преобразует строку или число в Unix timestamp (миллисекунды)."""
    if isinstance(date_input, int):  # Если передано число, возвращаем его без изменений
        return date_input
    elif isinstance(date_input, str):  # Если передана строка, конвертируем её
        dt = datetime.strptime(date_input, "%d.%m.%Y %H:%M:%S.%f")
        return int(dt.timestamp() * 1000)
    else:
        raise ValueError("Поддерживаются только строки и числа!")

# Пример использования:
a = datetime_str_to_int('05.02.2025 02:38:00.000000')
print(a)  # Конвертирует дату в timestamp
print(datetime_str_to_int(1670608800000))  # Возвращает число без изменений


dt = datetime.fromtimestamp(a / 1000)  # Перевод из миллисекунд в секунды

print(dt)