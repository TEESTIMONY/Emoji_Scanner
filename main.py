import logging
from telegram import Chat, ChatMember, ChatMemberUpdated, Update,InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes,ChatMemberHandler,CallbackQueryHandler,ConversationHandler,MessageHandler,filters
import requests
import json
from decimal import Decimal, getcontext
from datetime import datetime, timedelta, timezone
import asyncio
from concurrent.futures import ThreadPoolExecutor
import traceback
from mysql.connector import pooling
import mysql.connector

SEND_MEDIA =range(1)
####  ============ utils ======================== #
db_config = {
    'user': 'root',
    'password': 'Testimonyalade@2003',
    'host': 'localhost',
    'database': 'scanner_db',
}

# db_config = {
#     'user':'scanner_user',
#     'password':'Str0ng!Passw0rd',
#     'host':'154.12.231.59',
#     'database':'scanner_db'
# }

connection_pool = pooling.MySQLConnectionPool(pool_name="mypool",
                                              pool_size=32,  # Adjust based on your needs
                                              **db_config)
def create_connection():
    return connection_pool.get_connection()
def create_table():
    conn = create_connection()
    if conn:  
        try:
            cursor = conn.cursor()
            # Create `media` table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS media (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    file_id VARCHAR(255) NOT NULL,
                    file_type VARCHAR(50) NOT NULL,
                    chat_id BIGINT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY unique_chat (chat_id)

                )
            """)

            # Create `emojis` table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS emojis (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    emoji VARCHAR(50) NOT NULL,
                    chat_id BIGINT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY unique_chat (chat_id)
                    
                )
            """)
        except Exception as e:
            print(e)
        finally:
            cursor.close()
            conn.close()

def save_or_update_media_in_db(file_id: str, file_type: str, chat_id: int):
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO media (file_id, file_type, chat_id)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE
        file_id = VALUES(file_id),
        file_type = VALUES(file_type),
        created_at = CURRENT_TIMESTAMP
    """, (file_id, file_type, chat_id))
    conn.commit()
    cursor.close()
    conn.close()


def save_emoji_to_db(emoji: str, chat_id: int) -> None:
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO emojis (emoji, chat_id)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE
            emoji = VALUES(emoji),
            created_at = CURRENT_TIMESTAMP
        """, (emoji, chat_id))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(e)


def download_file(file_url):
    response = requests.get(file_url)
    if response.status_code == 200:
        return response.content
    else:
        raise Exception("Failed to download file")


def fetch_media_from_db(chat_id: int):
    conn =create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT file_id, file_type FROM media WHERE chat_id = %s ORDER BY created_at DESC LIMIT 1", (chat_id,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result


def special_format(number):
    if number == 'N/A':
        return number
    else:
        number = float(number)
        if number >= 1_000_000_000:  # Billions
            formatted = f"{number / 1_000_000_000:.1f}B"
        elif number >= 1_000_000:  # Millions
            formatted = f"{number / 1_000_000:.1f}M"
        elif number >= 1_000:  # Thousands
            formatted = f"{number / 1_000:.1f}K"
        elif number >= 0.000000001:  # Handle very small numbers (up to 9 decimal places)
            formatted = f"{number:.9f}".rstrip('0').rstrip('.')
        elif number > 0:  # Handle very small numbers using scientific notation
            formatted = f"{number:.9e}"
        else:  # Handle zero or negative numbers if needed
            formatted = f"{number:.9f}".rstrip('0').rstrip('.')
        return formatted

def calculate_age(pair_created_sec):
    # Ensure the input is in milliseconds (13 digits)
    if len(str(pair_created_sec)) > 10:
        # Convert Unix timestamp from milliseconds to seconds
        birthdate = datetime.fromtimestamp(pair_created_sec / 1000, tz=timezone.utc)
    else:
        raise ValueError("Timestamp should be in milliseconds (13 digits).")

    # Current time in UTC
    now = datetime.now(timezone.utc)
    
    # Calculate the difference between now and birthdate
    delta = now - birthdate

    # Extract total years, months, and days
    age_years = now.year - birthdate.year
    age_months = now.month - birthdate.month
    age_days = now.day - birthdate.day
    
    # Adjust for negative days or months
    if age_days < 0:
        age_months -= 1
        age_days += (birthdate.replace(month=(birthdate.month % 12) + 1, day=1) - birthdate.replace(month=birthdate.month, day=1)).days

    if age_months < 0:
        age_years -= 1
        age_months += 12

    # Prepare age components for output
    age_parts = []
    if age_years > 0:
        age_parts.append(f"{age_years} year{'s' if age_years != 1 else ''}")
    if age_months > 0:
        age_parts.append(f"{age_months} month{'s' if age_months != 1 else ''}")
    if age_days > 0:
        age_parts.append(f"{age_days} day{'s' if age_days != 1 else ''}")

    return ", ".join(age_parts) if age_parts else "0 days"

def get_token_pools(address, page="1"):
    url = (f"https://api.dexscreener.com/latest/dex/tokens/{address}")
    response = requests.get(url)
    with open('fe.json','w')as file:
        json.dump(response.json(),file,indent=4)
    return response.json()

def all_time_high(token_address,pair_created_sec):
    current_datetime = datetime.now()
    timestamp_seconds = int(current_datetime.timestamp())
    splited = token_address.split('::')
    used_address =splited[0]
    print(timestamp_seconds)
    print(pair_created_sec)

    url = f"https://public-api.birdeye.so/defi/history_price?address={used_address}%3A%3A{splited[-2]}%3A%3A{splited[-1]}&address_type=token&type=30m&time_from={pair_created_sec}&time_to={timestamp_seconds}"
    print(timestamp_seconds, 'after b4')
    print(pair_created_sec, 'after afta')
    headers = {
        "accept": "application/json",
        "x-chain": "sui",
        "X-API-KEY": "0dfb9c6c2e2540629463db7a61891f70"
    }
    response = requests.get(url, headers=headers)
    data = response.json()['data']['items']
    with open('de.json','w')as file:
        json.dump(data,file,indent=4)
    max_entry = max(data, key=lambda x: x["value"])
    return max_entry["value"], max_entry["unixTime"]

def get_holders(token_address:str):
    gg = token_address.split('::')
    print(gg)
    using_address =gg[0]
    url = f"https://api.blockberry.one/sui/v1/coins/{using_address}%3A%3A{gg[-2]}%3A%3A{gg[-1]}/holders?page=0&size=10&orderBy=DESC&sortBy=AMOUNT"

    headers = {
        "accept": "*/*",
        "x-api-key": "XYxEyo08B6FZ6ulFvOznTnhoPZvD0O"
    }
    response = requests.get(url, headers=headers)
    data =response.json()
    total_percentage = sum(holder['percentage'] for holder in data['content'])
    values = []
    addresses = []
    count =0
    for items in data['content']:
        if count <5:
            addresses.append(f"https://suivision.xyz/account/{items['holderAddress']}")
            values.append(round(items['percentage'],1))
            count +=1
    # print(' | '.join(map(str,values)))
    with open('f.json','w')as file:
        json.dump(data,file,indent=4)
    output = " | ".join([f"<a href='{url}'>{num}</a>" for num, url in zip(values, addresses)])
    return output,total_percentage

def get_holders_count(token_address):
    try:
        splited = token_address.split('::')
        used_address =splited[0]
        url = f"https://api.blockberry.one/sui/v1/coins/{used_address}%3A%3A{splited[-2]}%3A%3A{splited[-1]}"

        headers = {
            "accept": "*/*",
            "x-api-key": "XYxEyo08B6FZ6ulFvOznTnhoPZvD0O"
        }

        response = requests.get(url, headers=headers)
        with open('fd.json','w')as file:
            json.dump(response.json(),file,indent=4)
        data = response.json()['holdersCount']
        dev_wallet =response.json()['creatorAddress']

        return data,dev_wallet
    except Exception as e:
        print(e)
# RQHohI3MlLTjDAcbDTjXGk1S0Iv2Wf

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


## =========== bot =================++#
async def is_user_admin(update:Update,context:ContextTypes.DEFAULT_TYPE):
    ## check if usser is admin
    chat_id = update.effective_chat.id
    user_id = update.message.from_user.id
    admins = await context.bot.get_chat_administrators(chat_id)
    return any(admin.user.id == user_id for admin in admins)

async def bot_added_to_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.my_chat_member.new_chat_member.status == 'member':
        chat_id = update.my_chat_member.chat.id
        group_name = update.my_chat_member.chat.title
        logger.info(f"Bot added to group '{group_name}' (Chat ID: {chat_id})")
        welcome_message = (
            f'''
🚀✨ Thanks for adding me to this group, lets explore together
'''   
        )
        await context.bot.send_message(chat_id=chat_id, text=welcome_message)
        #then it automatically creates a new key on the database
executor = ThreadPoolExecutor(max_workers=4)

async def start(update:Update,context : ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    chat_type:str = update.message.chat.type
    if chat_type == 'private':
        message = (
    "🎉 <b>Welcome to Emoji Bot!</b> 🎉\n\n"
    "🔍 Scan and explore to receive an <b>analytical security report</b> of tokens on the <b>Sui Blockchain</b>.\n\n"
    "🤔 For questions, join our socials and let's see if you can keep up:\n\n"
    # "<a href='https://t.me/Suiemoji'>📱 Telegram</a> | <a href='https://x.com/SuiEmoji'>🐦 X</a> | <a href='https://hop.ag/swap/SUI-EMOJI'>💰 Buy Emoji</a>\n\n"
    "ℹ️ Don't forget to add me to a group chat and make me an admin—I'm a lot of fun there! 🎈"
)       
        btn2= InlineKeyboardButton("🤑Buy Emoji Token", callback_data='edit_wallet',url='https://hop.ag/swap/SUI-EMOJI')
        btn9= InlineKeyboardButton("💬Join Emoji Chat" , callback_data='add_wallet',url='https://t.me/Suiemoji')
        btn10= InlineKeyboardButton("🖲️Use Emoji Tracker" , callback_data='add_wallet',url='https://t.me/Emojitracker_bot')
        row2= [btn2]
        row9= [btn9]
        row10= [btn10]
        reply_markup = InlineKeyboardMarkup([row2,row9,row10])
        await context.bot.send_message(user_id,text=message,reply_markup=reply_markup,parse_mode='HTML',disable_web_page_preview=True)

async def set_media(update:Update , context : ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    await context.bot.send_message(user_id,text = '🖼️Send an Image or GIF')
    context.user_data['awaiting_media'] = True


async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo or update.message.animation or update.message.text.startswith("http"):
        user_data = context.user_data
        if user_data.get('awaiting_media'):
            message = update.message
            chat_id = update.effective_chat.id
            try:
                if message.photo:
                    file_id = message.photo[-1].file_id
                    save_or_update_media_in_db(file_id, 'photo', chat_id)
                    await message.reply_text("Photo received and saved.")
                    context.user_data.clear()
                    user_data['awaiting_media'] = False
                elif message.animation:
                    file_id = message.document.file_id
                    save_or_update_media_in_db(file_id, 'gif', chat_id)
                    await message.reply_text("GIF received and saved.")
                    context.user_data.clear()
                    user_data['awaiting_media'] = False
                else:
                    context.user_data.clear()
                    user_data['awaiting_media'] = False
            except Exception as e:
                print(e)
                traceback.print_exc()
                print('An error occured please type /settings to send media')


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    message = update.message.text
    if update.message.text and update.message.text.startswith("http"):
    
        if context.user_data['awaiting_media'] ==True:
            file_url = update.message.text
            if file_url.endswith(".gif"):
                try:
                    gif_file = download_file(file_url)
                    response = await context.bot.send_document(chat_id=chat_id, document=gif_file)
                    file_id = response.document.file_id
                    save_or_update_media_in_db(file_id, 'gif', chat_id)
                    await update.message.reply_text("GIF received from the link and saved.")
                except Exception as e:
                    await update.message.reply_text(f"Failed to process the link: {e}")
            else:
                await update.message.reply_text("Please provide a valid GIF link.")
    else:
        if message.startswith('0x'):
            try:
                # Offload blocking I/O operations to a separate thread
                data = await asyncio.get_event_loop().run_in_executor(executor, get_token_pools, message)
                value = data['pairs'][0]
                async def get_values():
                    try:
                        holders_count,dev_wallet = await asyncio.get_event_loop().run_in_executor(executor, get_holders_count, message)
                        holders_count = special_format(int(holders_count))
                        creators_wallet = dev_wallet
                    except Exception as e:
                        holders_count = ''
                        creators_wallet = ''
                    pair_address = value.get('pairAddress', "N/A")
                    name = value.get('baseToken', {}).get('name', "N/A")
                    symbol = value.get('baseToken', {}).get('symbol', "N/A")
                    price_in_usd = value.get('priceUsd', "N/A")
                    fdv = value.get('marketCap', "N/A")
                    socials = value.get('info', {}).get('socials', [])
                    telegram_url = next((item['url'] for item in socials if item.get('type') == 'telegram'), None)
                    telegram = f"<a href='{telegram_url}'>TG</a>" if telegram_url else "N/A"
                    # Find the Twitter (X) URL
                    twitter_url = next((item['url'] for item in socials if item.get('type') == 'twitter'), None)
                    # Create the Twitter (X) link if the URL is found
                    twitter = f"<a href='{twitter_url}'>X</a>" if twitter_url else "N/A"
                    website = f"<a href='{value.get('info', {}).get('websites', [{}])[0].get('url', '')}'>WEB</a>" if value.get('info', {}).get('websites') else "N/A"
                    # twitter = f"<a href='{value.get('info', {}).get('socials', [{}])[0].get('url', '')}'>X</a>" if value.get('info', {}).get('socials') else "N/A"
                    # telegram = f"<a href='{value.get('info', {}).get('socials', [{}])[-1].get('url', '')}'>TG</a>" if value.get('info', {}).get('socials') else "N/A"
                    pair_created = calculate_age(value.get('pairCreatedAt', "N/A"))
                    pair_created_sec = (value.get('pairCreatedAt', "N/A"))
                    print(pair_created, 'age')
                    hr_24 = value.get('priceChange', {}).get('h24', "N/A")
                    hr_1 = value.get('priceChange', {}).get('h1', "N/A")
                    vol_in_usd = value.get('volume', {}).get('h24', "N/A")
                    tnx_buy_1hr = value.get('txns', {}).get('h1', {}).get('buys', "N/A")
                    tnx_sell_1hr = value.get('txns', {}).get('h1', {}).get('sells', "N/A")
                    vol_in_usd_1hr = value.get('volume', {}).get('h1', "N/A")
                    liquidity = value.get('liquidity', {}).get('usd', "N/A")
                    dex_id = value.get('dexId', "N/A")
                    date_to_use = value.get('pairCreatedAt', 0) // 1000
                    highest_value, corresponding_unix_time = await asyncio.get_event_loop().run_in_executor(executor, all_time_high, message, date_to_use)
                    print(highest_value,price_in_usd,fdv)
                    try:
                        ath = (float(highest_value) * float(fdv)) / float(price_in_usd) if highest_value and fdv and price_in_usd else "N/A"
                    except Exception as e:
                        ath = 'N/A'
                    dex_chart = f"<a href='https://dexscreener.com/sui/{pair_address}'>DEXSCRENEER</a>"
                    blue_dex = f"<a href='https://dex.bluemove.net/swap/0x2::sui::SUI/{pair_address}'>BLUEMOVE</a>"
                    birdeye = f"<a href='https://birdeye.so/token/{message}'>BIRDEYE</a>"
                    hog = f"<a href='https://hop.ag/swap/SUI-{symbol}'>HOP</a>"
                    holders, top_holders = await asyncio.get_event_loop().run_in_executor(executor, get_holders, message)
                    print(corresponding_unix_time)
                    time_for_ath = calculate_age(int(corresponding_unix_time * 1000)) if corresponding_unix_time else "N/A"
                    print(time_for_ath)

                    

                    return {
                        "pair_address": pair_address, "name": name, "symbol": symbol, "price_in_usd": price_in_usd, 
                        "fdv": fdv, "website": website, "twitter": twitter, "telegram": telegram, "pair_created": pair_created, 
                        "hr_24": hr_24, "hr_1": hr_1, "vol_in_usd": vol_in_usd, "tnx_buy_1hr": tnx_buy_1hr, 
                        "tnx_sell_1hr": tnx_sell_1hr, "vol_in_usd_1hr": vol_in_usd_1hr, "liquidity": liquidity, 
                        "dex_id": dex_id, "ath": ath, "dex_chart": dex_chart, "blue_dex": blue_dex, "birdeye": birdeye, 
                        "hog": hog, "holders": holders, "time_for_ath": time_for_ath, "holders_count": holders_count,
                        "top_holders": top_holders,'dev_wallet':creators_wallet
                    }

                values = await get_values()
                
                message_content = (
                    f"🟢<b>{values['name']} [{special_format(values['fdv'])}/{values['hr_24']}%]</b> ${values['symbol']}\n"
                    f"💧SUI @ {values['dex_id']}\n"
                    f"💰USD: <code>${special_format(values['price_in_usd'])}</code>\n"
                    f"💎FDV: <code>${special_format(values['fdv'])}</code>\n"
                    f"💦Liq: <code>${special_format(values['liquidity'])}</code>\n"
                    f"📊Vol: <code>${special_format(values['vol_in_usd'])} Age: {values['pair_created']}</code>\n"
                    
                    f"🌋ATH: <code>${special_format(values['ath'])} @ {values['time_for_ath']}</code> \n"
                    f"📉 1H: <code><a href ='#'>{special_format(values['hr_1'])}% | ${special_format(values['vol_in_usd_1hr'])} | 🅑 {values['tnx_buy_1hr']} | 🅢 {values['tnx_sell_1hr']}</a></code>\n"
                    f"💬{values['telegram']} | {values['twitter']} | {values['website']}\n\n"
                    f"TOP: {values['holders']}\n\n"
                    f"HOLDERS: {values['holders_count']} | TOP 10: {round(values['top_holders'], 2)}%\n\n"
                    f"DEV WALLET: <code>{values['dev_wallet']}</code>\n\n"
                    f"<code>{message}</code>\n\n"
                    f"{values['hog']} | {values['blue_dex']} | {values['birdeye']} | {values['dex_chart']}"
                )

                media = fetch_media_from_db(chat_id)
                if media:
                    file_id, file_type = media
                    if file_type == 'photo':
                        await context.bot.send_photo(chat_id=chat_id, photo=file_id,caption=message_content,parse_mode='HTML'),
                    elif file_type == 'gif':
                        await context.bot.send_document(chat_id=chat_id, document=file_id,caption = message_content,parse_mode='HTML'),
                else:
                    await context.bot.send_message(chat_id, text=message_content, parse_mode='HTML', disable_web_page_preview=True)

            except Exception as e:
                print(e)
                # await context.bot.send_message(chat_id=chat_id, text='An Error Occurred')

async def scan(update:Update,context = ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    the_args = context.args[0]
    print(the_args)
    try:
        if the_args:
            try:
                holders_count,dev_wallet = await asyncio.get_event_loop().run_in_executor(executor, get_holders_count, the_args)
                holders_count = special_format(int(holders_count))
                creators_wallet = dev_wallet
            except Exception as e:
                holders_count = ''
                creators_wallet = ''

            # Offload blocking I/O operations to a separate thread
            data = await asyncio.get_event_loop().run_in_executor(executor, get_token_pools, the_args)
            value = data['pairs'][0]
            # Collect all the values asynchronously
            async def get_values():
                pair_address = value.get('pairAddress', "N/A")
                name = value.get('baseToken', {}).get('name', "N/A")
                symbol = value.get('baseToken', {}).get('symbol', "N/A")
                price_in_usd = value.get('priceUsd', "N/A")
                fdv = value.get('marketCap', "N/A")

                socials = value.get('info', {}).get('socials', [])
                telegram_url = next((item['url'] for item in socials if item.get('type') == 'telegram'), None)
                telegram = f"<a href='{telegram_url}'>TG</a>" if telegram_url else "N/A"
                # Find the Twitter (X) URL
                twitter_url = next((item['url'] for item in socials if item.get('type') == 'twitter'), None)
                # Create the Twitter (X) link if the URL is found
                twitter = f"<a href='{twitter_url}'>X</a>" if twitter_url else "N/A"
                website = f"<a href='{value.get('info', {}).get('websites', [{}])[0].get('url', '')}'>WEB</a>" if value.get('info', {}).get('websites') else "N/A"
                pair_created = calculate_age(value.get('pairCreatedAt', "N/A"))
                hr_24 = value.get('priceChange', {}).get('h24', "N/A")
                hr_1 = value.get('priceChange', {}).get('h1', "N/A")
                vol_in_usd = value.get('volume', {}).get('h24', "N/A")
                tnx_buy_1hr = value.get('txns', {}).get('h1', {}).get('buys', "N/A")
                tnx_sell_1hr = value.get('txns', {}).get('h1', {}).get('sells', "N/A")
                vol_in_usd_1hr = value.get('volume', {}).get('h1', "N/A")
                liquidity = value.get('liquidity', {}).get('usd', "N/A")
                dex_id = value.get('dexId', "N/A")
                date_to_use = value.get('pairCreatedAt', 0) // 1000

                highest_value, corresponding_unix_time = await asyncio.get_event_loop().run_in_executor(executor, all_time_high, the_args, date_to_use)
                try:
                    ath = (float(highest_value) * float(fdv)) / float(price_in_usd) if highest_value and fdv and price_in_usd else "N/A"
                except Exception as e:
                    ath = 'N/A'
                dex_chart = f"<a href='https://dexscreener.com/sui/{pair_address}'>DEXSCRENEER</a>"
                blue_dex = f"<a href='https://dex.bluemove.net/swap/0x2::sui::SUI/{pair_address}'>BLUEMOVE</a>"
                birdeye = f"<a href='https://birdeye.so/token/{the_args}'>BIRDEYE</a>"
                hog = f"<a href='https://hop.ag/swap/SUI-{symbol}'>HOP</a>"
                holders, top_holders = await asyncio.get_event_loop().run_in_executor(executor, get_holders, the_args)
                time_for_ath = calculate_age(int(corresponding_unix_time * 1000)) if corresponding_unix_time else "N/A"

                return {
                    "pair_address": pair_address, "name": name, "symbol": symbol, "price_in_usd": price_in_usd, 
                    "fdv": fdv, "website": website, "twitter": twitter, "telegram": telegram, "pair_created": pair_created, 
                    "hr_24": hr_24, "hr_1": hr_1, "vol_in_usd": vol_in_usd, "tnx_buy_1hr": tnx_buy_1hr, 
                    "tnx_sell_1hr": tnx_sell_1hr, "vol_in_usd_1hr": vol_in_usd_1hr, "liquidity": liquidity, 
                    "dex_id": dex_id, "ath": ath, "dex_chart": dex_chart, "blue_dex": blue_dex, "birdeye": birdeye, 
                    "hog": hog, "holders": holders, "time_for_ath": time_for_ath, "holders_count": holders_count,
                    "top_holders": top_holders,'dev_wallet':creators_wallet
                }

            values = await get_values()
            message_content = (
                f"🟢<b>{values['name']} [{special_format(values['fdv'])}/{values['hr_24']}%]</b> ${values['symbol']}\n"
                f"💧SUI @ {values['dex_id']}\n"
                f"💰USD: <code>${special_format(values['price_in_usd'])}</code>\n"
                f"💎FDV: <code>${special_format(values['fdv'])}</code>\n"
                f"💦Liq: <code>${special_format(values['liquidity'])}</code>\n"
                f"📊Vol: <code>${special_format(values['vol_in_usd'])} Age: {values['pair_created']}</code>\n"
                f"🌋ATH: <code>${special_format(values['ath'])} @ {values['time_for_ath']}</code> \n"
                f"📉 1H: <code><a href ='#'>{special_format(values['hr_1'])}% | ${special_format(values['vol_in_usd_1hr'])} | 🅑 {values['tnx_buy_1hr']} | 🅢 {values['tnx_sell_1hr']}</a></code>\n"
                f"💬{values['telegram']} | {values['twitter']} | {values['website']}\n\n"
                f"TOP: {values['holders']}\n\n"
                f"HOLDERS: {values['holders_count']} | TOP 10: {round(values['top_holders'], 2)}%\n\n"
                f"DEV WALLET: <code>{values['dev_wallet']}</code>\n\n"
                f"<code>{the_args}</code>\n\n"
                f"{values['hog']} | {values['blue_dex']} | {values['birdeye']} | {values['dex_chart']}"
            )
            media = fetch_media_from_db(chat_id)
            if media:

                file_id, file_type = media
                if file_type == 'photo':
                    await context.bot.send_photo(chat_id=chat_id, photo=file_id,caption=message_content,parse_mode='HTML'),
                elif file_type == 'gif':
                    await context.bot.send_document(chat_id=chat_id, document=file_id,caption = message_content,parse_mode='HTML'),
            else:
                await context.bot.send_message(chat_id, text=message_content, parse_mode='HTML', disable_web_page_preview=True)
    except Exception as e:
        traceback.print_exc()
        print('heree',e)

TOKEN_KEY_ = '8137029737:AAHegPYrIqn64szuBQuLsxO6oLs_h0OqGMQ'
# TOKEN_KEY_ = '7112307264:AAHpaP5uZfU8bYb0pVE7j7WWnVLBQzejLvA'
def main():
    create_table()
    app = ApplicationBuilder().token(TOKEN_KEY_).build()
    app.add_handler(ChatMemberHandler(bot_added_to_group, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CommandHandler("scan", scan))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setmedia", set_media))
    app.add_handler(MessageHandler(filters.PHOTO | filters.ANIMATION, handle_media))


    # app.add_handler()
    app.run_polling()

if __name__ == '__main__':
    main()
