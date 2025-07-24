# Better Wordle Bot

A comprehensive Discord bot that brings an enhanced Wordle experience to your server with interactive gameplay, advanced statistics, leaderboards, daily streaks, and automatic summaries!

## ✨ Features

### 🎯 Interactive Gameplay
- **Click-to-play interface** with buttons and modals - no more typing commands for each guess!
- **Daily words** - everyone gets the same word each day using official Wordle word lists
- **Enhanced validation** with 13,000+ valid words (official Wordle dictionary)
- **Visual feedback** with emoji squares (🟩🟨⬜) and interactive keyboard display
- **One game per day** per user with smart duplicate prevention
- **Performance celebrations** - special messages for incredible plays (1-guess wins!)
- **Game timing** - tracks how long each game takes

### � Advanced Statistics
- **Personal stats** - detailed analytics for each player
  - Games played, win rate, current/max streaks
  - Guess distribution with visual bar charts
  - Average guesses and favorite starting words
  - Achievement system (speedy goat, consistent goat, etc.)
- **Server leaderboards** - compete with friends across multiple categories
  - Win rate rankings
  - Best streaks
  - Most active players
  - Best average guesses
- **Comprehensive tracking** - all stats persist across games and servers

### 🔥 Streak Tracking & Automation
- **Server streaks** - counts consecutive days with at least 1 completion
- **Automatic daily summaries** posted at 12:01 AM with professional formatting
- **Enhanced results display** - grouped by performance with crown/medal emojis
- **Success rate tracking** - server-wide statistics and analytics
- **Fastest completion times** - speed leaderboards for quick solvers

### ⌨️ Visual Enhancements
- **Interactive keyboard display** - see which letters you've tried at a glance
- **Enhanced board layout** - numbered rows and clear progress indicators
- **Performance-based colors** - different celebration colors based on solve speed
- **Clean embed formatting** - professional Discord embed design

## 🎮 Commands

| Command | Description |
|---------|-------------|
| `/betterwordle` | Start a new Better Wordle game with interactive interface |
| `/help` | Show all commands and how to play (great for new users!) |
| `/mystats` | View your personal detailed statistics and achievements |
| `/leaderboard [category]` | View server leaderboards (winrate/streak/games/average) |
| `/results` | View today's server results and completions |
| `/streak` | Check current server streak status |
| `/setchannel [channel]` | Set channel for daily summaries (requires Manage Channels) |
| `/launch` | Handle Discord Activity requests gracefully |

### 🔧 Admin Debug Commands (Hidden)
*These commands are invisible to regular users and require authorization*
- `/debug2847` - View today's word for testing
- `/reset1947` - Reset daily completion for re-testing
- `/clearstats9182` - Nuclear stats reset (permanent)

## Setup

### 1. Prerequisites
- Python 3.8+
- Discord bot token from [Discord Developer Portal](https://discord.com/developers/applications)

### 2. Installation
```bash
# Clone the repository
git clone https://github.com/yourusername/discord-wordle-bot.git
cd discord-wordle-bot

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create environment file
cp .env.example .env
# Edit .env with your bot token and admin user ID
```

### 3. Environment Configuration
Create a `.env` file with:
```
DISCORD_BOT_TOKEN=your_bot_token_here
ADMIN_USER_ID=your_discord_user_id_here
```

### 4. Discord Bot Setup
1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application
3. Go to "Bot" section and create a bot
4. Copy the bot token to your `.env` file as `DISCORD_BOT_TOKEN`
5. Add your Discord user ID to `.env` as `ADMIN_USER_ID` (for debug commands)
6. Under "Privileged Gateway Intents", enable:
   - Message Content Intent (if needed)
6. Go to "OAuth2" > "URL Generator":
   - Scopes: `bot`, `applications.commands`
   - Bot Permissions: 
     - Send Messages
     - Use Slash Commands
     - Embed Links
     - Read Message History
7. Use the generated URL to add the bot to your server

### 5. Run the Bot
```bash
python app.py
```

## Usage

### Starting Games
- Use `/betterwordle` to start a new game
- New to the bot? Try `/help` for a complete guide!
- Click "Make Guess" button to enter your 5-letter word
- Get instant feedback with colored squares
- Try to guess the word in 6 attempts!

### Daily Summaries
- Use `/setchannel` to enable automatic daily summaries
- Every day at 12:01 AM, the bot posts yesterday's results
- Shows streak status and user rankings
- Tracks consecutive days with at least 1 completion

### Viewing Results
- `/results` - See today's completions
- `/streak` - Check current server streak
- Daily summaries show previous day's detailed results

## Features Explained

### Interactive UI
Instead of typing slash commands for each guess, players:
1. Start with `/wordlebot`
2. Click "Make Guess" button
3. Type in the modal popup
4. Get instant feedback
5. Continue until solved or failed

### Daily Streaks
- Tracks consecutive days where at least 1 person completes Wordle
- Automatic daily summaries show results like: "🔥 Your group is on a 20 day streak!"
- Results grouped by score: "👑 4/6: @User1 @User2"

### Word Validation
- Expanded dictionary with 1000+ valid 5-letter words
- Clear error messages for invalid words
- Prevents duplicate guesses

## File Structure
```
discord-wordle-bot/
├── app.py              # Main bot code
├── requirements.txt    # Python dependencies
├── .env.example       # Environment template
├── .gitignore         # Git ignore rules
└── README.md          # This file
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is open source. Feel free to use and modify!

## Support

If you encounter issues:
1. Check that your bot token is correct
2. Ensure the bot has proper permissions in your server
3. Verify Python version compatibility
4. Check the console for error messages

---

Made with ❤️ for Discord communities who love word games!
