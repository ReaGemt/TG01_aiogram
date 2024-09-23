import logging
import requests
import os
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from dotenv import load_dotenv
from cachetools import TTLCache

# Загружаем переменные окружения из файла .env
load_dotenv()

# Получаем значения из .env файла
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
WEATHER_API_KEY = os.getenv('WEATHER_API_KEY')

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
logger.info("Бот запущен.")

# Инициализация бота и диспетчера
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher(bot)

# Кеш для городов (на 10 минут)
weather_cache = TTLCache(maxsize=100, ttl=600)

# Словарь для перевода погодных условий
weather_descriptions = {
    "clear sky": "Ясное небо",
    "few clouds": "Малооблачно",
    "scattered clouds": "Рассеянные облака",
    "broken clouds": "Переменная облачность",
    "shower rain": "Ливневый дождь",
    "rain": "Дождь",
    "thunderstorm": "Гроза",
    "snow": "Снег",
    "mist": "Туман",
}

# Клавиатура с кнопкой "Старт"
start_button = KeyboardButton('/start')
help_button = KeyboardButton('/help')
markup = ReplyKeyboardMarkup(resize_keyboard=True).add(start_button, help_button)

# Функция для перевода погодных условий
def translate_description(description):
    description = description.lower()
    return weather_descriptions.get(description, description.capitalize())

# Команда /start
@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    logger.info(f"Получена команда /start от пользователя {message.from_user.id} ({message.from_user.first_name})")
    await message.reply(
        f'Привет, {message.from_user.first_name}!\nНапиши название города, чтобы узнать погоду.',
        reply_markup=markup  # Отправляем клавиатуру с кнопкой
    )

# Команда /help
@dp.message_handler(commands=['help'])
async def send_help(message: types.Message):
    logger.info(f"Получена команда /help от пользователя {message.from_user.id}")
    help_text = (
        "Я бот для получения прогноза погоды.\n"
        "Просто отправь название города, и я покажу текущую погоду.\n"
        "Доступные команды:\n"
        "/start - Начать взаимодействие с ботом\n"
        "/help - Получить список доступных команд"
    )
    await message.reply(help_text)

# Обработка текстового сообщения с названием города
@dp.message_handler()
async def get_weather_by_city(message: types.Message):
    city_name = message.text.strip().lower()  # Приведение города к нижнему регистру и удаление лишних пробелов
    logger.info(f"Запрос погоды для города: {city_name} от пользователя {message.from_user.id}")

    # Проверка на наличие данных в кеше
    if city_name in weather_cache:
        logger.info(f"Возвращаем закешированные данные для города: {city_name}")
        await message.reply(weather_cache[city_name])
        return

    try:
        # Установим тайм-аут для запроса в 20 секунд
        url = f"https://api.openweathermap.org/data/2.5/weather?q={city_name}&appid={WEATHER_API_KEY}&units=metric&lang=ru"
        logger.info(f"Отправка запроса к OpenWeatherMap для города: {city_name}")
        response = requests.get(url, timeout=20)  # Тайм-аут 20 секунд

        if response.status_code == 200:
            data = response.json()
            temp = data['main']['temp']
            description = data['weather'][0]['description']
            description_ru = translate_description(description)  # Перевод описания погоды

            # Формируем сообщение с погодой
            weather_message = (
                f"Погода в {city_name.capitalize()}:\n"
                f"Температура: {temp}°C\n"
                f"Условия: {description_ru}"
            )
            logger.info(f"Погода для города {city_name.capitalize()} успешно получена.")

            # Сохраняем данные в кеш
            weather_cache[city_name] = weather_message

        else:
            weather_message = 'Не удалось получить данные о погоде. Пожалуйста, проверьте правильность названия города.'
            logger.warning(f"Ошибка получения данных для города: {city_name}. Код ответа API: {response.status_code}")

        await message.reply(weather_message)

    except requests.exceptions.Timeout:
        logger.error(f"Тайм-аут при получении данных о погоде для города {city_name}")
        await message.reply("Превышено время ожидания ответа от сервера. Пожалуйста, попробуйте снова.")

    except Exception as e:
        logger.error(f"Ошибка получения данных о погоде для города {city_name}: {e}")
        await message.reply("Произошла ошибка при получении данных. Попробуйте снова позже.")

if __name__ == '__main__':
    logger.info("Запуск бота в режиме long-polling")
    try:
        executor.start_polling(dp, skip_updates=True)
    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске бота: {e}")
