<h1 align="center"><b>Altruix | UserBot</b></h1>
<p align="center"><img src="https://telegra.ph/file/f51efe570b5f0a9165f8e.png"; width="1155px"><br></p>  

#### **Altruix** | A Modern yet simple UserBot which is based on Pyrogram. **Built By The Developers Of Friday Userbot.** 
<br>

# Deploying To Different Platforms

> **🚀 Multi-Platform Support:** Altruix now supports automatic platform detection!
> 
> Supported Platforms:
> - 🪟 **Windows** (Native, Git Bash, WSL)
> - 🐧 **Linux** (Desktop, Server, VPS)
> - 📱 **Termux** (Android)
> - 🍎 **macOS**
> - ☁️ **Cloud** (Heroku, Railway, Render, Sevalla)
>
> For detailed deployment instructions, see:
> - [Quick Start Guide](QUICK_START.md) - Fast setup for all platforms
> - [Deployment Guide](DEPLOYMENT_GUIDE.md) - Complete documentation
>
> Quick Deploy:
> - For [Local Deployment](#Deploy-Locally) (Windows/Linux/macOS/Termux)
> - For [Cloud Deployment](#Deploy-on-Cloud) (Heroku/Railway/Render)

<br>

# Official Support/Updates
> - Join the official **Updates** Channel  
>    <a href="https://t.me/AltruiXUB"><img src="https://img.shields.io/badge/Join-Altruix%20Channel-red.svg?logo=Telegram"></a>  
> - Join the official **Support** Chat  
>    <a href="https://t.me/AltruixChat"><img src="https://img.shields.io/badge/Join-Altruix%20Group-blue.svg?logo=telegram"></a>

<br>

## Deploy Locally

Altruix supports automatic platform detection and will create the appropriate virtual environment for your system.

### Universal Command (All Platforms):

```bash
bash start.sh
```

### Platform-Specific Instructions:

#### 🪟 Windows

**Option 1: Git Bash / MSYS / Cygwin**
```bash
git clone https://github.com/Altruix/Altruix
cd Altruix
cp .env.sample .env
nano .env  # Edit configuration
bash start.sh
```

**Option 2: CMD / PowerShell (Native)**
```cmd
git clone https://github.com/Altruix/Altruix
cd Altruix
copy .env.sample .env
notepad .env  # Edit configuration
start.bat
```

#### 🐧 Linux / 🖥️ VPS

```bash
git clone https://github.com/Altruix/Altruix
cd Altruix
cp .env.sample .env
nano .env  # Edit configuration
bash start.sh
```

#### 🪟 WSL (Windows Subsystem for Linux)

```bash
git clone https://github.com/Altruix/Altruix
cd Altruix
cp .env.sample .env
nano .env  # Edit configuration
bash start.sh
```

#### 📱 Termux (Android)

```bash
pkg update && pkg upgrade -y
pkg install python git -y
git clone https://github.com/Altruix/Altruix
cd Altruix
cp .env.sample .env
nano .env  # Edit configuration
bash start.sh
```

#### 🍎 macOS

```bash
brew install python@3.11  # If not installed
git clone https://github.com/Altruix/Altruix
cd Altruix
cp .env.sample .env
nano .env  # Edit configuration
bash start.sh
```

### What the script does:
- ✅ Automatically detects your platform (Windows/Linux/WSL/VPS/Termux/macOS)
- ✅ Creates platform-specific virtual environment
- ✅ Installs all dependencies
- ✅ Loads environment variables from `.env`
- ✅ Cleans up existing processes
- ✅ Launches the bot

Example of [`.env`](#env)

<br>

## Deploy on Cloud

### ☁️ Heroku

```bash
# Install Heroku CLI first
heroku login
heroku create your-app-name
heroku buildpacks:set heroku/python

# Set environment variables
heroku config:set API_ID=your_api_id
heroku config:set API_HASH=your_api_hash
heroku config:set BOT_TOKEN=your_bot_token
# ... set all required env vars

# Deploy
git push heroku main
heroku ps:scale worker=1

# View logs
heroku logs --tail
```

### ☁️ Railway / Render / Sevalla

1. Connect your GitHub repository to the platform
2. Set environment variables in platform settings
3. Platform will auto-deploy using `Procfile`
4. Bot will start automatically

For detailed cloud deployment instructions, see [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)

<br>

## String Session

It's not necessary until you host the bot. You can get the String Session after you are done with hosting. Just run the Altruix Assistant bot and walk through the steps. 

## Required Variables

> Following are the required variables for the proper working of userbot, note down these somewhere for easier access so that you may use them in future:

<details close>

  > These are used to communicate with the telegram servers. You can get you your `API_HASH` and `API_ID` from [Telegram](my.telegram.com) by following the given steps:
  > - Go to [my.telegram.com](my.telegram.com).
  > - Login via adding your mobile number in the international format i.e `+00 9876543210`.
  > - You will receive an `11` character alphanumeric code via the Telegram App. Input this code into the input field and proceed.
  > - Now click on [API development tools](https://my.telegram.org/apps).
  > - Here you may add an `App title` and a `Short name` for it (they can be anything). Note down the `APP api_id` and `APP api_hash` for future use. Scroll down to the end of the page and click on `Save changes` button.

<summary> API_ID </summary>
</details>

<details close>

  > These are used to communicate with the telegram servers. You can get you your `API_HASH` and `API_ID` from [Telegram](my.telegram.com) by following the given steps:
  > - Go to [my.telegram.com](my.telegram.com).
  > - Login via adding your mobile number in the international format i.e `+00 9876543210`.
  > - You will receive an `11` character alphanumeric code via the Telegram App. Input this code into the input field and proceed.
  > - Now click on [API development tools](https://my.telegram.org/apps).
  > - Here you may add an `App title` and a `Short name` for it (they can be anything). Note down the `APP api_id` and `APP api_hash` for future use. Scroll down to the end of the page and click on `Save changes` button.

<summary> API_HASH </summary>
</details>

<details close>

  > It's used to control your bot's actions etc. You can get your `BOT_TOKEN` for your bot by following the given steps:
  > - Go to [@BotFather](t.me/BotFather).
  > - Do `/start` -> `/newbot`
  > - You'll be prompted to choose a name for your bot (it can be anything).
  > - You'll be prompted to choose a username name for your bot (it can be anything but should end with suffix `bot`).
  > - Your bot with the above details will be made! And a message containg your bots api token will also be sent.

<summary> BOT_TOKEN </summary>
</details>

<details close>

  > TO BE DONE

<summary> DB_URI </summary>
</details>

<details close>

  > It's used to tell your bot who is the owner of this bot and whom commands it should fulfil. Only the person with this ID can give the bot command to add more sessions to the database via `/add`.
  > - Go to [@MissRose_Bot](t.me/MissRose_Bot).
  > - Do `/start` -> `/info`
  > - You'll receive a message containing your ID.

<summary> OWNER_ID </summary>
</details>

<br>

## .env

<details close>
<p align="center"><img src="Main/assets/images/dot_env_template.png"; width="1155px"><br></p>
<summary> An example of how your `.env` file should look like: </summary>
</details>

<br>

## About the Repo

> Currently Running Stable version of Altruix.  
> [![](https://img.shields.io/badge/Altruix-v0.0.1-color=red)](#)  
> Is our project under active maintenance?  
> [![Maintenance](https://img.shields.io/badge/Maintained%3F-Yes-color=green)](https://github.com/Altruix/Altruix/graphs/commit-activity)   
> Developers aka Contributors for the Project.  
> [![Contributors](https://img.shields.io/github/contributors/Altruix/Altruix?style=flat-square&color=orange)](https://github.com/Altruix/Altruix/graphs/contributors)

## Credits


<details>
<summary><b>Developers &Maintainers</b></summary>

> - <a href="https://www.github.com/sukri369">Sukri369</a>
> - <a href="https://t.me/FakboiPensiun">Fakboi Pensiun</a>
> - <a href="https://t.me/MinigramDev">Sugar Milk</a>
> - <a href="https://t.me/coolkid369xr">CoolKid 369</a>

</details>

<details>
<summary><b>Core Contributors</b></summary>

> - <a href="https://www.github.com/sukri369">Sukri369</a>
> - <a href="https://t.me/FakboiPensiun">Fakboi Pensiun</a>
> - <a href="https://t.me/MinigramDev">Sugar Milk</a>
> - <a href="https://t.me/coolkid369xr">CoolKid 369</a>
> - <a href="https://www.github.com/EverythingSuckz">EverythingSuckz</a>
> - <a href="https://www.github.com/StarkGang">StarkGang</a>
> - <a href="https://www.github.com/BilakshanP">BilakshanP</a>
> - <a href="https://www.github.com/Reeshuxd">Reeshuxd</a>
> - <a href="https://www.github.com/Rohith-Sreedharan">Rohithaditya</a>
> - <a href="https://www.github.com/StarkBotIndustries">StarkBotIndustries</a>

</details>

<details>
<summary><b>Additional Contributors</b></summary>

> - <a href="https://www.github.com/sohag02">sohag02</a>
> - <a href="https://www.github.com/SHRE-YANSH">SHRE-YANSH</a>
> - <a href="https://www.github.com/lostb053">lostb053</a>
> - <a href="https://www.github.com/Nksama">Nksama</a>
> - <a href="https://www.github.com/Crackexy">Crackexy</a>
> - <a href="https://www.github.com/anonyindian">anonyindian</a>
> - <a href="https://www.github.com/N0BLEWOLF">N0BLEWOLF</a>
> - <a href="https://www.github.com/ramanveerji">ramanveerji</a>
> - <a href="https://www.github.com/swatv3nub">swatv3nub</a>

</details>

<details>
<summary><b>Libraries & Frameworks</b></summary>

> - <a href="https://www.github.com/pyrogram">Pyrogram</a>
> - <a href="https://www.github.com/KurimuzonAkuma/kurigram">Kurigram</a>
> - <a href="https://www.github.com/LonamiWebs/Telethon">Telethon</a>

</details>

<details>
<summary><b>Inspired By</b></summary>

> - <a href="https://www.github.com/TeamUltroid/Ultroid">Ultroid Team</a>
> - <a href="https://www.github.com/Altruix/Altruix">Altruix Dev</a>
> - <a href="https://www.github.com/hikariatama/hikka">Hikka Ubot</a>
> - <a href="https://www.github.com/UsergeTeam/Userge">Userge Team</a>
> - <a href="https://www.github.com/FridayDevs/Friday">Friday Dev</a>
> - <a href="https://www.github.com/TgCatUB/catuserbot">Cat Ubot</a>
> - <a href="https://www.github.com/Quiec/AsenaUserBot">Asena Ubot</a>
> - <a href="https://www.github.com/friendly-telegram/friendly-telegram">Friendly Ubot</a>
> - <a href="https://t.me/ShiiinaGroup">Shiiina Bot</a>
> - <a href="https://www.github.com/vckyou/GeezProjects">Geez Project</a>
> - <a href="https://www.github.com/">Veez Project</a>
> - <a href="https://www.github.com/mrismanaziz/PyroMan-Userbot">PyroMan Ubot</a>
> - <a href="https://t.me/AlphaXProject">Alpha-Xproject</a>


</details>

<p align="center">
  <img width="500" src="https://telegra.ph/file/5ee1e2ff5437b97aabf2e.png">
</p>
