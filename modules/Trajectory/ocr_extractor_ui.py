import os
import re
import sys
import threading
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                             QLabel, QFrame, QTextEdit, QLineEdit, QFileDialog, QMessageBox, QWidget, QApplication)
from PyQt6.QtCore import Qt, QUrl, QObject, pyqtSignal
from PyQt6.QtGui import QFont, QCursor


# =====================================================================
# 🌟 原生硬核拖拽重写类
# =====================================================================
class DragDropTextEdit(QTextEdit):
    file_dropped_sig = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
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
                file_path = urls[0].toLocalFile()
                self.file_dropped_sig.emit(file_path)
                event.acceptProposedAction()
        else:
            super().dropEvent(event)


# =====================================================================
# 🌟 统一调用入口
# =====================================================================
def open_ocr_extractor(*args, **kwargs):
    """供主程序调用的入口"""
    win = OcrExtractorDialog()
    win.show()


class OcrExtractorDialog(QDialog):
    def __init__(self):
        super().__init__(None)
        self._keep_alive = self  # 顶级保活护盾

        self.setWindowTitle("拆箱 OCR 单号智能提取器 (高精度特征匹配版)")
        self.resize(1150, 680)

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
        left_layout.setSpacing(8)

        lbl_input = QLabel("1. 拖入/导入 TXT 文件，或直接粘贴内容:")
        lbl_input.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        lbl_input.setStyleSheet("color: #34495e;")
        left_layout.addWidget(lbl_input)

        self.input_area = DragDropTextEdit()
        self.input_area.setFont(QFont("Consolas", 10))
        self.input_area.setStyleSheet("background-color: white; border: 1px solid #bdc3c7; border-radius: 3px;")
        self.input_area.file_dropped_sig.connect(self.load_txt_content)
        left_layout.addWidget(self.input_area)
        work_layout.addWidget(left_widget, stretch=4)

        # ------ 中栏：操作与参考卡片区 ------
        mid_frame = QWidget()
        mid_layout = QVBoxLayout(mid_frame)
        mid_layout.setContentsMargins(5, 0, 5, 0)
        mid_layout.setSpacing(12)
        mid_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # 🌟 核心控制：示例箱号参考配置卡片
        sample_card = QFrame()
        sample_card.setStyleSheet("background-color: white; border: 1px solid #bdc3c7; border-radius: 4px;")
        sample_lyt = QVBoxLayout(sample_card)
        sample_lyt.setContentsMargins(10, 10, 10, 12)
        sample_lyt.setSpacing(6)

        lbl_sample = QLabel("💡 参考示例箱号:")
        lbl_sample.setFont(QFont("Microsoft YaHei", 9, QFont.Weight.Bold))
        lbl_sample.setStyleSheet("color: #2c3e50; border: none;")
        sample_lyt.addWidget(lbl_sample)

        lbl_tip = QLabel("可留空或填入样例(如 7980053439)，自动按长度与前缀匹配：")
        lbl_tip.setWordWrap(True)
        lbl_tip.setFont(QFont("Microsoft YaHei", 8))
        lbl_tip.setStyleSheet("color: #7f8c8d; border: none;")
        sample_lyt.addWidget(lbl_tip)

        # 🌟 关键修改：默认留空，添加占位符提示
        self.sample_input = QLineEdit()
        self.sample_input.setFont(QFont("Consolas", 10))
        self.sample_input.setPlaceholderText("例如: 7980053439 或 UANG...")
        self.sample_input.setStyleSheet("background-color: #f8f9fa; border: 1px solid #ced4da; padding: 5px;")
        sample_lyt.addWidget(self.sample_input)
        mid_layout.addWidget(sample_card)

        # 5 颗功能按钮与专属色系
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
            btn.setFixedHeight(38)
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

        # 正常单号部分
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

        # 异常文件部分
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

    # ================= 文件导入与渲染逻辑 =================
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
    # 🌟 算法级特征匹配与前缀相似度打分引擎
    # =====================================================================
    def find_best_matching_code(self, block_text, sample_code):
        sample = sample_code.strip().replace(" ", "").upper()

        # 保底处理：未输入示例时优先尝试传统 UANG+12位，或 10位纯数字
        if not sample:
            m1 = re.search(r'(UANG\s*\d{12})', block_text, re.IGNORECASE)
            if m1: return m1.group(1).replace(" ", "").upper()
            m2 = re.search(r'\b\d{10}\b', block_text)
            if m2: return m2.group(0)
            return None

        sample_len = len(sample)
        letter_match = re.match(r'^[A-Z]+', sample)
        letter_prefix = letter_match.group(0) if letter_match else ""

        candidates = []

        if letter_prefix:
            # 带有字母前缀 (如 UANG123456789012)
            digits_len = sample_len - len(letter_prefix)
            pattern = rf'{letter_prefix}\s*\d{{{digits_len}}}'
            matches = re.findall(pattern, block_text, re.IGNORECASE)
            for m in matches:
                candidates.append(m.replace(" ", "").upper())
        else:
            # 纯数字型 (如 7980053439，长度 10)
            pattern = rf'\b\d{{{sample_len}}}\b'
            candidates = re.findall(pattern, block_text)

        # 如果单词边界未抓到，尝试不带词界的自由匹配
        if not candidates:
            pattern_flex = rf'\d{{{sample_len}}}'
            candidates = re.findall(pattern_flex, block_text)

        if not candidates:
            return None

        if len(candidates) == 1:
            return candidates[0]

        # 多候选打分：优先挑选与参考示例【前缀字符重合度最高】的项目
        def similarity_score(cand):
            score = 0
            for c1, c2 in zip(sample, cand):
                if c1 == c2:
                    score += 2
                else:
                    break
            for c1, c2 in zip(sample, cand):
                if c1 == c2:
                    score += 1
            return score

        candidates.sort(key=similarity_score, reverse=True)
        return candidates[0]

    def extract_data(self):
        raw_text = self.input_area.toPlainText().strip()
        if not raw_text: return

        sample_code = self.sample_input.text().strip()

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

            # 调用高精度特征匹配引擎提取单号
            matched_code = self.find_best_matching_code(block_text, sample_code)

            if matched_code:
                valid_numbers.append(matched_code)
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