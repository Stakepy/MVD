import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord.utils import get
import asyncio
import requests
from datetime import datetime, timedelta
import pytz

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Роли
TEMP_ROLE_ID = 1288585867774136454
APPROVED_ROLE_ID = 1282740488474067039

# ID вашего аккаунта
ADMIN_ID = 595160552758706187

# ID текстового канала для курса валют
CURRENCY_CHANNEL_ID = 1292824634424819712

# ID дополнительных каналов для очистки
ADDITIONAL_CHANNELS = [1234567890, 2345678901, 3456789012]  # Замените на реальные ID каналов

# Сопоставление валют и флагов
currency_flags = {
    "RUB": '🇷🇺',
    "UAH": '🇺🇦',
    "EUR": '🇪🇺',
    "USD": '🇺🇸',
    "CZK": '🇨🇿'
}


def get_exchange_rates():
    url = "https://api.exchangerate-api.com/v4/latest/USD"
    response = requests.get(url)
    data = response.json()
    rates = {
        "RUB": data["rates"]["RUB"],
        "UAH": data["rates"]["UAH"],
        "EUR": data["rates"]["EUR"],
        "USD": 1,
        "CZK": data["rates"]["CZK"]
    }
    return rates


async def delete_old_messages(channel):
    async for message in channel.history(limit=100):
        await message.delete()


@bot.event
async def on_ready():
    print(f'Бот {bot.user} запущен и готов к работе.')
    await send_exchange_rates()
    daily_tasks.start()
    try:
        synced = await bot.tree.sync()
        print(f"Синхронизировано {len(synced)} команд.")
    except Exception as e:
        print(f"Ошибка синхронизации команд: {e}")


@bot.event
async def on_member_join(member):
    guild = member.guild
    temp_role = get(guild.roles, id=TEMP_ROLE_ID)
    await member.add_roles(temp_role)
    admin = bot.get_user(ADMIN_ID)
    embed = discord.Embed(title="Новый участник",
                          description=f"Участник {member.mention} присоединился к серверу.\nРазрешить ли ему вход?",
                          color=discord.Color.blue())
    message = await admin.send(embed=embed)
    await message.add_reaction('✅')
    await message.add_reaction('❌')

    def check(reaction, user):
        return user.id == ADMIN_ID and str(reaction.emoji) in ['✅', '❌'] and reaction.message.id == message.id

    try:
        reaction, user = await bot.wait_for('reaction_add', timeout=86400, check=check)
        if str(reaction.emoji) == '✅':
            await member.remove_roles(temp_role)
            approved_role = get(guild.roles, id=APPROVED_ROLE_ID)
            await member.add_roles(approved_role)
            await admin.send(f'Участник {member.mention} был принят на сервер.')
        elif str(reaction.emoji) == '❌':
            await member.kick(reason="Отклонено администратором.")
            await admin.send(f'Участник {member.mention} был кикнут с сервера.')
    except asyncio.TimeoutError:
        await member.remove_roles(temp_role)
        approved_role = get(guild.roles, id=APPROVED_ROLE_ID)
        await member.add_roles(approved_role)
        await admin.send(f'Участник {member.mention} был автоматически принят на сервер спустя 24 часа.')


@tasks.loop(hours=24)
async def daily_tasks():
    now = datetime.now(pytz.timezone('Europe/Moscow'))
    next_run_time = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    await asyncio.sleep((next_run_time - now).total_seconds())

    # Очистка канала курса валют и отправка новых данных
    currency_channel = bot.get_channel(CURRENCY_CHANNEL_ID)
    await delete_old_messages(currency_channel)
    await send_exchange_rates()

    # Очистка дополнительных каналов
    for channel_id in ADDITIONAL_CHANNELS:
        channel = bot.get_channel(channel_id)
        if channel:
            await delete_old_messages(channel)


async def send_exchange_rates():
    channel = bot.get_channel(CURRENCY_CHANNEL_ID)
    rates = get_exchange_rates()
    embed = discord.Embed(title="Курсы валют на сегодня", color=discord.Color.green())
    for currency, rate in rates.items():
        flag = currency_flags.get(currency, '')
        embed.add_field(name=f"{flag} {currency}", value=f"{rate}", inline=False)
    await channel.send(embed=embed)


@bot.tree.command(name="kurs", description="Получить курс валют")
async def kurs(interaction: discord.Interaction, amount: float):
    rates = get_exchange_rates()
    embed = discord.Embed(title="Выберите валюту", description="Выберите валюту для сравнения:",
                          color=discord.Color.blue())
    await interaction.response.send_message(embed=embed)
    message = await interaction.original_response()

    for flag in ['🇷🇺', '🇺🇦', '🇪🇺', '🇺🇸', '🇨🇿', '❌']:
        await message.add_reaction(flag)

    def check(reaction, user):
        return user == interaction.user and str(reaction.emoji) in ['🇷🇺', '🇺🇦', '🇪🇺', '🇺🇸', '🇨🇿',
                                                                    '❌'] and reaction.message.id == message.id

    try:
        reaction, user = await bot.wait_for('reaction_add', timeout=60, check=check)
        await message.delete()

        if str(reaction.emoji) == '❌':
            await interaction.followup.send("Отмена.")
            return

        currency_map = {
            '🇷🇺': 'RUB', '🇺🇦': 'UAH', '🇪🇺': 'EUR', '🇺🇸': 'USD', '🇨🇿': 'CZK'
        }
        selected_currency = currency_map[str(reaction.emoji)]
        embed = discord.Embed(title=f"Курс валют для {amount} {selected_currency}", color=discord.Color.green())
        for currency, rate in rates.items():
            flag = currency_flags.get(currency, '')
            converted_amount = amount * rate / rates[selected_currency]
            embed.add_field(name=f"{flag} {currency}", value=f"{converted_amount:.2f}", inline=False)
        await interaction.followup.send(embed=embed)
    except asyncio.TimeoutError:
        await message.delete()
        await interaction.followup.send("Время ожидания истекло. Попробуйте снова.")


bot.run('')
