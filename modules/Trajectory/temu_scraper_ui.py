import os
import json
import time
import threading
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                             QLabel, QFrame, QTextEdit, QProgressBar, QMessageBox, QWidget, QApplication)
from PyQt6.QtCore import Qt, QObject, pyqtSignal
from PyQt6.QtGui import QFont, QCursor


# =====================================================================
# 🌟 线程安全通讯器 (保护主线程 UI 在 Selenium 疯狂翻页抓取时不卡死)
# =====================================================================
class ScraperUpdater(QObject):
    status_sig = pyqtSignal(str, int)  # 提示文本, 进度值
    finish_sig = pyqtSignal(bool, str)  # 是否成功, 结果数据或报错信息


# =====================================================================
# 🌟 核心抓取逻辑 (完美继承您原有的防缓冲吞字判定机制)
# =====================================================================
def get_browser_config():
    try:
        with open("browser_config.json", "r", encoding="utf-8") as f:
            cfg = json.load(f)
            return cfg.get("CHROME_PATH", ""), cfg.get("DRIVER_PATH", ""), cfg.get("USER_DATA_DIR", "")
    except Exception:
        return "", "", ""


def extract_awb_data(status_callback=None):
    _, DRIVER_PATH, _ = get_browser_config()
    if not DRIVER_PATH:
        return False, "找不到驱动路径！请确保运行目录下有 browser_config.json 文件并配置了 DRIVER_PATH。"

    options = Options()
    options.add_experimental_option("debuggerAddress", "127.0.0.1:9333")
    service = Service(executable_path=DRIVER_PATH)

    driver = None
    try:
        if status_callback: status_callback("正在接管 9333 端口浏览器...", 5)
        driver = webdriver.Chrome(service=service, options=options)
    except Exception as e:
        return False, f"接管失败！请确认已打开带 9333 端口的 Chrome 浏览器。\n报错: {e}"

    try:
        target_handle = None
        for handle in driver.window_handles:
            driver.switch_to.window(handle)
            if "logistics.temu.com/logistics/air-express/awb-list" in driver.current_url:
                target_handle = handle
                break

        if not target_handle:
            return False, "未找到指定的 Temu 空运列表页面，请先在浏览器中打开该页面！"

        wait = WebDriverWait(driver, 15)

        # 每页条数判断
        if status_callback: status_callback("正在检查页面显示数量...", 15)
        try:
            old_body_text = driver.find_element(By.TAG_NAME, "body").text
            dropdown_input = wait.until(EC.presence_of_element_located(
                (By.XPATH,
                 "//input[@data-testid='beast-core-select-htmlInput' and (@value='10' or @value='20' or @value='40')]")
            ))
            current_value = dropdown_input.get_attribute("value")

            if current_value == "40":
                if status_callback: status_callback("✨ 识别到已是每页 40 条，直接跳过切换！", 25)
            else:
                if status_callback: status_callback("正在切换每页显示 40 条...", 20)
                driver.execute_script("arguments[0].click();", dropdown_input)
                time.sleep(1)

                option_40 = wait.until(EC.presence_of_element_located(
                    (By.XPATH, "//li[@role='option']//span[text()='40']")
                ))
                driver.execute_script("arguments[0].click();", option_40)

                time.sleep(2)
                try:
                    WebDriverWait(driver, 30).until_not(
                        EC.presence_of_element_located((By.XPATH,
                                                        "//*[contains(translate(@class, 'LOADING', 'loading'), 'loading') or contains(translate(@class, 'SPIN', 'spin'), 'spin')]"))
                    )
                except:
                    pass

                for _ in range(20):
                    new_text = driver.find_element(By.TAG_NAME, "body").text
                    if new_text != old_body_text and "加载中" not in new_text:
                        break
                    time.sleep(1)
                time.sleep(2)
        except Exception:
            print("💡 切换分页提示: 未发现分页下拉框，继续执行...")

        # 页码判断
        if status_callback: status_callback("正在检查当前所在页码...", 30)
        try:
            prev_btn = driver.find_element(By.XPATH, "//li[@data-testid='beast-core-pagination-prev']")
            prev_class = prev_btn.get_attribute("class") or ""
            prev_disabled = prev_btn.get_attribute("aria-disabled")

            if "disabled" in prev_class.lower() or prev_disabled == "true":
                if status_callback: status_callback("✨ 已在第 1 页，直接开始极速读取！", 35)
            else:
                if status_callback: status_callback("当前不在第 1 页，正在强制退回...", 32)
                old_body_text_p1 = driver.find_element(By.TAG_NAME, "body").text

                page_1_btn = driver.find_element(By.XPATH,
                                                 "//li[contains(@class, 'pagerItem') and normalize-space(text())='1']")
                driver.execute_script("arguments[0].click();", page_1_btn)

                time.sleep(1)
                try:
                    WebDriverWait(driver, 10).until_not(
                        EC.presence_of_element_located((By.XPATH,
                                                        "//*[contains(translate(@class, 'LOADING', 'loading'), 'loading') or contains(translate(@class, 'SPIN', 'spin'), 'spin')]"))
                    )
                except:
                    pass

                for _ in range(20):
                    new_text = driver.find_element(By.TAG_NAME, "body").text
                    if new_text != old_body_text_p1 and "加载中" not in new_text:
                        break
                    time.sleep(0.5)
                time.sleep(1)
                if status_callback: status_callback("✅ 已回到第 1 页，开始提取！", 35)
        except Exception as e:
            print(f"💡 第一页检查提示: 可能是单页数据或无数据，继续执行。({e})")

        # 数据抓取循环
        all_extracted_text = []
        page_num = 1

        while True:
            if status_callback: status_callback(f"正在读取第 {page_num} 页数据...", min(40 + page_num * 5, 90))

            current_page_text = driver.find_element(By.TAG_NAME, "body").text
            all_extracted_text.append(f"========== 第 {page_num} 页 ==========\n{current_page_text}\n")

            try:
                next_btn = driver.find_element(By.XPATH, "//li[@data-testid='beast-core-pagination-next']")
                btn_class = next_btn.get_attribute("class") or ""
                aria_disabled = next_btn.get_attribute("aria-disabled")

                if "disabled" in btn_class.lower() or aria_disabled == "true":
                    if status_callback: status_callback("已到达最后一页，抓取结束。", 95)
                    break

                old_body_text = current_page_text
                driver.execute_script("arguments[0].click();", next_btn)
                page_num += 1

                if status_callback: status_callback(f"正在死等第 {page_num} 页数据缓冲...", min(40 + page_num * 5, 90))
                time.sleep(1.5)

                try:
                    WebDriverWait(driver, 30).until_not(
                        EC.presence_of_element_located((By.XPATH,
                                                        "//*[contains(translate(@class, 'LOADING', 'loading'), 'loading') or contains(translate(@class, 'SPIN', 'spin'), 'spin')]"))
                    )
                except:
                    pass

                for _ in range(30):
                    new_text = driver.find_element(By.TAG_NAME, "body").text
                    if new_text != old_body_text and "加载中" not in new_text and len(new_text) > 50:
                        break
                    time.sleep(1)
                time.sleep(2)

            except Exception as e:
                print(f"翻页异常或到达末页: {e}")
                break

        if status_callback: status_callback("数据提取完毕！", 100)
        return True, "\n\n".join(all_extracted_text)

    except Exception as e:
        return False, f"执行抓取过程中发生意外错误:\n{str(e)}"


# =====================================================================
# 🌟 GUI 操控中心组件
# =====================================================================
def open_temu_scraper(main_app):
    """主程序组件库点击事件绑定的外部调用入口"""
    win = TemuScraperDialog()
    win.show()


class TemuScraperDialog(QDialog):
    def __init__(self):
        super().__init__(None)
        self._keep_alive = self  # 🌟 护盾防垃圾回收秒退

        self.setWindowTitle("Temu 运单数据抓取工具")

        # 🌟 1. 允许自由放大拉伸：由 setFixedSize 改为安全最小尺寸
        self.setMinimumSize(700, 560)
        self.resize(750, 600)

        # 🌟 2. 开启完整的【最大化/还原/最小化/关闭】控制栏
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowMinMaxButtonsHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        self.setStyleSheet("background-color: #f0f2f5;")

        # 初始化线程通信
        self.updater = ScraperUpdater()
        self.updater.status_sig.connect(self._update_status_slot)
        self.updater.finish_sig.connect(self._finish_task_slot)

        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 15, 20, 15)
        main_layout.setSpacing(12)

        # --- 1. 顶部状态与进度条卡片 ---
        status_card = QFrame()
        status_card.setStyleSheet("background-color: white; border: 1px solid #dcdfe6; border-radius: 6px;")
        status_lyt = QVBoxLayout(status_card)
        status_lyt.setContentsMargins(15, 12, 15, 12)
        status_lyt.setSpacing(6)

        self.status_label = QLabel("准备就绪。请先确保浏览器已打开对应页面。")
        self.status_label.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        self.status_label.setStyleSheet("color: #7f8c8d; border: none;")
        status_lyt.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(12)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar { border: 1px solid #e2e8f0; border-radius: 4px; background-color: #f1f5f9; }
            QProgressBar::chunk { background-color: #4CAF50; border-radius: 3px; }
        """)
        self.progress_bar.setValue(0)
        status_lyt.addWidget(self.progress_bar)
        main_layout.addWidget(status_card)

        # --- 2. 中层按钮操控组合 ---
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.start_btn = QPushButton("🚀 开始接管并抓取")
        self.start_btn.setFixedWidth(180)
        self.start_btn.clicked.connect(self.start_scraping)
        self.start_btn.setStyleSheet("""
            QPushButton { background-color: #4CAF50; color: white; font-weight: bold; font-size: 13px; padding: 8px; border-radius: 4px; }
            QPushButton:hover { background-color: #43a047; }
            QPushButton:disabled { background-color: #cbd5e1; color: #94a3b8; }
        """)

        self.copy_btn = QPushButton("📋 复制结果")
        self.copy_btn.clicked.connect(self.copy_to_clipboard)
        self.clear_btn = QPushButton("🗑 清空面板")
        self.clear_btn.clicked.connect(self.clear_text)

        for btn in [self.start_btn, self.copy_btn, self.clear_btn]:
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            if btn != self.start_btn:
                btn.setStyleSheet("""
                    QPushButton { background-color: white; color: #2c3e50; font-size: 13px; padding: 8px 18px; border: 1px solid #cbd5e1; border-radius: 4px; }
                    QPushButton:hover { background-color: #f8f9fa; }
                """)
            btn_layout.addWidget(btn)
        btn_layout.addStretch()
        main_layout.addLayout(btn_layout)

        # --- 3. 底部大文本结果展示箱 ---
        result_box = QWidget()
        res_lyt = QVBoxLayout(result_box)
        res_lyt.setContentsMargins(0, 0, 0, 0)
        res_lyt.setSpacing(5)

        lbl_res = QLabel("抓取结果展示框：")
        lbl_res.setFont(QFont("Microsoft YaHei", 9))
        res_lyt.addWidget(lbl_res)

        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setFont(QFont("Consolas", 10))
        self.result_text.setStyleSheet(
            "background-color: white; border: 1px solid #cbd5e1; border-radius: 4px; padding: 8px;")
        res_lyt.addWidget(self.result_text)
        main_layout.addWidget(result_box, stretch=1)

    def start_scraping(self):
        self.start_btn.setEnabled(False)
        self.start_btn.setText("抓取中...")
        self.result_text.clear()
        self.progress_bar.setValue(0)

        # 交付后台线程执行 Selenium 抓取
        threading.Thread(target=self.run_scraping_task, daemon=True).start()

    def run_scraping_task(self):
        def callback(text, val):
            self.updater.status_sig.emit(text, val)

        success, result_or_error = extract_awb_data(status_callback=callback)
        self.updater.finish_sig.emit(success, result_or_error)

    # =====================================================================
    # 🌟 线程安全槽处理接收区 (完成时强行将窗口拉回最前台并弹窗)
    # =====================================================================
    def _update_status_slot(self, text, progress):
        self.status_label.setText(text)
        if progress >= 100:
            self.status_label.setStyleSheet("color: #27ae60; font-weight: bold;")
        else:
            self.status_label.setStyleSheet("color: #2c3e50; font-weight: bold;")
        self.progress_bar.setValue(progress)

    def _finish_task_slot(self, success, result_or_error):
        self.start_btn.setEnabled(True)
        self.start_btn.setText("🚀 开始接管并抓取")

        # 🌟 核心绝杀：无论抓取时浏览器怎么抢焦点，跑完瞬间将本工具窗口强行拉回屏幕前方并激活！
        self.showNormal()
        self.raise_()
        self.activateWindow()

        if success:
            self.result_text.setPlainText(result_or_error)
            # 自动塞入剪贴板
            QApplication.clipboard().setText(result_or_error.strip())
            QMessageBox.information(self, "执行完毕",
                                    "🎉 数据抓取圆满完成！\n\n✅ 结果已自动为您复制到剪贴板，可直接去粘贴。")
        else:
            self.status_label.setText("抓取失败！")
            self.status_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
            self.progress_bar.setValue(0)
            QMessageBox.critical(self, "执行中断", result_or_error)

    def copy_to_clipboard(self):
        content = self.result_text.toPlainText().strip()
        if content:
            QApplication.clipboard().setText(content)
            QMessageBox.information(self, "提示", "内容已成功复制到系统剪贴板！")
        else:
            QMessageBox.warning(self, "提示", "结果框是空的，没有内容可复制。")

    def clear_text(self):
        self.result_text.clear()
        self._update_status_slot("面板已清空。", 0)

    def closeEvent(self, event):
        self._keep_alive = None
        event.accept()