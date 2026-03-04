import os
import subprocess
import re
import random
import requests
from urllib.parse import urlparse
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type

# 引入我们第一部分写好的全局日志模块
from core.logger import logger

class VideoDownloadError(Exception):
    """自定义视频下载异常"""
    pass

class HeadlessDownloader:
    def __init__(self, config_data, base_output_dir):
        """
        初始化下载器
        :param config_data: 包含 cookie 和 header 的字典
        :param base_output_dir: 基础下载目录 (如 /downloads)
        """
        self.base_output_dir = base_output_dir
        self.cookies_str = config_data.get("cookies_string", "")
        self.auth_header = config_data.get("authorization", "")
        self.custom_headers = config_data.get("custom_headers", {})
        
        # 原代码中的反爬增强 User-Agents
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Firefox/113.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Safari/605.1.15"
        ]

    def _get_target_path(self, show_name, year, episode_num):
        """
        根据你的要求，按：名称+年 / 第几集 生成文件夹和文件路径
        例如: /downloads/甄嬛传 (2011)/第01集.mp4
        """
        show_folder = f"{show_name} ({year})" if year else show_name
        full_dir = os.path.join(self.base_output_dir, show_folder)
        
        if not os.path.exists(full_dir):
            os.makedirs(full_dir, exist_ok=True)
            logger.info(f"创建剧集目录: {full_dir}")
            
        file_prefix = f"第{str(episode_num).zfill(2)}集"
        return full_dir, file_prefix

    # 核心需求：下载失败时进行第二次重新试验 (最多尝试2次，中间等待5秒)
    @retry(
        stop=stop_after_attempt(2), 
        wait=wait_fixed(5),
        retry=retry_if_exception_type(VideoDownloadError),
        before_sleep=lambda retry_state: logger.warning(f"下载失败，准备进行第 {retry_state.attempt_number + 1} 次重试...")
    )
    def download_episode(self, url, show_name, year, episode_num, progress_callback=None):
        """
        下载单集视频的对外接口
        :param progress_callback: 用于给前端 Web UI 回传进度的回调函数
        """
        target_dir, file_prefix = self._get_target_path(show_name, year, episode_num)
        
        # yt-dlp 的输出模板：/downloads/剧名 (年份)/第01集.mp4
        output_template = os.path.join(target_dir, f"{file_prefix}.%(ext)s")
        
        logger.info(f"开始下载 {show_name} 第 {episode_num} 集: {url}")
        if progress_callback:
            progress_callback(0, f"准备下载 {file_prefix}...")

        success = self._download_with_yt_dlp(url, output_template, progress_callback)
        
        if not success:
            logger.error(f"{show_name} 第 {episode_num} 集下载彻底失败！")
            raise VideoDownloadError("yt-dlp 核心下载逻辑返回错误")
            
        logger.info(f"{show_name} 第 {episode_num} 集下载完成！")
        if progress_callback:
            progress_callback(100, "下载完成")
        
        return True

    def _download_with_yt_dlp(self, url, output_template, progress_callback):
        """改造自原代码的 yt-dlp 调用逻辑"""
        try:
            command = ["yt-dlp", "-o", output_template]
            
            # 注入 Authorization 和自定义头
            if self.auth_header:
                command.extend(["--add-header", f"Authorization:{self.auth_header}"])
            for key, value in self.custom_headers.items():
                command.extend(["--add-header", f"{key}:{value}"])
                
            # 注入 Cookie
            input_data = None
            if self.cookies_str:
                command.extend(["--cookies", "-"]) # 从标准输入读取
                input_data = self.cookies_str.encode('utf-8')
                
            # 随机 UA
            command.extend(["--user-agent", random.choice(self.user_agents)])
            
            # 使用最佳画质和音质
            command.extend(["-f", "bestvideo+bestaudio/best"])
            command.append(url)
            
            logger.info(f"执行下载命令: {' '.join(command[:-1])} [URL隐藏]")

            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE if input_data else None,
                text=True
            )
            
            # 写入 Cookie 到标准输入
            if input_data:
                process.stdin.write(input_data.decode())
                process.stdin.close()
                
            # 解析进度的正则
            yt_dlp_pattern = re.compile(r'\[download\]\s+(\d+\.\d+)%')
            
            while True:
                line = process.stdout.readline()
                if not line:
                    break
                line = line.strip()
                
                # 过滤掉过多无用的日志，只提取进度信息或者报错
                if "[download]" in line or "Error" in line:
                    logger.debug(line)
                    
                progress_match = yt_dlp_pattern.search(line)
                if progress_match and progress_callback:
                    percent = float(progress_match.group(1))
                    progress_callback(percent, line)
                    
            process.wait()
            return process.returncode == 0
            
        except Exception as e:
            logger.error(f"yt-dlp 执行异常: {str(e)}")
            return False