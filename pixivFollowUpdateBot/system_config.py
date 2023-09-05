from typing import List, Dict
import json
import os


config_path = "./system_config.json"


class SConfig:
    system_config_path = config_path
    admin_users: List[int]
    available_users: List[int]
    users: List[int]
    users_name: Dict[int, str]
    job_users: List[int]
    path: str

    def __init__(self, path: str, admin: List[int] = None, available: List[int] = None, users: List[int] = None
                 , job: List[int] = None):
        if admin is None:
            self.load(path)
            self.path = path

        else:
            self.admin_users = admin
            self.available_users = available
            self.users = users
            self.job_users = job
            self.path = path

    @classmethod
    def get(cls, path):
        if os.path.exists(path) and not os.path.isdir(path):
            return cls(path)
        else:
            return cls(path, [], [], [], [])

    @classmethod
    def Get(cls):
        return cls.get(cls.system_config_path)

    @classmethod
    def admin_verify(cls, user: int):
        if user in cls.Get().admin_users:
            return True
        else:
            return False

    @classmethod
    def available_verify(cls, user: int):
        available = cls.Get().available_users
        if available:
            if user in available:
                return True
            else:
                return False
        else:
            return True

    @classmethod
    def get_admin(cls):
        return cls.Get().admin_users

    @classmethod
    def get_available(cls):
        return cls.Get().available_users

    @classmethod
    def get_users(cls):
        return cls.Get().users

    @classmethod
    def get_job_users(cls):
        return cls.Get().job_users

    @classmethod
    def add_admin(cls, user: int):
        config = cls.Get()
        if user in config.admin_users:
            return False
        else:
            config.admin_users.append(user)
            config.save()
            return True

    @classmethod
    def remove_admin(cls, user: int):
        config = cls.Get()
        if user in config.admin_users:
            config.admin_users.remove(user)
            config.save()
            return True
        else:
            return False

    @classmethod
    def add_available(cls, user: int):
        config = cls.Get()
        if user in config.available_users:
            return False
        else:
            config.available_users.append(user)
            config.save()
            return True

    @classmethod
    def remove_available(cls, user: int):
        config = cls.Get()
        if user in config.available_users:
            config.available_users.remove(user)
            config.save()
            return True
        else:
            return False

    @classmethod
    def clean_available(cls):
        config = cls.Get()
        config.available_users = []
        config.save()
        return True

    @classmethod
    def add_user(cls, user: int):
        config = cls.Get()
        if user in config.users:
            return False
        else:
            config.users.append(user)
            config.save()
            return True

    @classmethod
    def add_job_user(cls, user: int):
        config = cls.Get()
        if user in config.job_users:
            return False
        else:
            config.job_users.append(user)
            config.save()
            return True

    @classmethod
    def remove_job_user(cls, user: int):
        config = cls.Get()
        if user in config.job_users:
            config.job_users.remove(user)
            config.save()
            return True
        else:
            return False

    @classmethod
    def clean_job_user(cls):
        config = cls.Get()
        config.job_users = []
        config.save()
        return True

    @classmethod
    def get_user_name(cls, user_id: int):
        config = cls.Get()
        if user_id in config.users_name:
            return config.users_name[user_id]
        return None

    @classmethod
    def add_user_name(cls, user_id: int, user_name: str):
        config = cls.Get()
        if user_name is None:
            user_name = "None"
        if user_id in config.users_name and user_name == config.users_name[user_id]:
            return False
        config.users_name[user_id] = user_name
        config.save()
        return True

    def save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(json.dumps({
                "admin_users": self.admin_users,
                "available_users": self.available_users,
                "users": self.users,
                "job_users": self.job_users,
                "users_name": self.users_name
            }, ensure_ascii=False))

    def load(self, path: str):
        with open(path, "r", encoding="utf-8") as f:
            config = json.loads(f.read())
            self.admin_users = config["admin_users"]
            self.available_users = config["available_users"]
            self.users = config["users"]
            self.job_users = config["job_users"]
            if "users_name" in config:
                self.users_name = config["users_name"]
            else:
                self.users_name = {}
