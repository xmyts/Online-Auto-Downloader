import os
import json
import gradio as gr
from pathlib import Path

# 导入核心模块 (假设这些类和方法在您的 core 目录中已经定义)
try:
    from core.task_manager import TaskManager
    from core.logger import setup_logger
except ImportError as e:
    print(f"警告: 核心模块导入失败，请确保 core 目录下有对应文件。错误信息: {e}")
    # 为了保证无核心代码时UI也能跑起来看效果，这里做个基础容错
    TaskManager = None 

# ---------------- 配置与初始化 ----------------

# 确保必要的目录存在
os.makedirs("config", exist_ok=True)
os.makedirs("logs", exist_ok=True)

# 日志文件路径设置
LOG_FILE = "logs/downloader.log"

# 全局任务管理器实例
if TaskManager:
    task_manager = TaskManager()
else:
    task_manager = None # 容错处理

# ---------------- 核心交互函数 ----------------

def check_cookies():
    """检查 cookie 文件是否存在且格式正确"""
    cookie_path = "config/cookies.json"
    if not os.path.exists(cookie_path):
        return "⚠️ 警告: config/cookies.json 文件不存在，下载可能会失败！请先配置好身份验证。"
    try:
        with open(cookie_path, "r", encoding="utf-8") as f:
            json.loads(f.read())
        return "✅ Cookie 配置已加载。"
    except Exception:
        return "❌ 错误: cookies.json 格式不正确，请检查 JSON 格式。"

def add_new_task(keyword):
    """处理用户提交的下载任务"""
    if not keyword.strip():
        return "提交失败：请输入剧名或优酷链接！"
    
    if not task_manager:
        return "系统错误：TaskManager 未初始化，无法添加任务。"
    
    # 调用核心模块添加任务
    success, msg = task_manager.add_task(keyword)
    if success:
        return f"✅ 成功添加任务: {keyword}。\n{msg}"
    else:
        return f"❌ 添加失败: {keyword}。\n{msg}"

def get_queue_status():
    """获取当前任务队列状态"""
    if not task_manager:
        return "TaskManager 未加载，无法获取状态。"
    
    # 假设 task_manager 有 get_status 方法返回字符串或字典
    return task_manager.get_status_text() 

def get_latest_logs():
    """读取最新的运行日志展示在 UI 上"""
    if not os.path.exists(LOG_FILE):
        return "暂无日志记录。"
    
    try:
        # 只读取最后 30 行日志防止 UI 卡顿
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
            return "".join(lines[-30:])
    except Exception as e:
        return f"读取日志失败: {e}"

# ---------------- Gradio Web UI 构建 ----------------

def create_ui():
    # 使用 Blocks 构建自定义仪表盘布局
    with gr.Blocks(title="Youku 自动下载器", css="footer {visibility: hidden}") as demo:
        gr.Markdown("# 🎬 Youku 自动化下载中心")
        
        # 顶部：状态自检栏
        with gr.Row():
            cookie_status = gr.Textbox(
                value=check_cookies(), 
                label="系统状态自检", 
                interactive=False,
                lines=1
            )
            
        # 中间：任务控制与状态展示
        with gr.Row():
            # 左侧：输入与控制
            with gr.Column(scale=1):
                gr.Markdown("### 📥 添加下载任务")
                keyword_input = gr.Textbox(
                    label="剧名或链接", 
                    placeholder="请输入剧名 (如: 甄嬛传) 或 优酷视频播放页URL",
                    lines=2
                )
                submit_btn = gr.Button("添加到下载队列", variant="primary")
                op_result = gr.Textbox(label="操作反馈", interactive=False, lines=2)
                
            # 右侧：队列查看
            with gr.Column(scale=2):
                gr.Markdown("### 📋 当前任务队列")
                queue_display = gr.Textbox(
                    label="队列详情 (剧集排队 & 进度)", 
                    interactive=False, 
                    lines=6
                )
                refresh_queue_btn = gr.Button("🔄 刷新队列状态")

        gr.Markdown("---")
        
        # 底部：日志展示区
        with gr.Row():
            with gr.Column():
                gr.Markdown("### 📝 运行日志 (排错专用)")
                log_display = gr.TextArea(
                    label=f"最新日志 (读取自 {LOG_FILE})", 
                    interactive=False, 
                    lines=10,
                    max_lines=15
                )
                refresh_log_btn = gr.Button("🔄 刷新日志")

        # ---------------- 事件绑定 ----------------
        
        # 提交任务事件
        submit_btn.click(
            fn=add_new_task, 
            inputs=keyword_input, 
            outputs=op_result
        )
        
        # 刷新队列事件
        refresh_queue_btn.click(
            fn=get_queue_status, 
            outputs=queue_display
        )
        
        # 刷新日志事件
        refresh_log_btn.click(
            fn=get_latest_logs, 
            outputs=log_display
        )

    return demo

if __name__ == "__main__":
    # 如果 task_manager 存在，启动后台下载循环
    if task_manager:
        task_manager.start_worker_thread() # 假设您有一个后台线程处理队列
        
    app = create_ui()
    # 启动 Gradio，server_name 设置为 0.0.0.0 以便 Docker 容器内外部都能访问
    app.launch(server_name="0.0.0.0", server_port=7860, share=False)
