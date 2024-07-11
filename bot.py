import discord
from discord.ext import commands
from discord import app_commands
import datetime
import json
import os

DATA_FILE = 'data.json' # Replace with your file name

intents = discord.Intents.default()
intents.voice_states = True
intents.message_content = True

default_channelID = "YOUR_CHANNEL_ID"  # Replace with your channel ID and remove quotes
guild_id = "YOUR_GUILD_ID" # Replace with your guild ID and remove quotes
vc_id = "YOUR_VC_ID" # Replace with your voice channel ID and remove quotes
role_id = "YOUR_ROLE_ID" # Replace with your role ID and remove quotes

class MyClient(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.announced_members = set()
        self.call_start_time = None
        self.participants = set()
        self.channelID = default_channelID # Default channel ID to ping to
        self.muted_ids = set()
        self.call_leaderboard = []
        self.load_data()

    def load_data(self):
        print("Loading data...")
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, 'r') as f:
                    data = json.load(f)
                    self.muted_ids = set(data.get('muted_ids', []))
                    self.call_leaderboard = data.get('leaderboard', [])
                    self.channelID = data.get('channelID', self.channelID)  # Load channelID if available
                print("Data loaded successfully.")
                print(f"Current channel ID: {self.channelID}")

            except Exception as e:
                print(f"Error loading data: {e}")
                self.muted_ids = {12345}  # Default muted id remove if not needed
                self.call_leaderboard = []
                self.channelID = default_channelID  # Reset to default if error
        else:
            print("Data file not found. Using default values.")
            self.muted_ids = {12345}  # Default muted id remove if not needed
            self.call_leaderboard = []

    def save_data(self):
        data = {
            'muted_ids': list(self.muted_ids),
            'leaderboard': self.call_leaderboard,
            'channelID': self.channelID  # Save current channelID
        }
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f)

    async def setup_hook(self):
        guild = discord.Object(id=guild_id)
        self.tree.copy_global_to(guild=guild)
        print("Commands copied to guild.")
        await self.tree.sync(guild=guild)
        print("Commands synced!")

    async def on_ready(self):
        print(f'Logged in as {self.user}!')

client = MyClient()

async def is_dev(interaction: discord.Interaction) -> bool:
    authorized_ids = [690702052128718948] # My Discord ID replace with yours
    return interaction.user.id in authorized_ids

@client.tree.command(name='changechannel', description='Change the channel ID for pingss')
@app_commands.check(is_dev)
async def change_channel(interaction: discord.Interaction, arg: str):
    try:
        client.channelID = int(arg)
        client.save_data()
        author = interaction.user.name
        authorID = interaction.user.id

        response_message = f"Changed channel ID to {client.channelID}. Authorized by {author} with User ID {authorID}."
        await interaction.response.send_message(response_message)
        print(response_message)
    except ValueError:
        await interaction.response.send_message("Invalid channel ID. Please provide a valid integer.")

@client.tree.command(name='ping', description='Check bot response time')
async def ping(interaction: discord.Interaction):
    latency = client.latency * 1000  # Convert to milliseconds
    await interaction.response.send_message(f'Pong! Latency is {latency:.2f}ms')

@client.tree.command(name='leaderboard', description='Show the leaderboard of longest calls')
async def leaderboard(interaction: discord.Interaction):
    if not client.call_leaderboard:
        await interaction.response.send_message("No call data available.")
        return

    leaderboard_message = "Leaderboard of Longest Calls:\n"
    for index, duration in enumerate(client.call_leaderboard, 1):
        leaderboard_message += f"{index}. {duration}\n"
    
    await interaction.response.send_message(leaderboard_message)

@client.tree.command(name='mute', description='Prevent pings for a user')
@app_commands.check(is_dev)
async def mute(interaction: discord.Interaction, user_id: int):
    client.muted_ids.add(user_id)
    client.save_data()
    await interaction.response.send_message(f"User ID {user_id} has been muted.")

@client.tree.command(name='unmute', description='Allow pings for a user')
@app_commands.check(is_dev)
async def unmute(interaction: discord.Interaction, user_id: int):
    if user_id in client.muted_ids:
        client.muted_ids.remove(user_id)
        client.save_data()
        await interaction.response.send_message(f"User ID {user_id} has been unmuted.")
    else:
        await interaction.response.send_message(f"User ID {user_id} was not muted.")

@client.tree.command(name='receivepings', description='Receive pings for the voice channel')
async def receive_pings(interaction: discord.Interaction):
    role = discord.utils.get(interaction.guild.roles, name='ReceivePings')
    if role:
        if role in interaction.user.roles:
            await interaction.response.send_message("You already have the role ReceivePings!")
        else:
            await interaction.user.add_roles(role)
            await interaction.response.send_message("You now have the role ReceivePings!")
    else:
        await interaction.response.send_message("Role ReceivePings does not exist.")

# Helper function to convert HH:MM:SS to total seconds
def duration_to_seconds(duration: str) -> int:
    try:
        parts = duration.split(':')
        if len(parts) == 3:  # HH:MM:SS
            hours, minutes, seconds = map(int, parts)
        elif len(parts) == 2:  # MM:SS
            hours = 0
            minutes, seconds = map(int, parts)
        elif len(parts) == 1:  # SS
            hours = 0
            minutes = 0
            seconds = int(parts[0])
        else:
            raise ValueError("Unexpected duration format")
        return hours * 3600 + minutes * 60 + seconds
    except ValueError as e:
        print(f"Error converting duration to seconds: {e}")
        return 0

# Event for voice state updates
@client.event
async def on_voice_state_update(member, before, after):

    if member.id in client.muted_ids:
        return

    if after.channel and after.channel.id == vc_id:
        if len(client.participants) == 0:
            client.call_start_time = datetime.datetime.now()

        client.participants.add(member.id)

        if member.id not in client.announced_members:
            target_channel = client.get_channel(client.channelID)
            target_role = discord.utils.get(member.guild.roles, id=role_id)

            if target_channel:
                await target_channel.send(f'{member.display_name} has joined the voice channel! {target_role.mention}')
                client.announced_members.add(member.id)
            else:
                print("Channel not found or bot lacks permission to send a message in the channel.")

    elif before.channel and before.channel.id == vc_id:
        client.participants.discard(member.id)

        target_channel = client.get_channel(client.channelID)
        if target_channel:
            await target_channel.send(f'{member.display_name} has left the voice channel!')
        else:
            print("Channel not found or bot lacks permission to send a message in the channel.")

        if len(client.participants) == 0 and client.call_start_time:
            call_end_time = datetime.datetime.now()
            call_duration = call_end_time - client.call_start_time

            # Convert call duration to HH:MM:SS format
            call_duration_seconds = int(call_duration.total_seconds())
            hours, remainder = divmod(call_duration_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            call_duration_str = f"{hours:02}:{minutes:02}:{seconds:02}"

            if target_channel:
                await target_channel.send(f"{call_duration_str} Call Ended")
                print(f"Call ended at {call_end_time}, duration was {call_duration_str}")

            # Append duration to leaderboard and sort
            client.call_leaderboard.append(call_duration_str)
            client.call_leaderboard = sorted(client.call_leaderboard, key=duration_to_seconds, reverse=True)[:5]
            client.save_data()

            client.call_start_time = None

        client.announced_members.discard(member.id)

client.run('YOUR_BOT_TOKEN')
