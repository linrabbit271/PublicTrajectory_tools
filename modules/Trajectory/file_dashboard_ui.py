import os
import threading
import pandas as pd

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QLabel, QFrame, QTableWidget, QTableWidgetItem,
                             QAbstractItemView, QHeaderView, QFileDialog, QMessageBox, QApplication)
from PyQt6.QtCore import Qt, QObject, pyqtSignal
from PyQt6.QtGui import QFont, QCursor, QKeySequence


# =====================================================================
# 🌟 线程安全通讯器
# =====================================================================
class DashboardUpdater(QObject):
    row_ready_sig = pyqtSignal(str, int, list)
    error_sig = pyqtSignal(str, str)
    status_sig = pyqtSignal(str, str)


# =====================================================================
# 🌟 原生支持拖拽 & Excel 级自由复制的智能数据表格
# =====================================================================
class DropTableWidget(QTableWidget):
    def __init__(self, parent_panel):
        super().__init__()
        self.parent_panel = parent_panel
        self.setAcceptDrops(True)

        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.verticalHeader().setVisible(False)

        headers = [
            "来源文件名", "包裹数", "包裹对应提单号", "头程轨迹上传类型",
            "包裹二级状态", "轨迹描述", "操作时间", "时区",
            "操作地点", "国家", "机场三字码", "机场类型", "航空公司", "航班号"
        ]
        self.setColumnCount(len(headers))
        self.setHorizontalHeaderLabels(headers)

        # =======================================================
        # 🌟 宽度与自适应交互优化升级
        # =======================================================
        header_view = self.horizontalHeader()

        # 1. 允许所有列都能被自由拖拽调整宽度
        for i in range(self.columnCount()):
            header_view.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)

        # 2. 设置舒适的初始默认宽度
        self.setColumnWidth(0, 180)  # 来源文件名
        self.setColumnWidth(1, 60)  # 包裹数
        self.setColumnWidth(2, 160)  # 提单号 (加宽)
        self.setColumnWidth(6, 160)  # 操作时间 (加宽)

        # 3. 🎯 核心黑科技：单击表头，瞬间自适应内容最长宽度！
        header_view.sectionClicked.connect(self.resizeColumnToContents)

        # 👇 ------ 在这里加上这一行，绑定双击事件 ------ 👇
        self.itemDoubleClicked.connect(self.check_cell_content)
        self.setStyleSheet("""
            QTableWidget {
                background-color: white;
                alternate-background-color: #f8f9fa;
                border: none;
                font-family: "Microsoft YaHei";
                font-size: 13px;
                gridline-color: #dee2e6;
            }
            QHeaderView::section {
                background-color: #e9ecef;
                font-weight: bold;
                color: #495057;
                padding: 8px;
                border: none;
                border-right: 1px solid #dee2e6;
                border-bottom: 1px solid #dee2e6;
            }
            /* 当鼠标悬浮在表头上时，给一点变色暗示它是可以点击的 */
            QHeaderView::section:hover {
                background-color: #dee2e6;
            }
            QTableWidget::item:selected {
                background-color: #cce5ff;
                color: #004085;
            }
        """)
        self.setAlternatingRowColors(True)

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.StandardKey.Copy):
            self.copy_excel_format_selection()
        else:
            super().keyPressEvent(event)

    def copy_excel_format_selection(self):
        selected_indexes = self.selectedIndexes()
        if not selected_indexes:
            return

        min_row = min(idx.row() for idx in selected_indexes)
        max_row = max(idx.row() for idx in selected_indexes)
        min_col = min(idx.column() for idx in selected_indexes)
        max_col = max(idx.column() for idx in selected_indexes)

        clipboard_text = ""
        for r in range(min_row, max_row + 1):
            row_data = []
            for c in range(min_col, max_col + 1):
                if any(idx.row() == r and idx.column() == c for idx in selected_indexes):
                    item = self.item(r, c)
                    row_data.append(item.text() if item else "")
                else:
                    row_data.append("")

            clipboard_text += "\t".join(row_data) + "\n"

        QApplication.clipboard().setText(clipboard_text.rstrip("\n"))

    # 👇 ------ 在 copy_excel_format_selection 方法的下面，插入这个新方法 ------ 👇
    def check_cell_content(self, item):
        """双击单元格时触发：高亮显示隐藏空格，方便人工核查"""
        if not item: return
        raw_text = item.text()

        # 将空格替换为明显的视觉符号，让你一眼看出哪里多敲了空格
        highlighted_text = raw_text.replace(" ", "·")

        # 统计空格细节
        space_count = raw_text.count(" ")
        leading_spaces = len(raw_text) - len(raw_text.lstrip(" "))
        trailing_spaces = len(raw_text) - len(raw_text.rstrip(" "))

        msg = (
            f"【原始数据】(加括号以显露边缘空格):\n「{raw_text}」\n\n"
            f"【空格分布】(空格已被替换为 '·'):\n{highlighted_text}\n\n"
            f"【统计信息】\n"
            f"- 总字符数: {len(raw_text)}\n"
            f"- 空格总数: {space_count}  (首部: {leading_spaces} | 尾部: {trailing_spaces})"
        )

        QMessageBox.information(self, "单元格数据精准核查", msg)

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
        self.parent_panel.handle_file_drop(file_paths)


# =====================================================================
# 🌟 看板主面板
# =====================================================================
def init_node_dashboard_panel(main_app, parent_widget):
    parent_widget.panel_instance = FileDashboardPanel(main_app, parent_widget)


class FileDashboardPanel:
    def __init__(self, main_app, parent_widget):
        self.main_app = main_app
        self.parent = parent_widget

        self.loaded_files = set()
        self.total_parcels = 0

        self.updater = DashboardUpdater()
        self.updater.row_ready_sig.connect(self._update_ui_with_data_slot)
        self.updater.error_sig.connect(self._show_error_slot)
        self.updater.status_sig.connect(self._update_status_slot)

        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self.parent)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 🟥 顶部区域
        top_frame = QFrame()
        top_frame.setFixedHeight(60)
        top_frame.setStyleSheet("background-color: #2c3e50; border: none;")
        top_lyt = QHBoxLayout(top_frame)
        top_lyt.setContentsMargins(20, 0, 20, 0)

        self.lbl_filename = QLabel(" 📥 顶层提示：支持多文件拖拽！【重新拖入新文件时自动刷新清空上次留存】")
        self.lbl_filename.setStyleSheet("color: #ecf0f1; font-size: 14px; font-weight: bold; border: none;")
        top_lyt.addWidget(self.lbl_filename, stretch=1)

        btn_browse = QPushButton("导入文件")
        btn_browse.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_browse.setStyleSheet("""
            QPushButton { background-color: #3498db; color: white; font-weight: bold; padding: 8px 20px; border-radius: 4px; border: none; border-bottom: 3px solid #2980b9; }
            QPushButton:hover { background-color: #2980b9; }
            QPushButton:pressed { border-bottom: 1px solid #2980b9; padding-top: 10px; }
        """)
        btn_browse.clicked.connect(self.open_file_dialog)
        top_lyt.addWidget(btn_browse)

        btn_clear = QPushButton("手动清空")
        btn_clear.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_clear.setStyleSheet("""
            QPushButton { background-color: #e74c3c; color: white; font-weight: bold; padding: 8px 20px; border-radius: 4px; border: none; border-bottom: 3px solid #c0392b; }
            QPushButton:hover { background-color: #c0392b; }
            QPushButton:pressed { border-bottom: 1px solid #c0392b; padding-top: 10px; }
        """)
        btn_clear.clicked.connect(self.manual_clear_click)
        top_lyt.addWidget(btn_clear)

        main_layout.addWidget(top_frame)

        # 🟩 中部表格区域
        table_container = QWidget()
        table_container.setStyleSheet("background-color: #ecf0f1; border: none;")
        table_lyt = QVBoxLayout(table_container)
        table_lyt.setContentsMargins(15, 15, 15, 15)

        self.table = DropTableWidget(self)
        table_lyt.addWidget(self.table)
        main_layout.addWidget(table_container, stretch=1)

        # 🟦 底部数据高亮区
        bottom_frame = QFrame()
        bottom_frame.setFixedHeight(50)
        bottom_frame.setStyleSheet("background-color: #16a085; border: none;")
        bottom_lyt = QHBoxLayout(bottom_frame)
        bottom_lyt.setContentsMargins(20, 0, 0, 0)
        bottom_lyt.setSpacing(0)

        self.lbl_count = QLabel("📊 底层统计：当前累计导入 0 个物流文件")
        self.lbl_count.setStyleSheet("color: white; font-size: 14px; font-weight: bold; border: none;")
        bottom_lyt.addWidget(self.lbl_count, stretch=1)

        total_frame = QFrame()
        total_frame.setStyleSheet("background-color: #e67e22; border: none; border-left: 2px solid #d35400;")
        total_lyt = QHBoxLayout(total_frame)
        total_lyt.setContentsMargins(30, 0, 30, 0)

        self.lbl_total_parcels = QLabel("📦 累计包裹总数: 0")
        self.lbl_total_parcels.setStyleSheet("color: white; font-size: 16px; font-weight: bold; border: none;")
        total_lyt.addWidget(self.lbl_total_parcels)

        bottom_lyt.addWidget(total_frame)
        main_layout.addWidget(bottom_frame)

    # =====================================================================
    # 🌟 核心业务逻辑
    # =====================================================================

    def auto_refresh_clear(self):
        self.loaded_files.clear()
        self.total_parcels = 0
        self.table.setRowCount(0)

        self.lbl_filename.setText(" ⏳ 正在接收新文件并加载数据（多线程后台极速解析中）...")
        self.lbl_filename.setStyleSheet("color: #f1c40f; font-size: 14px; font-weight: bold;")
        self.lbl_count.setText("📊 底层统计：正在重新核算文件数...")
        self.lbl_total_parcels.setText("📦 累计包裹总数: 计算中...")

    def manual_clear_click(self):
        reply = QMessageBox.question(self.parent, "确认", "确定要手动清空看板上的所有数据吗？",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.auto_refresh_clear()
            self.lbl_filename.setText(" 📂 看板已手动清空，请重新拖入文件...")
            self.lbl_filename.setStyleSheet("color: #ecf0f1; font-size: 14px; font-weight: bold;")
            self.lbl_count.setText("📊 底层统计：当前累计导入 0 个物流文件")
            self.lbl_total_parcels.setText("📦 累计包裹总数: 0")

    def handle_file_drop(self, file_paths):
        valid_files = [f for f in file_paths if f.lower().endswith((".xlsx", ".xls", ".csv"))]
        if valid_files:
            self.auto_refresh_clear()
            threading.Thread(target=self.process_multiple_files_async, args=(valid_files,), daemon=True).start()

    def open_file_dialog(self):
        file_paths, _ = QFileDialog.getOpenFileNames(
            self.parent,
            "选择物流轨迹文件(支持多选)",
            "",
            "Logistics Files (*.xlsx *.xls *.csv)"
        )
        if file_paths:
            self.auto_refresh_clear()
            threading.Thread(target=self.process_multiple_files_async, args=(file_paths,), daemon=True).start()

    def process_multiple_files_async(self, file_paths):
        for file_path in file_paths:
            self.process_and_append_file_core(file_path)

    def process_and_append_file_core(self, file_path):
        try:
            filename = os.path.basename(file_path)
            if filename in self.loaded_files: return

            ext = file_path.lower()
            df_first = pd.DataFrame()
            parcel_count = 0

            if ext.endswith(".csv"):
                try:
                    df_first = pd.read_csv(file_path, nrows=1, engine='c', encoding='utf-8')
                except UnicodeDecodeError:
                    df_first = pd.read_csv(file_path, nrows=1, engine='c', encoding='gbk')

                try:
                    with open(file_path, 'rb') as f:
                        parcel_count = sum(chunk.count(b'\n') for chunk in iter(lambda: f.read(1024 * 1024), b'')) - 1
                except Exception:
                    pass
            else:
                try:
                    df = pd.read_excel(file_path, engine="calamine")
                except ImportError:
                    engine = "openpyxl" if ext.endswith(".xlsx") else "xlrd"
                    df = pd.read_excel(file_path, engine=engine)

                parcel_count = len(df)
                df_first = df.iloc[[0]] if not df.empty else pd.DataFrame()

            if parcel_count <= 0 or df_first.empty: return
            first_row = df_first.iloc[0]

            row_data = [filename, str(parcel_count)]
            target_fields = [
                "包裹对应提单号", "头程轨迹上传类型", "包裹二级状态", "轨迹描述",
                "操作时间", "时区", "操作地点", "国家", "机场三字码",
                "机场类型", "航空公司", "航班号"
            ]

            for field in target_fields:
                if field in df_first.columns:
                    val = str(first_row[field])
                    row_data.append("-" if val == "nan" or val.strip() == "" else val)
                else:
                    row_data.append("【缺失】")

            self.updater.row_ready_sig.emit(filename, parcel_count, row_data)

        except Exception as e:
            err_msg = f"解析文件【{os.path.basename(file_path)}】失败:\n{str(e)[:100]}"
            self.updater.error_sig.emit("读取错误", err_msg)

    # =====================================================================
    # 🌟 UI 槽函数
    # =====================================================================

    def _update_ui_with_data_slot(self, filename, parcel_count, row_data):
        if filename in self.loaded_files: return
        self.loaded_files.add(filename)
        self.total_parcels += parcel_count

        row_idx = self.table.rowCount()
        self.table.insertRow(row_idx)

        for col_idx, text in enumerate(row_data):
            item = QTableWidgetItem(str(text))
            align = Qt.AlignmentFlag.AlignCenter if col_idx == 1 else Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
            item.setTextAlignment(align)
            self.table.setItem(row_idx, col_idx, item)

        self.lbl_filename.setText(f" ✅ 最近成功导入文件: {filename}")
        self.lbl_filename.setStyleSheet("color: #ecf0f1; font-size: 14px; font-weight: bold; border: none;")

        self.lbl_count.setText(f"📊 底层统计：当前看板已展示【 {len(self.loaded_files)} 】个文件")
        self.lbl_total_parcels.setText(f"📦 累计包裹总数: {self.total_parcels:,}")

    def _show_error_slot(self, title, msg):
        QMessageBox.showerror(self.parent, title, msg)

    def _update_status_slot(self, text, color):
        self.lbl_filename.setText(text)
        self.lbl_filename.setStyleSheet(f"color: {color}; font-size: 14px; font-weight: bold; border: none;")