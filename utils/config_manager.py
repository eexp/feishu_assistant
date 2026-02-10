"""配置管理模块：读写 app_id / app_secret 到本地 config.json"""

import json
import os

CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")


def load_config() -> dict:
    """从 config.json 加载配置，文件不存在则返回空字典"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def save_config(config: dict) -> None:
    """将配置保存到 config.json"""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def get_credentials() -> tuple[str, str]:
    """返回 (app_id, app_secret)，不存在则返回空字符串"""
    cfg = load_config()
    return cfg.get("app_id", ""), cfg.get("app_secret", "")


def save_credentials(app_id: str, app_secret: str) -> None:
    """保存 app_id 和 app_secret"""
    cfg = load_config()
    cfg["app_id"] = app_id
    cfg["app_secret"] = app_secret
    save_config(cfg)
