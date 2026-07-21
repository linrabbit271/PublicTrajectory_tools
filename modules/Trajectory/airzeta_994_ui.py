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

# 导入底层极速引擎
from modules.Trajectory.trackers.airzeta_994_tracker import run_airzeta_994_automation, capture_airzeta_fullpage_cdp, \
    get_browser_config


# =====================================================================
# 🌟 智能拦截输入框：自动清洗粘贴文本，剔除前后空格与隐式空白行
# =====================================================================
class SmartPasteTextEdit(QTextEdit):
    def insertFromMimeData(self, source):
        if source.hasText():
            raw_text = source.text()
            # 按行切分，剔除每行的前后空白，并过滤掉彻底为空的行
            lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
            # 重新用换行符连接纯净的单号
            clean_text = "\n".join(lines)
            self.insertPlainText(clean_text)
        else:
            super().insertFromMimeData(source)


class AirzetaUpdater(QObject):
    search_finish_sig = pyqtSignal(bool, str)
    screenshot_finish_sig = pyqtSignal(bool, str)


def open_airzeta_994(*args, **kwargs):
    win = Airzeta994Dialog(None)
    win.show()


class Airzeta994Dialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(None)
        self._keep_alive = self

        self.setWindowTitle("AirZeta 994 提取器")
        self.setFixedSize(680, 740)

        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        self.setStyleSheet("background-color: #ecf0f1;")

        self.updater = AirzetaUpdater()
        self.updater.search_finish_sig.connect(self._search_finish_slot)
        self.updater.screenshot_finish_sig.connect(self._screenshot_finish_slot)

        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        header = QLabel(" ✈️ AirZeta (994) 极速提取与截图")
        header.setFont(QFont("Microsoft YaHei", 15, QFont.Weight.Bold))
        header.setStyleSheet("background-color: #2980b9; color: white; padding: 15px 20px; border: none;")
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

        # --- 4. 提单号输入框 (🌟 关键修改：换用 SmartPasteTextEdit) ---
        awb_card = QFrame()
        awb_card.setStyleSheet("background-color: white; border: 1px solid #bdc3c7; border-radius: 4px;")
        awb_lyt = QVBoxLayout(awb_card)
        awb_lyt.setContentsMargins(15, 10, 15, 12)

        lbl_awb = QLabel("4. 目标提单号 (每行一个)")
        lbl_awb.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        lbl_awb.setStyleSheet("color: #2c3e50; border: none;")
        awb_lyt.addWidget(lbl_awb)

        # 🌟 替换为智能过滤输入框
        self.text_input = SmartPasteTextEdit()
        self.text_input.setFont(QFont("Consolas", 11))
        self.text_input.setStyleSheet("background-color: #f8f9fa; border: 1px solid #ced4da; padding: 5px;")
        awb_lyt.addWidget(self.text_input)
        work_layout.addWidget(awb_card, stretch=1)

        # --- 5. 底部按钮栏 ---
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
    # 🌟 强力外层 JS 强制对齐填单技术 (绕过底层引擎缺陷)
    # =====================================================================
    def do_search(self):
        raw_text = self.text_input.toPlainText().strip()
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]

        # 严格过滤出 8 位数字尾数单号
        cleaned_awbs = []
        for line in lines:
            if "-" in line:
                parts = line.split("-")
                cleaned_awbs.append(parts[1].strip() if len(parts) > 1 else line[-8:])
            else:
                cleaned_awbs.append(line[-8:])

        if not cleaned_awbs:
            QMessageBox.warning(self, "提示", "请输入提单号！")
            return

        self.btn_open.setEnabled(False)
        self.btn_open.setText(" ⏳ 强效填单中... ")

        def task(awbs):
            # 1. 依然原封不动调用你的底层引擎把所有网页打开
            run_airzeta_994_automation(awbs)

            # 2. 网页一开完，外层立刻拿着 100% 纯净的 awbs 列表去接管并执行降维打击强填
            try:
                time.sleep(1.5)  # 给网页结构重绘留 1.5 秒物理缓冲
                _, DRIVER_PATH, _ = get_browser_config()
                options = Options()
                options.add_experimental_option("debuggerAddress", "127.0.0.1:9333")
                service = Service(executable_path=DRIVER_PATH)
                force_driver = webdriver.Chrome(service=service, options=options)

                handles = force_driver.window_handles
                for h in handles:
                    force_driver.switch_to.window(h)
                    url = force_driver.current_url

                    if "airzetacargo.com" in url:
                        # 智能从当前标签页的 URL 里面反向捞出它对应的单号尾数
                        target_num = None
                        for single_awb in awbs:
                            if single_awb in url:
                                target_num = single_awb
                                break

                        # 保底逻辑：如果 URL 里没捞到，直接取第一个作为测试
                        if not target_num and awbs:
                            target_num = awbs[0]

                        if target_num:
                            # 🌟 绝杀：直接用原生 JavaScript 锁死【第一个】输入框，强行灌入 value，并触发点击！
                            fill_js = f"""
                                const inputs = document.querySelectorAll("input[name='awbNumber']");
                                if (inputs && inputs.length > 0) {{
                                    const firstInput = inputs[0];
                                    firstInput.value = "{target_num}";
                                    firstInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                    firstInput.dispatchEvent(new Event('change', {{ bubbles: true }}));

                                    const searchBtn = document.querySelector("#btn_search");
                                    if (searchBtn) searchBtn.click();
                                }}
                            """
                            force_driver.execute_script(fill_js)

                self.updater.search_finish_sig.emit(True, "成功")
            except Exception as e:
                self.updater.search_finish_sig.emit(False, str(e))

        threading.Thread(target=task, args=(cleaned_awbs,), daemon=True).start()

    def _search_finish_slot(self, success, msg):
        self.btn_open.setEnabled(True)
        self.btn_open.setText(" 🚀 批量开页查询 ")
        if success:
            QMessageBox.information(self, "完成", "所有页面已打开，单号已通过外层强行填入并查询！\n核对后可执行截图。")
        else:
            QMessageBox.critical(self, "错误", f"外层补件失败: {msg}")

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

                    if "airzetacargo.com" in current_url:
                        time.sleep(1)
                        awb_filename = f"未知单号_{idx + 1}"
                        try:
                            win_name = driver.execute_script("return window.name;")
                            if win_name and str(win_name).startswith("AWB_"):
                                awb_filename = win_name.replace("AWB_", "").strip()
                        except:
                            pass

                        temp_shot = os.path.join(os.environ["TEMP"], f"temp_airzeta_{idx}.png")

                        if capture_airzeta_fullpage_cdp(driver, awb_filename, temp_shot):
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
        event.accept()