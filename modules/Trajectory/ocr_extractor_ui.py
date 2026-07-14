import os
import re
import sys
import threading
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                             QLabel, QFrame, QTextEdit, QFileDialog, QMessageBox, QWidget, QApplication)
# 🌟 核心修正：在这里显式地把 pyqtSignal 给引入进来！
from PyQt6.QtCore import Qt, QUrl, QObject, pyqtSignal
from PyQt6.QtGui import QFont, QCursor


# =====================================================================
# 🌟 原生硬核拖拽重写类 (100% 优雅剥离对 tkinterdnd2 的外部依赖)
# =====================================================================
class DragDropTextEdit(QTextEdit):
    # 声明一个自定义的文本拖放加载完成信号
    file_dropped_sig = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        # 开启原生的接受拖放流
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                # 提取第一个被拖入的文件路径
                file_path = urls[0].toLocalFile()
                self.file_dropped_sig.emit(file_path)
                event.acceptProposedAction()
        else:
            super().dropEvent(event)


# =====================================================================
# 🌟 统一调用入口 (🌟 使用 *args 万能接收，彻底丢弃参数纠缠)
# =====================================================================
def open_ocr_extractor(*args, **kwargs):
    """供主程序调用的入口"""
    win = OcrExtractorDialog()
    win.show()


class OcrExtractorDialog(QDialog):
    def __init__(self):
        super().__init__(None)
        self._keep_alive = self  # 顶级保活护盾，彻底允许自由最小化和切屏

        self.setWindowTitle("拆箱 OCR 单号智能提取器")
        self.resize(1100, 650)

        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        self.setStyleSheet("background-color: #f4f6f9;")

        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ================= 顶部标题 =================
        header = QLabel(" 拆箱 OCR 数据智能过滤与提取 (支持 TXT 文件直接拖入) ")
        header.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        header.setStyleSheet("background-color: #2c3e50; color: white; padding: 12px 20px; border: none;")
        main_layout.addWidget(header)

        # 主工作核心区
        workspace = QWidget()
        work_layout = QHBoxLayout(workspace)
        work_layout.setContentsMargins(20, 20, 20, 20)
        work_layout.setSpacing(15)

        # ------ 左栏：输入区 (拖拽加载核心) ------
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(5)

        lbl_input = QLabel("1. 拖入/导入 TXT 文件，或直接粘贴内容:")
        lbl_input.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        lbl_input.setStyleSheet("color: #34495e;")
        left_layout.addWidget(lbl_input)

        # 🌟 核心调教：挂载重写后的原生高速拖拽编辑框
        self.input_area = DragDropTextEdit()
        self.input_area.setFont(QFont("Consolas", 10))
        self.input_area.setStyleSheet("background-color: white; border: 1px solid #bdc3c7; border-radius: 3px;")
        self.input_area.file_dropped_sig.connect(self.load_txt_content)
        left_layout.addWidget(self.input_area)
        work_layout.addWidget(left_widget, stretch=4)

        # ------ 中栏：操作按钮区 ------
        mid_frame = QWidget()
        mid_layout = QVBoxLayout(mid_frame)
        mid_layout.setContentsMargins(5, 20, 5, 0)
        mid_layout.setSpacing(15)
        mid_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # 完美对齐您原版的 5 颗功能按钮与专属色系
        self.btn_import = QPushButton("📂 导入 TXT")
        self.btn_extract = QPushButton("⚡ 智能提取 ➔")
        self.btn_copy_valid = QPushButton("📋 复制正常单号")
        self.btn_copy_error = QPushButton("⚠️ 复制异常图片")
        self.btn_clear = QPushButton("🧹 一键清空")

        self.btn_import.setStyleSheet(
            "QPushButton { background-color: #ffc107; color: #212529; border-radius: 4px; border: none; }")
        self.btn_extract.setStyleSheet(
            "QPushButton { background-color: #198754; color: white; border-radius: 4px; border: none; }")
        self.btn_copy_valid.setStyleSheet(
            "QPushButton { background-color: #0d6efd; color: white; border-radius: 4px; border: none; }")
        self.btn_copy_error.setStyleSheet(
            "QPushButton { background-color: #e74c3c; color: white; border-radius: 4px; border: none; }")
        self.btn_clear.setStyleSheet(
            "QPushButton { background-color: #6c757d; color: white; border-radius: 4px; border: none; }")

        for btn in [self.btn_import, self.btn_extract, self.btn_copy_valid, self.btn_copy_error, self.btn_clear]:
            btn.setFixedSize(130, 38)
            btn.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            mid_layout.addWidget(btn)

        self.btn_import.clicked.connect(self.import_file)
        self.btn_extract.clicked.connect(self.extract_data)
        self.btn_copy_valid.clicked.connect(self.copy_valid_numbers)
        self.btn_copy_error.clicked.connect(self.copy_error_files)
        self.btn_clear.clicked.connect(self.clear_all)
        work_layout.addWidget(mid_frame)

        # ------ 右栏：输出区 (上下切分黄金比例) ------
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        # 正常单号部分 (Excel 环保淡绿底色)
        lbl_valid = QLabel("✅ 成功提取的单号:")
        lbl_valid.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        lbl_valid.setStyleSheet("color: #198754;")
        self.valid_area = QTextEdit()
        self.valid_area.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.valid_area.setFont(QFont("Consolas", 11))
        self.valid_area.setStyleSheet(
            "background-color: #f0fdf4; border: 1px solid #bdc3c7; color: #198754; border-radius: 3px;")

        right_layout.addWidget(lbl_valid)
        right_layout.addWidget(self.valid_area, stretch=6)

        # 异常文件部分 (柔和浅红预警色)
        lbl_error = QLabel("❌ 未提取到单号的图片名 (残缺或无单号):")
        lbl_error.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        lbl_error.setStyleSheet("color: #e74c3c;")
        self.error_area = QTextEdit()
        self.error_area.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.error_area.setFont(QFont("Consolas", 10))
        self.error_area.setStyleSheet(
            "background-color: #fff5f5; border: 1px solid #bdc3c7; color: #c0392b; border-radius: 3px;")

        right_layout.addWidget(lbl_error)
        right_layout.addWidget(self.error_area, stretch=4)

        work_layout.addWidget(right_widget, stretch=5)
        main_layout.addWidget(workspace)

    # ================= 文件导入与纯净洗白逻辑 =================
    def import_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "请选择 OCR 文本文件", "", "Text 文本文件 (*.txt);;所有文件 (*.*)"
        )
        if file_path:
            self.load_txt_content(file_path)

    def load_txt_content(self, file_path):
        if not file_path.lower().endswith('.txt'):
            QMessageBox.warning(self, "格式错误", "目前仅支持读取 .txt 格式的文本文件！")
            return

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            try:
                with open(file_path, 'r', encoding='gbk') as f:
                    content = f.read()
            except Exception as e:
                QMessageBox.critical(self, "读取失败", f"无法解析该文件编码：\n{str(e)}")
                return
        except Exception as e:
            QMessageBox.critical(self, "读取失败", f"文件打开失败：\n{str(e)}")
            return

        self.clear_all()
        self.input_area.setPlainText(content)
        self.extract_data()

    # =====================================================================
    # 🌟 核心业务解析逻辑 (100% 还原算法，使用 splitlines() 保底清洗)
    # =====================================================================
    def extract_data(self):
        raw_text = self.input_area.toPlainText().strip()
        if not raw_text: return

        pattern = r"≦\s*(.*?)\s*≧"
        matches = list(re.finditer(pattern, raw_text))

        if not matches:
            QMessageBox.warning(self, "提示", "未检测到图片分割符(如：≦ 文件名 ≧)，请确认文本格式！")
            return

        valid_numbers = []
        error_files = []

        for i in range(len(matches)):
            filename = matches[i].group(1).strip()
            start_idx = matches[i].end()
            end_idx = matches[i + 1].start() if i + 1 < len(matches) else len(raw_text)

            block_text = raw_text[start_idx:end_idx]
            num_match = re.search(r'(UANG\s*\d{12})', block_text, re.IGNORECASE)

            if num_match:
                clean_num = num_match.group(1).replace(" ", "").upper()
                valid_numbers.append(clean_num)
            else:
                error_files.append(filename)

        self.valid_area.clear()
        self.error_area.clear()

        if valid_numbers:
            self.valid_area.append("\n".join(valid_numbers))
            self.valid_area.append(f"\n\n--- 共提取成功 {len(valid_numbers)} 个 ---")
        else:
            self.valid_area.setPlainText("未找到任何有效单号。")

        if error_files:
            self.error_area.append("\n".join(error_files))
            self.error_area.append(f"\n\n--- 共发现 {len(error_files)} 个异常图片 ---")
        else:
            self.error_area.setPlainText("完美！所有图片均成功提取到单号。")

    def copy_valid_numbers(self):
        content = self.valid_area.toPlainText().strip()
        # 🌟 绝杀洗白：使用 splitlines 剔除 \r\n 毒素后送入剪贴板
        lines = [line for line in content.splitlines() if line and not line.startswith('---')]
        if lines and "未找到" not in content:
            QApplication.clipboard().setText("\n".join(lines))
            QMessageBox.information(self, "成功", f"✅ 已成功复制 {len(lines)} 个正常单号！")
        else:
            QMessageBox.warning(self, "警告", "没有可复制的正常单号。")

    def copy_error_files(self):
        content = self.error_area.toPlainText().strip()
        lines = [line for line in content.splitlines() if line and not line.startswith('---')]
        if lines and "完美" not in content:
            QApplication.clipboard().setText("\n".join(lines))
            QMessageBox.information(self, "成功", f"⚠️ 已成功复制 {len(lines)} 个异常图片名！")
        else:
            QMessageBox.warning(self, "警告", "没有可复制的异常图片名。")

    def clear_all(self):
        self.input_area.clear()
        self.valid_area.clear()
        self.error_area.clear()

    def closeEvent(self, event):
        self._keep_alive = None
        event.accept()