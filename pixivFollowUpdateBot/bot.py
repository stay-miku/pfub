import asyncio
import logging

import pbrm
from telegram import __version__ as TG_VER
import os
from pbrm import spider
from pbrm import save_illust
from .user_config import Config
from .utils import get_tags, delete_files_in_folder, compress_image_if_needed
import time
from .system_config import SConfig

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
from telegram import Update, InputMediaPhoto, BotCommand
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)

tmp_path: str
user_config_path: str
do_stop_bot = False


def get_user_config_path(update: Update):
    global user_config_path
    return os.path.join(user_config_path, str(update.effective_message.from_user.id) + ".json")


def get_tmp_path():
    global tmp_path
    return tmp_path


async def check_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if SConfig.admin_verify(update.effective_message.from_user.id):
        SConfig.add_user(update.effective_message.from_user.id)
        return True
    else:
        await context.bot.send_message(chat_id=update.effective_message.chat_id, text="权限不足")
        return False


async def check_available(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if SConfig.available_verify(update.effective_message.from_user.id):
        SConfig.add_user(update.effective_message.from_user.id)
        return True
    else:
        await context.bot.send_message(chat_id=update.effective_message.chat_id, text="你不在白名单内")
        return False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await check_available(update, context):
        return
    logging.info("start by {}".format(update.effective_message.from_user.id))
    await update.get_bot().send_message(chat_id=update.message.chat_id, text="""
一个自动推送p站关注画师更新作品到频道的bot
使用方法
/set <PARAMETER> <VALUE> 设置cookie,最新作品的id,查询间隔
/add_channel <CHANNEL> 添加推送频道(频道操作需要频道id,需要将bot设为管理员并给予发送信息权限)
/del_channel <CHANNEL> 删除推送频道
/del_all_channel 删除所有推送频道
/run 开始推送任务
/stop 停止推送任务
/get <PARAMETER> 获取配置信息
/cookie_verify 验证cookie可用性
/status 查看任务状态
/post <PID/URL> [<CHANNEL>] 手动推送作品
对于有参数命令,直接使用命令本身可以查看对应命令帮助
在频道中发送/id可以获取对应的频道id(需要将bot设置管理员并给予发送信息权限)
注意: 设置last_page时不要让bot一次性发送过多消息(大概25张图片的量),否则大概率会被tg掐断,当报错Flood control exceeded时就说明被掐断了,等待下一轮的推送即可

使用步骤:
先使用/set设置cookie(必须),last_page(必须),check_interval(可选,默认为10分钟)
使用/add_channel添加要发送的频道(必须,需要将bot设为管理员并给予发送信息权限,之后在频道内发送/id可以获取到当前频道id)
使用/cookie_verify验证cookie可用性(可选)
使用/run开始推送
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
    delete_files_in_folder(tmp_dir)
    cookie = config.cookie
    try:
        for illust in new_illusts:
            logging.info("try to post illust {} by {}".format(illust, context.job.chat_id))
            try:
                meta = spider.get_illust_meta(illust, cookie)
                save_illust.save_illust(illust, tmp_dir, cookie, True, False, True, False)
            except pbrm.UnSupportIllustType:
                logging.warning("unsupported illust type by {}, illust: {}".format(context.job.chat_id, illust))
                await context.bot.send_message(chat_id=context.job.chat_id, text="暂不支持插画 漫画 动图以外的作品推送, 不支持的作品id为: {}"
                                               .format(illust))
                config.last_page = illust
                continue
            except Exception as e:
                logging.error(context.job.data + " " + str(e))
                await context.bot.send_message(chat_id=context.job.chat_id, text="下载文件时发生错误: {}, 发生错误的作品id为: {}"
                                               .format(str(e), illust))
                config.last_page = illust
                continue
            origin_url = "https://www.pixiv.net/artworks/{}".format(illust)
            title = meta["illustTitle"]
            user_url = "https://www.pixiv.net/users/{}".format(meta["userId"])
            user_name = meta["userName"]
            tags = get_tags(meta)
            has_spoiler = "#R18" in tags  # 对r18自动遮罩
            caption = "Tags: {}\nauthor: <a href=\"{}\">{}</a> \norigin: <a href=\"{}\">{}</a>".format(
                " ".join(tags), user_url, user_name, origin_url, title
            )
            # 区分动图和图片
            if meta["illustType"] == 0 or meta["illustType"] == 1:
                files = [open(os.path.join(tmp_dir, i), "rb") for i in sorted(os.listdir(tmp_dir)) if
                         not os.path.isdir(os.path.join(tmp_dir, i))]
                if len(files) > 10:
                    caption += "\n<i>作品图片共{}张,未显示完全</i>".format(len(files))
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
                    await context.bot.send_animation(chat_id=channel, animation=file, caption=caption,
                                                     parse_mode="HTML",
                                                     has_spoiler=has_spoiler)
                file.close()
                delete_files_in_folder(tmp_dir)
            config.last_page = illust
            time.sleep(1)
    except Exception as e:
        await context.bot.send_message(chat_id=context.job.chat_id
                                       , text="发生错误: {}, 当前last_page: {}".format(str(e), config.last_page))
        logging.error("发生错误: {}, 当前last_page: {}".format(str(e), config.last_page))


async def get_value(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await check_available(update, context):
        return
    logging.info("get by {}".format(update.effective_message.from_user.id))
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
    if not await check_available(update, context):
        return
    logging.info("add_channel by {}".format(update.effective_message.from_user.id))
    try:
        global user_config_path
        channel_id = int(context.args[0])
        config = Config.get(get_user_config_path(update))
        if channel_id in Config.get_managed_channel_without_someone(user_config_path, get_user_config_path(update)):
            await context.bot.send_message(chat_id=update.message.chat_id, text="该频道已由其他人管理,不可添加")
            return
        if config.channel_append(channel_id):
            config.my_channel_append(channel_id)
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
    if not await check_available(update, context):
        return
    logging.info("del_channel by {}".format(update.effective_message.from_user.id))
    try:
        channel_id = int(context.args[0])
        config = Config.get(get_user_config_path(update))
        if config.channel_remove(channel_id):
            config.my_channel_remove(channel_id)
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
    if not await check_available(update, context):
        return
    logging.info("del_all_channel by {}".format(update.effective_message.from_user.id))
    try:
        config = Config.get(get_user_config_path(update))
        config.channel = []
        config.my_channel = []
        await context.bot.send_message(chat_id=update.message.chat_id, text="清除成功")
    except (IndexError, KeyError, ValueError):
        await context.bot.send_message(chat_id=update.message.chat_id, text="""
用法:
/del_all_channel
删除所有的推送频道
        """)


async def set_value(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await check_available(update, context):
        return
    logging.info("set by {}".format(update.effective_message.from_user.id))
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
cookie: 账号cookie
last_page: 关注的列表最新作品(不要乱设置,否则会导致将所有(34页)关注的画师最近更新全部发出来,然后被掐断推送),该参数用于让bot知道关注列表中最新的作品是哪一个,之后会将这个作品之后的所有作品推送出来
check_interval: 更新间隔,单位为秒,默认600(10分钟),不要设置太低,有可能导致被p站ban掉
        """)


async def run_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await check_available(update, context):
        return
    logging.info("run by {}".format(update.effective_message.from_user.id))
    if context.job_queue.get_jobs_by_name(str(update.message.from_user.id)):
        await context.bot.send_message(chat_id=update.message.chat_id, text="任务已启动，无需再次启动")
        return
    config = Config.get(get_user_config_path(update))
    if config.cookie_verify()["userId"] is None:
        await context.bot.send_message(chat_id=update.message.chat_id, text="cookie无效,请先设置cookie")
        return
    try:
        pid = int(config.last_page)
    except ValueError:
        logging.warning("error last_page: {} by {}".format(config.last_page, update.effective_message.from_user.id))
        await context.bot.send_message(chat_id=update.effective_message.chat_id, text="无效的last_page： {}"
                                       .format(config.last_page))
        return
    SConfig.add_job_user(update.effective_message.from_user.id)
    context.job_queue.run_repeating(check_task, first=1, interval=config.check_interval,
                                    name=str(update.message.from_user.id)
                                    , data=get_user_config_path(update), chat_id=update.effective_message.chat_id)
    await context.bot.send_message(chat_id=update.message.chat_id, text="运行成功")


async def stop_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await check_available(update, context):
        return
    logging.info("stop by {}".format(update.effective_message.from_user.id))
    all_jobs = context.job_queue.get_jobs_by_name(str(update.message.from_user.id))
    if not all_jobs:
        await context.bot.send_message(chat_id=update.message.chat_id, text="任务未运行，无需再停止")
        return
    for job in all_jobs:
        job.schedule_removal()
    SConfig.remove_job_user(update.effective_message.from_user.id)
    await context.bot.send_message(chat_id=update.message.chat_id, text="停止成功")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await check_available(update, context):
        return
    logging.info("status by {}".format(update.effective_message.from_user.id))
    if context.job_queue.get_jobs_by_name(str(update.message.from_user.id)):
        await context.bot.send_message(chat_id=update.message.chat_id, text="当前任务正在运行")
    else:
        await context.bot.send_message(chat_id=update.message.chat_id, text="当前任务已经停止")


async def cookie_verify(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await check_available(update, context):
        return
    logging.info("cookie_verify by {}".format(update.effective_message.from_user.id))
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


async def set_des(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await check_admin(update, context):
        return
    logging.info("set_des by {}".format(update.effective_message.from_user.id))
    command_list = [BotCommand("start", "开始和基础的帮助"),
                    BotCommand("set", "设置相关参数"),
                    BotCommand("get", "获取相关参数"),
                    BotCommand("run", "运行定时推送任务"),
                    BotCommand("stop", "停止定时推送任务"),
                    BotCommand("cookie_verify", "查询当前cookie可用性"),
                    BotCommand("add_channel", "添加频道到推送列表"),
                    BotCommand("del_channel", "从推送列表中删除特定频道"),
                    BotCommand("del_all_channel", "清空推送列表"),
                    BotCommand("status", "查看当然任务状态"),
                    BotCommand("post", "手动推送某些作品(用于补发等)")]
    await context.bot.set_my_commands(command_list)

    await context.bot.set_my_description(
        "一个推送pixiv账号关注画师更新的机器人,可以自动将更新的作品推送到频道中(注意,bot重启并不会通知,重启会导致推送任务丢失需要手动重新开启),使用/start开始")
    await context.bot.set_my_short_description(
        "一个推送pixiv账号关注画师更新的机器人,可以自动将更新的作品推送到频道中(注意,bot重启并不会通知,重启会导致推送任务丢失需要手动重新开启)")

    await update.message.reply_text("ok")


async def post(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await check_available(update, context):
        return
    logging.info("post by {}".format(update.effective_message.from_user.id))
    try:
        if len(context.args) >= 2:
            channel = int(context.args[1])
        else:
            channel = None
        pid = context.args[0].split("/")[-1]
        a = int(pid)
        if a < 0:
            raise ValueError
        tmp_dir = get_tmp_path()
        config = Config.get(get_user_config_path(update))
        user = config.cookie_verify()
        if user["userId"] is None:
            await context.bot.send_message(chat_id=update.message.chat_id, text="cookie无效,请先重新设置cookie")
            return

        global user_config_path
        if channel and channel in Config.get_managed_channel_without_someone(user_config_path,
                                                                             get_user_config_path(update)):
            await context.bot.send_message(chat_id=update.message.chat_id, text="该频道由其他人管理,不可推送消息")
            return

        if channel:
            config.my_channel_append(channel)

        cookie = config.cookie
        if not os.path.exists(tmp_dir):
            os.makedirs(tmp_dir)
        delete_files_in_folder(tmp_dir)

        try:
            meta = spider.get_illust_meta(pid, cookie)
            save_illust.save_illust(pid, tmp_dir, cookie, True, False, True, False)
        except pbrm.UnSupportIllustType:
            await context.bot.send_message(chat_id=update.message.chat_id, text="暂不支持插画 漫画 动图以外的作品推送"
                                           .format(pid))
            return
        except Exception as e:
            logging.error(context.job.data + " " + str(e))
            await context.bot.send_message(chat_id=update.message.chat_id, text="下载文件时发生错误: {}"
                                           .format(str(e), pid))
            return
        origin_url = "https://www.pixiv.net/artworks/{}".format(pid)
        title = meta["illustTitle"]
        user_url = "https://www.pixiv.net/users/{}".format(meta["userId"])
        user_name = meta["userName"]
        tags = get_tags(meta)
        has_spoiler = "#R18" in tags  # 对r18自动遮罩
        caption = "Tags: {}\nauthor: <a href=\"{}\">{}</a>\norigin: <a href=\"{}\">{}</a>".format(
            " ".join(tags), user_url, user_name, origin_url, title
        )
        # 区分动图和图片
        if meta["illustType"] == 0 or meta["illustType"] == 1:
            files = [open(os.path.join(tmp_dir, i), "rb") for i in sorted(os.listdir(tmp_dir)) if
                     not os.path.isdir(os.path.join(tmp_dir, i))]
            if len(files) > 10:
                caption += "\n<i>作品图片共{}张,未显示完全</i>".format(len(files))
            caption += "\n<i>手动推送</i>"
            bytes_files = [compress_image_if_needed(f.read()) for f in files][
                          0:10]  # 对超过9.5MB的图片压缩(其实上限是10MB),最多只发送10张图(上限)
            if channel:
                await context.bot.send_media_group(chat_id=channel,
                                                   media=[InputMediaPhoto(media=m, has_spoiler=has_spoiler) for m in
                                                          bytes_files]
                                                   , caption=caption, parse_mode="HTML")
            else:
                for c in config.channel:
                    await context.bot.send_media_group(chat_id=c,
                                                       media=[InputMediaPhoto(media=m, has_spoiler=has_spoiler) for m in
                                                              bytes_files]
                                                       , caption=caption, parse_mode="HTML")
            for i in files:
                i.close()
            delete_files_in_folder(tmp_dir)
        elif meta["illustType"] == 2:
            file = open(os.path.join(tmp_dir, [f for f in os.listdir(tmp_dir) if f.endswith(".gif")][0]), "rb")
            if channel:
                await context.bot.send_animation(chat_id=channel, animation=file, caption=caption, parse_mode="HTML",
                                                 has_spoiler=has_spoiler)
            else:
                for c in config.channel:
                    await context.bot.send_animation(chat_id=c, animation=file, caption=caption, parse_mode="HTML",
                                                     has_spoiler=has_spoiler)
            file.close()
            delete_files_in_folder(tmp_dir)

    except (KeyError, IndexError, ValueError):
        await context.bot.send_message(chat_id=update.message.chat_id, text="""
用法:
/post <PID/URL> [<CHANNEL>]
<PID/URL>: 作品的id或者链接(如111286968或https://www.pixiv.net/artworks/111286968)
<CHANNEL>: 可选,频道id,为空时向推送列表里所有的频道推送,不为空则向指定频道推送
和定时推送任务不同的是会在发送消息里额外附加一个"手动推送"
        """)
    except Exception as e:
        await context.bot.send_message(chat_id=update.message.chat_id, text="发送错误: {}".format(str(e)))
        logging.error("发送错误: {}".format(str(e)))


def block_thread():
    while not do_stop_bot:
        time.sleep(1)
        print("wait")


async def run_bot(application: Application):
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
    application.add_handler(CommandHandler("set_des", set_des))
    application.add_handler(CommandHandler("post", post))
    application.add_handler(MessageHandler(filters.ChatType.CHANNEL, get_channel_id))

    await application.initialize()
    await application.start()
    await application.updater.start_polling(allowed_updates=Update.ALL_TYPES, read_timeout=600, write_timeout=600
                                            , pool_timeout=600, connect_timeout=600, timeout=600)

    command_list = [BotCommand("start", "开始和基础的帮助"),
                    BotCommand("set", "设置相关参数"),
                    BotCommand("get", "获取相关参数"),
                    BotCommand("run", "运行定时推送任务"),
                    BotCommand("stop", "停止定时推送任务"),
                    BotCommand("cookie_verify", "查询当前cookie可用性"),
                    BotCommand("add_channel", "添加频道到推送列表"),
                    BotCommand("del_channel", "从推送列表中删除特定频道"),
                    BotCommand("del_all_channel", "清空推送列表"),
                    BotCommand("status", "查看当然任务状态"),
                    BotCommand("post", "手动推送某些作品(用于补发等)")]
    await application.bot.set_my_commands(command_list)

    await application.bot.set_my_description(
        "一个推送pixiv账号关注画师更新的机器人,可以自动将更新的作品推送到频道中(注意,bot重启并不会通知,重启会导致推送任务丢失需要手动重新开启),使用/start开始")
    await application.bot.set_my_short_description(
        "一个推送pixiv账号关注画师更新的机器人,可以自动将更新的作品推送到频道中(注意,bot重启并不会通知,重启会导致推送任务丢失需要手动重新开启)")

    for admin in SConfig.get_admin():
        await application.bot.send_message(chat_id=admin, text="bot启动成功")

    for job_user in SConfig.get_job_users():
        await application.bot.send_message(chat_id=job_user, text="bot重启成功,请手动开启推送任务")
    SConfig.clean_job_user()

    block = asyncio.to_thread(block_thread)
    await block

    for admin in SConfig.get_admin():
        await application.bot.send_message(chat_id=admin, text="bot即将关闭")

    for job_user in SConfig.get_job_users():
        await application.bot.send_message(chat_id=job_user, text="bot即将关闭(维护或更新),重启后会有上线提示")

    await application.updater.stop()
    await application.stop()
    await application.shutdown()


def run(bot_key, tmp, config_path):
    global tmp_path, user_config_path
    tmp_path = tmp
    delete_files_in_folder(tmp)
    user_config_path = config_path
    application = Application.builder().token(bot_key).build()

    asyncio.run(run_bot(application))
