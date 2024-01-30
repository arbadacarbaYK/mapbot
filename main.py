import requests
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler

# Replace 'YOUR_BOT_TOKEN' with your actual Telegram bot token
TOKEN = 'YOUR_BOT_TOKEN'

# Dictionary to store user preferences (countries)
user_preferences = {}

# API endpoint
API_URL = 'https://api.btcmap.org/v2/elements'

def start(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id

    # Set up a custom keyboard with country options
    countries_keyboard = [['Netherlands', 'Germany']]

    # Display the keyboard to the user
    update.message.reply_text(
        'Bot started. Please choose your preferred country:',
        reply_markup=ReplyKeyboardMarkup(countries_keyboard, one_time_keyboard=True)
    )

    # Set a handler to process the user's choice
    context.user_data['waiting_for_country'] = True
    return COUNTRY_CHOICE

def country_choice(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    text = update.message.text

    # Check if the user has chosen a country
    if text in ['Netherlands', 'Germany']:
        # Store the user's country preference
        user_preferences[user_id] = {'country': text}

        # Inform the user about their choice
        update.message.reply_text(f'Your preferred country is set to: {text}', reply_markup=ReplyKeyboardRemove())

        # Call the function to poll the API with the user's preference
        poll_api(context, user_id)

        # Set up polling interval to every 60 minutes (60 * 60 seconds)
        context.job_queue.run_repeating(poll_api, interval=3600, first=0, context={'user_id': user_id})
    else:
        # Invalid choice, ask the user to choose again
        update.message.reply_text('Please choose a valid country:', reply_markup=ReplyKeyboardMarkup([['Netherlands', 'Germany']], one_time_keyboard=True))

    # End the conversation
    return ConversationHandler.END

def poll_api(context: CallbackContext) -> None:
    user_id = context.job.context['user_id']

    # Make a request to the API
    response = requests.get('https://api.btcmap.org/v2/elements?updated_since=2024-01-30T13:51:29.268Z&limit=5000')

    if response.status_code == 200:
        # Parse the JSON response
        entries = response.json()

        # Filter entries based on the user's country preference
        user_country = user_preferences.get(user_id, {}).get('country')
        filtered_entries = [entry for entry in entries if is_entry_in_selected_country(entry, user_country)]

        # Send the filtered entries to the user
        send_entries_to_telegram(user_id, filtered_entries)

    else:
        print(f"Failed to fetch data from the API. Status code: {response.status_code}")

def is_entry_in_selected_country(entry: dict, user_country: str) -> bool:
    # Extract the country code from the phone number
    country_code = entry.get('phone', '').split(' ')[0]

    # Check if the country code matches the user's preference
    return country_code == '+31' if user_country == 'Netherlands' else country_code == '+49' if user_country == 'Germany' else False

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
    country = 'Netherlands' if country_code == '+31' else 'Germany' if country_code == '+49' else 'Unknown'

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
