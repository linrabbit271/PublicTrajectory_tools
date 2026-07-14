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
    """实时读取用户在 UI 界面配置的路径"""
    try:
        with open("browser_config.json", "r", encoding="utf-8") as f:
            cfg = json.load(f)
            return cfg.get("CHROME_PATH", ""), cfg.get("DRIVER_PATH", ""), cfg.get("USER_DATA_DIR", "")
    except Exception:
        return "", "", ""


def run_airzeta_994_automation(awb_list):
    """
    【AirZeta 994 专用组件】瞬间爆开网页 + 自动点击兜底 + 烙印预埋
    """
    if not awb_list: return False, "没有传入任何提单号"

    CHROME_PATH, DRIVER_PATH, USER_DATA_DIR = get_browser_config()
    if not CHROME_PATH or not DRIVER_PATH:
        return False, "系统找不到浏览器核心！请先在主界面配置路径。"

    valid_uris = []

    # 第一波：瞬间构建 IPC 弹药包
    for awb in awb_list:
        clean_awb = awb.replace("-", "").strip()
        # 提取后 8 位
        if len(clean_awb) >= 8:
            suffix = clean_awb[-8:]
        else:
            continue

        # 994 网站支持 URL 传参，我们直接构造最终 URL
        target_url = f"https://portal.airzetacargo.com/tracking/viewTraceAirWaybill.do?mawb=994-{suffix}"

        # 烙印预埋：利用 Base64 瞬间打上 window.name，并跳转到带参数的真实地址
        js_code = f'<script>window.name="AWB_994-{suffix}";window.location.replace("{target_url}");</script>'
        b64_code = base64.b64encode(js_code.encode('utf-8')).decode('utf-8')
        data_uri = f"data:text/html;base64,{b64_code}"
        valid_uris.append(data_uri)

    if not valid_uris: return False, "单号格式不正确 (需包含8位尾数)"

    # 第二波：瞬间爆破开页
    try:
        cmd = [CHROME_PATH, '--remote-debugging-port=9333', f'--user-data-dir={USER_DATA_DIR}',
               '--no-first-run', '--no-default-browser-check'] + valid_uris
        subprocess.Popen(cmd)
    except Exception as e:
        return False, f"Chrome 启动失败: {str(e)}"

    # 第三波：派出幽灵探针执行兜底搜索 (防止 URL 传参后不自动查询)
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

            if "airzetacargo.com" in current_url:
                wait = WebDriverWait(driver, 10)
                try:
                    # 1. 精准定位输入框 (根据你提供的 name="awbNumber")
                    input_field = wait.until(
                        EC.element_to_be_clickable((By.XPATH, "//input[@name='awbNumber']")))

                    # 提取当前网页 URL 中的 8 位单号
                    suffix = current_url.split("994-")[-1][:8]

                    # 重新填入确保无误
                    input_field.clear()
                    input_field.send_keys(suffix)
                    time.sleep(0.5)

                    # 2. 精准定位搜索按钮 (根据你提供的 id="btn_search")
                    search_btn = driver.find_element(By.ID, "btn_search")

                    # 三路提交保险
                    try:
                        search_btn.click()
                    except:
                        try:
                            driver.execute_script("arguments[0].click();", search_btn)
                        except:
                            input_field.send_keys(Keys.ENTER)

                    # 3. 再次加固烙印
                    time.sleep(2)
                    driver.execute_script(f'window.name="AWB_994-{suffix}";')
                except Exception as inner_e:
                    # 容错：如果网页本身已经通过 URL 查出了结果，找不到框也不影响
                    continue

        return True, "AirZeta (994) 已全部自动查询完毕。"
    except Exception as e:
        return False, str(e)
    finally:
        if driver: driver.quit()


def capture_airzeta_fullpage_cdp(driver, awb_name, save_path):
    """
    【AirZeta 专用截图引擎】CDP 协议无损全景截图 + 终极防挤压护盾
    """
    # =========================================================
    # ☢️ 核弹级护盾 1：全局 CSS 镇压 (使用 !important 废掉前端 JS 的修改权限)
    # =========================================================
    nuclear_css_js = """
    var style = document.createElement('style');
    style.type = 'text/css';
    style.innerHTML = `
        /* 强制外层所有响应式容器完全展开 */
        .col-sm-12, .dataTables_wrapper, .table-responsive {
            width: 100% !important;
            max-width: none !important;
            overflow: visible !important;
        }
        /* 强制表格本身及所有单元格绝不换行 */
        table.dataTable, table.dataTable th, table.dataTable td {
            width: auto !important;
            white-space: nowrap !important;
            word-break: keep-all !important;
        }
    `;
    document.head.appendChild(style);
    """
    try:
        driver.execute_script(nuclear_css_js)
    except Exception as e:
        print(f"CSS 镇压注入失败: {e}")

    # =========================================================
    # 📸 开始执行 CDP 协议无损截图
    # =========================================================
    try:
        # 先获取当前网页真实的物理高度
        metrics = driver.execute_cdp_cmd("Page.getLayoutMetrics", {})
        rect = metrics.get('cssContentSize') or metrics.get('contentSize') or metrics.get('layoutViewport')
        full_height = min(math.ceil(rect['height']), 15000)

        # =========================================================
        # ☢️ 核弹级护盾 2：强伪装分辨率 (欺骗响应式框架)
        # 强行把视口宽度锁死在 1920 (标准宽屏)，防止 CDP 截图时触发窄屏布局！
        # =========================================================
        driver.execute_cdp_cmd("Emulation.setDeviceMetricsOverride", {
            "width": 1920,
            "height": full_height,
            "deviceScaleFactor": 1,
            "mobile": False
        })

        # 给前端框架 0.5 秒钟，让它在 1920 的“大屏幕”下重新把表格舒展开来
        time.sleep(0.5)

        # 正式按下快门
        clip_params = {
            "clip": {
                "x": 0,
                "y": 0,
                "width": 1920,  # 宽度与上方锁定一致
                "height": full_height,
                "scale": 1
            },
            "captureBeyondViewport": True,
            "fromSurface": True
        }

        result = driver.execute_cdp_cmd("Page.captureScreenshot", clip_params)

        # 截图完成后，撤销分辨率伪装，恢复浏览器原本状态
        driver.execute_cdp_cmd("Emulation.clearDeviceMetricsOverride", {})

        with open(save_path, "wb") as f:
            f.write(base64.b64decode(result['data']))
        return True

    except Exception as e:
        print(f"AirZeta 全景截图失败: {e}")
        # 万一报错，也记得把分辨率恢复，以免影响后续操作
        try:
            driver.execute_cdp_cmd("Emulation.clearDeviceMetricsOverride", {})
        except:
            pass
        return False