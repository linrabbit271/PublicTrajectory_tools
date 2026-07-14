import subprocess
import json
import os

# ================= 新增：动态配置读取器 =================
def get_browser_config():
    """实时读取用户在 UI 界面配置的路径"""
    try:
        with open("browser_config.json", "r", encoding="utf-8") as f:
            cfg = json.load(f)
            return cfg.get("CHROME_PATH", ""), cfg.get("DRIVER_PATH", ""), cfg.get("USER_DATA_DIR", "")
    except Exception:
        return "", "", ""


def open_aat_tracking():
    """
    【AAT 极简纯净版】仅在 9333 端口浏览器中打开官网，交由人工接管
    """
    # 🌟 每次运行时，向系统索要最新路径 (AAT不需要驱动，所以中间的用 _ 占位忽略)
    CHROME_PATH, _, USER_DATA_DIR = get_browser_config()

    # 防呆校验
    if not CHROME_PATH or not USER_DATA_DIR:
        return False, "系统找不到浏览器核心！请先在右侧点击【⚙️ 浏览器环境配置】设置你的专属路径。"

    target_url = "https://www.aat.com.hk/en/tracking"

    try:
        # 直接利用底层命令瞬间打开网页
        cmd = [
            CHROME_PATH,
            f'--remote-debugging-port=9333',
            f'--user-data-dir={USER_DATA_DIR}',
            '--no-first-run',
            '--no-default-browser-check',
            target_url
        ]

        subprocess.Popen(cmd)
        return True, "成功！请在浏览器中手动进行 AAT 查询。"

    except Exception as e:
        return False, f"极速拉起 AAT 失败: {str(e)}"