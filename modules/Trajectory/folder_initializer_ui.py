import os
import sys
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QFrame, QFileDialog, QMessageBox)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QFont, QDesktopServices


def open_folder_initializer(main_app):
    """
    供主程序扩展组件库（AnimatedComponentCard）调用的标准入口函数
    """
    # 唤起独立的子窗口，并保持置顶交互
    sub_win = FolderInitializerApp()
    sub_win.setWindowModality(Qt.WindowModality.ApplicationModal)
    sub_win.show()
    # 挂载到主应用实例防止被垃圾回收
    if not hasattr(main_app, '_sub_windows'):
        main_app._sub_windows = []
    main_app._sub_windows.append(sub_win)


class FolderInitializerApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🧩 自动化多级目录初始化引擎")
        self.resize(580, 320)
        self.selected_path = ""
        self.setup_ui()

    def setup_ui(self):
        # 1. 🟥 顶部科技感 Header
        header = QLabel(" 📁 自动化多级目录初始化面板", self)
        header.setStyleSheet("""
            background-color: #34495e; 
            color: white; 
            font-size: 15px; 
            font-weight: bold; 
            padding: 15px 20px;
            border-bottom: 2px solid #2c3e50;
        """)

        # 2. 🟨 主工作布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(header)

        content_frame = QFrame()
        content_frame.setStyleSheet("background-color: #f5f7fa;")
        content_layout = QVBoxLayout(content_frame)
        content_layout.setContentsMargins(25, 20, 25, 25)
        content_layout.setSpacing(15)

        # 提示标签
        tip_lbl = QLabel(
            "说明：选择目标根目录后，系统将自动以当前日期（YYYY-MM-DD）建档，并深度流水线化生成「截图」、「解压（内含完成）」、「完成」等四维结构仓。")
        tip_lbl.setWordWrap(True)
        tip_lbl.setFont(QFont("Microsoft YaHei", 9))
        tip_lbl.setStyleSheet("color: #7f8c8d; line-height: 1.5;")
        content_layout.addWidget(tip_lbl)

        # 路径展示区
        path_box = QHBoxLayout()
        self.lbl_path = QLabel("当前未选择任何路径，请点击右侧按钮选择...")
        self.lbl_path.setStyleSheet("""
            background-color: #ffffff;
            border: 1px dashed #bdc3c7;
            border-radius: 6px;
            padding: 10px;
            color: #95a5a6;
            font-size: 12px;
        """)
        self.lbl_path.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        btn_browse = QPushButton("📁 浏览...")
        btn_browse.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_browse.setStyleSheet("""
            QPushButton {
                background-color: #3498db; color: white; font-weight: bold; font-size: 13px;
                padding: 9px 18px; border-radius: 6px; border-bottom: 3px solid #2980b9;
            }
            QPushButton:hover { background-color: #2980b9; }
            QPushButton:pressed { border-bottom: 1px solid #2980b9; padding-top: 11px; }
        """)
        btn_browse.clicked.connect(self.select_directory)

        path_box.addWidget(self.lbl_path, stretch=1)
        path_box.addWidget(btn_browse)
        content_layout.addLayout(path_box)
        content_layout.addStretch()

        # 3. 🟩 底部动作按钮区
        action_box = QHBoxLayout()
        self.btn_execute = QPushButton("🚀 一键流水线建档")
        self.btn_execute.setEnabled(False)
        self.btn_execute.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_execute.setStyleSheet("""
            QPushButton {
                background-color: #2ecc71; color: white; font-weight: bold; font-size: 14px;
                padding: 12px 30px; border-radius: 6px; border-bottom: 3px solid #27ae60;
            }
            QPushButton:hover { background-color: #27ae60; }
            QPushButton:pressed { border-bottom: 1px solid #27ae60; padding-top: 14px; }
            QPushButton:disabled { background-color: #bdc3c7; border: none; color: #ecf0f1; }
        """)
        self.btn_execute.clicked.connect(self.execute_folder_generation)

        action_box.addStretch()
        action_box.addWidget(self.btn_execute)
        content_layout.addLayout(action_box)

        main_layout.addWidget(content_frame, stretch=1)

    def select_directory(self):
        """唤起原生文件树选择根目录"""
        dir_path = QFileDialog.getExistingDirectory(self, "选择物流轨迹归档根路径", "")
        if dir_path:
            self.selected_path = os.path.abspath(dir_path)
            self.lbl_path.setText(self.selected_path)
            self.lbl_path.setStyleSheet("""
                background-color: #ffffff; border: 1px solid #1abc9c; border-radius: 6px;
                padding: 10px; color: #2c3e50; font-size: 12px; font-weight: bold;
            """)
            self.btn_execute.setEnabled(True)

    def execute_folder_generation(self):
        """核心建档算法：多级树状拓扑智能生成"""
        if not self.selected_path or not os.path.exists(self.selected_path):
            QMessageBox.warning(self, "路径失效", "选中的根路径不存在，请重新选择！")
            return

        # 获取当今日期格式化字符串 (例如: 2026-07-13)
        today_str = datetime.now().strftime("%Y-%m-%d")

        # 构建主日期拓扑路径
        target_root_dir = os.path.join(self.selected_path, today_str)

        # 深度定义子文件夹矩阵结构
        sub_folders = [
            os.path.join(target_root_dir, "截图"),
            os.path.join(target_root_dir, "完成"),
            os.path.join(target_root_dir, "解压"),
            os.path.join(target_root_dir, "解压", "完成")  # 深度嵌套二级完成仓
        ]

        try:
            created_count = 0
            # 使用 os.makedirs(..., exist_ok=True) 优雅地物理绞杀递归建档中的“已存在”报错
            for folder in sub_folders:
                if not os.path.exists(folder):
                    os.makedirs(folder, exist_ok=True)
                    created_count += 1
                else:
                    os.makedirs(folder, exist_ok=True)  # 确保完好

            # 联动系统桌面服务：一键秒开刚刚建好的当天工作区文件夹，极佳的用户闭环体验
            QMessageBox.information(self, "同步成功", f"🎉 当日轨迹流水线工作舱初始化完毕！\n目录位置：{target_root_dir}")
            QDesktopServices.openUrl(QUrl.fromLocalFile(target_root_dir))
            self.close()

        except Exception as e:
            QMessageBox.critical(self, "磁盘写入异常", f"无法在指定路径下初始化工作舱，错误阻断原因：\n{str(e)}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = FolderInitializerApp()
    win.show()
    sys.exit(app.exec())