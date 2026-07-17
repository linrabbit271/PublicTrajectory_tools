import os
import json
import threading

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QLabel, QFrame, QTextEdit, QProgressBar,
                             QMessageBox, QDialog, QLineEdit, QCheckBox,
                             QGridLayout, QFileDialog, QApplication, QSizePolicy)
from PyQt6.QtCore import Qt, QObject, pyqtSignal
from PyQt6.QtGui import QFont, QCursor

# --- 导入外部追踪模块 ---
from modules.Trajectory.trackers.mawb_tracker import open_mawb_tracking
from modules.Trajectory.trackers.parcels_tracker import open_parcels_tracking
from modules.Trajectory.trackers.hactl_tracker import open_hactl_tracking
from modules.Trajectory.trackers.aat_tracker import open_aat_tracking
from modules.Trajectory.trackers.screenshot_worker import batch_fullpage_screenshot

from PyQt6.QtWidgets import QTextEdit
from PyQt6.QtGui import QClipboard

class SmartPasteTextEdit(QTextEdit):
    """ 自定义输入框：强行拦截剪贴板，剥离尾部多余的换行与空格 """
    def insertFromMimeData(self, source):
        if source.hasText():
            # 1. 拿到剪贴板里的原始文本
            raw_text = source.text()
            # 2. 核心绝杀：strip() 瞬间剔除文本开头和末尾所有看不见的空格、换行、制表符
            clean_text = raw_text.strip()
            # 3. 将干净的文本塞入输入框，此时光标会死死咬在最后一个数字后面
            self.insertPlainText(clean_text)
        else:
            super().insertFromMimeData(source)
# =====================================================================
# 🌟 线程安全通讯器
# =====================================================================
class UIUpdater(QObject):
    status_sig = pyqtSignal(str, int, str)  # text, progress, color
    info_sig = pyqtSignal(str, str)  # title, msg
    error_sig = pyqtSignal(str, str)  # title, msg
    btn_state_sig = pyqtSignal(bool)  # 按钮启用状态


def init_node_time_panel(main_app, parent_widget):
    """
    外部主程序调用的入口函数
    """
    # 🌟 核心修复：将实例死死绑定到 parent_widget 的属性上！
    # 彻底杜绝 Python 垃圾回收机制（GC）在后台将其隐式销毁导致的按钮失效 Bug！
    parent_widget.panel_instance = TrajectoryCheckerApp(main_app, parent_widget)


class TrajectoryCheckerApp:
    def __init__(self, main_app, parent_widget):
        self.main_app = main_app
        self.parent = parent_widget
        self.config_file = "browser_config.json"

        # 初始化线程安全的 UI 更新器
        self.updater = UIUpdater()
        self.updater.status_sig.connect(self._update_ui_status_slot)
        self.updater.info_sig.connect(self._show_info_slot)
        self.updater.error_sig.connect(self._show_error_slot)
        self.updater.btn_state_sig.connect(self._set_btn_state_slot)

        self.setup_ui()

    def setup_ui(self):
        # 页面主垂直布局
        layout = QVBoxLayout(self.parent)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ================= 顶部横幅 =================
        header = QLabel(" ⏰ 查时间 (提单轨迹批量查询与截图)")
        header.setStyleSheet("""
            background-color: #1abc9c; 
            color: white; 
            font-size: 16px; 
            font-weight: bold; 
            padding: 15px 20px;
            border-bottom: 2px solid #16a085;
        """)
        layout.addWidget(header)

        # ================= 主体工作区 =================
        main_area = QWidget()
        main_area.setStyleSheet("background-color: #ecf0f1;")
        main_layout = QHBoxLayout(main_area)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)
        layout.addWidget(main_area, stretch=1)

        # --- 左侧输入区 (比例 5) ---
        left_frame = QWidget()
        left_layout = QVBoxLayout(left_frame)
        left_layout.setContentsMargins(0, 0, 0, 0)

        lbl_input = QLabel("目标提单号 (每行一个):")
        lbl_input.setStyleSheet("font-weight: bold; color: #34495e; font-size: 14px;")
        left_layout.addWidget(lbl_input)

        # 修改后：换成我们手搓的智能过滤框
        self.input_area = SmartPasteTextEdit()
        self.input_area.setStyleSheet("""
            QTextEdit {
                font-family: Consolas, monospace;
                font-size: 14px;
                border: 1px solid #bdc3c7;
                border-radius: 6px;
                background-color: white;
                padding: 10px;
            }
        """)
        left_layout.addWidget(self.input_area, stretch=1)
        main_layout.addWidget(left_frame, stretch=5)

        # --- 右侧操作区 (比例 3) ---
        right_frame = QWidget()
        right_layout = QVBoxLayout(right_frame)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        # 提示按钮
        btn_tips = QPushButton("💡 首次使用必看（新手提示）")
        btn_tips.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_tips.setStyleSheet("""
            QPushButton { background-color: #f1c40f; color: #2c3e50; font-weight: bold; font-size: 13px; padding: 8px; border-radius: 6px; border-bottom: 3px solid #f39c12; }
            QPushButton:hover { background-color: #f39c12; }
            QPushButton:pressed { border-bottom: 1px solid #f39c12; padding-top: 10px; }
        """)
        btn_tips.clicked.connect(self.show_tips)
        right_layout.addWidget(btn_tips)

        lbl_step1 = QLabel("第一步：批量开网页")
        lbl_step1.setStyleSheet("font-weight: bold; color: #7f8c8d; font-size: 13px; margin-top: 5px;")
        right_layout.addWidget(lbl_step1)

        # 4 个查询按钮网格 (2x2)
        grid_trackers = QGridLayout()
        grid_trackers.setSpacing(8)

        btn_mawb = self.create_grid_btn("查 MAWB", "#2980b9", "#2471a3", self.open_mawb)
        btn_hactl = self.create_grid_btn("查 Hactl", "#27ae60", "#229954", self.open_hactl)
        btn_aat = self.create_grid_btn("查 AAT", "#d35400", "#ba4a00", self.open_aat)
        btn_parcels = self.create_grid_btn("查 Parcels", "#8e44ad", "#7d3c98", self.open_parcels)

        grid_trackers.addWidget(btn_mawb, 0, 0)
        grid_trackers.addWidget(btn_hactl, 0, 1)
        grid_trackers.addWidget(btn_aat, 1, 0)
        grid_trackers.addWidget(btn_parcels, 1, 1)
        right_layout.addLayout(grid_trackers)

        # 分割线
        line1 = QFrame()
        line1.setFrameShape(QFrame.Shape.HLine)
        line1.setStyleSheet("background-color: #bdc3c7;")
        right_layout.addWidget(line1)

        lbl_step2 = QLabel("第二步：数据收网与智能归档")
        lbl_step2.setStyleSheet("font-weight: bold; color: #7f8c8d; font-size: 13px;")
        right_layout.addWidget(lbl_step2)

        # 提单信息卡片
        card_subfolder = QFrame()
        card_subfolder.setStyleSheet("background-color: white; border: 1px solid #dcdfe6; border-radius: 6px;")
        lyt_subfolder = QVBoxLayout(card_subfolder)
        lyt_subfolder.setContentsMargins(12, 10, 12, 12)
        lbl_sub = QLabel("📂 提单信息 (共享表A列名称):")
        lbl_sub.setStyleSheet("font-weight: bold; color: #2c3e50; font-size: 12px; border: none;")
        self.sub_folder_entry = QLineEdit()
        self.sub_folder_entry.setStyleSheet(
            "background-color: #f8f9fa; border: 1px solid #ced4da; padding: 6px; border-radius: 4px;")
        lyt_subfolder.addWidget(lbl_sub)
        lyt_subfolder.addWidget(self.sub_folder_entry)
        right_layout.addWidget(card_subfolder)

        # =====================================================================
        # 🌟 空间拓展：状态多选卡片 (大幅扩容占比，增加复选框间距与尺寸)
        # =====================================================================
        card_status = QFrame()
        card_status.setStyleSheet("background-color: white; border: 1px solid #dcdfe6; border-radius: 6px;")
        lyt_status = QVBoxLayout(card_status)
        lyt_status.setContentsMargins(15, 15, 15, 15)  # 加大四周留白
        lyt_status.setSpacing(12)

        lbl_status = QLabel("☑️ 选择轨迹状态 (支持多选, 自动分发):")
        lbl_status.setStyleSheet("font-weight: bold; color: #2c3e50; font-size: 13px; border: none;")
        lyt_status.addWidget(lbl_status)

        grid_status = QGridLayout()
        grid_status.setSpacing(16)  # 极大增加复选框横纵间距，撑开网格空间
        grid_status.setAlignment(Qt.AlignmentFlag.AlignTop)  # 顶部对齐，干净工整

        self.statuses = ["1-揽收", "2-入航司仓", "3-已起飞", "4-到达中转机场", "5-中转机场起飞", "6-到达目的地机场"]
        self.status_boxes = {}
        for idx, status in enumerate(self.statuses):
            cb = QCheckBox(status)
            # 强化美化：增大字号、增大内部勾选框尺寸 (width/height 16px)
            cb.setStyleSheet("""
                QCheckBox { 
                    font-size: 13px; 
                    color: #34495e; 
                    border: none; 
                    padding: 4px; 
                } 
                QCheckBox::indicator { 
                    width: 17px; 
                    height: 17px; 
                }
            """)
            cb.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            self.status_boxes[status] = cb
            grid_status.addWidget(cb, idx // 2, idx % 2)

        lyt_status.addLayout(grid_status)

        # 🌟 通过设定 stretch=1，强行命令该卡片吞掉右侧剩余的垂直空白空间，使其大范围占比显现！
        right_layout.addWidget(card_status, stretch=1)

        # 截图按钮
        self.btn_screenshot = QPushButton("📸 一键提取全长截图")
        self.btn_screenshot.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_screenshot.setStyleSheet("""
            QPushButton { background-color: #e67e22; color: white; font-weight: bold; font-size: 14px; padding: 10px; border-radius: 6px; border-bottom: 3px solid #d35400; }
            QPushButton:hover { background-color: #d35400; }
            QPushButton:pressed { border-bottom: 1px solid #d35400; padding-top: 12px; }
            QPushButton:disabled { background-color: #bdc3c7; border-bottom: 3px solid #95a5a6; color: #7f8c8d; }
        """)
        self.btn_screenshot.clicked.connect(self.take_screenshots)
        right_layout.addWidget(self.btn_screenshot)

        # 清空与配置按钮
        lyt_actions = QHBoxLayout()
        lyt_actions.setSpacing(10)
        btn_clear = QPushButton("清空输入")
        btn_clear.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_clear.setStyleSheet("""
            QPushButton { background-color: #bdc3c7; color: #2c3e50; font-weight: bold; padding: 8px; border-radius: 6px; border-bottom: 3px solid #95a5a6; }
            QPushButton:hover { background-color: #aeb6bf; }
            QPushButton:pressed { border-bottom: 1px solid #95a5a6; padding-top: 10px; }
        """)
        btn_clear.clicked.connect(self.clear_input)

        btn_settings = QPushButton("⚙️ 环境配置")
        btn_settings.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_settings.setStyleSheet("""
            QPushButton { background-color: #34495e; color: white; font-weight: bold; padding: 8px; border-radius: 6px; border-bottom: 3px solid #2c3e50; }
            QPushButton:hover { background-color: #2c3e50; }
            QPushButton:pressed { border-bottom: 1px solid #2c3e50; padding-top: 10px; }
        """)
        btn_settings.clicked.connect(self.open_settings_window)

        lyt_actions.addWidget(btn_clear)
        lyt_actions.addWidget(btn_settings)
        right_layout.addLayout(lyt_actions)

        # 分割线
        line2 = QFrame()
        line2.setFrameShape(QFrame.Shape.HLine)
        line2.setStyleSheet("background-color: #bdc3c7;")
        right_layout.addWidget(line2)

        # 状态指示区
        lbl_sys = QLabel("系统执行状态")
        lbl_sys.setStyleSheet("font-weight: bold; color: #7f8c8d; font-size: 13px;")
        right_layout.addWidget(lbl_sys)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(12)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar { border: 1px solid #bdc3c7; border-radius: 5px; background-color: #e9ecef; }
            QProgressBar::chunk { background-color: #1abc9c; border-radius: 4px; }
        """)
        right_layout.addWidget(self.progress_bar)

        self.log_badge = QLabel("等候指令")
        self.log_badge.setStyleSheet("""
            background-color: #e9ecef; color: #495057; font-weight: bold; 
            padding: 8px; border-radius: 6px; border: 1px solid #ced4da; font-size: 12px;
        """)
        right_layout.addWidget(self.log_badge)

        # 🌟 移除原有的 addStretch()，把控制权完全交由状态多选卡片去拉伸
        main_layout.addWidget(right_frame, stretch=3)

    def create_grid_btn(self, text, bg_color, border_color, connect_func):
        btn = QPushButton(text)
        btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn.setStyleSheet(f"""
            QPushButton {{ background-color: {bg_color}; color: white; font-weight: bold; padding: 8px; border-radius: 6px; border-bottom: 3px solid {border_color}; }}
            QPushButton:hover {{ background-color: {border_color}; }}
            QPushButton:pressed {{ border-bottom: 1px solid {border_color}; padding-top: 10px; }}
        """)
        btn.clicked.connect(connect_func)
        return btn

    # ================= 辅助窗口 =================
    def show_tips(self):
        win = QDialog(self.parent)
        win.setWindowTitle("使用帮助 / 新手提示")
        win.setFixedSize(460, 220)
        win.setStyleSheet("background-color: #f8f9fa;")

        layout = QVBoxLayout(win)
        card = QFrame()
        card.setStyleSheet("background-color: white; border: 1px solid #dcdfe6; border-radius: 8px;")
        card_lyt = QVBoxLayout(card)

        tip_text = (
            "欢迎使用轨迹工具箱！以下是要点说明：\n\n"
            "1.请先配置【环境配置】，输入单号点击需要查找的网站即可。\n"
            "2.AAT网站不支持软件的控制，不支持单号批量查询，可单点呼出网站界面，请搭配组件库内的【尾数提取】手动输入。\n"
            "3.关于更多的查时间组件都在组件库里可随意使用。\n"
            "4.更新按钮一般用不上，而且有点显示bug，不过应该是能用的。"
        )
        lbl = QLabel(tip_text)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("font-size: 13px; color: #2c3e50; border: none; line-height: 1.5;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        card_lyt.addWidget(lbl)
        layout.addWidget(card)
        win.exec()

    def open_settings_window(self):
        win = QDialog(self.parent)
        win.setWindowTitle("环境配置 (只需设置一次)")
        win.setFixedSize(580, 320)
        win.setStyleSheet("background-color: #ecf0f1;")

        layout = QVBoxLayout(win)
        layout.setContentsMargins(20, 20, 20, 20)

        cfg = {"CHROME_PATH": "", "DRIVER_PATH": "", "USER_DATA_DIR": ""}
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    cfg.update(json.load(f))
            except:
                pass

        entries = {}

        def add_row(label_text, key, is_dir=False):
            lbl = QLabel(label_text)
            lbl.setStyleSheet("font-weight: bold; font-size: 12px; color: #34495e; margin-top: 10px;")
            layout.addWidget(lbl)

            row_lyt = QHBoxLayout()
            entry = QLineEdit(cfg[key])
            entry.setStyleSheet(
                "background-color: white; padding: 6px; border: 1px solid #bdc3c7; border-radius: 4px; font-family: Consolas;")
            entries[key] = entry
            row_lyt.addWidget(entry, stretch=1)

            btn_browse = QPushButton("浏览...")
            btn_browse.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn_browse.setStyleSheet(
                "background-color: #bdc3c7; color: #2c3e50; padding: 6px 15px; border-radius: 4px; font-weight: bold;")

            def browse_action():
                if is_dir:
                    path = QFileDialog.getExistingDirectory(win, "选择文件夹")
                else:
                    path, _ = QFileDialog.getOpenFileName(win, "选择程序文件", "",
                                                          "Executable Files (*.exe);;All Files (*)")
                if path:
                    entry.setText(path)

            btn_browse.clicked.connect(browse_action)
            row_lyt.addWidget(btn_browse)
            layout.addLayout(row_lyt)

        add_row("1. Chrome 浏览器路径 (chrome.exe):", "CHROME_PATH")
        add_row("2. Selenium 驱动路径 (chromedriver.exe):", "DRIVER_PATH")
        add_row("3. 独立缓存数据夹 (Data 文件夹):", "USER_DATA_DIR", is_dir=True)

        layout.addStretch()
        btn_save = QPushButton("💾 保存并应用配置")
        btn_save.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_save.setStyleSheet("""
            QPushButton { background-color: #27ae60; color: white; font-size: 14px; font-weight: bold; padding: 10px; border-radius: 6px; border-bottom: 3px solid #1e8449;}
            QPushButton:hover { background-color: #229954; }
            QPushButton:pressed { border-bottom: 1px solid #1e8449; padding-top: 12px; }
        """)

        def save_config():
            new_cfg = {k: v.text().strip() for k, v in entries.items()}
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(new_cfg, f, ensure_ascii=False, indent=4)
            QMessageBox.information(win, "成功", "浏览器底层配置已保存！")
            win.accept()

        btn_save.clicked.connect(save_config)
        layout.addWidget(btn_save)

        win.exec()

    # ================= 核心业务槽函数与子线程逻辑 =================

    def _update_ui_status_slot(self, text, progress_value, color):
        self.log_badge.setText(text)
        self.log_badge.setStyleSheet(f"""
            background-color: #e9ecef; color: {color}; font-weight: bold; 
            padding: 8px; border-radius: 6px; border: 1px solid #ced4da; font-size: 12px;
        """)
        self.progress_bar.setValue(progress_value)

    def _show_info_slot(self, title, msg):
        QMessageBox.information(self.parent, title, msg)

    def _show_error_slot(self, title, msg):
        QMessageBox.critical(self.parent, title, msg)

    def _set_btn_state_slot(self, is_enabled):
        self.btn_screenshot.setEnabled(is_enabled)

    def get_awb_list_or_warn(self):
        raw_text = self.input_area.toPlainText().strip()
        if not raw_text:
            QMessageBox.warning(self.parent, "提示", "请先在左侧输入需要查询的提单号！")
            return None
        return [line.strip() for line in raw_text.split('\n') if line.strip()]

    def open_mawb(self):
        awb_list = self.get_awb_list_or_warn()
        if not awb_list: return
        self._update_ui_status_slot(f"正在极速打开 {len(awb_list)} 个 MAWB 网页...", 50, "#2980b9")

        def run_task():
            success, msg = open_mawb_tracking(awb_list)
            if success:
                self.updater.status_sig.emit("MAWB 网页已开，等待数据加载...", 100, "#27ae60")
            else:
                self.updater.status_sig.emit("配置缺失或启动失败", 0, "#dc3545")
                self.updater.error_sig.emit("报错", msg)

        threading.Thread(target=run_task, daemon=True).start()

    def open_hactl(self):
        awb_list = self.get_awb_list_or_warn()
        if not awb_list: return
        self._update_ui_status_slot(f"正在接管底层驱动，自动化填报 {len(awb_list)} 个 Hactl 查询...", 50, "#27ae60")

        def run_task():
            success, msg = open_hactl_tracking(awb_list)
            if success:
                self.updater.status_sig.emit("Hactl 自动化输入完毕，等待出结果...", 100, "#27ae60")
            else:
                self.updater.status_sig.emit("配置缺失或启动失败", 0, "#dc3545")
                self.updater.error_sig.emit("报错", msg)

        threading.Thread(target=run_task, daemon=True).start()

    def open_aat(self):
        self._update_ui_status_slot("正在为你极速拉起 AAT 官网...", 50, "#d35400")

        def run_task():
            success, msg = open_aat_tracking()
            if success:
                self.updater.status_sig.emit("AAT 已打开，请手工核对", 100, "#27ae60")
            else:
                self.updater.status_sig.emit("配置缺失或启动失败", 0, "#dc3545")
                self.updater.error_sig.emit("报错", msg)

        threading.Thread(target=run_task, daemon=True).start()

    def open_parcels(self):
        awb_list = self.get_awb_list_or_warn()
        if not awb_list: return
        self._update_ui_status_slot(f"正在极速打开 {len(awb_list)} 个 ParcelsApp 网页...", 50, "#8e44ad")

        def run_task():
            success, msg = open_parcels_tracking(awb_list)
            if success:
                self.updater.status_sig.emit("ParcelsApp 网页已开，等待数据加载...", 100, "#27ae60")
            else:
                self.updater.status_sig.emit("配置缺失或启动失败", 0, "#dc3545")
                self.updater.error_sig.emit("报错", msg)

        threading.Thread(target=run_task, daemon=True).start()

    def take_screenshots(self):
        raw_text = self.input_area.toPlainText().strip()
        awb_list = [line.strip() for line in raw_text.split('\n') if line.strip()]

        custom_sub_folder = self.sub_folder_entry.text().strip()
        selected_statuses = [status for status, cb in self.status_boxes.items() if cb.isChecked()]

        self.btn_screenshot.setEnabled(False)
        self._update_ui_status_slot("正在初始化截图底层组件...", 5, "#e67e22")

        def run_screenshot():
            def callback(msg, val):
                self.updater.status_sig.emit(msg, val, "#e67e22")

            success, msg = batch_fullpage_screenshot(
                status_callback=callback,
                awb_list=awb_list,
                sub_folder=custom_sub_folder,
                selected_statuses=selected_statuses
            )

            if success:
                self.updater.status_sig.emit("截图全部成功！", 100, "#27ae60")
                self.updater.info_sig.emit("截图完毕", msg)
            else:
                self.updater.status_sig.emit("配置缺失或截图异常", 0, "#dc3545")
                self.updater.error_sig.emit("截图报错", msg)

            self.updater.btn_state_sig.emit(True)

        threading.Thread(target=run_screenshot, daemon=True).start()

    def clear_input(self):
        self.input_area.clear()
        self.sub_folder_entry.clear()
        for cb in self.status_boxes.values():
            cb.setChecked(False)
        self._update_ui_status_slot("等候指令", 0, "#495057")