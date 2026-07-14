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


def get_browser_config():
    try:
        with open("browser_config.json", "r", encoding="utf-8") as f:
            cfg = json.load(f)
            return cfg.get("CHROME_PATH", ""), cfg.get("DRIVER_PATH", ""), cfg.get("USER_DATA_DIR", "")
    except Exception:
        return "", "", ""


def run_china_airlines_297_automation(awb_list):
    """
    【中华航空 297 专用组件】瞬间爆开网页 + 突破按钮禁用校验
    """
    if not awb_list: return False, "没有传入任何提单号"

    CHROME_PATH, DRIVER_PATH, USER_DATA_DIR = get_browser_config()
    if not CHROME_PATH or not DRIVER_PATH:
        return False, "系统找不到浏览器核心！请先在主界面配置路径。"

    valid_uris = []

    for awb in awb_list:
        # 华航需要 11 位纯数字 (例如: 29774518426)
        clean_awb = awb.replace("-", "").strip()
        if len(clean_awb) < 11 or not clean_awb.startswith("297"):
            continue

        target_url = f"https://icargowebportal.china-airlines.com/icargoneoportal/app/#/app?mawb={clean_awb}"

        # 烙印预埋并跳转
        js_code = f'<script>window.name="AWB_{awb}";window.location.replace("{target_url}");</script>'
        b64_code = base64.b64encode(js_code.encode('utf-8')).decode('utf-8')
        data_uri = f"data:text/html;base64,{b64_code}"
        valid_uris.append(data_uri)

    if not valid_uris: return False, "单号格式不正确 (需为 297 开头的 11 位纯数字或标准格式)"

    try:
        cmd = [CHROME_PATH, '--remote-debugging-port=9333', f'--user-data-dir={USER_DATA_DIR}',
               '--no-first-run', '--no-default-browser-check'] + valid_uris
        subprocess.Popen(cmd)
    except Exception as e:
        return False, f"Chrome 启动失败: {str(e)}"

    options = Options()
    options.add_experimental_option("debuggerAddress", "127.0.0.1:9333")
    service = Service(executable_path=DRIVER_PATH)

    driver = None
    try:
        time.sleep(4)
        driver = webdriver.Chrome(service=service, options=options)

        for handle in driver.window_handles:
            driver.switch_to.window(handle)
            current_url = driver.current_url

            if "china-airlines.com" in current_url:
                wait = WebDriverWait(driver, 10)
                try:
                    # 获取当前 URL 里的 11 位单号
                    clean_awb = current_url.split("mawb=")[-1][:11]

                    # 1. 精准定位输入框
                    input_field = wait.until(EC.presence_of_element_located((By.ID, "shipmentValue")))

                    # 突破前端校验：先清空，再通过 send_keys 模拟真实键盘敲击，唤醒框架的 v-model 绑定
                    input_field.clear()
                    input_field.send_keys(clean_awb)
                    time.sleep(0.5)

                    # 2. 定位“下一步”按钮并点击
                    btn_xpath = "//button[@data-testid='shipment-search-form-panel__submit-button']"

                    # 确保按钮从 disabled 状态解除并可点击
                    search_btn = wait.until(EC.element_to_be_clickable((By.XPATH, btn_xpath)))

                    try:
                        search_btn.click()
                    except:
                        try:
                            driver.execute_script("arguments[0].click();", search_btn)
                        except:
                            input_field.send_keys(Keys.ENTER)

                    time.sleep(2)
                    # 还原标准带横杠的烙印，方便截图命名
                    formatted_awb = f"297-{clean_awb[3:]}"
                    driver.execute_script(f'window.name="AWB_{formatted_awb}";')
                except Exception:
                    continue

        return True, "中华航空 (297) 已全部自动查询完毕。"
    except Exception as e:
        return False, str(e)
    finally:
        if driver: driver.quit()


def capture_china_airlines_fullpage_cdp(driver, awb_name, save_path):
    """
    【华航专用截图引擎】CDP 协议无损全景截图
    """
    try:
        metrics = driver.execute_cdp_cmd("Page.getLayoutMetrics", {})
        rect = metrics.get('cssContentSize') or metrics.get('contentSize') or metrics.get('layoutViewport')

        full_width = math.ceil(rect['width'])
        full_height = min(math.ceil(rect['height']), 15000)

        clip_params = {
            "clip": {
                "x": 0, "y": 0, "width": full_width, "height": full_height, "scale": 1
            },
            "captureBeyondViewport": True,
            "fromSurface": True
        }

        result = driver.execute_cdp_cmd("Page.captureScreenshot", clip_params)
        with open(save_path, "wb") as f:
            f.write(base64.b64decode(result['data']))
        return True
    except Exception as e:
        print(f"中华航空全景截图失败: {e}")
        return False