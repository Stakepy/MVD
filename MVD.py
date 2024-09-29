import discord
from discord.ext import commands, tasks
from discord.utils import get
import asyncio

intents = discord.Intents.default()
intents.members = True  # Для отслеживания участников
bot = commands.Bot(command_prefix="!", intents=intents)

# Роли
TEMP_ROLE_ID = id
APPROVED_ROLE_ID = id

# ID вашего аккаунта
ADMIN_ID = id

@bot.event
async def on_ready():
    print(f'Бот {bot.user} запущен и готов к работе.')

@bot.event
async def on_member_join(member):
    guild = member.guild
    temp_role = get(guild.roles, id=TEMP_ROLE_ID)

    # Выдать временную роль новому участнику
    await member.add_roles(temp_role)

    # Отправить сообщение администратору
    admin = bot.get_user(ADMIN_ID)
    embed = discord.Embed(title="Новый участник",
                          description=f"Участник {member.mention} присоединился к серверу.\nРазрешить ли ему вход?",
                          color=discord.Color.blue())
    message = await admin.send(embed=embed)

    # Добавить эмодзи для выбора
    await message.add_reaction('✅')
    await message.add_reaction('❌')

    def check(reaction, user):
        return user.id == ADMIN_ID and str(reaction.emoji) in ['✅', '❌'] and reaction.message.id == message.id

    try:
        reaction, user = await bot.wait_for('reaction_add', timeout=86400, check=check)  # 24 часа = 86400 секунд

        if str(reaction.emoji) == '✅':
            await member.remove_roles(temp_role)
            approved_role = get(guild.roles, id=APPROVED_ROLE_ID)
            await member.add_roles(approved_role)
            await admin.send(f'Участник {member.mention} был принят на сервер.')
        elif str(reaction.emoji) == '❌':
            await member.kick(reason="Отклонено администратором.")
            await admin.send(f'Участник {member.mention} был кикнут с сервера.')
    except asyncio.TimeoutError:
        # Если время ожидания истекло, одобряем автоматически
        await member.remove_roles(temp_role)
        approved_role = get(guild.roles, id=APPROVED_ROLE_ID)
        await member.add_roles(approved_role)
        await admin.send(f'Участник {member.mention} был автоматически принят на сервер спустя 24 часа.')

# Запуск бота
bot.run('token')
