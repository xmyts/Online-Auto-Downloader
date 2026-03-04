import time
import random
import re
from urllib.parse import urljoin
from tenacity import retry, stop_after_attempt, wait_fixed
from playwright.sync_api import sync_playwright

# 引入全局日志
from core.logger import logger

class YoukuScraper:
    def __init__(self, config_data):
        self.cookies_str = config_data.get("cookies_string", "")
        # 将原生 cookie 字符串转换为 playwright 需要的字典格式
        self.cookies = self._parse_cookies(self.cookies_str)
        self.base_url = "https://www.youku.com"

    def _parse_cookies(self, cookie_str):
        """解析 Cookie 字符串"""
        cookies = []
        if not cookie_str:
            return cookies
        for item in cookie_str.split(';'):
            if '=' in item:
                name, value = item.strip().split('=', 1)
                cookies.append({
                    "name": name,
                    "value": value,
                    "domain": ".youku.com",
                    "path": "/"
                })
        return cookies

    @retry(stop=stop_after_attempt(2), wait=wait_fixed(5), before_sleep=lambda rs: logger.warning(f"获取剧集列表失败，准备第 {rs.attempt_number + 1} 次重试..."))
    def fetch_show_episodes(self, show_name):
        """
        核心方法：模拟人类搜索并获取全集链接
        返回格式: {"show_name": "甄嬛传", "year": "2011", "episodes": [{"num": 1, "url": "..."}]}
        """
        logger.info(f"开始爬取电视剧信息: {show_name}")
        
        with sync_playwright() as p:
            # 使用 Chromium，开启无头模式 (Docker环境必备)
            browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
            )
            context.add_cookies(self.cookies)
            page = context.new_page()

            try:
                # 1. 模拟人类访问搜索页
                search_url = f"https://so.youku.com/search_video/q_{show_name}"
                page.goto(search_url, timeout=30000)
                time.sleep(random.uniform(2, 4)) # 随机停顿模仿人类

                # 提取年份 (这里假设能在页面中找到包含年份的元素，实际情况需根据优酷DOM调整)
                # 作为一个兜底策略，如果没有抓到年份，则默认空
                year = ""
                year_element = page.query_selector('.pub-time') # 需根据实际页面结构调整
                if year_element:
                    year_match = re.search(r'\d{4}', year_element.inner_text())
                    if year_match:
                        year = year_match.group()

                # 2. 获取第一集/主播放页链接
                first_video_link = page.query_selector('a[href*="v.youku.com/v_show/id_"]')
                if not first_video_link:
                    raise Exception("未能在搜索结果中找到播放链接")
                
                play_url = urljoin(self.base_url, first_video_link.get_attribute("href"))
                logger.info(f"找到主播放页: {play_url}")

                # 3. 进入播放页，提取所有集数
                page.goto(play_url, timeout=30000)
                time.sleep(random.uniform(3, 5)) # 等待剧集列表加载

                # 抓取选集列表 (这里需根据优酷当前 DOM 结构精细调整选择器，通常在类似 .anthology-content 下)
                # 作为一个通用化示例，我们抓取所有包含正片链接的 a 标签
                episode_elements = page.query_selector_all('a.anthology-item-link, div.anthology-wrap a')
                
                episodes = []
                for idx, el in enumerate(episode_elements):
                    href = el.get_attribute('href')
                    if href and 'v_show/id_' in href:
                        ep_url = urljoin(self.base_url, href)
                        episodes.append({
                            "num": idx + 1,
                            "url": ep_url
                        })
                
                # 去重并排序
                seen = set()
                unique_episodes = []
                for ep in episodes:
                    if ep['url'] not in seen:
                        seen.add(ep['url'])
                        unique_episodes.append(ep)

                if not unique_episodes:
                    logger.warning("未抓取到任何剧集，可能是DOM结构变化或需要展开按钮。返回主播放页作为单集。")
                    unique_episodes.append({"num": 1, "url": play_url})

                logger.info(f"成功获取到 {len(unique_episodes)} 集信息。年份: {year}")
                return {
                    "show_name": show_name,
                    "year": year,
                    "episodes": unique_episodes
                }

            except Exception as e:
                logger.error(f"爬取过程中发生错误: {str(e)}")
                raise
            finally:
                browser.close()