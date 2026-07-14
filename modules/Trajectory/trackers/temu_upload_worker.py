import os
import time
import json
import subprocess
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def get_browser_config():
    try:
        with open("browser_config.json", "r", encoding="utf-8") as f:
            cfg = json.load(f)
            return cfg.get("CHROME_PATH", ""), cfg.get("DRIVER_PATH", ""), cfg.get("USER_DATA_DIR", "")
    except Exception:
        return "", "", ""


def launch_9333_browser():
    CHROME_PATH, _, USER_DATA_DIR = get_browser_config()
    if not CHROME_PATH or not USER_DATA_DIR:
        return False, "系统找不到 Chrome 路径或缓存文件夹！请先在主界面点击【⚙️ 浏览器环境配置】。"

    try:
        cmd = [
            CHROME_PATH,
            '--remote-debugging-port=9333',
            f'--user-data-dir={USER_DATA_DIR}',
            '--no-first-run',
            '--no-default-browser-check'
        ]
        subprocess.Popen(cmd)
        return True, "✅ 已成功唤醒专属浏览器！\n请在新弹出的浏览器中打开 Temu 轨迹页面并保持登录状态。"
    except Exception as e:
        return False, f"唤醒浏览器失败: {str(e)}"


def batch_upload_to_temu(file_paths, region="EU", status_callback=None):
    if not file_paths:
        return False, "没有传入任何文件！"

    _, DRIVER_PATH, _ = get_browser_config()
    if not DRIVER_PATH:
        return False, "找不到驱动路径，请先在主界面配置环境。"

    options = Options()
    options.add_experimental_option("debuggerAddress", "127.0.0.1:9333")
    service = Service(executable_path=DRIVER_PATH)

    driver = None
    try:
        if status_callback: status_callback("正在接管 9333 端口浏览器...", 5, "#f39c12")
        driver = webdriver.Chrome(service=service, options=options)
    except Exception as e:
        return False, f"接管浏览器失败，请确保您已打开带 9333 端口的浏览器。\n报错: {e}"

    try:
        target_handle = None
        for handle in driver.window_handles:
            driver.switch_to.window(handle)
            if "temu.com" in driver.current_url and "tracking-manage" in driver.current_url:
                target_handle = handle
                break

        if not target_handle:
            region_name = "欧区 (logistics-eu)" if region == "EU" else "美区 (logistics)"
            return False, f"未找到 Temu {region_name} 的轨迹管理页面！\n请确保您已经在浏览器中打开了对应的后台。"

        if status_callback: status_callback("已锁定 Temu 页面，准备开始批量上传...", 15, "#3498db")

        success_count = 0
        total_files = len(file_paths)
        wait = WebDriverWait(driver, 15)

        for idx, file_path in enumerate(file_paths):
            if not os.path.exists(file_path):
                continue

            progress = 15 + int((idx / total_files) * 80)
            file_name = os.path.basename(file_path)
            if status_callback: status_callback(f"正在准备 ({idx + 1}/{total_files}): {file_name}", progress, "#2980b9")

            try:
                # 定位并发送文件
                file_input = wait.until(EC.presence_of_element_located(
                    (By.XPATH, "//input[@data-testid='beast-core-upload-input' and @type='file']")))
                file_input.send_keys(file_path)
            except Exception as e:
                return False, f"找不到文件上传入口，网页结构可能已改变。\n报错: {str(e)}"

            time.sleep(1)

            try:
                # =====================================================================
                # 🌟 核心修复：使用 JS 强制点击确认导入，无视一切网页弹窗的物理遮挡！
                # 注意这里把 expected_conditions 改成了 presence_of_element_located
                # 因为 element_to_be_clickable 遇到遮挡会判定为不可点击，而 presence 只要元素在底层存在就行
                # =====================================================================
                confirm_btn = wait.until(
                    EC.presence_of_element_located((By.XPATH, "//button[.//span[contains(text(), '确认导入')]]")))
                driver.execute_script("arguments[0].click();", confirm_btn)
            except Exception as e:
                return False, f"文件 {file_name} 解析后，未能找到'确认导入'按钮。\n报错: {str(e)}"

            if status_callback: status_callback(f"文件 {file_name} 正在传输至服务器...", progress + 2, "#e67e22")

            # 超长动态轮询机制 (容忍最高 10 分钟的极慢转圈)
            max_wait_seconds = 600  # 最高容忍等待 600 秒 (10分钟)
            poll_interval = 3  # 每 3 秒偷偷检查一次
            elapsed_time = 0
            upload_success = False

            while elapsed_time < max_wait_seconds:
                try:
                    btn = driver.find_element(By.XPATH, "//button[.//span[contains(text(), '+ 按包裹号导入轨迹')]]")
                    is_disabled_attr = btn.get_attribute("disabled")
                    classes = btn.get_attribute("class") or ""

                    # 如果按钮不再灰显禁用，说明转圈结束了！
                    if not is_disabled_attr and "BTN_disabled" not in classes:
                        upload_success = True
                        break
                except:
                    pass  # 元素如果在弹窗遮挡或刷新时找不到，不报错，继续等

                time.sleep(poll_interval)
                elapsed_time += poll_interval

                # 每隔约 15 秒，向 UI 汇报一次等待时间，防止用户以为程序死机了
                if elapsed_time % 15 == 0:
                    if status_callback:
                        status_callback(f"Temu 服务器处理较慢，已等待 {elapsed_time} 秒，请耐心...", progress + 2,
                                        "#e67e22")

            if not upload_success:
                return False, f"文件 {file_name} 上传严重超时 (超过10分钟)！\n可能是 Temu 服务器卡死，请刷新网页后重试。"

            # 转圈结束后，给予一点安全缓冲，再继续下一个文件
            time.sleep(2)
            success_count += 1

        if status_callback: status_callback("所有文件上传完毕！", 100, "#27ae60")
        return True, f"✅ 批量上传任务圆满完成！\n共成功导入 {success_count} 个文件。"

    except Exception as e:
        return False, f"执行上传过程中发生意外错误:\n{str(e)}"
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass