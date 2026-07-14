import subprocess
import base64
import subprocess
import base64
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


def open_parcels_tracking(awb_list):
    """
    【ParcelsApp极速加密注入版】利用 Base64 Data URI 提前给标签页烙印 window.name
    """
    if not awb_list:
        return False, "没有传入任何提单号"

    # 🌟 每次运行时，向系统索要最新路径
    CHROME_PATH, DRIVER_PATH, USER_DATA_DIR = get_browser_config()

    # 防呆校验
    if not CHROME_PATH or not USER_DATA_DIR:
        return False, "系统找不到浏览器核心！请先在右侧点击【⚙️ 浏览器环境配置】设置你的专属路径。"

    target_uris = []
    for awb in awb_list:
        awb = awb.strip()
        if not awb:
            continue

        # 🌟 ParcelsApp 的专属 URL 拼接规则
        real_url = f"https://parcelsapp.com/en/tracking/{awb}"

        # 核心黑魔法：同样保持 AWB_ 隐形烙印前缀，后续截图脚本完全不需要改动，无缝通杀！
        js_code = f'<script>window.name="AWB_{awb}";window.location.href="{real_url}";</script>'

        # 转化为 Base64 安全格式
        b64_code = base64.b64encode(js_code.encode('utf-8')).decode('utf-8')
        data_uri = f"data:text/html;base64,{b64_code}"

        target_uris.append(data_uri)

    if not target_uris:
        return False, "传入的提单号无效"

    chunk_size = 10  # 每次连发 10 个，防止命令行过长
    try:
        for i in range(0, len(target_uris), chunk_size):
            chunk_uris = target_uris[i:i + chunk_size]

            cmd = [
                      CHROME_PATH,
                      f'--remote-debugging-port=9333',
                      f'--user-data-dir={USER_DATA_DIR}',
                      '--no-first-run',
                      '--no-default-browser-check'
                  ] + chunk_uris

            subprocess.Popen(cmd)

        return True, "成功"
    except Exception as e:
        return False, f"启动 Chrome 失败: {str(e)}"