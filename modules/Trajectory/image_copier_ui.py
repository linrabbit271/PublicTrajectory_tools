import os
import sys
import shutil
from datetime import datetime

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                             QLabel, QFrame, QTextEdit, QLineEdit, QCheckBox,
                             QGridLayout, QFileDialog, QMessageBox, QWidget, QApplication)
from PyQt6.QtCore import Qt, QObject, pyqtSignal
from PyQt6.QtGui import QFont, QCursor


# =====================================================================
# 🌟 统一调用入口
# =====================================================================
def open_image_copier(*args, **kwargs):
    """主程序调用此方法，以子窗口形式弹出"""
    win = ImageCopierDialog()
    win.show()


class ImageCopierDialog(QDialog):
    def __init__(self):
        super().__init__(None)
        self._keep_alive = self

        self.setWindowTitle("图片批量克隆分发组件")
        self.setFixedSize(500, 580)

        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        self.setStyleSheet("background-color: #ecf0f1;")

        self.statuses = ["1-揽收", "2-入航司仓", "3-已起飞", "4-到达中转机场", "5-中转机场起飞", "6-到达目的地机场"]
        self.status_boxes = {}

        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- 顶部标题 ---
        header = QLabel(" 🖼️ 提单图片批量克隆与分发")
        header.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        header.setStyleSheet("background-color: #3498db; color: white; padding: 10px 15px; border: none;")
        main_layout.addWidget(header)

        workspace = QWidget()
        work_layout = QVBoxLayout(workspace)
        work_layout.setContentsMargins(20, 15, 20, 15)
        work_layout.setSpacing(10)

        # 1. 提单号输入区
        lbl_input = QLabel("目标提单号 (一行一个, 或逗号隔开):")
        lbl_input.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        lbl_input.setStyleSheet("color: #2c3e50;")
        work_layout.addWidget(lbl_input)

        self.text_input = QTextEdit()
        self.text_input.setFont(QFont("Consolas", 11))
        self.text_input.setStyleSheet("background-color: white; border: 1px solid #bdc3c7; border-radius: 3px;")
        work_layout.addWidget(self.text_input, stretch=1)

        # 2. 文件夹配置区
        subfolder_card = QFrame()
        subfolder_card.setStyleSheet("background-color: white; border: 1px solid #bdc3c7; border-radius: 4px;")
        card_lyt1 = QVBoxLayout(subfolder_card)
        card_lyt1.setContentsMargins(12, 8, 12, 10)
        card_lyt1.setSpacing(4)

        lbl_sub = QLabel("📂 归档子文件夹 (如共享表A列名称):")
        lbl_sub.setFont(QFont("Microsoft YaHei", 9, QFont.Weight.Bold))
        lbl_sub.setStyleSheet("color: #2c3e50; border: none;")
        self.sub_folder_entry = QLineEdit()
        self.sub_folder_entry.setFont(QFont("Microsoft YaHei", 10))
        self.sub_folder_entry.setStyleSheet("background-color: #f8f9fa; border: 1px solid #ced4da; padding: 4px;")

        card_lyt1.addWidget(lbl_sub)
        card_lyt1.addWidget(self.sub_folder_entry)
        work_layout.addWidget(subfolder_card)

        # 3. 状态节点多选区 (🌟 视觉强化，彻底逼出小方框)
        status_card = QFrame()
        status_card.setStyleSheet("background-color: white; border: 1px solid #bdc3c7; border-radius: 4px;")
        card_lyt2 = QVBoxLayout(status_card)
        card_lyt2.setContentsMargins(12, 8, 12, 10)
        card_lyt2.setSpacing(6)

        lbl_status = QLabel("☑️ 选择分发节点 (支持多选, 自动建档):")
        lbl_status.setFont(QFont("Microsoft YaHei", 9, QFont.Weight.Bold))
        lbl_status.setStyleSheet("color: #2c3e50; border: none;")
        card_lyt2.addWidget(lbl_status)

        grid_layout = QGridLayout()
        grid_layout.setSpacing(8)
        for idx, status in enumerate(self.statuses):
            cb = QCheckBox(status)
            cb.setFont(QFont("Microsoft YaHei", 9))
            cb.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

            # 🌟 绝杀优化：通过 QCheckBox::indicator 显式微雕小方框的轮廓线，使其在白底下异常醒目
            cb.setStyleSheet("""
                QCheckBox { 
                    color: #2c3e50; 
                    border: none; 
                    background: transparent; 
                }
                QCheckBox::indicator {
                    width: 14px;
                    height: 14px;
                    border: 1px solid #bdc3c7; /* 逼出灰色轮廓 */
                    border-radius: 2px;
                    background-color: #f8f9fa;
                }
                QCheckBox::indicator:hover {
                    border: 1px solid #3498db; /* 悬浮变成高亮蓝 */
                }
                QCheckBox::indicator:checked {
                    background-color: #3498db;
                    border: 1px solid #2980b9;
                    image: url(); /* 清除默认，依靠QT原生勾选或靠底色激活 */
                }
            """)
            self.status_boxes[status] = cb
            grid_layout.addWidget(cb, idx // 2, idx % 2)

        card_lyt2.addLayout(grid_layout)
        work_layout.addWidget(status_card)

        # 4. 底部执行按钮
        self.btn_run = QPushButton("🚀 选择源图片并开始分发")
        self.btn_run.setFixedHeight(45)
        self.btn_run.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        self.btn_run.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_run.setStyleSheet(
            "QPushButton { background-color: #27ae60; color: white; border-radius: 4px; border: none; }")
        self.btn_run.clicked.connect(self.batch_copy_images)
        work_layout.addWidget(self.btn_run)

        main_layout.addWidget(workspace, stretch=1)

    def batch_copy_images(self):
        raw_text = self.text_input.toPlainText().strip()
        if not raw_text:
            QMessageBox.warning(self, "提示", "请先在上方输入提单号！")
            return

        cleaned_text = raw_text.replace(',', '\n')
        bl_list = [no.strip() for no in cleaned_text.splitlines() if no.strip()]

        custom_sub_folder = self.sub_folder_entry.text().strip()
        selected_statuses = [status for status, cb in self.status_boxes.items() if cb.isChecked()]

        source_file, _ = QFileDialog.getOpenFileName(
            self, "选择要复制的源图片", "", "图片文件 (*.png *.jpg *.jpeg *.bmp *.webp)"
        )
        if not source_file:
            return

        today_str = datetime.now().strftime("%Y年%m月%d日")

        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.getcwd()

        save_dir = os.path.join(base_dir, "截图保存", today_str)

        if custom_sub_folder:
            save_dir = os.path.join(save_dir, custom_sub_folder)

        os.makedirs(save_dir, exist_ok=True)

        success_count = 0
        fail_count = 0

        for bl_no in bl_list:
            safe_bl_no = "".join([c for c in bl_no if c not in r'\/:*?"<>|'])
            if not safe_bl_no:
                fail_count += 1
                continue

            try:
                if not selected_statuses:
                    filepath = os.path.join(save_dir, f"{safe_bl_no}.png")
                    shutil.copy2(source_file, filepath)
                else:
                    for status in selected_statuses:
                        status_dir = os.path.join(save_dir, status)
                        os.makedirs(status_dir, exist_ok=True)

                        filepath = os.path.join(status_dir, f"{safe_bl_no}.png")
                        shutil.copy2(source_file, filepath)

                success_count += 1
            except Exception as e:
                print(f"克隆失败: {bl_no}, 错误: {e}")
                fail_count += 1

        msg = f"✅ 图片批量分发完毕！\n\n成功处理提单数：{success_count}\n失败数量：{fail_count}\n\n文件已归档至:\n{save_dir}"
        QMessageBox.information(self, "完成", msg)

    def closeEvent(self, event):
        self._keep_alive = None
        event.accept()