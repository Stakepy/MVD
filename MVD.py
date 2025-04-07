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

# Конфигурация
TEMP_ROLE_ID = 1288585867774136454
APPROVED_ROLE_ID = 1282740488474067039
ADMIN_ID = 595160552758706187
ALLOWED_ROLE_IDS = [1226236176298541196, 1225212269541986365]
CURRENCY_CHANNEL_ID = 1292824634424819712
ADDITIONAL_CHANNELS = [1299347859828903977, 1289934447453667462, 1345863315569512558]

currency_flags = {
    "RUB": '🇷🇺',
    "UAH": '🇺🇦',
    "EUR": '🇪🇺',
    "USD": '🇺🇸',
    "CZK": '🇨🇿',
    "CNY": '🇨🇳'
}


def get_exchange_rates():
    url = "https://api.exchangerate-api.com/v4/latest/USD"
    response = requests.get(url)
    data = response.json()
    return {
        "RUB": data["rates"]["RUB"],
        "UAH": data["rates"]["UAH"],
        "EUR": data["rates"]["EUR"],
        "USD": 1,
        "CZK": data["rates"]["CZK"],
        "CNY": data["rates"]["CNY"]
    }


async def delete_old_messages(channel):
    async for message in channel.history(limit=100):
        await message.delete()


@bot.event
async def on_ready():
    print(f'Бот {bot.user} запущен.')
    currency_channel = bot.get_channel(CURRENCY_CHANNEL_ID)
    await delete_old_messages(currency_channel)
    await send_exchange_rates()

    for channel_id in ADDITIONAL_CHANNELS:
        if channel := bot.get_channel(channel_id):
            await delete_old_messages(channel)

    daily_tasks.start()
    await bot.tree.sync()


@bot.event
async def on_member_join(member):
    guild = member.guild
    temp_role = get(guild.roles, id=TEMP_ROLE_ID)
    await member.add_roles(temp_role)

    try:
        join_embed = discord.Embed(
            title="Добро пожаловать на **ВОСТОЧНЫЙ ФРОНТ**!",
            description="Производится проверка Ваших данных на разрешение пребывания на этом сервере. Проверка может занять до 24 часов.",
            color=discord.Color.gold()
        )
        join_embed.set_image(url="attachment://join.jpg")
        await member.send(
            file=discord.File("join.jpg"),
            embed=join_embed
        )
    except Exception as e:
        print(f"Ошибка отправки приветствия: {e}")

    admin = bot.get_user(ADMIN_ID)
    embed = discord.Embed(
        title="Новый участник",
        description=f"Участник {member.mention} присоединился к серверу.\nРазрешить ли ему вход?",
        color=0x3498db
    )
    message = await admin.send(embed=embed)
    for emoji in ['✅', '❌']:
        await message.add_reaction(emoji)

    def check(reaction, user):
        return user.id == ADMIN_ID and reaction.message.id == message.id

    try:
        reaction, _ = await bot.wait_for('reaction_add', timeout=86400, check=check)
        if str(reaction.emoji) == '✅':
            await member.remove_roles(temp_role)
            await member.add_roles(get(guild.roles, id=APPROVED_ROLE_ID))
            await member.send("✅ Виза разрешена! Добро пожаловать на сервер!")
            await admin.send(f'{member.mention} принят.')
        else:
            await member.send("Вам отказано в визе на въезд!")
            await member.kick(reason="Отклонено Правительством.")
            await admin.send(f'Участник {member.mention} был кикнут с сервера.')
    except asyncio.TimeoutError:
        await member.send("Время проверки истекло. Вы были автоматически исключены с сервера.")
        await member.kick(reason="Автоматическое исключение по истечении 24 часов без ответа от Правительства.")
        await admin.send(f'Участник {member.mention} был автоматически исключён с сервера спустя 24 часа.')


@tasks.loop(hours=24)
async def daily_tasks():
    now = datetime.now(pytz.timezone('Europe/Moscow'))
    next_run_time = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    await asyncio.sleep((next_run_time - now).total_seconds())

    currency_channel = bot.get_channel(CURRENCY_CHANNEL_ID)
    await delete_old_messages(currency_channel)
    await send_exchange_rates()

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
    # Проверяем, что команда вызвана в нужном канале
    if interaction.channel.id != CURRENCY_CHANNEL_ID:
        return await interaction.response.send_message(
            "❌ Команда доступна только в канале для курса валют.", ephemeral=True
        )

    rates = get_exchange_rates()
    embed = discord.Embed(title="Выберите валюту", description="Выберите валюту для сравнения:",
                          color=discord.Color.blue())
    await interaction.response.send_message(embed=embed)
    message = await interaction.original_response()

    for flag in ['🇷🇺', '🇺🇦', '🇪🇺', '🇺🇸', '🇨🇿', '🇨🇳', '❌']:
        await message.add_reaction(flag)

    def check(reaction, user):
        return user == interaction.user and str(reaction.emoji) in ['🇷🇺', '🇺🇦', '🇪🇺', '🇺🇸', '🇨🇿', '🇨🇳',
                                                                    '❌'] and reaction.message.id == message.id

    try:
        reaction, user = await bot.wait_for('reaction_add', timeout=60, check=check)
        await message.delete()

        if str(reaction.emoji) == '❌':
            await interaction.followup.send("Отмена.")
            return

        currency_map = {
            '🇷🇺': 'RUB', '🇺🇦': 'UAH', '🇪🇺': 'EUR', '🇺🇸': 'USD', '🇨🇿': 'CZK', '🇨🇳': "CNY"
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


@bot.tree.command(name="ban", description="Забанить пользователя")
@app_commands.describe(user="Пользователь для бана", reason="Причина бана")
@app_commands.guild_only()
async def ban(interaction: discord.Interaction, user: discord.Member, reason: str):
    try:
        # Немедленно подтверждаем взаимодействие
        await interaction.response.defer(ephemeral=True)

        # Проверка прав
        has_permission = interaction.user.id == ADMIN_ID
        if not has_permission:
            for role_id in ALLOWED_ROLE_IDS:
                if get(interaction.user.roles, id=role_id):
                    has_permission = True
                    break

        if not has_permission:
            return await interaction.followup.send(
                "❌ Недостаточно прав для выполнения команды!",
                ephemeral=True
            )

        # Отправка сообщения нарушителю
        try:
            ban_embed = discord.Embed(
                title="✪ ДЕПОРТАЦИЯ ✪",
                description=f"```json\n{{\n  \"сервер\": \"{interaction.guild.name}\",\n  \"причина\": \"{reason}\"\n}}```",
                color=discord.Color.red()
            )
            ban_embed.set_image(url="attachment://ban.gif")
            await user.send(
                file=discord.File("ban.gif"),
                embed=ban_embed
            )
        except Exception as e:
            print(f"Ошибка отправки бана: {e}")

        # Бан пользователя
        await user.ban(reason=reason)

        # Отправка финального ответа
        await interaction.followup.send(
            f"✅ Пользователь {user.mention} был депортирован!\nПричина: {reason}",
            ephemeral=True
        )

    except Exception as e:
        print(f"Критическая ошибка: {e}")
        await interaction.followup.send(
            "⚠️ Произошла ошибка при выполнении команды",
            ephemeral=True
        )


bot.run('token')