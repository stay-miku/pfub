import logging

import pbrm
from telegram import __version__ as TG_VER
import os
from pbrm import spider
from pbrm import save_illust
from .user_config import Config
from .utils import get_tags, delete_files_in_folder, compress_image_if_needed
import time

try:
    from telegram import __version_info__
except ImportError:
    __version_info__ = (0, 0, 0, 0, 0)  # type: ignore[assignment]

if __version_info__ < (20, 0, 0, "alpha", 1):
    raise RuntimeError(
        f"This example is not compatible with your current PTB version {TG_VER}. To view the "
        f"{TG_VER} version of this example, "
        f"visit https://docs.python-telegram-bot.org/en/v{TG_VER}/examples.html"
    )
from telegram import Update, InputMediaPhoto
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)

tmp_path: str
user_config_path: str


def get_user_config_path(update: Update):
    global user_config_path
    return os.path.join(user_config_path, str(update.message.from_user.id) + ".json")


def get_tmp_path():
    global tmp_path
    return tmp_path


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.get_bot().send_message(chat_id=update.message.chat_id, text="""
一个自动推送p站关注画师更新作品到频道的bot
使用方法
/set <PARAMETER> <VALUE> 设置cookie,最新作品的id,查询间隔
/add_channel 添加推送频道(频道操作需要频道id,需要将bot设为管理员并给予发送信息权限)
/del_channel 删除推送频道
/del_all_channel 删除所有推送频道
/run 开始推送任务
/stop 停止推送任务
/get <PARAMETER> 获取配置信息
/cookie_verify 验证cookie可用性
/status 查看任务状态
在频道中发送/id可以获取对应的频道id(需要将bot设置管理员并给予发送信息权限)
注意: 设置last_page时不要让bot一次性发送过多消息(大概25张图片的量),否则大概率会被tg掐断
    """)


async def check_task(context: ContextTypes.DEFAULT_TYPE) -> None:
    tmp_dir = get_tmp_path()
    config = Config.get(context.job.data)
    user = config.cookie_verify()
    if user["userId"] is None:
        logging.error(context.job.data + " cookie无效")
        for channel in config.channel:
            await context.bot.send_message(chat_id=channel, text="cookie无效,请重新配置cookie")

    logging.info(
        "Start update: {}, userId: {}, userName: {}".format(context.job.data, user["userId"], user["userName"]))

    new_illusts = config.get_update()

    if not os.path.exists(tmp_dir):
        os.makedirs(tmp_dir)
    cookie = config.cookie

    for illust in new_illusts:
        try:
            meta = spider.get_illust_meta(illust, cookie)
            save_illust.save_illust(illust, tmp_dir, cookie, True, False, True, False)
        except pbrm.UnSupportIllustType:
            for channel in config.channel:
                await context.bot.send_message(chat_id=channel, text="暂不支持插画 漫画 动图以外的作品推送, 不支持的作品id为: {}"
                                               .format(illust))
            config.last_page = illust
            continue
        except Exception as e:
            logging.error(context.job.data + " " + str(e))
            for channel in config.channel:
                await context.bot.send_message(chat_id=channel, text="下载文件时发生错误: {}, 发生错误的作品id为: {}"
                                               .format(str(e), illust))
            config.last_page = illust
            continue
        origin_url = "https://www.pixiv.net/artworks/{}".format(illust)
        title = meta["illustTitle"]
        user_url = "https://www.pixiv.net/users/{}".format(meta["userId"])
        user_name = meta["userName"]
        tags = get_tags(meta)
        has_spoiler = "#R-18" in tags  # 对r18自动遮罩
        caption = "Tags: {}\nauthor: <a href=\"{}\">{}</a> \norigin: <a href=\"{}\">{}</a>".format(
            " ".join(tags), user_url, user_name, origin_url, title
        )
        # 区分动图和图片
        if meta["illustType"] == 0 or meta["illustType"] == 1:
            files = [open(os.path.join(tmp_dir, i), "rb") for i in sorted(os.listdir(tmp_dir)) if
                     not os.path.isdir(os.path.join(tmp_dir, i))]
            bytes_files = [compress_image_if_needed(f.read()) for f in files][
                          0:10]  # 对超过9.5MB的图片压缩(其实上限是10MB),最多只发送10张图(上限)
            for channel in config.channel:
                await context.bot.send_media_group(chat_id=channel,
                                                   media=[InputMediaPhoto(media=m, has_spoiler=has_spoiler) for m in
                                                          bytes_files]
                                                   , caption=caption, parse_mode="HTML")
            for i in files:
                i.close()
            delete_files_in_folder(tmp_dir)
        elif meta["illustType"] == 2:
            file = open(os.path.join(tmp_dir, [f for f in os.listdir(tmp_dir) if f.endswith(".gif")][0]), "rb")
            for channel in config.channel:
                await context.bot.send_animation(chat_id=channel, animation=file, caption=caption, parse_mode="HTML",
                                                 has_spoiler=has_spoiler)
            file.close()
            delete_files_in_folder(tmp_dir)
        config.last_page = illust
        time.sleep(1)


async def get_value(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        if context.args[0] == "cookie":
            await context.bot.send_message(chat_id=update.message.chat_id, text="cookie: {}"
                                           .format(Config.get(get_user_config_path(update)).cookie))
        elif context.args[0] == "last_page":
            await context.bot.send_message(chat_id=update.message.chat_id, text="last_page: {}"
                                           .format(Config.get(get_user_config_path(update)).last_page))
        elif context.args[0] == "check_interval":
            await context.bot.send_message(chat_id=update.message.chat_id, text="check_interval: {}"
                                           .format(Config.get(get_user_config_path(update)).check_interval))
        elif context.args[0] == "channel":
            channel = Config.get(get_user_config_path(update)).channel
            c = [str(i) for i in channel]
            await context.bot.send_message(chat_id=update.message.chat_id, text="channels: {}"
                                           .format("\n".join(c)))
        else:
            raise KeyError
    except (IndexError, KeyError):
        await context.bot.send_message(chat_id=update.message.chat_id, text="""
用法:
/get <PARAMETER>
<PARAMETER>可为: cookie, last_page, check_interval, channel
分别为获取配置的cookie, 关注列表的最新作品, 检查更新的间隔, 推送的频道id
        """)


async def add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        channel_id = int(context.args[0])
        config = Config.get(get_user_config_path(update))
        if config.channel_append(channel_id):
            await context.bot.send_message(chat_id=update.message.chat_id, text="添加成功")
        else:
            await context.bot.send_message(chat_id=update.message.chat_id, text="频道已存在")
    except (IndexError, KeyError, ValueError):
        await context.bot.send_message(chat_id=update.message.chat_id, text="""
用法:
/add_channel <CHANNEL_ID>
<CHANNEL_ID>需为负数整形数字
添加后bot将会把更新消息推送到对应的频道
        """)


async def del_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        channel_id = int(context.args[0])
        config = Config.get(get_user_config_path(update))
        if config.channel_remove(channel_id):
            await context.bot.send_message(chat_id=update.message.chat_id, text="删除成功")
        else:
            await context.bot.send_message(chat_id=update.message.chat_id, text="频道不存在")
    except (IndexError, KeyError, ValueError):
        await context.bot.send_message(chat_id=update.message.chat_id, text="""
用法:
/del_channel <CHANNEL_ID>
<CHANNEL_ID>需为整形数字
删除后bot会停止向对应的频道推送消息
        """)


async def del_all_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        config = Config.get(get_user_config_path(update))
        config.channel = []
        await context.bot.send_message(chat_id=update.message.chat_id, text="清除成功")
    except (IndexError, KeyError, ValueError):
        await context.bot.send_message(chat_id=update.message.chat_id, text="""
用法:
/del_all_channel
删除所有的推送频道
        """)


async def set_value(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        if context.args[0] == "cookie":
            cookie = " ".join(context.args[1:])
            config = Config.get(get_user_config_path(update))
            config.cookie = cookie
            await context.bot.send_message(chat_id=update.message.chat_id, text="设置成功")
        elif context.args[0] == "last_page":
            last_page = context.args[1]
            config = Config.get(get_user_config_path(update))
            config.last_page = last_page
            await context.bot.send_message(chat_id=update.message.chat_id, text="设置成功")
        elif context.args[0] == "check_interval":
            check_interval = int(context.args[1])
            config = Config.get(get_user_config_path(update))
            config.check_interval = check_interval
            await context.bot.send_message(chat_id=update.message.chat_id, text="设置成功")
        else:
            raise KeyError
    except (IndexError, KeyError, ValueError):
        await context.bot.send_message(chat_id=update.message.chat_id, text="""
用法:
/set <PARAMETER> <VALUE>
<PARAMETER>可以为: cookie, last_page, check_interval(VALUE需要为整数)
        """)


async def run_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.job_queue.get_jobs_by_name(str(update.message.from_user.id)):
        await context.bot.send_message(chat_id=update.message.chat_id, text="任务已启动，无需再次启动")
        return
    config = Config.get(get_user_config_path(update))
    if config.cookie_verify()["userId"] is None:
        await context.bot.send_message(chat_id=update.message.chat_id, text="cookie无效,请先设置cookie")
        return
    context.job_queue.run_repeating(check_task, first=1, interval=config.check_interval,
                                    name=str(update.message.from_user.id)
                                    , data=get_user_config_path(update))
    await context.bot.send_message(chat_id=update.message.chat_id, text="运行成功")


async def stop_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    all_jobs = context.job_queue.get_jobs_by_name(str(update.message.from_user.id))
    if not all_jobs:
        await context.bot.send_message(chat_id=update.message.chat_id, text="任务未运行，无需再停止")
        return
    for job in all_jobs:
        job.schedule_removal()
    await context.bot.send_message(chat_id=update.message.chat_id, text="停止成功")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.job_queue.get_jobs_by_name(str(update.message.from_user.id)):
        await context.bot.send_message(chat_id=update.message.chat_id, text="当前任务正在运行")
    else:
        await context.bot.send_message(chat_id=update.message.chat_id, text="当前任务已经停止")


async def cookie_verify(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config = Config.get(get_user_config_path(update))
    user = config.cookie_verify()
    if user["userId"] is None:
        await context.bot.send_message(chat_id=update.message.chat_id, text="cookie无效")
    else:
        await context.bot.send_message(chat_id=update.message.chat_id, text="cookie有效, userId: {}, userName: {}"
                                       .format(user["userId"], user["userName"]))


async def get_channel_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.channel_post.text == "/id":
        await update.channel_post.reply_text("当前频道id为: `{}`"
                                             .format(update.channel_post.chat_id, update.channel_post.chat_id)
                                             , parse_mode="MarkdownV2")


def run(bot_key, tmp, config_path):
    global tmp_path, user_config_path
    tmp_path = tmp
    delete_files_in_folder(tmp)
    user_config_path = config_path
    application = Application.builder().token(bot_key).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("set", set_value))
    application.add_handler(CommandHandler("get", get_value))
    application.add_handler(CommandHandler("run", run_task))
    application.add_handler(CommandHandler("stop", stop_task))
    application.add_handler(CommandHandler("cookie_verify", cookie_verify))
    application.add_handler(CommandHandler("add_channel", add_channel))
    application.add_handler(CommandHandler("del_channel", del_channel))
    application.add_handler(CommandHandler("del_all_channel", del_all_channel))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(MessageHandler(filters.ChatType.CHANNEL, get_channel_id))

    application.run_polling(allowed_updates=Update.ALL_TYPES, read_timeout=600, write_timeout=600, pool_timeout=600, connect_timeout=600, timeout=600)
