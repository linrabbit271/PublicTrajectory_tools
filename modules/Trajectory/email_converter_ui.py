import os
import re
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                             QLabel, QFrame, QTextEdit, QMessageBox, QWidget, QApplication)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QCursor


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


# =====================================================================
# 🌟 统一调用入口（主程序组件库点击事件绑定的外部调用入口）
# =====================================================================
def open_email_converter(main_app):
    win = EmailConverterApp()
    win.show()


class EmailConverterApp(QDialog):
    def __init__(self):
        super().__init__(None)
        self._keep_alive = self  # 🌟 强力护盾防内存回收秒退

        self.setWindowTitle("提单号批量转换器 v2.1")
        self.setFixedSize(650, 500)

        # 🌟 遵照共识：不使用 StaysOnTopHint 强制置顶，完美恢复自由层级
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        self.setStyleSheet("background-color: #f4f6f9;")

        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(10)

        # ================= 上部：输入区域 =================
        lbl_in = QLabel("1. 请输入或粘贴提单号 (支持空格、逗号或换行分隔)：")
        lbl_in.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        lbl_in.setStyleSheet("color: #2c3e50;")
        main_layout.addWidget(lbl_in)

        # 🌟 关键修改：替换为 SmartPasteTextEdit 智能过滤输入框
        self.input_text = SmartPasteTextEdit()
        self.input_text.setFont(QFont("Consolas", 11))
        self.input_text.setStyleSheet(
            "background-color: white; border: 1px solid #bdc3c7; border-radius: 4px; padding: 5px;")
        main_layout.addWidget(self.input_text, stretch=1)

        # ================= 中间：操作按钮区域 =================
        toolbar = QWidget()
        tool_layout = QHBoxLayout(toolbar)
        tool_layout.setContentsMargins(0, 5, 0, 5)
        tool_layout.setSpacing(10)

        self.btn_convert = QPushButton("🔄 转换格式")
        self.btn_clear = QPushButton("清空 🧹")
        self.btn_copy = QPushButton("📋 一键复制")

        # 统一样式渲染
        self.btn_convert.setStyleSheet(
            "QPushButton { background-color: #198754; color: white; border-radius: 4px; border: none; }")
        self.btn_clear.setStyleSheet(
            "QPushButton { background-color: #6c757d; color: white; border-radius: 4px; border: none; }")
        self.btn_copy.setStyleSheet(
            "QPushButton { background-color: #0d6efd; color: white; border-radius: 4px; border: none; }")

        for btn in [self.btn_convert, self.btn_clear, self.btn_copy]:
            btn.setFixedHeight(38)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
            if btn == self.btn_copy:
                btn.setFixedWidth(120)
                tool_layout.addStretch()  # 将复制按钮挤到最右边
            else:
                btn.setFixedWidth(110)
            tool_layout.addWidget(btn)

        self.btn_convert.clicked.connect(self.convert_text)
        self.btn_clear.clicked.connect(self.clear_all)
        self.btn_copy.clicked.connect(self.copy_to_clipboard)
        main_layout.addWidget(toolbar)

        # ================= 下部：输出区域 =================
        lbl_out = QLabel("2. 转换后的结果：")
        lbl_out.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        lbl_out.setStyleSheet("color: #2c3e50;")
        main_layout.addWidget(lbl_out)

        self.output_text = QTextEdit()
        self.output_text.setFont(QFont("Consolas", 11))
        self.output_text.setStyleSheet(
            "background-color: white; border: 1px solid #bdc3c7; border-radius: 4px; padding: 5px;")
        main_layout.addWidget(self.output_text, stretch=1)

    # =====================================================================
    # 🌟 核心业务逻辑
    # =====================================================================
    def convert_text(self):
        input_data = self.input_text.toPlainText().strip()

        if not input_data:
            QMessageBox.warning(self, "提示", "请输入提单号！")
            return

        # 提取提单号（支持数字和连字符）
        raw_numbers = re.findall(r"[0-9\-]+", input_data)

        if not raw_numbers:
            QMessageBox.warning(self, "提示", "未检测到有效的提单号，请检查输入！")
            return

        # 拼接格式：全文:xxx or 全文:xxx
        formatted_list = [f"全文:{num}" for num in raw_numbers]
        result = " or ".join(formatted_list)

        self.output_text.clear()
        self.output_text.setPlainText(result)

    def copy_to_clipboard(self):
        result_data = self.output_text.toPlainText().strip()

        if not result_data:
            QMessageBox.warning(self, "提示", "没有可复制的内容，请先转换！")
            return

        # 将新内容写入剪贴板
        QApplication.clipboard().setText(result_data)

        # 🌟 完美的动态倒计时反馈效果：改变按钮文字和颜色提示复制成功
        self.btn_copy.setText("✔ 已复制")
        self.btn_copy.setStyleSheet(
            "QPushButton { background-color: #20c997; color: white; border-radius: 4px; border: none; }")
        QTimer.singleShot(1500, self.reset_copy_button)

    def reset_copy_button(self):
        # 恢复复制按钮的默认状态
        self.btn_copy.setText("📋 一键复制")
        self.btn_copy.setStyleSheet(
            "QPushButton { background-color: #0d6efd; color: white; border-radius: 4px; border: none; }")

    def clear_all(self):
        self.input_text.clear()
        self.output_text.clear()

    def closeEvent(self, event):
        self._keep_alive = None
        event.accept()