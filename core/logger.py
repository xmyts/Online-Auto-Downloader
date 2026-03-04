import logging
import os
from logging.handlers import RotatingFileHandler

# 确保日志目录存在
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

def setup_logger(name="YoukuDownloader"):
    logger = logging.getLogger(name)
    
    # 避免重复绑定 handler
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        
        # 定义日志格式: [时间] [级别] - 消息
        formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 1. 输出到文件，最大10MB，保留3个备份
        log_file = os.path.join(LOG_DIR, "downloader.log")
        file_handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=3, encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        # 2. 输出到控制台
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
    return logger

# 实例化一个全局可用的 logger
logger = setup_logger()