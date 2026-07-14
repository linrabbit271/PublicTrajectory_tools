import subprocess
import time
import base64
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# 🌟 绝杀 PyInstaller 漏包 Bug 的隐式导入！强行逼迫打包工具将其塞入 exe
import selenium.webdriver.chrome.webdriver
import selenium.webdriver.common.service
import selenium.webdriver.common.options

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


def open_hactl_tracking(awb_list):
    """
    【HACTL 原生 JS 光速闪击版 - 反后台冻结终极版】
    彻底分离填表与点击动作，通过 Python 层的同步等待，
    完美避开 Chrome 对后台标签页 JavaScript 计时器的限速与冻结机制。
    """
    if not awb_list:
        return False, "没有传入任何提单号"

    CHROME_PATH, DRIVER_PATH, USER_DATA_DIR = get_browser_config()

    if not CHROME_PATH or not USER_DATA_DIR:
        return False, "系统找不到浏览器核心！请先在右侧点击【⚙️ 浏览器环境配置】设置你的专属路径。"

    target_uris = []
    valid_awbs = []
    base_home_url = "https://cargo.hactl.com/site/en-US/overview.html?mode=ct"

    for awb in awb_list:
        clean_awb = awb.replace("-", "").strip()
        if len(clean_awb) < 11:
            continue
        valid_awbs.append(awb)
        prefix = clean_awb[:3]
        suffix = clean_awb[3:11]

        real_url = f"{base_home_url}#{prefix}-{suffix}"

        js_code = f'<script>window.name="AWB_{awb}";window.location.href="{real_url}";</script>'
        b64_code = base64.b64encode(js_code.encode('utf-8')).decode('utf-8')
        data_uri = f"data:text/html;base64,{b64_code}"

        target_uris.append(data_uri)

    if not target_uris:
        return False, "传入的提单号无效"

    chunk_size = 10
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
    except Exception as e:
        return False, f"底层 Chrome 唤醒失败: {str(e)}"

    options = Options()
    options.add_experimental_option("debuggerAddress", "127.0.0.1:9333")
    service = Service(executable_path=DRIVER_PATH)

    driver = None
    try:
        time.sleep(3.5)
        driver = webdriver.Chrome(service=service, options=options)
    except Exception as e:
        return False, f"后台探针接管失败，网页已打开但无法自动输入。\n报错: {str(e)}"

    success_count = 0
    last_hactl_handle = None

    try:
        all_handles = driver.window_handles

        for handle in all_handles:
            try:
                driver.switch_to.window(handle)

                # 🌟 核心破局 1：唤醒冻结。标签页刚切过来时可能还在被浏览器限速，强制给它 0.4 秒恢复全速运行。
                time.sleep(0.4)

                current_url = driver.current_url

                if "hactl.com" in current_url:
                    awb = None

                    win_name = driver.execute_script("return window.name;")
                    if win_name and str(win_name).startswith("AWB_"):
                        awb = win_name.replace("AWB_", "")

                    if not awb and "#" in current_url:
                        hash_val = current_url.split("#")[-1].replace("-", "")
                        for original_awb in valid_awbs:
                            if original_awb.replace("-", "") == hash_val:
                                awb = original_awb
                                break

                    if awb:
                        clean_awb = awb.replace("-", "").strip()
                        prefix = clean_awb[:3]
                        suffix = clean_awb[3:11]

                        wait = WebDriverWait(driver, 15)
                        wait.until(lambda d: d.execute_script('return document.readyState') == 'complete')
                        wait.until(EC.visibility_of_element_located((By.ID, "txtAirlineCode")))
                        wait.until(
                            EC.element_to_be_clickable((By.XPATH, "//span[normalize-space(text())='TRACK NOW']")))

                        # 🌟 核心破局 2：只管填入数据，彻底废弃 JS 里的 setTimeout
                        js_inject = """
                        var prefix = arguments[0];
                        var suffix = arguments[1];
                        var awb = arguments[2];

                        window.name = "AWB_" + awb;

                        var elPrefix = document.getElementById('txtAirlineCode');
                        var elSuffix = document.getElementById('txtAirwayBill');

                        function triggerVirtualDOMInput(element, value) {
                            element.focus(); // 聚焦，增强框架感知
                            var lastValue = element.value;
                            element.value = value;
                            var event = new Event("input", { bubbles: true });
                            event.simulated = true;
                            var tracker = element._valueTracker;
                            if (tracker) { tracker.setValue(lastValue); }
                            element.dispatchEvent(event);

                            // 双重保险：触发 change 事件，逼迫 Vue/React 更新内部状态
                            var changeEvent = new Event("change", { bubbles: true });
                            element.dispatchEvent(changeEvent);
                            element.blur();
                        }

                        if (elPrefix && elSuffix) {
                            triggerVirtualDOMInput(elPrefix, prefix);
                            triggerVirtualDOMInput(elSuffix, suffix);
                            return true;
                        }
                        return false;
                        """

                        is_injected = driver.execute_script(js_inject, prefix, suffix, awb)

                        if is_injected:
                            # 🌟 核心破局 3：由 Python 控制节奏！此时当前网页是焦点状态，绝对不会被浏览器冻结
                            # 给前端框架 0.3 秒的时间消化填入的数据
                            time.sleep(0.3)

                            # 🌟 核心破局 4：分步触发点击
                            js_click = """
                            var btn = document.evaluate("//span[normalize-space(text())='TRACK NOW']", document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                            if(btn) { btn.click(); return true; }
                            return false;
                            """
                            is_clicked = driver.execute_script(js_click)

                            if is_clicked:
                                success_count += 1
                                last_hactl_handle = handle

            except Exception as e_dom:
                print(f"❌ Hactl 网页加载失败或卡死: {e_dom}")
                continue

        if last_hactl_handle:
            try:
                driver.switch_to.window(last_hactl_handle)
            except:
                pass

        return True, f"✅ 网页全开！彻底绕过休眠机制，稳定处理了 {success_count} 个查询。"

    except Exception as e:
        return False, f"后台自动输入报错: {str(e)}"

    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass