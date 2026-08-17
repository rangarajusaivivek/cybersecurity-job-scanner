#!/usr/bin/env python3
"""
setup_telegram.py
==================
One-time Telegram bot setup helper.
Run: py setup_telegram.py
"""
import sys, io
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

print("""
=== TELEGRAM BOT SETUP (5 minutes) ===

STEP 1: Create your bot
  1. Open Telegram on your phone
  2. Search for: @BotFather
  3. Tap Start, then send: /newbot
  4. Name: Job Scanner
  5. Username: saivivek_jobscanner_bot (or any unique name ending in _bot)
  6. BotFather gives you a TOKEN -- copy it
     Looks like: 7612345678:AAF-xyz123abc...

STEP 2: Get your Chat ID
  1. Search for: @userinfobot on Telegram
  2. Tap Start
  3. It replies with your ID number
     Looks like: 123456789

STEP 3: Start your bot
  1. Search for your bot by username
  2. Tap Start (IMPORTANT -- bot cant message you until you do this)

STEP 4: Add to .env file
""")

token = input("Paste your Bot Token here (or press Enter to skip): ").strip()
chat_id = input("Paste your Chat ID here (or press Enter to skip): ").strip()

if token and chat_id:
    # Test the connection
    try:
        import httpx
        resp = httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": "Job Scanner connected! You will receive daily job alerts here."},
            timeout=10,
        )
        data = resp.json()
        if data.get("ok"):
            print("\n[OK] Test message sent! Check your Telegram.")
            print("\nAdd these to your .env file:")
            print(f"TELEGRAM_BOT_TOKEN={token}")
            print(f"TELEGRAM_CHAT_ID={chat_id}")
            print(f"DIGEST_EMAIL=rangarajusaivivek@gmail.com")

            # Offer to write to .env automatically
            write = input("\nWrite to .env file automatically? (y/n): ").strip().lower()
            if write == "y":
                import os
                env_path = ".env"
                if os.path.exists(env_path):
                    with open(env_path, "r") as f:
                        env_content = f.read()
                    # Update or add values
                    lines = env_content.split("\n")
                    new_lines = []
                    keys_written = set()
                    for line in lines:
                        if line.startswith("TELEGRAM_BOT_TOKEN="):
                            new_lines.append(f"TELEGRAM_BOT_TOKEN={token}")
                            keys_written.add("TELEGRAM_BOT_TOKEN")
                        elif line.startswith("TELEGRAM_CHAT_ID="):
                            new_lines.append(f"TELEGRAM_CHAT_ID={chat_id}")
                            keys_written.add("TELEGRAM_CHAT_ID")
                        elif line.startswith("DIGEST_EMAIL="):
                            new_lines.append(f"DIGEST_EMAIL=rangarajusaivivek@gmail.com")
                            keys_written.add("DIGEST_EMAIL")
                        else:
                            new_lines.append(line)
                    # Add any missing keys
                    if "TELEGRAM_BOT_TOKEN" not in keys_written:
                        new_lines.append(f"TELEGRAM_BOT_TOKEN={token}")
                    if "TELEGRAM_CHAT_ID" not in keys_written:
                        new_lines.append(f"TELEGRAM_CHAT_ID={chat_id}")
                    if "DIGEST_EMAIL" not in keys_written:
                        new_lines.append(f"DIGEST_EMAIL=rangarajusaivivek@gmail.com")
                    with open(env_path, "w", encoding="utf-8") as f:
                        f.write("\n".join(new_lines))
                    print("[OK] .env file updated!")
                    print("\nNow run: py main.py --schedule")
                    print("You will get job alerts on Telegram 3x daily + EOD report at 9pm")
        else:
            print(f"\n[ERROR] Could not send message: {data}")
            print("Make sure you started the bot on Telegram (tap Start on the bot)")
    except ImportError:
        print("[ERROR] httpx not installed. Run: py -m pip install httpx")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        print("Check your token and chat ID and try again")
else:
    print("\nSkipped. Add manually to .env:")
    print("TELEGRAM_BOT_TOKEN=your_token_here")
    print("TELEGRAM_CHAT_ID=your_chat_id_here")
    print("DIGEST_EMAIL=rangarajusaivivek@gmail.com")
