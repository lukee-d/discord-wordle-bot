import discord
from discord.ext import commands, tasks
import random
import datetime
import json
import os
import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# official wordle list
with open("wordle-answers-alphabetical.txt") as f:
    ANSWER_WORDS = [line.strip() for line in f]

with open("wordle-allowed-guesses.txt") as f:
    VALID_GUESSES = set(line.strip() for line in f)

ALL_VALID_WORDS = set(ANSWER_WORDS).union(VALID_GUESSES)

# Game storage with proper daily results
active_games = {}  # Maps user ID to game data
daily_results = {}  # Maps guild_id -> {date: {user_id: result}}
guild_settings = {}  # Maps guild_id -> {channel_id: str, streak_count: int, last_streak_date: str}
DATA_FILE = "wordle_data.json"

def load_data():
    """Load saved game data"""
    global daily_results, guild_settings
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
                daily_results = data.get('daily_results', {})
                guild_settings = data.get('guild_settings', {})
        except:
            daily_results = {}
            guild_settings = {}

def save_data():
    """Save game data"""
    with open(DATA_FILE, 'w') as f:
        json.dump({
            'daily_results': daily_results,
            'guild_settings': guild_settings
        }, f, indent=2)

def get_today_string():
    """Get today's date as string"""
    return datetime.date.today().strftime("%Y-%m-%d")

def get_yesterday_string():
    """Get yesterday's date as string"""
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    return yesterday.strftime("%Y-%m-%d")

def update_streak(guild_id):
    """Update the streak count for a guild"""
    guild_id = str(guild_id)
    today = get_today_string()
    yesterday = get_yesterday_string()
    
    if guild_id not in guild_settings:
        guild_settings[guild_id] = {'streak_count': 0, 'last_streak_date': None, 'channel_id': None}
    
    # Ensure all keys exist
    if 'streak_count' not in guild_settings[guild_id]:
        guild_settings[guild_id]['streak_count'] = 0
    if 'last_streak_date' not in guild_settings[guild_id]:
        guild_settings[guild_id]['last_streak_date'] = None
    if 'channel_id' not in guild_settings[guild_id]:
        guild_settings[guild_id]['channel_id'] = None
    
    # Check if anyone completed yesterday's Wordle
    if (guild_id in daily_results and 
        yesterday in daily_results[guild_id] and 
        len(daily_results[guild_id][yesterday]) > 0):
        
        # If this is the first day or consecutive day, increment streak
        if (guild_settings[guild_id]['last_streak_date'] is None or 
            guild_settings[guild_id]['last_streak_date'] == get_date_string_days_ago(2)):
            guild_settings[guild_id]['streak_count'] += 1
        else:
            # Reset streak if there was a gap
            guild_settings[guild_id]['streak_count'] = 1
        
        guild_settings[guild_id]['last_streak_date'] = yesterday
    else:
        # No one played yesterday, reset streak
        if guild_settings[guild_id]['last_streak_date'] == get_date_string_days_ago(2):
            # Streak was broken yesterday
            guild_settings[guild_id]['streak_count'] = 0
            guild_settings[guild_id]['last_streak_date'] = None
    
    save_data()

def get_date_string_days_ago(days):
    """Get date string for N days ago"""
    target_date = datetime.date.today() - datetime.timedelta(days=days)
    return target_date.strftime("%Y-%m-%d")

def get_daily_word():
    """Get today's word"""
    today = datetime.date.today()
    random.seed(today.toordinal())
    word = random.choice(ANSWER_WORDS)
    random.seed()
    return word

def get_feedback(guess, answer):
    """Get Wordle feedback"""
    feedback = []
    answer_chars = list(answer.lower())
    guess_chars = list(guess.lower())
    
    # First pass: mark correct positions
    for i in range(5):
        if guess_chars[i] == answer_chars[i]:
            feedback.append("🟩")
            answer_chars[i] = None
            guess_chars[i] = None
        else:
            feedback.append(None)
    
    # Second pass: mark wrong positions
    for i in range(5):
        if feedback[i] is None:
            if guess_chars[i] in answer_chars:
                feedback[i] = "🟨"
                answer_chars[answer_chars.index(guess_chars[i])] = None
            else:
                feedback[i] = "⬜"
    
    return "".join(feedback)

class WordleGame:
    def __init__(self, answer, user_id, guild_id):
        self.answer = answer.lower()
        self.guesses = []
        self.max_guesses = 6
        self.completed = False
        self.won = False
        self.user_id = user_id
        self.guild_id = guild_id
    
    def make_guess(self, guess):
        guess = guess.lower()
        if len(guess) != 5:
            return False, "Guess must be 5 letters!"
        
        if guess in [g[0] for g in self.guesses]:
            return False, "You already guessed that word!"
        
        feedback = get_feedback(guess, self.answer)
        self.guesses.append((guess, feedback))
        
        if guess == self.answer:
            self.completed = True
            self.won = True
        elif len(self.guesses) >= self.max_guesses:
            self.completed = True
            self.won = False
        
        return True, feedback
    
    def get_board_display(self):
        board = ""
        for guess, feedback in self.guesses:
            board += f"`{guess.upper()}` {feedback}\n"
        
        # Add empty rows
        for i in range(len(self.guesses), self.max_guesses):
            board += "`_____` ⬜⬜⬜⬜⬜\n"
        
        return board
    
    def get_result_string(self):
        """Get the shareable result string like real Wordle"""
        if not self.completed:
            return None
        
        result = f"Wordle {get_today_string()} "
        if self.won:
            result += f"{len(self.guesses)}/6\n\n"
        else:
            result += "X/6\n\n"
        
        # Add just the emoji grid
        for guess, feedback in self.guesses:
            result += feedback + "\n"
        
        return result

async def post_daily_summary(guild_id):
    """Post yesterday's results and current streak"""
    guild_id = str(guild_id)
    yesterday = get_yesterday_string()
    
    # Update streak before posting
    update_streak(guild_id)
    
    # Get channel to post in
    if (guild_id not in guild_settings or 
        guild_settings[guild_id].get('channel_id') is None):
        return  # No channel set
    
    channel_id = guild_settings[guild_id]['channel_id']
    channel = bot.get_channel(int(channel_id))
    if not channel:
        return
    
    # Get yesterday's results
    if (guild_id not in daily_results or 
        yesterday not in daily_results[guild_id] or 
        len(daily_results[guild_id][yesterday]) == 0):
        # No one played yesterday
        embed = discord.Embed(title="📊 Daily Better Wordle Summary", color=0xED4245)
        embed.add_field(name="No Activity Yesterday", 
                       value="No one completed yesterday's Better Wordle! 😔\nStreak broken.", 
                       inline=False)
        await channel.send(embed=embed)
        return
    
    results_data = daily_results[guild_id][yesterday]
    streak_count = guild_settings[guild_id].get('streak_count', 0)
    
    # Create the summary embed like the image
    embed = discord.Embed(title="📊 Daily Better Wordle Summary", color=0x5865F2)
    
    # Add streak info
    if streak_count > 0:
        embed.add_field(name=f"🔥 Your group is on a {streak_count} day streak!", 
                       value=f"Here are yesterday's results:", 
                       inline=False)
    else:
        embed.add_field(name="📊 Yesterday's Results", 
                       value="Here's how everyone did:", 
                       inline=False)
    
    # Sort results by performance (like the image)
    sorted_results = sorted(results_data.items(), 
                           key=lambda x: (not x[1]['won'], x[1]['guesses'] if x[1]['won'] else 999))
    
    # Group by score
    score_groups = {}
    for user_id, result in sorted_results:
        if result['won']:
            score = f"{result['guesses']}/6"
        else:
            score = "X/6"
        
        if score not in score_groups:
            score_groups[score] = []
        score_groups[score].append(result['username'])
    
    # Format like the image: "👑 4/6: @User1 @User2"
    result_lines = []
    for score in ["1/6", "2/6", "3/6", "4/6", "5/6", "6/6", "X/6"]:
        if score in score_groups:
            users = " ".join([f"@{name}" for name in score_groups[score]])
            if score == "1/6":
                result_lines.append(f"👑 {score}: {users}")
            elif score == "X/6":
                result_lines.append(f"❌ {score}: {users}")
            else:
                result_lines.append(f"✅ {score}: {users}")
    
    embed.add_field(name="Results", value="\n".join(result_lines), inline=False)
    
    # Add some stats
    total_players = len(results_data)
    winners = sum(1 for r in results_data.values() if r['won'])
    embed.add_field(name="📈 Stats", 
                   value=f"**Players:** {total_players} | **Success Rate:** {round(winners/total_players*100)}%", 
                   inline=False)
    
    await channel.send(embed=embed)

@tasks.loop(hours=24)
async def daily_summary_task():
    """Task that runs daily to post summaries"""
    # Post summary for all guilds that have it enabled
    for guild_id in guild_settings:
        if guild_settings[guild_id].get('channel_id'):
            try:
                await post_daily_summary(guild_id)
            except Exception as e:
                print(f"Error posting daily summary for guild {guild_id}: {e}")

@daily_summary_task.before_loop
async def before_daily_summary():
    """Wait until bot is ready before starting the task"""
    await bot.wait_until_ready()
    
    # Calculate time until next midnight (or a specific time like 12:01 AM)
    now = datetime.datetime.now()
    next_run = now.replace(hour=0, minute=1, second=0, microsecond=0) + datetime.timedelta(days=1)
    
    # Wait until then
    wait_seconds = (next_run - now).total_seconds()
    await asyncio.sleep(wait_seconds)

class GuessModal(discord.ui.Modal, title='Make a Guess'):
    def __init__(self, game):
        super().__init__()
        self.game = game

    guess = discord.ui.TextInput(
        label='Enter your 5-letter guess',
        placeholder='Type your guess here...',
        max_length=5,
        min_length=5,
    )

    async def on_submit(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        guess_word = self.guess.value.lower()
        
        # Validate the guess
        if guess_word not in ALL_VALID_WORDS:
            # Send a clear error message instead of another modal
            try:
                await interaction.response.send_message(
                    f"❌ **'{guess_word.upper()}'** is not a valid word!\n" +
                    "Please enter a valid 5-letter word from our dictionary.",
                    ephemeral=True
                )
            except discord.errors.InteractionResponded:
                await interaction.followup.send(
                    f"❌ **'{guess_word.upper()}'** is not a valid word!",
                    ephemeral=True
                )
            return
        
        success, feedback = self.game.make_guess(guess_word)
        
        if not success:
            try:
                await interaction.response.send_message(feedback, ephemeral=True)
            except discord.errors.InteractionResponded:
                await interaction.followup.send(feedback, ephemeral=True)
            return
        
        # Create the updated board display
        embed = discord.Embed(title="🎯 Better Wordle", color=0x2F3136)
        embed.add_field(name="Your Progress", value=self.game.get_board_display(), inline=False)
        embed.add_field(name=f"Guesses: {len(self.game.guesses)}/{self.game.max_guesses}", value="\u200b", inline=False)
        
        # Show the guess that was just made
        embed.add_field(name="✅ Valid Guess!", 
                       value=f"**'{guess_word.upper()}'** {feedback}", 
                       inline=False)
        
        if self.game.completed:
            # Save result to daily results
            guild_id = str(self.game.guild_id)
            today = get_today_string()
            
            if guild_id not in daily_results:
                daily_results[guild_id] = {}
            if today not in daily_results[guild_id]:
                daily_results[guild_id][today] = {}
            
            daily_results[guild_id][today][str(user_id)] = {
                'won': self.game.won,
                'guesses': len(self.game.guesses),
                'result_string': self.game.get_result_string(),
                'username': interaction.user.display_name
            }
            save_data()
            
            if self.game.won:
                embed.add_field(name="🎉 Congratulations!", value=f"You got it in {len(self.game.guesses)} guesses!", inline=False)
                embed.color = 0x57F287
            else:
                embed.add_field(name="😔 Game Over", value=f"The word was: **{self.game.answer.upper()}**", inline=False)
                embed.color = 0xED4245
            
            # Remove the game from active games
            if user_id in active_games:
                del active_games[user_id]
            
            try:
                await interaction.response.edit_message(embed=embed, view=None)
            except discord.errors.InteractionResponded:
                await interaction.edit_original_response(embed=embed, view=None)
        else:
            view = WordleView(self.game)
            try:
                await interaction.response.edit_message(embed=embed, view=view)
            except discord.errors.InteractionResponded:
                await interaction.edit_original_response(embed=embed, view=view)

class WordleView(discord.ui.View):
    def __init__(self, game):
        super().__init__(timeout=300)
        self.game = game

    @discord.ui.button(label='Make Guess', style=discord.ButtonStyle.primary, emoji='✏️')
    async def make_guess(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = GuessModal(self.game)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label='Give Up', style=discord.ButtonStyle.danger, emoji='❌')
    async def give_up(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        
        embed = discord.Embed(title="🎯 Better Wordle - Game Over", color=0xED4245)
        embed.add_field(name="You gave up!", value=f"The word was: **{self.game.answer.upper()}**", inline=False)
        embed.add_field(name="Your Progress", value=self.game.get_board_display(), inline=False)
        
        # Remove the game from active games
        if user_id in active_games:
            del active_games[user_id]
        
        await interaction.response.edit_message(embed=embed, view=None)

@bot.event
async def on_ready():
    print(f'Bot logged in as {bot.user}')
    
    load_data()  # Load saved data
    
    # Start the daily summary task
    if not daily_summary_task.is_running():
        daily_summary_task.start()
        print("Daily summary task started")
    
    # Simple sync - just try to sync and don't worry about complications
    try:
        synced = await bot.tree.sync()
        print(f'Synced {len(synced)} commands')
    except Exception as e:
        print(f'Failed to sync: {e}')

@bot.tree.command(name="betterwordle", description="Start a new Better Wordle game!")
async def betterwordle(interaction: discord.Interaction):
    user_id = interaction.user.id
    guild_id = interaction.guild_id
    
    # Check if user already has an active game
    if user_id in active_games:
        await interaction.response.send_message("You already have an active game! Finish it first or use the 'Give Up' button.", ephemeral=True)
        return
    
    # Check if user already completed today's Wordle
    today = get_today_string()
    if (str(guild_id) in daily_results and 
        today in daily_results[str(guild_id)] and 
        str(user_id) in daily_results[str(guild_id)][today]):
        
        result = daily_results[str(guild_id)][today][str(user_id)]
        embed = discord.Embed(title="🎯 Already Completed!", color=0x5865F2)
        embed.add_field(name="You've already played today!", 
                       value=f"Your result:\n```\n{result['result_string']}\n```", inline=False)
        embed.add_field(name="Come back tomorrow!", value="A new Wordle will be available tomorrow.", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    # Get today's word
    word = get_daily_word()
    game = WordleGame(word, user_id, guild_id)
    active_games[user_id] = game
    
    # Create initial embed
    embed = discord.Embed(title="🎯 Better Wordle - Daily Challenge", color=0x2F3136)
    embed.add_field(name="Your Progress", value=game.get_board_display(), inline=False)
    embed.add_field(name=f"Guesses: {len(game.guesses)}/{game.max_guesses}", value="\u200b", inline=False)
    embed.add_field(name="How to Play", value="Click 'Make Guess' to enter your 5-letter word!\n🟩 = Correct letter and position\n🟨 = Correct letter, wrong position\n⬜ = Letter not in word", inline=False)
    embed.add_field(name="Daily Word", value=f"Everyone gets the same word today!\nDate: {today}", inline=False)
    
    view = WordleView(game)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# Removed /play command - redundant with /wordlebot

# Removed /guess command - using interactive UI instead

@bot.tree.command(name="results", description="View today's Wordle results for this server")
async def results(interaction: discord.Interaction):
    guild_id = str(interaction.guild_id)
    today = get_today_string()
    
    embed = discord.Embed(title=f"📊 Daily Better Wordle Results - {today}", color=0x5865F2)
    
    if guild_id not in daily_results or today not in daily_results[guild_id]:
        embed.add_field(name="No Results Yet", value="No one has completed today's Better Wordle yet!\nUse `/betterwordle` to start playing!", inline=False)
        await interaction.response.send_message(embed=embed)
        return
    
    results_data = daily_results[guild_id][today]
    
    # Sort by completion status, then by number of guesses
    sorted_results = sorted(results_data.items(), key=lambda x: (not x[1]['won'], x[1]['guesses'] if x[1]['won'] else 999))
    
    completed_users = []
    failed_users = []
    
    for user_id, result in sorted_results:
        username = result['username']
        if result['won']:
            completed_users.append(f"✅ **{username}** - {result['guesses']}/6")
        else:
            failed_users.append(f"❌ **{username}** - X/6")
    
    if completed_users:
        embed.add_field(name="✅ Completed", value="\n".join(completed_users), inline=True)
    
    if failed_users:
        embed.add_field(name="❌ Failed", value="\n".join(failed_users), inline=True)
    
    total_players = len(results_data)
    completed_count = len(completed_users)
    success_rate = round((completed_count / total_players) * 100) if total_players > 0 else 0
    
    embed.add_field(name="📈 Server Stats", 
                   value=f"**Players:** {total_players}\n**Success Rate:** {success_rate}%", 
                   inline=False)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="stats", description="Show your Wordle statistics")
async def stats(interaction: discord.Interaction):
    try:
        embed = discord.Embed(title="📊 Your Better Wordle Stats", color=0x5865F2)
        embed.add_field(name="Coming Soon!", value="Personal stats tracking will be added in the next update!\nFor now, use `/results` to see today's server results.", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    except discord.errors.InteractionResponded:
        # Interaction was already responded to, ignore
        pass
    except Exception as e:
        print(f"Error in stats command: {e}")
        try:
            await interaction.followup.send("❌ Something went wrong with the stats command.", ephemeral=True)
        except:
            pass

@bot.tree.command(name="launch", description="Launch an activity")
async def launch(interaction: discord.Interaction):
    embed = discord.Embed(title="🚀 Activity Not Available", color=0xFEE75C)
    embed.add_field(name="Discord Activity Disabled", value="The Discord Activity feature is not currently available.\nUse `/betterwordle` to play Wordle with the interactive interface!", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="setchannel", description="Set the channel for daily Wordle summaries")
async def set_channel(interaction: discord.Interaction, channel: discord.TextChannel = None):
    # Check if user has manage channels permission
    if not interaction.user.guild_permissions.manage_channels:
        await interaction.response.send_message("❌ You need 'Manage Channels' permission to use this command.", ephemeral=True)
        return
    
    guild_id = str(interaction.guild_id)
    
    if channel is None:
        channel = interaction.channel
    
    # Initialize guild settings if needed
    if guild_id not in guild_settings:
        guild_settings[guild_id] = {'streak_count': 0, 'last_streak_date': None, 'channel_id': None}
    
    guild_settings[guild_id]['channel_id'] = str(channel.id)
    save_data()
    
    embed = discord.Embed(title="✅ Channel Set!", color=0x57F287)
    embed.add_field(name="Daily Summaries Enabled", 
                   value=f"Daily Better Wordle summaries will be posted in {channel.mention} at 12:01 AM!\n\nI'll show:\n🔥 Streak count\n📊 Yesterday's results\n📈 Server stats", 
                   inline=False)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="streak", description="Check the current Wordle streak for this server")
async def streak_command(interaction: discord.Interaction):
    guild_id = str(interaction.guild_id)
    
    # Update streak first
    update_streak(guild_id)
    
    if guild_id not in guild_settings:
        guild_settings[guild_id] = {'streak_count': 0, 'last_streak_date': None, 'channel_id': None}
    
    streak_count = guild_settings[guild_id].get('streak_count', 0)
    
    embed = discord.Embed(title="🔥 Server Better Wordle Streak", color=0x5865F2)
    
    if streak_count > 0:
        embed.add_field(name=f"Current Streak: {streak_count} days!", 
                       value="Keep it up! At least one person has completed Wordle every day.", 
                       inline=False)
        embed.color = 0x57F287
    else:
        embed.add_field(name="No Active Streak", 
                       value="Start a streak by having at least one person complete today's Better Wordle!", 
                       inline=False)
        embed.color = 0xED4245
    
    # Show if daily summaries are enabled
    if guild_settings[guild_id].get('channel_id'):
        channel = bot.get_channel(int(guild_settings[guild_id]['channel_id']))
        if channel:
            embed.add_field(name="📊 Daily Summaries", 
                           value=f"Enabled in {channel.mention}", 
                           inline=False)
    else:
        embed.add_field(name="📊 Daily Summaries", 
                       value="Not enabled. Use `/setchannel` to enable daily streak updates!", 
                       inline=False)
    
    await interaction.response.send_message(embed=embed)

# Get bot token
TOKEN = os.getenv('DISCORD_BOT_TOKEN')
if not TOKEN:
    print("Error: DISCORD_BOT_TOKEN not found!")
    exit(1)

bot.run(TOKEN)
