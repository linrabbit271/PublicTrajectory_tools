import os
import sys
import time
import math
import base64
import re
import json
import urllib.parse
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service


def get_browser_config():
    try:
        with open("browser_config.json", "r", encoding="utf-8") as f:
            cfg = json.load(f)
            return cfg.get("CHROME_PATH", ""), cfg.get("DRIVER_PATH", ""), cfg.get("USER_DATA_DIR", "")
    except Exception:
        return "", "", ""


# ================= 各个渠道专属的提取策略 =================

def extract_mawb_awb(driver):
    try:
        win_name = driver.execute_script("return window.name;")
        if win_name and str(win_name).startswith("AWB_"):
            return win_name.replace("AWB_", "").strip()
    except:
        pass

    try:
        current_url = driver.current_url
        if "#" in current_url:
            hash_val = current_url.split("#")[-1].replace("AWB_", "").strip()
            if len(hash_val) > 5 and "-" in hash_val:
                return hash_val
    except:
        pass

    try:
        history = driver.execute_cdp_cmd("Page.getNavigationHistory", {})
        entries = history.get('entries', [])
        for entry in entries:
            url = entry.get('url', '')
            url = urllib.parse.unquote(url)
            if url.startswith("data:text/html"):
                if ";base64," in url:
                    b64_str = url.split(";base64,")[1]
                    b64_str += "=" * ((4 - len(b64_str) % 4) % 4)
                    js_code = base64.b64decode(b64_str).decode('utf-8', errors='ignore')
                    if 'AWB_' in js_code:
                        awb = js_code.split('AWB_')[1].split('"')[0]
                        return awb.strip()
    except Exception as e:
        pass
    return None


def extract_parcels_awb(driver):
    url_match = re.search(r"parcelsapp\.com/en/tracking/([^/?#]+)", driver.current_url, re.IGNORECASE)
    if url_match: return url_match.group(1).strip()
    return None


def extract_universal_awb(driver, awb_list):
    if not awb_list: return None
    current_url = driver.current_url.replace("-", "")
    title = driver.title.replace("-", "")

    for awb in awb_list:
        clean_awb = awb.replace("-", "").strip()
        if not clean_awb: continue
        if clean_awb in current_url or clean_awb in title:
            return awb
        if len(clean_awb) == 11:
            prefix = clean_awb[:3]
            suffix = clean_awb[3:]
            if prefix in current_url and suffix in current_url:
                return awb
    return None


# ================= 无懈可击路由与截图主控 =================

def batch_fullpage_screenshot(status_callback=None, awb_list=None, sub_folder="", selected_statuses=None):
    if selected_statuses is None:
        selected_statuses = []

    if status_callback: status_callback("正在唤醒底层驱动程序...", 5)

    CHROME_PATH, DRIVER_PATH, USER_DATA_DIR = get_browser_config()
    if not DRIVER_PATH:
        return False, "系统找不到 Selenium 驱动！请先在右侧点击【⚙️ 浏览器环境配置】设置你的专属路径。"

    options = Options()
    options.add_experimental_option("debuggerAddress", "127.0.0.1:9333")
    service = Service(executable_path=DRIVER_PATH)
    driver = None

    try:
        driver = webdriver.Chrome(service=service, options=options)
    except Exception as e:
        return False, f"驱动接管失败！请确认9333浏览器已开启。\n详细报错: {str(e)}"

    # =====================================================================
    # 🌟 核心修改：动态获取程序当前所在目录，彻底告别写死的绝对路径
    # =====================================================================
    today_str = datetime.now().strftime("%Y年%m月%d日")

    # 智能判定：如果是打包后的 exe 运行，取 exe 所在目录；如果是源码运行，取当前工作目录
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.getcwd()

    save_dir = os.path.join(base_dir, "截图保存", today_str)

    if sub_folder:
        save_dir = os.path.join(save_dir, sub_folder)

    # 如果 "截图保存" 文件夹不存在，这里会自动把外层和内层文件夹一起建好
    os.makedirs(save_dir, exist_ok=True)

    success_count = 0
    skipped_count = 0

    try:
        original_window = driver.current_window_handle
        all_handles = driver.window_handles
        total_tabs = len(all_handles)

        if status_callback: status_callback(f"成功接管！共发现 {total_tabs} 个标签页，开始扫描...", 15)

        for idx, handle in enumerate(all_handles):
            try:
                driver.switch_to.window(handle)
                current_progress = 15 + int((idx / total_tabs) * 80)
                time.sleep(0.3)
                current_url = driver.current_url
                awb = None

                awb = extract_mawb_awb(driver)
                if not awb:
                    if "parcelsapp.com" in current_url:
                        time.sleep(0.3)
                        awb = extract_parcels_awb(driver)

                if not awb and awb_list:
                    awb = extract_universal_awb(driver, awb_list)

                # ================= 执行底层全景无裁切长截图 =================
                if awb:
                    if status_callback: status_callback(f"📸 抓取到目标单号: {awb}，正在长截图中...", current_progress)

                    metrics = driver.execute_cdp_cmd("Page.getLayoutMetrics", {})
                    rect = metrics.get('cssContentSize') or metrics.get('contentSize') or metrics.get('layoutViewport')

                    width = math.ceil(rect['width'])
                    height = min(math.ceil(rect['height']), 15000)

                    clip = {'x': 0, 'y': 0, 'width': width, 'height': height, 'scale': 1}

                    res = driver.execute_cdp_cmd("Page.captureScreenshot", {
                        "format": "png",
                        "clip": clip,
                        "captureBeyondViewport": True,
                        "fromSurface": True
                    })

                    # 从内存中解码出纯粹的图像数据
                    img_data = base64.b64decode(res['data'])

                    # 核心分发逻辑
                    if not selected_statuses:
                        filepath = os.path.join(save_dir, f"{awb}.png")
                        with open(filepath, "wb") as f:
                            f.write(img_data)
                    else:
                        for status in selected_statuses:
                            status_dir = os.path.join(save_dir, status)
                            os.makedirs(status_dir, exist_ok=True)

                            filepath = os.path.join(status_dir, f"{awb}.png")
                            with open(filepath, "wb") as f:
                                f.write(img_data)

                    success_count += 1
                else:
                    skipped_count += 1

            except Exception as page_e:
                print(f"单页截图失败 (跳过): {str(page_e)}")
                skipped_count += 1
                continue

        try:
            driver.switch_to.window(original_window)
        except:
            pass

        return True, f"✅ 截图与归档圆满完成！\n成功截取: {success_count} 张\n\n数据已自动归档至:\n{save_dir}"

    except Exception as e:
        return False, f"全局运行发生意外错误: {str(e)}"
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass