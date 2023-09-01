# p站关注画师推送bot

## 部署方法

1. 拉取仓库  
`git clone https://github.com/stay-miku/pfub.git`
2. 安装依赖,必须依赖为**pbrm, Pillow, python-telegram-bot, python-telegram-bot\[job-queue\]**  
`pip install --upgrade pbrm Pillow python-telegram-bot "python-telegram-bot[job-queue]"`  
需要确保python版本为**3.9**及以上  
`python --version`
3. 修改pixivFollowUpdateBot内的 **\_\_main\_\_.py**中的bot_key为自己bot的api_key  
`bot_key = "KEY"`
4. 运行bot  
`python -m pixivFollowUpdateBot`  

## 配置文件
### 系统配置文件
系统配置文件位于运行bot目录下的**system_config.json**,可以在**pixivFollowUpdateBot/system_config.py**中修改默认的配置文件路径  
`config_path = "./system_config.json"`  


### 系统配置文件内容:
1. admin_users, 管理员账号,数组,填写自己tg账号的**纯数字id**,某些命令需要管理员权限
2. available_users, 可使用bot账号,数组,填写你希望可以使用你的bot的账号的**纯数字id**,为空时所有人都可以使用
3. users, 用于记录使用过当前bot的账号数组, 用于/post_all 命令
4. job_users, 用于记录目前有哪些账号启动了推送任务,用于关闭bot和启动bot时推送提醒消息和/post_job 命令


### 用户配置文件
用户配置文件默认位于 **./user**下,可以在**pixivFollowUpdateBot/\_\_main\_\_.py**中修改默认路径,由于使用文件储存数据,所以不适合大量用户使用  
`user_config_path = "./user"`


### 其他一些配置
临时文件夹,默认为 **./tmp**,用于存储临时下载文件,可于 **pixivFollowUpdateBot/\_\_main\_\_.py**中修改  
`tmp_path = "./tmp"`


log文件夹,默认为 **./logs**,可于**pixivFollowUpdateBot/bot.py**中自行修改(就是懒)