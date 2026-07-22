import os
import re
import sys
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                             QLabel, QFrame, QTextEdit, QTableWidget, QTableWidgetItem,
                             QHeaderView, QFileDialog, QMessageBox, QWidget, QApplication)
from PyQt6.QtCore import Qt, pyqtSignal
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
            clean_text = "\n".join(lines)
            self.insertPlainText(clean_text)
        else:
            super().insertFromMimeData(source)


# =====================================================================
# 🌟 支持文件与文件夹拖拽的表格组件
# =====================================================================
class DropFileTableWidget(QTableWidget):
    file_dropped_sig = pyqtSignal(list)

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
            paths = [url.toLocalFile() for url in event.mimeData().urls()]
            self.file_dropped_sig.emit(paths)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)


# =====================================================================
# 🌟 统一调用入口
# =====================================================================
def open_customs_renamer(*args, **kwargs):
    win = CustomsRenamerDialog()
    win.show()


class CustomsRenamerDialog(QDialog):
    def __init__(self):
        super().__init__(None)
        self._keep_alive = self  # 顶级保活护盾

        self.setWindowTitle("报关资料名修改器 (原地直接重命名)")

        # 允许自由放大缩小，限制最小安全尺寸
        self.setMinimumSize(980, 650)
        self.resize(1080, 700)

        # 开启完整窗口控制栏（最大化/还原/最小化/关闭）
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowMinMaxButtonsHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        self.setStyleSheet("background-color: #f4f6f9;")

        self.loaded_files = []  # 存入格式：{"path": file_path, "dir": dir_path, "name": filename}
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(12)

        # 1. 顶栏 Header
        header = QLabel(" 📝 报关资料文件名修改器 (拖入即替换，原路径直接修改)")
        header.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        header.setStyleSheet("background-color: #2c3e50; color: white; padding: 12px 18px; border-radius: 4px;")
        main_layout.addWidget(header)

        # 2. 中间工作核心区 (左右切分布局)
        workspace = QWidget()
        work_layout = QHBoxLayout(workspace)
        work_layout.setContentsMargins(0, 0, 0, 0)
        work_layout.setSpacing(15)

        # ====== 左侧：文件挂载预览表格 (支持拖拽) ======
        left_box = QWidget()
        left_lyt = QVBoxLayout(left_box)
        left_lyt.setContentsMargins(0, 0, 0, 0)
        left_lyt.setSpacing(8)

        lbl_files = QLabel("1. 拖入文件/文件夹 (每次拖入自动覆盖上次)：")
        lbl_files.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        lbl_files.setStyleSheet("color: #34495e;")
        left_lyt.addWidget(lbl_files)

        self.table = DropFileTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["序号", "原文件名", "预计新文件名", "文件所在目录"])
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #ced4da;
                alternate-background-color: #f9f9f9;
                background-color: white;
                gridline-color: #e2e8f0;
            }
            QHeaderView::section {
                background-color: #f1f2f6;
                font-weight: bold;
                color: #2c3e50;
                border: 1px solid #dcdde1;
                padding: 6px;
            }
        """)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(0, 50)
        self.table.setColumnWidth(3, 180)
        self.table.file_dropped_sig.connect(self.handle_dropped_paths)
        left_lyt.addWidget(self.table, stretch=1)

        work_layout.addWidget(left_box, stretch=6)

        # ====== 右侧：单号比对输入与操作面板 ======
        right_box = QFrame()
        right_box.setStyleSheet("background-color: white; border: 1px solid #ced4da; border-radius: 6px;")
        right_lyt = QVBoxLayout(right_box)
        right_lyt.setContentsMargins(15, 12, 15, 15)
        right_lyt.setSpacing(10)

        # 旧提单号输入框
        lbl_old = QLabel("2. 旧提单号列表 (要被替换的):")
        lbl_old.setFont(QFont("Microsoft YaHei", 9, QFont.Weight.Bold))
        lbl_old.setStyleSheet("color: #c0392b; border: none;")
        right_lyt.addWidget(lbl_old)

        self.txt_old_awb = SmartPasteTextEdit()
        self.txt_old_awb.setFont(QFont("Consolas", 10))
        self.txt_old_awb.setPlaceholderText("每行一个旧单号，如: 065-70094323")
        self.txt_old_awb.setStyleSheet("background-color: #fff5f5; border: 1px solid #f5c2c7; border-radius: 4px;")
        self.txt_old_awb.textChanged.connect(self.preview_renaming)
        right_lyt.addWidget(self.txt_old_awb, stretch=1)

        # 新提单号输入框
        lbl_new = QLabel("3. 新提单号列表 (替换后的目标):")
        lbl_new.setFont(QFont("Microsoft YaHei", 9, QFont.Weight.Bold))
        lbl_new.setStyleSheet("color: #27ae60; border: none;")
        right_lyt.addWidget(lbl_new)

        self.txt_new_awb = SmartPasteTextEdit()
        self.txt_new_awb.setFont(QFont("Consolas", 10))
        self.txt_new_awb.setPlaceholderText("对应的新单号，未填则替换为'未填写新提单号'")
        self.txt_new_awb.setStyleSheet("background-color: #f0fdf4; border: 1px solid #a3cfbb; border-radius: 4px;")
        self.txt_new_awb.textChanged.connect(self.preview_renaming)
        right_lyt.addWidget(self.txt_new_awb, stretch=1)

        work_layout.addWidget(right_box, stretch=4)
        main_layout.addWidget(workspace, stretch=1)

        # 3. 底部操作按钮控制栏
        action_bar = QHBoxLayout()
        action_bar.setSpacing(15)

        self.btn_import = QPushButton("📂 导入文件/文件夹")
        self.btn_clear = QPushButton("🧹 一键清空")
        self.btn_run = QPushButton("🚀 开始原地重命名")

        self.btn_import.setStyleSheet("""
            QPushButton { background-color: #cbd5e1; color: #1e293b; font-weight: bold; border-radius: 4px; padding: 10px; }
            QPushButton:hover { background-color: #94a3b8; }
        """)
        self.btn_clear.setStyleSheet("""
            QPushButton { background-color: #6c757d; color: white; font-weight: bold; border-radius: 4px; padding: 10px; }
            QPushButton:hover { background-color: #5a6268; }
        """)
        self.btn_run.setStyleSheet("""
            QPushButton { background-color: #198754; color: white; font-size: 14px; font-weight: bold; border-radius: 4px; border-bottom: 3px solid #146c43; padding: 10px; }
            QPushButton:hover { background-color: #157347; }
            QPushButton:pressed { border-bottom: 1px solid #146c43; padding-top: 12px; }
        """)

        for btn in [self.btn_import, self.btn_clear, self.btn_run]:
            btn.setFixedHeight(42)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))

        self.btn_import.setFixedWidth(160)
        self.btn_clear.setFixedWidth(120)

        self.btn_import.clicked.connect(self.manual_import_dialog)
        self.btn_clear.clicked.connect(self.clear_all)
        self.btn_run.clicked.connect(self.execute_renaming)

        action_bar.addWidget(self.btn_import)
        action_bar.addWidget(self.btn_clear)
        action_bar.addWidget(self.btn_run, stretch=1)
        main_layout.addLayout(action_bar)

    # =====================================================================
    # 🌟 拖拽与文件加载处理 (瞬间清空上次，极速读取)
    # =====================================================================
    def handle_dropped_paths(self, path_list):
        # 每次重新拖入时，清空上一次的文件缓存与表格
        self.loaded_files.clear()
        self.table.setRowCount(0)

        extracted_files = []
        for p in path_list:
            if os.path.isfile(p):
                extracted_files.append(p)
            elif os.path.isdir(p):
                # 递归获取文件夹下所有文件
                for root, _, files in os.walk(p):
                    for f in files:
                        extracted_files.append(os.path.join(root, f))

        # 去重
        extracted_files = list(dict.fromkeys(extracted_files))

        for f_path in extracted_files:
            dir_path, f_name = os.path.split(f_path)
            self.loaded_files.append({
                "path": f_path,
                "dir": dir_path,
                "name": f_name
            })

        self.refresh_table_display()

    def manual_import_dialog(self):
        files, _ = QFileDialog.getOpenFileNames(self, "选择要修改名称的文件", "", "所有文件 (*.*)")
        if files:
            self.handle_dropped_paths(files)

    # =====================================================================
    # 🌟 实时预览与重命名引擎
    # =====================================================================
    def get_awb_mapping(self):
        """ 解析左右两框的映射关系 """
        old_raw = self.txt_old_awb.toPlainText()
        new_raw = self.txt_new_awb.toPlainText()

        old_lines = [line.strip() for line in old_raw.splitlines() if line.strip()]
        new_lines = [line.strip() for line in new_raw.splitlines() if line.strip()]

        mapping = []
        for idx, old_awb in enumerate(old_lines):
            target_new = new_lines[idx] if idx < len(new_lines) and new_lines[idx] else "未填写新提单号"
            mapping.append((old_awb, target_new))
        return mapping

    def refresh_table_display(self):
        self.table.setRowCount(0)
        mapping = self.get_awb_mapping()

        for idx, f_info in enumerate(self.loaded_files, 1):
            row = self.table.rowCount()
            self.table.insertRow(row)

            orig_name = f_info["name"]
            new_name = orig_name

            # 匹配替换
            for old_awb, new_awb in mapping:
                if old_awb in orig_name:
                    new_name = orig_name.replace(old_awb, new_awb)
                    break

            i0 = QTableWidgetItem(str(idx))
            i1 = QTableWidgetItem(orig_name)
            i2 = QTableWidgetItem(new_name)
            i3 = QTableWidgetItem(f_info["dir"])

            i0.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            i1.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            i2.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            i3.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

            # 如果文件名被修改了，突出高亮显示
            if new_name != orig_name:
                i2.setForeground(Qt.GlobalColor.darkGreen)
                font = i2.font()
                font.setBold(True)
                i2.setFont(font)

            self.table.setItem(row, 0, i0)
            self.table.setItem(row, 1, i1)
            self.table.setItem(row, 2, i2)
            self.table.setItem(row, 3, i3)

    def preview_renaming(self):
        if self.loaded_files:
            self.refresh_table_display()

    # =====================================================================
    # 🌟 原地直接执行重命名逻辑
    # =====================================================================
    def execute_renaming(self):
        if not self.loaded_files:
            QMessageBox.warning(self, "提示", "请先拖入或导入要修改的文件！")
            return

        mapping = self.get_awb_mapping()
        if not mapping:
            QMessageBox.warning(self, "提示", "请至少在右侧输入一个要替换的旧提单号！")
            return

        success_count = 0
        fail_count = 0

        for f_info in self.loaded_files:
            old_filepath = f_info["path"]
            dir_path = f_info["dir"]
            orig_name = f_info["name"]

            target_name = orig_name
            matched = False

            for old_awb, new_awb in mapping:
                if old_awb in orig_name:
                    target_name = orig_name.replace(old_awb, new_awb)
                    matched = True
                    break

            if matched and target_name != orig_name:
                new_filepath = os.path.join(dir_path, target_name)
                try:
                    os.rename(old_filepath, new_filepath)
                    # 同步更新本地记录，防止重复修改
                    f_info["path"] = new_filepath
                    f_info["name"] = target_name
                    success_count += 1
                except Exception as e:
                    print(f"重命名失败: {orig_name}, 错误: {e}")
                    fail_count += 1

        self.refresh_table_display()
        msg = f"🎉 批量重命名完成！\n\n✅ 成功修改文件数：{success_count}\n⚠️ 失败/未变动数：{fail_count}"
        QMessageBox.information(self, "完成", msg)

    def clear_all(self):
        self.loaded_files.clear()
        self.table.setRowCount(0)
        self.txt_old_awb.clear()
        self.txt_new_awb.clear()

    def closeEvent(self, event):
        self._keep_alive = None
        event.accept()