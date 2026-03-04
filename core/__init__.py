# 将核心类暴露出来，方便外部的 main.py 统一导入
from .logger import logger
from .task_manager import TaskManager
from .scraper import YoukuScraper
from .downloader import HeadlessDownloader

__all__ = [
    'logger',
    'TaskManager',
    'YoukuScraper',
    'HeadlessDownloader'
]