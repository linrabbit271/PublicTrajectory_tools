import os
import re
import threading
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QLabel, QFrame, QListWidget, QRadioButton,
                             QButtonGroup, QProgressBar, QMessageBox, QApplication, QMenu)
from PyQt6.QtCore import Qt, QObject, pyqtSignal, QPoint
from PyQt6.QtGui import QCursor, QAction

# 导入底层引擎与资料分割器
from modules.Trajectory.trackers.temu_upload_worker import batch_upload_to_temu, launch_9333_browser
from modules.Trajectory.data_splitter_ui import open_data_splitter


# =====================================================================
# 🌟 线程安全通讯器 (保护主线程 UI 在疯狂上传时不卡死闪退)
# =====================================================================
class UploadUpdater(QObject):
    status_sig = pyqtSignal(str, int, str)  # 状态文本, 进度值, 颜色代码


# =====================================================================
# 🌟 原生支持拖拽的现代数据队列列表
# =====================================================================
class DropListWidget(QListWidget):
    def __init__(self, parent_panel):
        super().__init__()
        self.parent_panel = parent_panel
        self.setAcceptDrops(True)  # 开启原生拖放
        self.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)  # 支持批量选中

        self.setStyleSheet("""
            QListWidget {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                font-family: "Consolas", "Microsoft YaHei";
                font-size: 13px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 6px 10px;
                border-bottom: 1px solid #f1f3f5;
            }
            QListWidget::item:hover {
                background-color: #e9ecef;
                color: #212529;
            }
            QListWidget::item:selected {
                background-color: #3498db;
                color: white;
            }
        """)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        file_paths = [url.toLocalFile() for url in event.mimeData().urls()]
        self.parent_panel.handle_drop_files(file_paths)


# =====================================================================
# 🌟 主面板控制中心
# =====================================================================
def init_node_upload_panel(main_app, parent_widget):
    parent_widget.panel_instance = NodeUploadApp(main_app, parent_widget)


class NodeUploadApp:
    def __init__(self, main_app, parent_widget):
        self.main_app = main_app
        self.parent = parent_widget
        self.file_paths = []

        # 初始化安全通讯信号
        self.updater = UploadUpdater()
        self.updater.status_sig.connect(self._update_status_slot)

        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self.parent)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. 顶部紫色横幅
        header = QLabel(" 📤 节点三：Temu 轨迹批量上传")
        header.setStyleSheet("""
            background-color: #9b59b6; 
            color: white; 
            font-size: 16px; 
            font-weight: bold; 
            padding: 15px 20px;
            border-bottom: 2px solid #8e44ad;
        """)
        main_layout.addWidget(header)

        # 2. 核心大容器 (左右分流)
        workspace = QWidget()
        workspace.setStyleSheet("background-color: #ecf0f1;")
        work_layout = QHBoxLayout(workspace)
        work_layout.setContentsMargins(25, 20, 25, 20)
        work_layout.setSpacing(20)
        main_layout.addWidget(workspace, stretch=1)

        # ================= 🟢 左侧：挂载与队列区 =================
        left_layout = QVBoxLayout()
        left_layout.setSpacing(15)

        # 拖拽挂载卡片
        drop_card = QFrame()
        drop_card.setStyleSheet("background-color: white; border: 1px solid #ced4da; border-radius: 6px;")
        drop_lyt = QVBoxLayout(drop_card)
        drop_lyt.setContentsMargins(15, 12, 15, 15)
        drop_lyt.setSpacing(8)

        lbl_drop_title = QLabel("1. 挂载待上传文件")
        lbl_drop_title.setStyleSheet("font-weight: bold; color: #2c3e50; font-size: 13px; border: none;")
        drop_lyt.addWidget(lbl_drop_title)

        # 伪托付提示区 (DropTableWidget 会全屏覆盖事件)
        self.drop_area_ui = DropListWidget(self)

        # 👇 ------ 修改此处：删掉 setPlaceholderText，改为正确的 addItem 默认文字提示 ------ 👇
        self.drop_area_ui.addItem("📁 将 Excel/CSV 文件拖拽至此处 (新文件会自动覆盖)")


        # 允许弹出右键菜单
        # 👇 ------ 修改此处：去掉中间的 ContextMenuPolicy，直接连到后缀 ------ 👇
        self.drop_area_ui.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.drop_area_ui.customContextMenuRequested.connect(self.show_context_menu)
        drop_lyt.addWidget(self.drop_area_ui, stretch=1)

        left_layout.addWidget(drop_card, stretch=1)
        work_layout.addLayout(left_layout, stretch=1)

        # ================= 🔴 右侧：控制与操纵台 =================
        right_frame = QFrame()
        right_frame.setFixedWidth(310)
        right_lyt = QVBoxLayout(right_frame)
        right_lyt.setContentsMargins(0, 0, 0, 0)
        right_lyt.setSpacing(12)

        # 新手必看按钮 (金黄色立体)
        btn_tips = QPushButton("💡 首次使用必看（新手提示）")
        btn_tips.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_tips.setStyleSheet("""
            QPushButton { background-color: #f1c40f; color: #2c3e50; font-weight: bold; font-size: 13px; padding: 10px; border-radius: 5px; border-bottom: 3px solid #f39c12; }
            QPushButton:hover { background-color: #f39c12; color: white; }
            QPushButton:pressed { border-bottom: 1px solid #f39c12; padding-top: 12px; }
        """)
        btn_tips.clicked.connect(self.show_tips)
        right_lyt.addWidget(btn_tips)

        # 核心操控卡片
        action_card = QFrame()
        action_card.setStyleSheet("background-color: white; border: 1px solid #ced4da; border-radius: 6px;")
        action_lyt = QVBoxLayout(action_card)
        action_lyt.setContentsMargins(15, 15, 15, 15)
        action_lyt.setSpacing(12)

        lbl_act_title = QLabel("2. 执行操作")
        lbl_act_title.setStyleSheet("font-weight: bold; color: #2c3e50; font-size: 13px; border: none;")
        action_lyt.addWidget(lbl_act_title)

        # 站点单选矩阵
        region_frame = QWidget()
        region_frame.setStyleSheet("border: none;")
        region_lyt = QHBoxLayout(region_frame)
        region_lyt.setContentsMargins(5, 0, 5, 0)

        lbl_site = QLabel("🌍 目标站点:")
        lbl_site.setStyleSheet("font-weight: bold; color: #7f8c8d; font-size: 12px;")
        region_lyt.addWidget(lbl_site)

        self.radio_group = QButtonGroup(self.parent)
        self.radio_eu = QRadioButton("🇪🇺 欧区")
        self.radio_eu.setChecked(True)
        self.radio_eu.setStyleSheet("font-weight: bold; color: #2c3e50; font-size: 12px;")
        self.radio_us = QRadioButton("🇺🇸 美区")
        self.radio_us.setStyleSheet("font-weight: bold; color: #2c3e50; font-size: 12px;")

        self.radio_group.addButton(self.radio_eu, 0)
        self.radio_group.addButton(self.radio_us, 1)
        region_lyt.addWidget(self.radio_eu)
        region_lyt.addWidget(self.radio_us)
        action_lyt.addWidget(region_frame)

        lbl_warn = QLabel("⚠️ 提示：执行前请先启动浏览器并登录后台。")
        lbl_warn.setStyleSheet("color: #e74c3c; font-size: 11px; font-weight: bold; border: none;")
        action_lyt.addWidget(lbl_warn)

        # 操作按钮组合
        self.btn_browser = self.create_action_btn("🌐 启动浏览器", "#3498db", "#2980b9", self.open_9333_browser)
        self.btn_upload = self.create_action_btn("🚀 批量上传", "#8e44ad", "#7d3c98", self.start_upload)
        action_lyt.addWidget(self.btn_browser)
        action_lyt.addWidget(self.btn_upload)

        # 底层复制与清空双拼
        twin_lyt = QHBoxLayout()
        twin_lyt.setSpacing(8)
        self.btn_copy_all = self.create_action_btn("📋 复制单号", "#16a085", "#117a65", self.copy_all)
        self.btn_clear = self.create_action_btn("🗑️ 清空", "#bdc3c7", "#95a5a6", self.clear_files, is_dark_text=True)
        twin_lyt.addWidget(self.btn_copy_all)
        twin_lyt.addWidget(self.btn_clear)
        action_lyt.addLayout(twin_lyt)

        right_lyt.addWidget(action_card)

        # 执行状态卡片
        status_card = QFrame()
        status_card.setStyleSheet("background-color: white; border: 1px solid #ced4da; border-radius: 6px;")
        status_lyt = QVBoxLayout(status_card)
        status_lyt.setContentsMargins(15, 12, 15, 15)
        status_lyt.setSpacing(8)

        lbl_status_title = QLabel("系统执行状态")
        lbl_status_title.setStyleSheet("font-weight: bold; color: #7f8c8d; font-size: 11px; border: none;")
        status_lyt.addWidget(lbl_status_title)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(12)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar { border: 1px solid #e5e7eb; border-radius: 4px; background-color: #f3f4f6; }
            QProgressBar::chunk { background-color: #9b59b6; border-radius: 3px; }
        """)
        status_lyt.addWidget(self.progress_bar)

        self.log_badge = QLabel("等待挂载文件...")
        self.log_badge.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self.log_badge.setStyleSheet("""
            QLabel {
                background-color: #f3f4f6;
                color: #495057;
                font-size: 12px;
                font-weight: bold;
                padding: 6px 10px;
                border-radius: 4px;
                border: none;
            }
        """)
        status_lyt.addWidget(self.log_badge)
        right_lyt.addWidget(status_card)

        # 分割器按钮 (黄色高危兜底)
        btn_splitter = QPushButton("🐜 资料分割器(上传失败时中断可用)")
        btn_splitter.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_splitter.setStyleSheet("""
            QPushButton { background-color: #f1c40f; color: #2c3e50; font-weight: bold; font-size: 13px; padding: 12px; border-radius: 5px; border-bottom: 3px solid #f39c12; }
            QPushButton:hover { background-color: #e6b800; }
            QPushButton:pressed { border-bottom: 1px solid #f39c12; padding-top: 14px; }
        """)
        btn_splitter.clicked.connect(lambda: open_data_splitter(self.parent))
        right_lyt.addWidget(btn_splitter)

        right_lyt.addStretch()
        work_layout.addWidget(right_frame)

    def create_action_btn(self, text, bg, hover, cmd, is_dark_text=False):
        btn = QPushButton(text)
        btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        text_color = "#2c3e50" if is_dark_text else "white"
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg}; color: {text_color}; font-weight: bold; font-size: 13px; padding: 10px; border-radius: 5px; border: none; border-bottom: 3px solid {hover};
            }}
            QPushButton:hover {{ background-color: {hover}; color: white; }}
            QPushButton:pressed {{ border-bottom: 1px solid {hover}; padding-top: 12px; }}
            QPushButton:disabled {{ background-color: #cbd5e1; color: #94a3b8; border-bottom: 3px solid #94a3b8; }}
        """)
        if cmd: btn.clicked.connect(cmd)
        return btn

    # =====================================================================
    # 🌟 右键菜单与智能提单号提取机制
    # =====================================================================
    def extract_awb(self, filename):
        match = re.search(r'\d{3}-\d{8}', filename)
        return match.group(0) if match else os.path.splitext(filename)[0]

    def show_context_menu(self, pos: QPoint):
        if self.drop_area_ui.count() == 0: return

        menu = QMenu(self.drop_area_ui)
        menu.setStyleSheet(
            "QMenu { background-color: white; border: 1px solid #ced4da; font-family: 'Microsoft YaHei'; font-size: 12px; } QMenu::item:selected { background-color: #3498db; color: white; }")

        act_copy_sel = QAction("✂️ 智能复制选中项的单号", menu)
        act_copy_sel.triggered.connect(self.copy_selected)

        act_copy_cursor = QAction("⬇️ 智能复制至鼠标处的所有单号", menu)
        act_copy_cursor.triggered.connect(lambda: self.copy_to_cursor(pos))

        menu.addAction(act_copy_sel)
        menu.addAction(act_copy_cursor)
        menu.exec(self.drop_area_ui.mapToGlobal(pos))

    def copy_selected(self):
        selected_items = self.drop_area_ui.selectedItems()
        if selected_items:
            items = [self.extract_awb(item.text()) for item in selected_items]
            QApplication.clipboard().setText('\n'.join(items))
            self.updater.status_sig.emit(f"✅ 已复制 {len(items)} 个提单号", 100, "#27ae60")

    def copy_to_cursor(self, pos):
        item_under_mouse = self.drop_area_ui.itemAt(pos)
        if item_under_mouse:
            target_row = self.drop_area_ui.row(item_under_mouse)
            items = [self.extract_awb(self.drop_area_ui.item(i).text()) for i in range(target_row + 1)]
            QApplication.clipboard().setText('\n'.join(items))
            self.updater.status_sig.emit(f"✅ 已复制前 {len(items)} 个提单号", 100, "#27ae60")

    def copy_all(self):
        if self.drop_area_ui.count() > 0:
            items = [self.extract_awb(self.drop_area_ui.item(i).text()) for i in range(self.drop_area_ui.count())]
            QApplication.clipboard().setText('\n'.join(items))
            self.updater.status_sig.emit(f"✅ 已复制全部 {len(items)} 个提单号", 100, "#3498db")
        else:
            QMessageBox.warning(self.parent, "提示", "队列为空，没有可复制的提单号！")

    # =====================================================================
    # 🌟 原生异步拖放处理与基础命令
    # =====================================================================
    def handle_drop_files(self, file_paths):
        self.file_paths.clear()
        self.drop_area_ui.clear()

        for path in file_paths:
            if path.lower().endswith((".xls", ".xlsx", ".csv")) and path not in self.file_paths:
                self.file_paths.append(path)
                self.drop_area_ui.addItem(os.path.basename(path))

        self.updater.status_sig.emit(f"已挂载 {len(self.file_paths)} 个文件准备上传", 0, "#2980b9")

    def clear_files(self):
        self.file_paths.clear()
        self.drop_area_ui.clear()
        self.updater.status_sig.emit("等待挂载文件...", 0, "#495057")

    def show_tips(self):
        msg = (
            "欢迎使用轨迹工具箱！以下是重要说明：\n\n"
            "1. 请先配置好【查时间】节点里的【环境配置】。\n\n"
            "2. 【启动浏览器】后请登录并手动点击跳转到上传界面。\n\n"
            "3. 使用时请务必确认当前选中的目标站点是欧区还是美区。\n\n"
            "4. 如果上传中途遇到网络或后台错误导致中止，请点击下方的【资料分割器】，系统会帮你快速整理、分离出未完成的文件继续上传。"
        )
        QMessageBox.information(self.parent, "使用帮助 / 新手提示", msg)

    # =====================================================================
    # 🌟 异步多线程执行器 (修复版：绝不在子线程弹窗，彻底解决卡死假死)
    # =====================================================================
    def open_9333_browser(self):
        self.updater.status_sig.emit("正在底层唤醒浏览器...", 20, "#3498db")

        def run_task():
            success, msg = launch_9333_browser()
            if success:
                self.updater.status_sig.emit("浏览器已成功启动", 100, "#27ae60")
                # 🌟 核心修复：通过主线程通信器或直接发出通知，绝不在当前子线程里弹窗
                self.updater.status_sig.emit(f"成功: {msg}", 100, "#27ae60")
            else:
                self.updater.status_sig.emit("唤醒浏览器失败", 0, "#e74c3c")
                # 🌟 核心修复：直接把错误反馈写在系统状态栏，不要直接在这里 QMessageBox.critical 阻断线程！
                self.updater.status_sig.emit(f"❌ 唤醒失败: {msg}", 0, "#e74c3c")

        threading.Thread(target=run_task, daemon=True).start()

    def start_upload(self):
        if not self.file_paths:
            self.updater.status_sig.emit("⚠️ 请先将需要上传的 Excel/CSV 文件拖入左侧区域！", 0, "#e67e22")
            return

        selected_region = "EU" if self.radio_group.checkedId() == 0 else "US"
        self.btn_upload.setEnabled(False)
        self.btn_upload.setText("⏳ 上传中...")

        def run_task():
            def callback(msg, val, color):
                self.updater.status_sig.emit(msg, val, color)

            success, msg = batch_upload_to_temu(self.file_paths, region=selected_region, status_callback=callback)

            if success:
                self.file_paths.clear()
                self.updater.status_sig.emit(f"✅ 上传完成: {msg}", 100, "#27ae60")
            else:
                self.updater.status_sig.emit(f"❌ 上传中止: {msg}", 0, "#e74c3c")

            self.btn_upload.setText("🚀 批量上传")
            self.btn_upload.setEnabled(True)

        threading.Thread(target=run_task, daemon=True).start()

    # =====================================================================
    # 🌟 槽函数区域
    # =====================================================================
    def _update_status_slot(self, text, progress, color_hex):
        self.log_badge.setText(text)
        self.log_badge.setStyleSheet(
            f"QLabel {{ background-color: #f3f4f6; color: {color_hex}; font-size: 12px; font-weight: bold; padding: 6px 10px; border-radius: 4px; border: none; }}")
        self.progress_bar.setValue(progress)
        if text == "等待挂载文件...":
            self.drop_area_ui.clear()