import os
import re
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                             QLabel, QFrame, QTextEdit, QMessageBox, QWidget, QApplication)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QCursor


# =====================================================================
# 🌟 统一调用入口（主程序组件库点击事件绑定的外部调用入口）
# =====================================================================
def open_loading_time_extractor(main_app):
    win = DataExtractorApp()
    win.show()


class DataExtractorApp(QDialog):
    def __init__(self):
        super().__init__(None)
        self._keep_alive = self  # 🌟 强力护盾防内存回收秒退

        self.setWindowTitle("装货时间极简提取器")
        self.setFixedSize(1100, 650)

        # 🌟 遵照共识：去除了 StaysOnTopHint 强制置顶，使其层级自由
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
        header = QLabel(" 提单装货数据提取 (自动过滤无时间任务) ")
        header.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        header.setStyleSheet("""
            background-color: #2c3e50; 
            color: white; 
            padding: 12px 20px;
            border: none;
        """)
        main_layout.addWidget(header)

        # ================= 主体框架布局 =================
        workspace = QWidget()
        work_layout = QHBoxLayout(workspace)
        work_layout.setContentsMargins(20, 20, 20, 20)
        work_layout.setSpacing(15)

        # ------ 左栏：输入区 ------
        left_box = QWidget()
        left_lyt = QVBoxLayout(left_box)
        left_lyt.setContentsMargins(0, 0, 0, 0)
        left_lyt.setSpacing(5)

        lbl_in = QLabel("1. 粘贴原始数据 (Ctrl+V)")
        lbl_in.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        lbl_in.setStyleSheet("color: #34495e;")
        left_lyt.addWidget(lbl_in)

        self.input_area = QTextEdit()
        self.input_area.setFont(QFont("Consolas", 10))
        self.input_area.setStyleSheet(
            "background-color: white; border: 1px solid #bdc3c7; border-radius: 4px; padding: 5px;")
        left_lyt.addWidget(self.input_area)
        work_layout.addWidget(left_box, stretch=1)

        # ------ 中栏：操作按钮区 ------
        mid_frame = QWidget()
        mid_lyt = QVBoxLayout(mid_frame)
        mid_lyt.setContentsMargins(0, 0, 0, 0)
        mid_lyt.setSpacing(15)
        mid_lyt.addStretch()

        self.btn_extract = QPushButton("提取 ➔")
        self.btn_copy = QPushButton("📋 复制 Excel")
        self.btn_clear = QPushButton("工业清空 🧹")

        for btn, style in [(self.btn_extract, "background-color: #198754; color: white;"),
                           (self.btn_copy, "background-color: #0d6efd; color: white;"),
                           (self.btn_clear, "background-color: #6c757d; color: white;")]:
            btn.setFixedSize(130, 42)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
            btn.setStyleSheet(f"QPushButton {{ {style} border-radius: 4px; border: none; }}")
            mid_lyt.addWidget(btn)

        self.btn_extract.clicked.connect(self.extract_data)
        self.btn_copy.clicked.connect(self.copy_to_excel)
        self.btn_clear.clicked.connect(self.clear_all)

        mid_lyt.addStretch()
        work_layout.addWidget(mid_frame)

        # ------ 右栏：输出区 ------
        right_box = QWidget()
        right_lyt = QVBoxLayout(right_box)
        right_lyt.setContentsMargins(0, 0, 0, 0)
        right_lyt.setSpacing(5)

        lbl_out = QLabel("2. 有效提取结果")
        lbl_out.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        lbl_out.setStyleSheet("color: #34495e;")
        right_lyt.addWidget(lbl_out)

        self.result_area = QTextEdit()
        self.result_area.setReadOnly(True)
        self.result_area.setFont(QFont("Consolas", 10))
        self.result_area.setStyleSheet(
            "background-color: white; border: 1px solid #bdc3c7; border-radius: 4px; padding: 5px;")
        right_lyt.addWidget(self.result_area)
        work_layout.addWidget(right_box, stretch=1)

        main_layout.addWidget(workspace, stretch=1)

    # =====================================================================
    # 🌟 核心提取业务逻辑 (完美继承您原有的数据清洗过滤算法)
    # =====================================================================
    def extract_data(self):
        raw_text = self.input_area.toPlainText().strip()
        if not raw_text:
            QMessageBox.warning(self, "提示", "请先在左侧输入框中粘贴原始文本内容")
            return

        bill_pattern = r"^(\d{3}-\d{8})$"
        time_pattern = r"(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})"

        lines = [line.strip() for line in raw_text.split('\n') if line.strip()]
        results = []

        i = 0
        while i < len(lines):
            if re.match(bill_pattern, lines[i]):
                bill_no = lines[i]
                loading_time = None
                k = i + 1
                while k < len(lines):
                    if re.match(bill_pattern, lines[k]):
                        break
                    if "YS" in lines[k]:
                        sub_block = " ".join(lines[k:k + 6])
                        found_times = re.findall(time_pattern, sub_block)
                        if len(found_times) >= 2:
                            loading_time = found_times[1]
                        break
                    if "待分配" in lines[k] or "已取消" in lines[k]:
                        break
                    k += 1

                if not loading_time:
                    i += 1
                    continue

                warehouse = "未知子仓"
                j = i - 1
                while j >= 0:
                    if re.match(bill_pattern, lines[j]):
                        break
                    if "子仓" in lines[j] and "实际提货子仓" not in lines[j]:
                        warehouse = lines[j]
                        break
                    elif "子仓" in lines[j] and "实际提货子仓" in lines[j]:
                        warehouse = lines[j].split("实际提货子仓")[0].strip()
                        break
                    j -= 1

                results.append(f"{bill_no}\t{warehouse}\t{loading_time}")
            i += 1

        self.result_area.clear()
        if results:
            self.result_area.setPlainText("\n".join(results))
        else:
            self.result_area.setPlainText("本次提取未发现包含【有效装货完成时间】的提单数据。")

    def copy_to_excel(self):
        content = self.result_area.toPlainText().strip()
        if content and "本次提取未发现" not in content:
            QApplication.clipboard().setText(content)
            QMessageBox.information(self, "成功", "有效数据已成功复制！\n可直接前往 Excel 粘贴。")
        else:
            QMessageBox.warning(self, "警告", "结果框中没有有效的数据可供复制。")

    def clear_all(self):
        self.input_area.clear()
        self.result_area.clear()

    def closeEvent(self, event):
        self._keep_alive = None
        event.accept()