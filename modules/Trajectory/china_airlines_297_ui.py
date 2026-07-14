import os
import time
import shutil
import threading
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                             QLabel, QFrame, QTextEdit, QLineEdit, QCheckBox,
                             QGridLayout, QFileDialog, QMessageBox, QWidget, QApplication)
from PyQt6.QtCore import Qt, QObject, pyqtSignal
from PyQt6.QtGui import QFont, QCursor

# 导入底层驱动
from modules.Trajectory.trackers.china_airlines_297_tracker import run_china_airlines_297_automation, \
    capture_china_airlines_fullpage_cdp, get_browser_config


# =====================================================================
# 🌟 线程安全通讯器 (完全对齐原版的跨线程逻辑通知，替代原生 win.after)
# =====================================================================
class ChinaAirlinesUpdater(QObject):
    search_finish_sig = pyqtSignal(bool, str)
    screenshot_finish_sig = pyqtSignal(bool, str)


# =====================================================================
# 🌟 统一调用入口 (🌟 使用 *args 万能接收，彻底丢弃参数纠缠)
# =====================================================================
def open_china_airlines_297(*args, **kwargs):
    """
    中华航空 (297) 独立组件窗口 - 焦点完全隔离版
    """
    win = ChinaAirlines297Dialog(None)
    win.show()


class ChinaAirlines297Dialog(QDialog):
    def __init__(self, parent=None):
        # 🌟 核心破局：parent 强制置为 None，将 PyQt6 从系统的焦点争夺中完美剔除
        super().__init__(None)
        self._keep_alive = self  # 独立顶级窗口生存护盾

        self.setWindowTitle("中华航空 297 提取器")
        self.setFixedSize(680, 740)

        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        self.setStyleSheet("background-color: #ecf0f1;")

        self.updater = ChinaAirlinesUpdater()
        self.updater.search_finish_sig.connect(self._search_finish_slot)
        self.updater.screenshot_finish_sig.connect(self._screenshot_finish_slot)

        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- 顶栏 Header (华航企业色紫色主题) ---
        header = QLabel(" ✈️ 中华航空 (297) 极速提取与截图")
        header.setFont(QFont("Microsoft YaHei", 15, QFont.Weight.Bold))
        header.setStyleSheet("background-color: #8e44ad; color: white; padding: 15px 20px; border: none;")
        main_layout.addWidget(header)

        workspace = QWidget()
        work_layout = QVBoxLayout(workspace)
        work_layout.setContentsMargins(20, 15, 20, 15)
        work_layout.setSpacing(10)

        def create_card(title):
            card = QFrame()
            card.setStyleSheet("background-color: white; border: 1px solid #bdc3c7; border-radius: 4px;")
            card_lyt = QVBoxLayout(card)
            card_lyt.setContentsMargins(15, 10, 15, 12)
            card_lyt.setSpacing(6)
            lbl = QLabel(title)
            lbl.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
            lbl.setStyleSheet("color: #2c3e50; border: none;")
            card_lyt.addWidget(lbl)
            return card, card_lyt

        # --- 1. 保存路径 ---
        path_card, path_lyt = create_card("1. 截图保存根目录")
        path_row = QHBoxLayout()
        self.entry_path = QLineEdit()
        self.entry_path.setFont(QFont("Consolas", 11))
        self.entry_path.setStyleSheet("background-color: #f8f9fa; border: 1px solid #ced4da; padding: 5px;")
        path_row.addWidget(self.entry_path)

        btn_browse = QPushButton("📂 浏览")
        btn_browse.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_browse.setFont(QFont("Microsoft YaHei", 9))
        btn_browse.setStyleSheet(
            "QPushButton { background-color: #bdc3c7; color: #2c3e50; padding: 5px 15px; border-radius: 3px; }")
        btn_browse.clicked.connect(self.select_path)
        path_row.addWidget(btn_browse)
        path_lyt.addLayout(path_row)
        work_layout.addWidget(path_card)

        # --- 2. 文件夹名称 ---
        name_card, name_lyt = create_card("2. 第一层文件夹名称")
        self.entry_folder_name = QLineEdit()
        self.entry_folder_name.setFont(QFont("Microsoft YaHei", 11))
        self.entry_folder_name.setStyleSheet("background-color: #f8f9fa; border: 1px solid #ced4da; padding: 5px;")
        name_lyt.addWidget(self.entry_folder_name)
        work_layout.addWidget(name_card)

        # --- 3. 状态选择 ---
        status_card, status_lyt = create_card("3. 第二层文件夹状态 (支持多选)")
        statuses = ["2-入航司仓", "3-已起飞", "4-到达中转机场", "5-中转机场起飞", "6-到达目的地机场"]
        self.status_boxes = {}
        grid_layout = QGridLayout()
        grid_layout.setSpacing(10)
        for idx, status in enumerate(statuses):
            cb = QCheckBox(status)
            cb.setFont(QFont("Microsoft YaHei", 10))
            cb.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            cb.setStyleSheet("QCheckBox { color: #2c3e50; border: none; }")
            self.status_boxes[status] = cb
            grid_layout.addWidget(cb, idx // 3, idx % 3)
        status_lyt.addLayout(grid_layout)
        work_layout.addWidget(status_card)

        # --- 4. 提单号输入框 ---
        awb_card = QFrame()
        awb_card.setStyleSheet("background-color: white; border: 1px solid #bdc3c7; border-radius: 4px;")
        awb_lyt = QVBoxLayout(awb_card)
        awb_lyt.setContentsMargins(15, 10, 15, 12)

        lbl_awb = QLabel("4. 目标提单号 (每行一个)")
        lbl_awb.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        lbl_awb.setStyleSheet("color: #2c3e50; border: none;")
        awb_lyt.addWidget(lbl_awb)

        self.text_input = QTextEdit()
        self.text_input.setFont(QFont("Consolas", 11))
        self.text_input.setStyleSheet("background-color: #f8f9fa; border: 1px solid #ced4da; padding: 5px;")
        awb_lyt.addWidget(self.text_input)
        work_layout.addWidget(awb_card, stretch=1)

        # --- 5. 底部按钮栏 (钉死在最下方) ---
        btn_frame = QWidget()
        btn_lyt = QHBoxLayout(btn_frame)
        btn_lyt.setContentsMargins(0, 5, 0, 5)
        btn_lyt.setSpacing(15)

        self.btn_open = QPushButton(" 🚀 批量开页查询 ")
        self.btn_shot = QPushButton(" 📸 一键全景截图 ")

        self.btn_open.setStyleSheet(
            "QPushButton { background-color: #e67e22; color: white; border-radius: 4px; border: none; }")
        self.btn_shot.setStyleSheet(
            "QPushButton { background-color: #00665f; color: white; border-radius: 4px; border: none; }")

        for btn in [self.btn_open, self.btn_shot]:
            btn.setFixedHeight(45)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
            btn_lyt.addWidget(btn)

        self.btn_open.clicked.connect(self.do_search)
        self.btn_shot.clicked.connect(self.do_screenshot)
        work_layout.addWidget(btn_frame)

        main_layout.addWidget(workspace, stretch=1)

    def select_path(self):
        path_selected = QFileDialog.getExistingDirectory(self, "选择航司截图根目录")
        if path_selected:
            self.entry_path.setText(path_selected)

    # =====================================================================
    # 🌟 100% 纯净对齐原生数据流 (绝不改动任何核心自动化与收尾逻辑)
    # =====================================================================
    def do_search(self):
        raw_text = self.text_input.toPlainText().strip()

        # 🌟 核心安全盾：使用 splitlines() 彻底洗净 PyQt6 文本框里的隐藏回车符 \r
        awb_list = [line.strip() for line in raw_text.splitlines() if line.strip()]

        if not awb_list:
            QMessageBox.warning(self, "提示", "请输入提单号！")
            return

        self.btn_open.setEnabled(False)
        self.btn_open.setText(" ⏳ 执行中... ")

        def task():
            success, msg = run_china_airlines_297_automation(awb_list)
            self.updater.search_finish_sig.emit(success, msg)

        threading.Thread(target=task, daemon=True).start()

    def _search_finish_slot(self, success, msg):
        self.btn_open.setEnabled(True)
        self.btn_open.setText(" 🚀 批量开页查询 ")
        if success:
            QMessageBox.information(self, "完成", "所有页面已打开并查询完毕！\n核对后可执行截图。")
        else:
            QMessageBox.critical(self, "错误", msg)

    def do_screenshot(self):
        base_dir = self.entry_path.text().strip()
        first_layer = self.entry_folder_name.text().strip()
        selected_statuses = [status for status, cb in self.status_boxes.items() if cb.isChecked()]

        if not base_dir or not first_layer or not selected_statuses:
            QMessageBox.warning(self, "提示", "请确保路径、文件夹名已填，且状态已勾选！")
            return

        self.btn_shot.setEnabled(False)
        self.btn_shot.setText(" ⏳ 截图中... ")

        def task():
            _, DRIVER_PATH, _ = get_browser_config()
            options = Options()
            options.add_experimental_option("debuggerAddress", "127.0.0.1:9333")
            service = Service(executable_path=DRIVER_PATH)
            driver = None

            try:
                driver = webdriver.Chrome(service=service, options=options)
                all_handles = driver.window_handles
                success_count = 0

                for idx, handle in enumerate(all_handles):
                    driver.switch_to.window(handle)
                    current_url = driver.current_url

                    if "china-airlines.com" in current_url:
                        time.sleep(1)
                        awb_filename = f"未知单号_{idx + 1}"
                        try:
                            win_name = driver.execute_script("return window.name;")
                            if win_name and str(win_name).startswith("AWB_"):
                                awb_filename = win_name.replace("AWB_", "").strip()
                        except:
                            pass

                        temp_shot = os.path.join(os.environ["TEMP"], f"temp_cal_{idx}.png")

                        if capture_china_airlines_fullpage_cdp(driver, awb_filename, temp_shot):
                            for status in selected_statuses:
                                target_folder = os.path.join(base_dir, first_layer, status)
                                os.makedirs(target_folder, exist_ok=True)
                                shutil.copy(temp_shot, os.path.join(target_folder, f"{awb_filename}.png"))
                            success_count += 1
                            if os.path.exists(temp_shot): os.remove(temp_shot)

                self.updater.screenshot_finish_sig.emit(True, f"截图分发完毕！共截取 {success_count} 张。")
            except Exception as e:
                self.updater.screenshot_finish_sig.emit(False, str(e))
            finally:
                if driver:
                    try:
                        # 严格复刻：100% 完整保留你原版代码中的原生退出行为
                        driver.quit()
                    except:
                        pass

        threading.Thread(target=task, daemon=True).start()

    def _screenshot_finish_slot(self, success, msg):
        self.btn_shot.setEnabled(True)
        self.btn_shot.setText(" 📸 一键全景截图 ")
        if success:
            QMessageBox.information(self, "完成", msg)
        else:
            QMessageBox.critical(self, "错误", f"截图失败: {msg}")

    def closeEvent(self, event):
        self._keep_alive = None
        event.accept()