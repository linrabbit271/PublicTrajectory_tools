import subprocess
import time
import base64
import json
import math
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys


# ================= 动态配置读取器 (复用主框架) =================
def get_browser_config():
    try:
        with open("browser_config.json", "r", encoding="utf-8") as f:
            cfg = json.load(f)
            return cfg.get("CHROME_PATH", ""), cfg.get("DRIVER_PATH", ""), cfg.get("USER_DATA_DIR", "")
    except Exception:
        return "", "", ""


# ================= 第一部分：国泰专属极速自动化 (查 160) =================

def run_cathay_160_automation(awb_list):
    """
    【国泰货运专用组件】瞬间爆开网页 + 三路保险搜索 + 自动打烙印
    """
    if not awb_list: return False, "没有传入任何提单号"

    CHROME_PATH, DRIVER_PATH, USER_DATA_DIR = get_browser_config()
    if not CHROME_PATH or not DRIVER_PATH:
        return False, "系统找不到浏览器核心！请先在主界面配置路径。"

    target_url = "https://www.cathaycargo.com/zh-cn/track-and-trace.html"
    valid_uris = []

    # 瞬间构建 IPC 弹药包
    for awb in awb_list:
        clean_awb = awb.replace("-", "").strip()
        if len(clean_awb) < 8: continue

        # 烙印预埋
        js_code = f'<script>window.name="AWB_{awb}";window.location.href="{target_url}#{clean_awb}";</script>'
        b64_code = base64.b64encode(js_code.encode('utf-8')).decode('utf-8')
        data_uri = f"data:text/html;base64,{b64_code}"
        valid_uris.append(data_uri)

    if not valid_uris: return False, "单号格式不正确 (需160开头)"

    # 第一波：瞬间爆破开页
    try:
        cmd = [CHROME_PATH, '--remote-debugging-port=9333', f'--user-data-dir={USER_DATA_DIR}',
               '--no-first-run', '--no-default-browser-check'] + valid_uris
        subprocess.Popen(cmd)
    except Exception as e:
        return False, f"Chrome 启动失败: {str(e)}"

    # 第二波：派出幽灵探针执行“三路保险”搜索
    options = Options()
    options.add_experimental_option("debuggerAddress", "127.0.0.1:9333")
    service = Service(executable_path=DRIVER_PATH)

    driver = None
    try:
        time.sleep(4)  # 给网页缓冲时间
        driver = webdriver.Chrome(service=service, options=options)

        for handle in driver.window_handles:
            driver.switch_to.window(handle)
            current_url = driver.current_url
            if "cathaycargo.com" in current_url:
                # 从 URL 锚点取回单号后缀
                suffix = current_url.split("#")[-1][-8:]
                wait = WebDriverWait(driver, 20)

                try:
                    # 1. 定位并填入
                    input_field = wait.until(
                        EC.element_to_be_clickable((By.XPATH, "//input[contains(@name, 'airWaybill')]")))
                    input_field.clear()
                    input_field.send_keys(suffix)
                    time.sleep(1)

                    # 2. 三路提交保险 (你的原创逻辑)
                    btn_xpath = "//input[@type='submit' and @value='搜索' and contains(@class, '-searchbar-submit')]"
                    search_btn = driver.find_element(By.XPATH, btn_xpath)

                    try:
                        search_btn.click()  # 保险 1
                    except:
                        try:
                            driver.execute_script("arguments[0].click();", search_btn)  # 保险 2
                        except:
                            input_field.send_keys(Keys.ENTER)  # 保险 3

                    # 3. 搜索后补全烙印，确保截图能识别
                    time.sleep(3)
                    driver.execute_script(f'window.name="AWB_160-{suffix}";')

                except:
                    continue
        return True, "国泰货运已全部自动查询完毕。"
    except Exception as e:
        return False, str(e)
    finally:
        if driver: driver.quit()


# ================= 第二部分：国泰专属 CDP 长截图 (全景无裁切版) =================

def capture_cathay_fullpage_cdp(driver, awb_name, save_path):
    """
    【国泰专用截图引擎 - GoFullPage 完全体】全宽全长，绝不裁切边缘！
    """
    try:
        # 获取页面最真实的、完整的布局尺寸
        metrics = driver.execute_cdp_cmd("Page.getLayoutMetrics", {})
        rect = metrics.get('cssContentSize') or metrics.get('contentSize') or metrics.get('layoutViewport')

        full_width = math.ceil(rect['width'])
        full_height = min(math.ceil(rect['height']), 15000)  # 防止无限下拉网页导致内存崩溃

        # 🌟 核心修改：移除 1200px 的裁切限制，从坐标 (0,0) 开始，截取真实的全部宽高！
        clip_params = {
            "clip": {
                "x": 0,
                "y": 0,
                "width": full_width,
                "height": full_height,
                "scale": 1  # 保持 1:1 原生比例，拒绝模糊缩放
            },
            "captureBeyondViewport": True,
            "fromSurface": True
        }

        result = driver.execute_cdp_cmd("Page.captureScreenshot", clip_params)
        with open(save_path, "wb") as f:
            f.write(base64.b64decode(result['data']))
        return True
    except Exception as e:
        print(f"国泰全景截图失败: {e}")
        return False


