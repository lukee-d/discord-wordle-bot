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

# Get admin user ID from environment variable
ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID', 0))

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# official wordle list
try:
    with open("wordle-answers-alphabetical.txt") as f:
        ANSWER_WORDS = [line.strip() for line in f]
    
    with open("wordle-allowed-guesses.txt") as f:
        VALID_GUESSES = set(line.strip() for line in f)
except FileNotFoundError:
    print("Error: Word list files not found!")
    print("Make sure wordle-answers-alphabetical.txt and wordle-allowed-guesses.txt are uploaded")
    exit(1)

ALL_VALID_WORDS = set(ANSWER_WORDS).union(VALID_GUESSES)

# Game storage with proper daily results
active_games = {}  # Maps user ID to game data
daily_results = {}  # Maps guild_id -> {date: {user_id: result}}
guild_settings = {}  # Maps guild_id -> {channel_id: str, streak_count: int, last_streak_date: str}
user_stats = {}  # Maps user_id -> {games_played, games_won, guess_distribution, current_streak, max_streak, total_time, first_guesses}
DATA_FILE = "wordle_data.json"

def load_data():
    """Load saved game data"""
    global daily_results, guild_settings, user_stats
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
                daily_results = data.get('daily_results', {})
                guild_settings = data.get('guild_settings', {})
                user_stats = data.get('user_stats', {})
        except:
            daily_results = {}
            guild_settings = {}
            user_stats = {}

def save_data():
    """Save game data"""
    with open(DATA_FILE, 'w') as f:
        json.dump({
            'daily_results': daily_results,
            'guild_settings': guild_settings,
            'user_stats': user_stats
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

def update_user_stats(user_id, won, guesses, first_guess, game_time=None):
    """Update user statistics after a game"""
    user_id = str(user_id)
    
    if user_id not in user_stats:
        user_stats[user_id] = {
            'games_played': 0,
            'games_won': 0,
            'guess_distribution': {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0, '6': 0},
            'current_streak': 0,
            'max_streak': 0,
            'total_time': 0,
            'first_guesses': {},
            'average_guesses': 0.0,
            'last_played': None
        }
    
    stats = user_stats[user_id]
    stats['games_played'] += 1
    
    if won:
        stats['games_won'] += 1
        stats['guess_distribution'][str(guesses)] += 1
        
        # Update streak
        today = get_today_string()
        yesterday = get_yesterday_string()
        
        if stats['last_played'] == yesterday or stats['last_played'] is None:
            stats['current_streak'] += 1
        else:
            stats['current_streak'] = 1
        
        if stats['current_streak'] > stats['max_streak']:
            stats['max_streak'] = stats['current_streak']
    else:
        stats['current_streak'] = 0
    
    stats['last_played'] = get_today_string()
    
    # Track first guess patterns
    if first_guess in stats['first_guesses']:
        stats['first_guesses'][first_guess] += 1
    else:
        stats['first_guesses'][first_guess] = 1
    
    # Update average guesses (only for won games)
    if stats['games_won'] > 0:
        total_guesses = sum(int(k) * v for k, v in stats['guess_distribution'].items())
        stats['average_guesses'] = round(total_guesses / stats['games_won'], 2)
    
    if game_time:
        stats['total_time'] += game_time
    
    save_data()

def get_keyboard_display(guesses):
    """Generate a clean visual keyboard that works properly in Discord"""
    keyboard_layout = [
        ['Q', 'W', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P'],
        ['A', 'S', 'D', 'F', 'G', 'H', 'J', 'K', 'L'],
        ['Z', 'X', 'C', 'V', 'B', 'N', 'M']
    ]
    
    letter_status = {}  # Track best status for each letter
    
    # Analyze all guesses to determine letter status
    for guess, feedback in guesses:
        for i, letter in enumerate(guess.upper()):
            if feedback[i] == "🟩":  # Correct position
                letter_status[letter] = "🟩"
            elif feedback[i] == "🟨" and letter_status.get(letter) != "🟩":  # Wrong position but in word
                letter_status[letter] = "🟨"
            elif feedback[i] == "⬜" and letter not in letter_status:  # Not in word
                letter_status[letter] = "⬜"
    
    # Build visual keyboard display
    keyboard_display = ""
    for row in keyboard_layout:
        row_display = ""
        for letter in row:
            if letter in letter_status:
                if letter_status[letter] == "🟩":
                    row_display += f"🟩{letter} "  # Green background
                elif letter_status[letter] == "🟨":
                    row_display += f"🟨{letter} "  # Yellow background
                else:  # ⬜
                    row_display += f"⬜{letter} "  # Gray background
            else:
                row_display += f"⬛{letter} "  # Black background (unused)
        keyboard_display += row_display.rstrip() + "\n"

    
    return keyboard_display

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
        self.start_time = datetime.datetime.now()
    
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
    
    def get_enhanced_board_display(self):
        """Enhanced board display with progress indicators"""
        board = ""
        for i, (guess, feedback) in enumerate(self.guesses):
            board += f"**{i+1}.** `{guess.upper()}` {feedback}\n"
        
        # Add empty rows with numbers
        for i in range(len(self.guesses), self.max_guesses):
            board += f"**{i+1}.** `_____` ⬜⬜⬜⬜⬜\n"
        
        return board
    
    def get_game_time(self):
        """Get time spent on the game in seconds"""
        if self.completed:
            return (datetime.datetime.now() - self.start_time).total_seconds()
        return 0
    
    def get_result_string(self):
        """Get the shareable result string like real Wordle"""
        if not self.completed:
            return None
        
        result = f"Better Wordle {get_today_string()} "
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
    
    # Get yesterday's word
    yesterday_date = datetime.date.today() - datetime.timedelta(days=1)
    random.seed(yesterday_date.toordinal())
    yesterday_word = random.choice(ANSWER_WORDS).upper()
    random.seed()
    
    # Get yesterday's results
    if (guild_id not in daily_results or 
        yesterday not in daily_results[guild_id] or 
        len(daily_results[guild_id][yesterday]) == 0):
        # No one played yesterday
        embed = discord.Embed(title="📊 Daily Better Wordle Summary", color=0xED4245)
        embed.add_field(name="💔 No Activity Yesterday", 
                       value=f"No one completed yesterday's Better Wordle! 😔\n**Yesterday's word was: {yesterday_word}**\nStreak broken.", 
                       inline=False)
        embed.set_footer(text=f"Date: {yesterday}")
        await channel.send(embed=embed)
        return
    
    results_data = daily_results[guild_id][yesterday]
    streak_count = guild_settings[guild_id].get('streak_count', 0)
    
    # Create the enhanced summary embed
    embed = discord.Embed(title="📊 Daily Better Wordle Summary", color=0x5865F2)
    
    # Add yesterday's word
    embed.add_field(name="🎯 Yesterday's Word", value=f"**{yesterday_word}**", inline=False)
    
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
            users = " • ".join([f"**{name}**" for name in score_groups[score]])
            if score == "1/6":
                result_lines.append(f"👑 {score}: {users}")
            elif score == "2/6":
                result_lines.append(f"🥇 {score}: {users}")
            elif score == "X/6":
                result_lines.append(f"❌ {score}: {users}")
            else:
                result_lines.append(f"✅ {score}: {users}")
    
    embed.add_field(name="🏆 Results", value="\n".join(result_lines), inline=False)
    
    # Add enhanced stats
    total_players = len(results_data)
    winners = sum(1 for r in results_data.values() if r['won'])
    
    # Calculate average guesses for winners
    total_guesses = sum(r['guesses'] for r in results_data.values() if r['won'])
    avg_guesses = round(total_guesses / winners, 1) if winners > 0 else 0
    
    # Find fastest solver if time data exists
    fastest_time = None
    fastest_player = None
    for user_id, result in results_data.items():
        if result['won'] and 'game_time' in result and result['game_time'] < 300:  # Less than 5 minutes
            if fastest_time is None or result['game_time'] < fastest_time:
                fastest_time = result['game_time']
                fastest_player = result['username']
    
    stats_text = f"**Players:** {total_players} | **Success Rate:** {round(winners/total_players*100)}%"
    if avg_guesses > 0:
        stats_text += f" | **Avg Guesses:** {avg_guesses}"
    if fastest_player:
        time_str = f"{int(fastest_time // 60)}m {int(fastest_time % 60)}s" if fastest_time >= 60 else f"{int(fastest_time)}s"
        stats_text += f"\n⚡ **Fastest:** {fastest_player} ({time_str})"
    
    embed.add_field(name="📈 Stats", value=stats_text, inline=False)
    
    embed.set_footer(text=f"Date: {yesterday} • Use /betterwordle to play today!")
    
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
        embed.add_field(name="📋 Your Progress", value=self.game.get_enhanced_board_display(), inline=False)
        
        # Add keyboard display
        if len(self.game.guesses) > 0:
            keyboard = get_keyboard_display(self.game.guesses)
            embed.add_field(name="⌨️ Keyboard", value=f"```\n{keyboard}\n```", inline=False)
        
        embed.add_field(name=f"📊 Progress: {len(self.game.guesses)}/{self.game.max_guesses}", value="\u200b", inline=False)
        
        # Show the guess that was just made with better formatting
        embed.add_field(name="✅ Valid Guess!", 
                       value=f"**'{guess_word.upper()}'** {feedback}", 
                       inline=False)
        
        if self.game.completed:
            # Calculate game time
            game_time = self.game.get_game_time()
            
            # Update user statistics
            first_guess = self.game.guesses[0][0] if self.game.guesses else None
            update_user_stats(user_id, self.game.won, len(self.game.guesses), first_guess, game_time)
            
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
                'username': interaction.user.display_name,
                'game_time': round(game_time)
            }
            save_data()
            
            if self.game.won:
                # Different colors and messages based on performance
                if len(self.game.guesses) == 1:
                    embed.add_field(name="🤯 INCREDIBLE!", value="Got it in 1 guess! Are you psychic?! 🔮", inline=False)
                    embed.color = 0xFFD700  # Gold
                elif len(self.game.guesses) <= 2:
                    embed.add_field(name="🏆 AMAZING!", value=f"Solved in {len(self.game.guesses)} guesses! Brilliant! ⭐", inline=False)
                    embed.color = 0xFFD700  # Gold
                elif len(self.game.guesses) <= 4:
                    embed.add_field(name="🎉 Great job!", value=f"Solved in {len(self.game.guesses)} guesses! Well done! 👏", inline=False)
                    embed.color = 0x57F287  # Green
                else:
                    embed.add_field(name="✅ Nice work!", value=f"Got it in {len(self.game.guesses)} guesses! 🎯", inline=False)
                    embed.color = 0x5865F2  # Blue
                
                # Add time info if reasonable
                if game_time < 300:  # Less than 5 minutes
                    time_str = f"{int(game_time // 60)}m {int(game_time % 60)}s" if game_time >= 60 else f"{int(game_time)}s"
                    embed.add_field(name="⏱️ Time", value=time_str, inline=True)
            else:
                embed.add_field(name="😔 Game Over", value=f"The word was: **{self.game.answer.upper()}**\nBetter luck next time! 💪", inline=False)
                embed.color = 0xED4245  # Red
            
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
    
    # Create initial embed with enhanced design
    embed = discord.Embed(title="🎯 Better Wordle - Daily Challenge", color=0x5865F2)
    embed.add_field(name="📋 Your Progress", value=game.get_enhanced_board_display(), inline=False)
    embed.add_field(name=f"📊 Progress: {len(game.guesses)}/{game.max_guesses}", value="\u200b", inline=False)
    embed.add_field(name="🎮 How to Play", 
                   value="Click **'Make Guess'** to enter your 5-letter word!\n" +
                         "🟩 = Correct letter and position\n" +
                         "🟨 = Correct letter, wrong position\n" +
                         "⬜ = Letter not in word", 
                   inline=False)
    embed.add_field(name="📅 Daily Challenge", 
                   value=f"Everyone gets the same word today!\n**Date:** {today}", 
                   inline=False)
    embed.set_footer(text="💡 Tip: Common starting words include ADIEU, SLATE, or CRANE!")
    
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

@bot.tree.command(name="mystats", description="View your personal Better Wordle statistics")
async def my_stats(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    
    if user_id not in user_stats or user_stats[user_id]['games_played'] == 0:
        embed = discord.Embed(title="📊 Your Better Wordle Stats", color=0x5865F2)
        embed.add_field(name="No Games Yet!", 
                       value="You haven't played any games yet!\nUse `/betterwordle` to start your first game! 🎯", 
                       inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    stats = user_stats[user_id]
    
    # Calculate win percentage
    win_percentage = round((stats['games_won'] / stats['games_played']) * 100) if stats['games_played'] > 0 else 0
    
    # Create main stats embed
    embed = discord.Embed(title=f"📊 {interaction.user.display_name}'s Better Wordle Stats", color=0x5865F2)
    
    # Main stats
    embed.add_field(name="🎮 Games Played", value=str(stats['games_played']), inline=True)
    embed.add_field(name="🏆 Games Won", value=str(stats['games_won']), inline=True)
    embed.add_field(name="📈 Win Rate", value=f"{win_percentage}%", inline=True)
    
    # Streak stats
    embed.add_field(name="🔥 Current Streak", value=str(stats['current_streak']), inline=True)
    embed.add_field(name="⭐ Best Streak", value=str(stats['max_streak']), inline=True)
    embed.add_field(name="🎯 Avg Guesses", value=str(stats['average_guesses']) if stats['games_won'] > 0 else "N/A", inline=True)
    
    # Guess distribution (only if they have wins)
    if stats['games_won'] > 0:
        distribution = ""
        for i in range(1, 7):
            count = stats['guess_distribution'][str(i)]
            if count > 0:
                # Create a simple bar chart
                bar_length = min(20, int((count / stats['games_won']) * 20))
                bar = "█" * bar_length + "░" * (20 - bar_length)
                distribution += f"**{i}**: {count} {bar}\n"
        
        if distribution:
            embed.add_field(name="📊 Guess Distribution", value=distribution, inline=False)
    
    # Favorite starting word
    if stats['first_guesses']:
        favorite_word = max(stats['first_guesses'].items(), key=lambda x: x[1])
        embed.add_field(name="💭 Favorite First Guess", 
                       value=f"**{favorite_word[0].upper()}** (used {favorite_word[1]} times)", 
                       inline=False)
    
    # Last played
    if stats['last_played']:
        embed.add_field(name="📅 Last Played", value=stats['last_played'], inline=True)
    
    # Add some fun achievements
    achievements = []
    if stats['max_streak'] >= 10:
        achievements.append("🔥 consistent goat")
    if stats['games_played'] >= 30:
        achievements.append("🎮 longevity goat")
    if any(stats['guess_distribution'][str(i)] > 0 for i in [1, 2]):
        achievements.append("🎯 speedy goat")
    if stats['games_won'] >= 100:
        achievements.append("🏆 super goat")
    
    if achievements:
        embed.add_field(name="🏅 Achievements", value=" • ".join(achievements), inline=False)
    
    embed.set_footer(text="💡 Keep playing to improve your stats!")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="leaderboard", description="View the server leaderboard")
async def leaderboard(interaction: discord.Interaction, category: str = "winrate"):
    """
    Show server leaderboard
    category: winrate, streak, games, average
    """
    guild_id = str(interaction.guild_id)
    
    # Get all users who have played in this server
    server_players = set()
    if guild_id in daily_results:
        for date_results in daily_results[guild_id].values():
            server_players.update(date_results.keys())
    
    if not server_players:
        embed = discord.Embed(title="� Server Leaderboard", color=0x5865F2)
        embed.add_field(name="No Players Yet!", 
                       value="No one has played Better Wordle in this server yet!\nUse `/betterwordle` to be the first! 🎯", 
                       inline=False)
        await interaction.response.send_message(embed=embed)
        return
    
    # Filter users who have stats and played in this server
    valid_players = []
    for user_id in server_players:
        if user_id in user_stats and user_stats[user_id]['games_played'] > 0:
            stats = user_stats[user_id]
            try:
                user = await bot.fetch_user(int(user_id))
                username = user.display_name if user else f"User {user_id[:8]}"
            except:
                username = f"User {user_id[:8]}"
            
            valid_players.append({
                'user_id': user_id,
                'username': username,
                'stats': stats
            })
    
    if not valid_players:
        embed = discord.Embed(title="📈 Server Leaderboard", color=0x5865F2)
        embed.add_field(name="No Stats Available", 
                       value="No players have enough data for the leaderboard yet!", 
                       inline=False)
        await interaction.response.send_message(embed=embed)
        return
    
    # Sort based on category
    if category.lower() == "winrate":
        # Sort by win rate, then by games played
        valid_players.sort(key=lambda x: (
            (x['stats']['games_won'] / x['stats']['games_played']) * 100 if x['stats']['games_played'] > 0 else 0,
            x['stats']['games_played']
        ), reverse=True)
        title = "📈 Leaderboard - Win Rate"
        
    elif category.lower() == "streak":
        # Sort by max streak, then current streak
        valid_players.sort(key=lambda x: (x['stats']['max_streak'], x['stats']['current_streak']), reverse=True)
        title = "🔥 Leaderboard - Best Streaks"
        
    elif category.lower() == "games":
        # Sort by games played
        valid_players.sort(key=lambda x: x['stats']['games_played'], reverse=True)
        title = "🎮 Leaderboard - Most Active"
        
    elif category.lower() == "average":
        # Sort by average guesses (lower is better, but only for players with wins)
        players_with_wins = [p for p in valid_players if p['stats']['games_won'] > 0]
        players_with_wins.sort(key=lambda x: x['stats']['average_guesses'])
        valid_players = players_with_wins
        title = "🎯 Leaderboard - Best Average"
        
    else:
        category = "winrate"  # Default fallback
        valid_players.sort(key=lambda x: (
            (x['stats']['games_won'] / x['stats']['games_played']) * 100 if x['stats']['games_played'] > 0 else 0,
            x['stats']['games_played']
        ), reverse=True)
        title = "📈 Leaderboard - Win Rate"
    
    embed = discord.Embed(title=title, color=0x5865F2)
    
    # Show top 10 players
    leaderboard_text = ""
    for i, player in enumerate(valid_players[:10]):
        stats = player['stats']
        username = player['username']
        
        if i == 0:
            rank_emoji = "👑"
        elif i == 1:
            rank_emoji = "🥈"
        elif i == 2:
            rank_emoji = "🥉"
        else:
            rank_emoji = f"**{i+1}.**"
        
        if category.lower() == "winrate":
            win_rate = round((stats['games_won'] / stats['games_played']) * 100) if stats['games_played'] > 0 else 0
            leaderboard_text += f"{rank_emoji} **{username}** - {win_rate}% ({stats['games_won']}/{stats['games_played']})\n"
            
        elif category.lower() == "streak":
            leaderboard_text += f"{rank_emoji} **{username}** - Best: {stats['max_streak']}, Current: {stats['current_streak']}\n"
            
        elif category.lower() == "games":
            leaderboard_text += f"{rank_emoji} **{username}** - {stats['games_played']} games played\n"
            
        elif category.lower() == "average":
            leaderboard_text += f"{rank_emoji} **{username}** - {stats['average_guesses']} avg guesses\n"
    
    embed.add_field(name="🏆 Top Players", value=leaderboard_text or "No data available", inline=False)
    
    # Add category selection info
    embed.add_field(name="📊 Categories", 
                   value="Use `/leaderboard <category>` where category is:\n" +
                         "• `winrate` - Win percentage\n" +
                         "• `streak` - Best streaks\n" +
                         "• `games` - Most active players\n" +
                         "• `average` - Best average guesses", 
                   inline=False)
    
    embed.set_footer(text=f"Showing data from {len(valid_players)} players")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="debug2847", description="System diagnostic tool")
async def debug_word_check(interaction: discord.Interaction):
    # Whitelist of authorized user IDs
    AUTHORIZED_USERS = [
        ADMIN_USER_ID,  # Admin user from environment variable
    ]
    
    # Check if user is in the authorized list
    if interaction.user.id not in AUTHORIZED_USERS:
        await interaction.response.send_message("❌ Access denied.", ephemeral=True)
        return
    
    # Get today's word
    word = get_daily_word()
    today = get_today_string()
    
    embed = discord.Embed(title="🔍 Admin Debug - Today's Word", color=0xFF6B6B)
    embed.add_field(name="⚠️ Admin Only", 
                   value="This command is for debugging purposes only.\nDo not share this word with players!", 
                   inline=False)
    embed.add_field(name="📅 Date", value=today, inline=True)
    embed.add_field(name="🎯 Today's Word", value=f"**{word.upper()}**", inline=True)
    embed.add_field(name="💡 Debug Info", 
                   value=f"Word length: {len(word)}\nIs valid answer: {word.lower() in ANSWER_WORDS}\nIs valid guess: {word.lower() in ALL_VALID_WORDS}", 
                   inline=False)
    
    # Show how many people have played today
    guild_id = str(interaction.guild_id)
    today_players = 0
    if guild_id in daily_results and today in daily_results[guild_id]:
        today_players = len(daily_results[guild_id][today])
    
    embed.add_field(name="📊 Today's Activity", 
                   value=f"Players who completed today: {today_players}", 
                   inline=False)
    
    embed.set_footer(text="🚨 This message is only visible to you")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="reset1947", description="System cache reset utility")
async def reset_cache(interaction: discord.Interaction):
    # Whitelist of authorized user IDs
    AUTHORIZED_USERS = [
        ADMIN_USER_ID,  # Admin user from environment variable
    ]
    
    # Check if user is in the authorized list
    if interaction.user.id not in AUTHORIZED_USERS:
        await interaction.response.send_message("❌ Access denied.", ephemeral=True)
        return
    
    user_id = str(interaction.user.id)
    guild_id = str(interaction.guild_id)
    today = get_today_string()
    
    # Check if user has completed today's puzzle
    reset_performed = False
    if (guild_id in daily_results and 
        today in daily_results[guild_id] and 
        user_id in daily_results[guild_id][today]):
        
        # Remove the user's completion record for today
        del daily_results[guild_id][today][user_id]
        
        # If no one else played today, remove the empty date entry
        if len(daily_results[guild_id][today]) == 0:
            del daily_results[guild_id][today]
        
        save_data()
        reset_performed = True
    
    # Also remove from active games if they have one
    if interaction.user.id in active_games:
        del active_games[interaction.user.id]
    
    embed = discord.Embed(title="🔄 Cache Reset Complete", color=0x57F287 if reset_performed else 0xFEE75C)
    
    if reset_performed:
        embed.add_field(name="✅ Reset Successful", 
                       value=f"Your completion status for {today} has been cleared.\nYou can now play today's puzzle again for testing.", 
                       inline=False)
    else:
        embed.add_field(name="ℹ️ No Reset Needed", 
                       value=f"No completion record found for {today}.\nYou can play today's puzzle normally.", 
                       inline=False)
    
    embed.add_field(name="⚠️ Debug Mode", 
                   value="This is a debugging tool. Your personal stats remain unchanged.", 
                   inline=False)
    
    embed.set_footer(text="🚨 This message is only visible to you")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="clearstats9182", description="System data cleanup utility")
async def clear_user_data(interaction: discord.Interaction):
    # Whitelist of authorized user IDs
    AUTHORIZED_USERS = [
        ADMIN_USER_ID,  # Admin user from environment variable
    ]
    
    # Check if user is in the authorized list
    if interaction.user.id not in AUTHORIZED_USERS:
        await interaction.response.send_message("❌ Access denied.", ephemeral=True)
        return
    
    user_id = str(interaction.user.id)
    
    # Check if user has any stats to clear
    stats_existed = user_id in user_stats and user_stats[user_id]['games_played'] > 0
    
    if stats_existed:
        # Store current stats for confirmation message
        old_games = user_stats[user_id]['games_played']
        old_wins = user_stats[user_id]['games_won']
        old_streak = user_stats[user_id]['max_streak']
        
        # Reset user stats to default
        user_stats[user_id] = {
            'games_played': 0,
            'games_won': 0,
            'guess_distribution': {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0, '6': 0},
            'current_streak': 0,
            'max_streak': 0,
            'total_time': 0,
            'first_guesses': {},
            'average_guesses': 0.0,
            'last_played': None
        }
        
        save_data()
        
        embed = discord.Embed(title="🗑️ Stats Reset Complete", color=0xED4245)
        embed.add_field(name="⚠️ PERMANENT RESET", 
                       value=f"All personal statistics have been permanently cleared.\n\n**Previous Stats:**\n• Games: {old_games}\n• Wins: {old_wins}\n• Best Streak: {old_streak}", 
                       inline=False)
        embed.add_field(name="✅ Fresh Start", 
                       value="Your stats counter is now reset to zero.\nDaily completion records remain unchanged.", 
                       inline=False)
    else:
        embed = discord.Embed(title="🗑️ Stats Reset", color=0xFEE75C)
        embed.add_field(name="ℹ️ No Stats Found", 
                       value="No personal statistics found to clear.\nYour account is already at a fresh start.", 
                       inline=False)
    
    embed.add_field(name="⚠️ Nuclear Option", 
                   value="This is a permanent action. Stats cannot be recovered.", 
                   inline=False)
    
    embed.set_footer(text="🚨 This message is only visible to you")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

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
