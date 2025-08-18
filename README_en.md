# Discord Bot
## 🌐 Select Language

[<img src="https://upload.wikimedia.org/wikipedia/commons/2/21/Flag_of_Vietnam.svg" alt="Tiếng Việt" width="40"/>](README_vi.md)
[<img src="https://upload.wikimedia.org/wikipedia/en/a/a4/Flag_of_the_United_States.svg" alt="English" width="40"/>](README.md)

EN
A feature-rich Discord bot built with Python and `discord.py`, offering over 100 commands for information, entertainment, music, moderation, economy, and advanced utilities. This bot is designed to enhance server interaction with features like GIF search, URL shortening, translation, podcast search, and more.

## Features
- **Information & Utilities**: Commands like `!ping`, `!translate`, `!shorten`, `!qr`, etc.
- **Entertainment & Games**: Includes `!gif`, `!joke`, `!trivia`, `!hangman`, etc.
- **Music & Media**: Supports `!podcast` with Vietnamese text-to-speech descriptions.
- **Moderation**: Commands like `!ban`, `!kick`, `!mute`, etc. (requires admin permissions).
- **Economy & Leveling**: Features `!daily`, `!balance`, `!leaderboard`, etc.
- **Advanced Utilities**: Includes `!remind`, `!timer`, `!news` (pending API integration), etc.
- **Dynamic Status**: Bot cycles through statuses like "Playing a fun game", "Watching a movie", etc.

## Prerequisites
- Python 3.12 or higher
- A Discord bot token (from [Discord Developer Portal](https://discord.com/developers/applications))
- Optional API keys for enhanced features:
  - [Bitly API](https://dev.bitly.com/) for URL shortening (`!shorten`)
  - [Listen Notes API](https://www.listennotes.com/api/) for podcast search (`!podcast`)
  - [Tenor API](https://tenor.com/developer/keyregistration) for GIF search (`!gif`)

## Installation
1. **Clone the Repository**:
   ```bash
   git clone https://github.com/your-username/your-repo.git
   cd your-repo
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Install FFmpeg**:

Windows
```bash
   choco install ffmpeg
   ```
Linux
```bash
   sudo apt-get install ffmpeg
   ```
Mac os
```bash
   brew install ffmpeg
   ```      

4. **Set Up Environment Variables**:
   - Create a `.env` file in the project root.
   - Add the following:
     ```plaintext
     DISCORD_BOT_TOKEN=your_discord_bot_token
     BITLY_API_KEY=your_bitly_api_key
     LISTENNOTES_API_KEY=your_listennotes_api_key
     TENOR_API_KEY=your_tenor_api_key
     ```
   - Replace `your_discord_bot_token`, etc., with actual keys. For instructions on obtaining keys, see the [Prerequisites](#prerequisites).

5. **Run the Bot**:
   ```bash
   python main.py
   ```

## Configuration
- **Discord Bot Permissions**:
  - Enable **Presence Intent**, **Server Members Intent**, and **Message Content Intent** in the Discord Developer Portal.
  - Ensure the bot has permissions: `send_messages`, `embed_links`, `attach_files` (for `!podcast`), and moderation permissions for commands like `!ban`.

- **Database**: The bot uses SQLite (`bot_data.db`) for user data, reminders, and notes. No additional setup is needed; the database is created automatically.

## Usage
1. **Invite the Bot**:
   - Use the bot's invite link from the Discord Developer Portal to add it to your server.
2. **Commands**:
   - Prefix: `!`
   - View all commands: `!help_all`
   - Examples:
     - `!gif funny cat`: Search for a funny cat GIF.
     - `!translate vi Hello`: Translate "Hello" to Vietnamese.
     - `!shorten https://example.com`: Shorten a URL.
     - `!podcast tech`: Search for tech podcasts with Vietnamese TTS description.
3. **Dynamic Status**: The bot cycles through statuses every 30 seconds (e.g., "Watching a movie", "Listening to music").

## Contributing
- Fork the repository.
- Create a new branch (`git checkout -b feature/your-feature`).
- Commit changes (`git commit -m "Add your feature"`).
- Push to the branch (`git push origin feature/your-feature`).
- Open a Pull Request.

## License
Copyright (c) 2025 Nguyen Hoang

This software is free to use, modify and share
for personal or non-commercial purposes.
Any form of commercial use (sale, rental, paid services)
is strictly prohibited without the written consent of the author.

## Contact

<img src="qr.png">