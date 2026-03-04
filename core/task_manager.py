import threading
import queue
import time
from core.logger import logger
from core.scraper import YoukuScraper
from core.downloader import HeadlessDownloader

class TaskManager:
    def __init__(self, config_data, base_output_dir):
        self.task_queue = queue.Queue() # 存放剧名的队列
        self.scraper = YoukuScraper(config_data)
        self.downloader = HeadlessDownloader(config_data, base_output_dir)
        
        # 状态记录，用于在 Web UI 上展示
        self.status = {
            "current_show": None,
            "current_episode": None,
            "progress_percent": 0.0,
            "progress_text": "闲置中",
            "queue_list": [],
            "completed_list": []
        }
        
        # 启动后台守护线程，不断检查队列
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()

    def add_shows(self, show_names_str):
        """将前端输入的电视剧名单（逗号分隔）加入队列"""
        shows = [s.strip() for s in show_names_str.split(',') if s.strip()]
        for show in shows:
            self.task_queue.put(show)
            self.status["queue_list"].append(show)
            logger.info(f"已将 {show} 加入下载队列")

    def get_status(self):
        """供前端 Web UI 调用的状态接口"""
        return self.status

    def _update_progress(self, percent, text):
        """传给 downloader 的回调函数，用于实时更新进度"""
        self.status["progress_percent"] = percent
        self.status["progress_text"] = text

    def _worker_loop(self):
        """后台苦力线程：严格按顺序执行"""
        while True:
            try:
                # 阻塞式获取任务，如果没有任务则等待
                current_show = self.task_queue.get()
                self.status["current_show"] = current_show
                self.status["queue_list"].remove(current_show)
                
                logger.info(f"======== 开始处理新剧集: {current_show} ========")
                self._update_progress(0, f"正在搜索抓取 {current_show} 的全集信息...")
                
                # 1. 调用爬虫获取剧集列表
                try:
                    show_data = self.scraper.fetch_show_episodes(current_show)
                except Exception as e:
                    logger.error(f"{current_show} 信息抓取彻底失败，跳过。原因: {str(e)}")
                    self.task_queue.task_done()
                    continue

                # 2. 依次下载每一集 (核心：等待上一集下完，再下下一集)
                for ep in show_data["episodes"]:
                    ep_num = ep["num"]
                    ep_url = ep["url"]
                    
                    self.status["current_episode"] = f"第{ep_num}集"
                    logger.info(f"准备下载 {current_show} 第 {ep_num} 集...")
                    
                    try:
                        self.downloader.download_episode(
                            url=ep_url,
                            show_name=show_data["show_name"],
                            year=show_data["year"],
                            episode_num=ep_num,
                            progress_callback=self._update_progress
                        )
                        # 模仿人类，两集之间停顿一下
                        time.sleep(random.uniform(5, 10))
                    except Exception as e:
                        logger.error(f"{current_show} 第 {ep_num} 集下载失败，继续尝试下一集。")
                
                # 该部剧全部处理完毕
                logger.info(f"======== {current_show} 全集处理完毕 ========")
                self.status["completed_list"].append(current_show)
                self.status["current_show"] = None
                self.status["current_episode"] = None
                self._update_progress(100, "等待新任务...")
                
                self.task_queue.task_done()
                
            except Exception as e:
                logger.error(f"Worker Loop 发生异常: {str(e)}")
                time.sleep(5)