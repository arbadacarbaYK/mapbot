import os
import requests
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler
import datetime

# Retrieve the Telegram bot token from the environment variable
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')

# Dictionary to store user preferences (countries)
user_preferences = {}

# API endpoint
API_URL = 'https://api.btcmap.org/v2/elements'

# Initialize the last polled time with the current time
last_polled_time = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S') + 'Z'

def start(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id

    # Set up a custom keyboard with country options
    countries_keyboard = [['Portugal', 'Spain', 'Czech Republic'], ['Great Britain', 'Ireland'], ['Netherlands', 'Germany']]

    # Display the keyboard to the user
    update.message.reply_text(
        'Bot started. Please choose your preferred country:',
        reply_markup=ReplyKeyboardMarkup(countries_keyboard, one_time_keyboard=True)
    )

    # Set a handler to process the user's choice
    context.user_data['waiting_for_country'] = True
    return COUNTRY_CHOICE

def poll_api(context: CallbackContext) -> None:
    global last_polled_time
    user_id = context.job.context['user_id']

    # Update the API URL with the last polled time
    api_url = f'https://api.btcmap.org/v2/elements?updated_since={last_polled_time}&limit=5000'

    # Make a request to the updated API URL
    response = requests.get(api_url)

    if response.status_code == 200:
        # Parse the JSON response
        entries = response.json()

        # Filter entries based on the user's country preference
        user_country = user_preferences.get(user_id, {}).get('country')
        filtered_entries = [entry for entry in entries if is_entry_in_selected_country(entry, user_country)]

        # Send the filtered entries to the user
        send_entries_to_telegram(user_id, filtered_entries)

        # Update the last polled time with the current time
        last_polled_time = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'

    else:
        print(f"Failed to fetch data from the API. Status code: {response.status_code}")

def country_choice(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    text = update.message.text

    # Check if the user has chosen a country
    countries = ['Portugal', 'Spain', 'Czech Republic', 'Great Britain', 'Ireland', 'Netherlands', 'Germany']
    if text in countries:
        # Store the user's country preference
        user_preferences[user_id] = {'country': text}

        # Inform the user about their choice
        update.message.reply_text('Please choose a valid country:', reply_markup=ReplyKeyboardMarkup([countries], one_time_keyboard=True, resize_keyboard=True))

        # Call the function to poll the API with the user's preference
        context.job_queue.run_repeating(poll_api, interval=600, first=0, context={'user_id': user_id})
    else:
        # Invalid choice, ask the user to choose again
        update.message.reply_text('Please choose a valid country:', reply_markup=ReplyKeyboardMarkup([countries], one_time_keyboard=True))

    # End the conversation
    return ConversationHandler.END

def send_entries_to_telegram(user_id: int, entries: list) -> None:
    # Initialize the Telegram bot
    updater = Updater(token=TOKEN)
    dp = updater.dispatcher

    # Send each entry as a separate message to the user
    for entry in entries:
        message = format_entry_message(entry)
        dp.bot.send_message(chat_id=user_id, text=message)

    # Stop the bot after sending messages
    updater.stop()

def format_entry_message(entry: dict) -> str:
    # Extract relevant information from the entry
    name = entry.get('name', 'N/A')
    city = entry.get('addr:city', 'N/A')
    country_code = entry.get('phone', '').split(' ')[0]

    # Determine the country based on the country code
    country_codes = {'+351': 'Portugal', '+34': 'Spain', '+420': 'Czech Republic', '+44': 'Great Britain', '+353': 'Ireland', '+31': 'Netherlands', '+49': 'Germany'}
    country = country_codes.get(country_code, 'Unknown')

    # Extract currency, lightning, android icon, and service information
    currency_xbt = entry.get('currency:XBT', 'no') == 'yes'
    lightning = entry.get('payment:lightning', 'no') == 'yes'
    android_icon = entry.get('tags', {}).get('icon:android', 'N/A')
    service = entry.get('tags', {}).get('service:vehicle:garage', 'N/A')

    # Format symbols based on currency and lightning information
    currency_symbol = '🍊' if currency_xbt else ''
    lightning_symbol = '⚡️' if lightning else ''

    # Format the message with the extracted information
    message = f"Name: {name}\nCity: {city}\nCountry: {country}\nCurrency: {currency_symbol}\nLightning: {lightning_symbol}\nAndroid Icon: {android_icon}\nService: {service}"

    return message

if __name__ == '__main__':
    updater = Updater(token=TOKEN, use_context=True)
    dp = updater.dispatcher

    # Set up a conversation handler
    COUNTRY_CHOICE = 1
    country_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            COUNTRY_CHOICE: [MessageHandler(Filters.text & ~Filters.command, country_choice)]
        },
        fallbacks=[]
    )
    dp.add_handler(country_handler)

    updater.start_polling()
    updater.idle()
