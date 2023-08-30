from . import bot
import os


bot_key = ""
user_config_path = "./user"
tmp_path = "./tmp"

if __name__ == "__main__":
    if not os.path.exists(user_config_path):
        os.makedirs(user_config_path)
    if not os.path.exists(tmp_path):
        os.makedirs(tmp_path)
    await bot.run(bot_key, tmp_path, user_config_path)
