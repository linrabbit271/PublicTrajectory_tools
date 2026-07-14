import subprocess
import base64
import json
import os
import urllib.request
import ssl
import concurrent.futures
import time


def get_browser_config():
    """实时读取用户在 UI 界面配置的路径"""
    try:
        with open("browser_config.json", "r", encoding="utf-8") as f:
            cfg = json.load(f)
            return cfg.get("CHROME_PATH", ""), cfg.get("DRIVER_PATH", ""), cfg.get("USER_DATA_DIR", "")
    except Exception:
        return "", "", ""


def fetch_real_src(awb):
    """
    【API 刺客】底层单任务：突破 8443 接口拿底层 src (无视 VPN 代理干扰)
    """
    url = "https://www.mawb.cn:8443/Webservice/WSMawbSystem.asmx/WSTrackTrace"
    payload = {
        "data": {
            "TypeStr": "TRACK",
            "UserLanguage": "zh-cn",
            "MawbNo": awb
        }
    }
    data = json.dumps(payload).encode('utf-8')

    req = urllib.request.Request(url, data=data)
    req.add_header('Content-Type', 'application/json; charset=utf-8')
    req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
    req.add_header('Origin', 'https://www.mawb.cn')
    req.add_header('Referer', 'https://www.mawb.cn/')

    try:
        context = ssl._create_unverified_context()

        # 🌟 核心防线 1：强行清空代理，让请求不走 VPN，直连国内 mawb.cn！
        proxy_handler = urllib.request.ProxyHandler({})
        opener = urllib.request.build_opener(proxy_handler)

        response = opener.open(req, timeout=12)

        if response.getcode() == 200:
            res_json = json.loads(response.read().decode('utf-8'))
            d_str = res_json.get("d", "[]")
            parsed = json.loads(d_str)

            if parsed and len(parsed) > 0 and parsed[0].get("src"):
                src = parsed[0]["src"]
                # 补全绝对路径
                if src.startswith('/'):
                    src = "https://www.mawb.cn" + src
                return awb, src
    except Exception as e:
        print(f"[{awb}] 接口刺探失败: {e}")

    return awb, None


def open_mawb_tracking(awb_list):
    """
    【极速注入 终极防封版 V4.2】
    稳定并发 + 强行直连修复，既能查常规单号，也能完美代理查询 157 提单！
    """
    if not awb_list:
        return False, "没有传入任何提单号"

    CHROME_PATH, DRIVER_PATH, USER_DATA_DIR = get_browser_config()

    if not CHROME_PATH or not USER_DATA_DIR:
        return False, "系统找不到浏览器核心！请先在右侧点击【⚙️ 浏览器环境配置】设置你的专属路径。"

    valid_awbs = [awb.strip() for awb in awb_list if awb.strip()]
    if not valid_awbs:
        return False, "传入的提单号无效"

    # =========================================================
    # 🌟 核心防线 2：将并发数稳定在 5，防止爱德文限流触发
    # =========================================================
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(fetch_real_src, awb) for awb in valid_awbs]
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())

    target_uris = []

    for awb, real_url in results:
        if not real_url:
            real_url = f"https://www.mawb.cn/zh-cn/?MawbNo={awb}"

        html_content = f'''
        <!DOCTYPE html>
        <html>
        <head><meta charset="utf-8"></head>
        <body style="display:flex; justify-content:center; align-items:center; height:100vh; background:#f0f2f5;">
            <h3 style="font-family:'Microsoft YaHei'; color:#6c757d;">
                🚀 正在极速注入提单 {awb} ...
            </h3>
            <script>
                window.name="AWB_{awb}";
                window.location.replace("{real_url}");
            </script>
        </body>
        </html>
        '''

        b64_code = base64.b64encode(html_content.encode('utf-8')).decode('utf-8')
        data_uri = f"data:text/html;base64,{b64_code}"
        target_uris.append(data_uri)

    if not target_uris:
        return False, "未能生成任何有效的启动任务"

    chunk_size = 10
    try:
        for i in range(0, len(target_uris), chunk_size):
            chunk_uris = target_uris[i:i + chunk_size]

            cmd = [
                      CHROME_PATH,
                      f'--remote-debugging-port=9333',
                      f'--user-data-dir={USER_DATA_DIR}',
                      '--no-first-run',
                      '--no-default-browser-check',
                      '--no-proxy-server'  # 🌟 核心防线 3：强行让 Chrome 绕过代理直连
                  ] + chunk_uris

            subprocess.Popen(cmd)

        return True, "成功"
    except Exception as e:
        return False, f"启动 Chrome 失败: {str(e)}"