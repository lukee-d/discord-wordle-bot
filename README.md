# Discord Wordle Bot

A Discord bot that brings Wordle to your server with interactive gameplay, daily streaks, and automatic summaries!

## Features

### 🎯 Interactive Gameplay
- **Click-to-play interface** with buttons and modals
- **Daily words** - everyone gets the same word each day
- **5-letter word validation** with expanded dictionary (1000+ words)
- **Visual feedback** with emoji squares (🟩🟨⬜)
- **One game per day** per user

### 🔥 Streak Tracking
- **Daily streaks** - counts consecutive days with at least 1 completion
- **Automatic daily summaries** posted at 12:01 AM
- **Yesterday's results** with user scores and rankings
- **Server statistics** with success rates

### 📊 Statistics & Results
- **Live results** - see today's completions with `/results`
- **Streak status** - check current streak with `/streak`
- **Daily summaries** - automatic posts showing yesterday's results

## Commands

| Command | Description |
|---------|-------------|
| `/wordlebot` | Start a new Wordle game with interactive buttons |
| `/results` | View today's server results |
| `/streak` | Check current server streak |
| `/setchannel` | Set channel for daily summaries (requires Manage Channels permission) |
| `/stats` | Personal stats (coming soon) |
| `/launch` | Handle Entry Point requests gracefully |

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
# Edit .env with your bot token
```

### 3. Discord Bot Setup
1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application
3. Go to "Bot" section and create a bot
4. Copy the bot token to your `.env` file
5. Under "Privileged Gateway Intents", enable:
   - Message Content Intent (if needed)
6. Go to "OAuth2" > "URL Generator":
   - Scopes: `bot`, `applications.commands`
   - Bot Permissions: 
     - Send Messages
     - Use Slash Commands
     - Embed Links
     - Read Message History
7. Use the generated URL to add the bot to your server

### 4. Run the Bot
```bash
python app.py
```

## Usage

### Starting Games
- Use `/wordlebot` to start a new game
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
