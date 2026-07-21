import os
import shutil
import platform
import subprocess
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                             QLabel, QFrame, QLineEdit, QTextEdit, QFileDialog, QMessageBox, QWidget, QApplication)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCursor


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


def open_data_splitter(parent_app):
    # 🌟 实例化时传入 None，彻底切断连带缩小机制，让其拥有独立任务栏控制权
    win = DataSplitterDialog()
    win.show()


class DataSplitterDialog(QDialog):
    def __init__(self):
        super().__init__(None)
        self._keep_alive = self  # 🌟 独立窗口防内存垃圾回收秒退

        self.setWindowTitle("资料分割器")

        # 🌟 1. 允许自由放大与自适应拉伸
        self.setMinimumSize(580, 650)
        self.resize(620, 680)

        # 🌟 2. 显式开启【最大化/还原/最小化/关闭】完整控制栏
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowMinMaxButtonsHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        self.setStyleSheet("background-color: #ecf0f1;")

        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. 顶栏 Header
        header = QLabel(" 🗂️ 资料分割器 (提单分类提取)")
        header.setStyleSheet("""
            background-color: #34495e; 
            color: white; 
            font-size: 16px; 
            font-weight: bold; 
            padding: 15px 20px;
        """)
        header.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        main_layout.addWidget(header)

        # 2. 核心工作区容器 (开启弹性自适应)
        workspace = QWidget()
        work_layout = QVBoxLayout(workspace)
        work_layout.setContentsMargins(20, 15, 20, 15)
        work_layout.setSpacing(15)
        main_layout.addWidget(workspace, stretch=1)

        # --- 第一行：工作目录卡片 ---
        dir_card = QFrame()
        dir_card.setStyleSheet("background-color: white; border: 1px solid #ced4da; border-radius: 6px;")
        dir_lyt = QVBoxLayout(dir_card)
        dir_lyt.setContentsMargins(15, 12, 15, 15)
        dir_lyt.setSpacing(8)

        lbl_dir_title = QLabel("1. 工作目录:")
        lbl_dir_title.setStyleSheet("font-weight: bold; color: #2c3e50; font-size: 13px; border: none;")
        dir_lyt.addWidget(lbl_dir_title)

        dir_input_lyt = QHBoxLayout()
        dir_input_lyt.setContentsMargins(0, 0, 0, 0)
        dir_input_lyt.setSpacing(10)

        self.entry_folder = QLineEdit()
        self.entry_folder.setStyleSheet("""
            QLineEdit {
                font-family: "Consolas", "Microsoft YaHei"; font-size: 13px;
                padding: 6px; border: 1px solid #ced4da; border-radius: 4px;
                background-color: #f8f9fa;
            }
        """)
        dir_input_lyt.addWidget(self.entry_folder, stretch=1)

        btn_browse = QPushButton("📂 浏览...")
        btn_browse.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_browse.setStyleSheet("""
            QPushButton { background-color: #cbd5e1; color: #1e293b; font-weight: bold; padding: 7px 15px; border-radius: 4px; }
            QPushButton:hover { background-color: #94a3b8; }
        """)
        btn_browse.clicked.connect(self.select_folder)
        dir_input_lyt.addWidget(btn_browse)
        dir_lyt.addLayout(dir_input_lyt)
        work_layout.addWidget(dir_card)

        # --- 第二行：提单号输入卡片 (🌟 换用 SmartPasteTextEdit) ---
        bl_card = QFrame()
        bl_card.setStyleSheet("background-color: white; border: 1px solid #ced4da; border-radius: 6px;")
        bl_lyt = QVBoxLayout(bl_card)
        bl_lyt.setContentsMargins(15, 12, 15, 15)
        bl_lyt.setSpacing(8)

        lbl_bl_title = QLabel("2. 目标提单号 (每行一个):")
        lbl_bl_title.setStyleSheet("font-weight: bold; color: #2c3e50; font-size: 13px; border: none;")
        bl_lyt.addWidget(lbl_bl_title)

        self.bl_text_box = SmartPasteTextEdit()
        self.bl_text_box.setStyleSheet("""
            QTextEdit {
                font-family: "Consolas", "Microsoft YaHei"; font-size: 13px;
                padding: 8px; border: 1px solid #ced4da; border-radius: 4px;
                background-color: #f8f9fa;
            }
        """)
        bl_lyt.addWidget(self.bl_text_box, stretch=1)
        work_layout.addWidget(bl_card, stretch=1)

        # --- 第三行：底部双按钮栏 (🌟 彻底修复组件未绑定渲染的 Bug) ---
        btn_lyt = QHBoxLayout()
        btn_lyt.setContentsMargins(0, 5, 0, 5)
        btn_lyt.setSpacing(15)

        self.btn_run = QPushButton("🚀 开始执行分类")
        self.btn_run.setFixedHeight(48)
        self.btn_run.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_run.setStyleSheet("""
            QPushButton { background-color: #27ae60; color: white; font-size: 14px; font-weight: bold; border-radius: 5px; border-bottom: 3px solid #1e8449; }
            QPushButton:hover { background-color: #219653; }
            QPushButton:pressed { border-bottom: 1px solid #1e8449; padding-top: 4px; }
        """)
        self.btn_run.clicked.connect(self.run_separation)
        btn_lyt.addWidget(self.btn_run, stretch=1)

        self.btn_open = QPushButton("📂 打开工作目录")
        self.btn_open.setFixedHeight(48)
        self.btn_open.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_open.setStyleSheet("""
            QPushButton { background-color: #2980b9; color: white; font-size: 14px; font-weight: bold; border-radius: 5px; border-bottom: 3px solid #1f618d; }
            QPushButton:hover { background-color: #2471a3; }
            QPushButton:pressed { border-bottom: 1px solid #1f618d; padding-top: 4px; }
        """)
        self.btn_open.clicked.connect(self.open_folder)
        btn_lyt.addWidget(self.btn_open, stretch=1)

        work_layout.addLayout(btn_lyt)

    # =====================================================================
    # 🌟 核心槽逻辑函数
    # =====================================================================
    def select_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "选择工作文件夹")
        if folder_path:
            self.entry_folder.setText(folder_path)

    def open_folder(self):
        source_dir = self.entry_folder.text().strip()
        if not source_dir or not os.path.exists(source_dir):
            QMessageBox.warning(self, "提示", "目前没有有效的文件夹路径可打开。")
            return
        try:
            if platform.system() == "Windows":
                os.startfile(source_dir)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", source_dir])
            else:
                subprocess.Popen(["xdg-open", source_dir])
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法打开文件夹：\n{str(e)}")

    def run_separation(self):
        source_dir = self.entry_folder.text().strip()
        raw_bl_text = self.bl_text_box.toPlainText()
        target_bl_list = [line.strip() for line in raw_bl_text.splitlines() if line.strip()]

        if not source_dir or not os.path.exists(source_dir):
            QMessageBox.warning(self, "提示", "请选择有效的文件夹路径。")
            return
        if not target_bl_list:
            QMessageBox.warning(self, "提示", "请输入至少一个提单号。")
            return

        uploaded_dir = os.path.join(source_dir, "已上传")
        not_uploaded_dir = os.path.join(source_dir, "未上传")

        try:
            if os.path.exists(uploaded_dir):
                shutil.rmtree(uploaded_dir)
            if os.path.exists(not_uploaded_dir):
                shutil.rmtree(not_uploaded_dir)

            os.makedirs(uploaded_dir)
            os.makedirs(not_uploaded_dir)

            uploaded_count = 0
            not_uploaded_count = 0

            import sys
            current_script_name = os.path.basename(sys.argv[0])

            for filename in os.listdir(source_dir):
                if filename in ["已上传", "未上传"] or filename == current_script_name:
                    continue

                file_path = os.path.join(source_dir, filename)
                matched = any(bl in filename for bl in target_bl_list)
                target_path = os.path.join(uploaded_dir, filename) if matched else os.path.join(not_uploaded_dir,
                                                                                                filename)

                if os.path.isfile(file_path):
                    shutil.copy2(file_path, target_path)
                    if matched:
                        uploaded_count += 1
                    else:
                        not_uploaded_count += 1
                elif os.path.isdir(file_path):
                    if os.path.exists(target_path):
                        shutil.rmtree(target_path)
                    shutil.copytree(file_path, target_path)
                    if matched:
                        uploaded_count += 1
                    else:
                        not_uploaded_count += 1

            msg = (f"分类复制已完成！\n\n"
                   f"📁 [已上传]: {uploaded_count} 个\n"
                   f"📁 [未上传]: {not_uploaded_count} 个\n\n"
                   f"是否立即打开工作目录查看结果？")

            reply = QMessageBox.question(self, "处理完成", msg,
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.open_folder()

        except Exception as e:
            QMessageBox.critical(self, "错误", f"发生异常：\n{str(e)}")

    def closeEvent(self, event):
        self._keep_alive = None
        event.accept()