import os
import re
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QLabel, QFrame, QTextEdit, QLineEdit, QTableWidget,
                             QTableWidgetItem, QAbstractItemView, QHeaderView,
                             QMessageBox, QApplication, QGridLayout)
from PyQt6.QtCore import Qt, QMimeData
from PyQt6.QtGui import QFont, QCursor, QKeySequence, QShortcut, QColor


# =====================================================================
# 🌟 原生增强：支持文件拖拽的智能数据表格
# =====================================================================
class DropTableWidget(QTableWidget):
    def __init__(self, parent_panel):
        super().__init__()
        self.parent_panel = parent_panel
        self.setAcceptDrops(True)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.verticalHeader().setVisible(False)

        self.setColumnCount(4)
        self.setHorizontalHeaderLabels(["序号", "提单号", "操作时间", "挂载文件名"])

        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(0, 60)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(1, 140)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.setColumnWidth(2, 200)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

        self.setStyleSheet("""
            QTableWidget {
                background-color: white;
                alternate-background-color: #f8f9fa;
                border: 1px solid #ced4da;
                border-radius: 4px;
                font-family: "Microsoft YaHei";
                font-size: 13px;
                gridline-color: #e9ecef;
            }
            QHeaderView::section {
                background-color: #f1f3f5;
                font-weight: bold;
                color: #495057;
                padding: 6px;
                border: 1px solid #dee2e6;
            }
            QTableWidget::item:selected {
                background-color: #cce5ff;
                color: #004085;
            }
        """)
        self.setAlternatingRowColors(True)

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
        paths = [url.toLocalFile() for url in event.mimeData().urls()]
        self.parent_panel.handle_drop(paths)


# =====================================================================
# 🌟 主面板入口
# =====================================================================
def init_node_doc_panel(main_app, parent_widget):
    parent_widget.panel_instance = TrajectoryDocApp(main_app, parent_widget)


class TrajectoryDocApp:
    def __init__(self, main_app, parent_widget):
        self.main_app = main_app
        self.parent = parent_widget

        if not hasattr(self.main_app, 'mounted_database'):
            self.main_app.mounted_database = {}
            self.main_app.match_data = {}
            self.main_app.file_index = 0

        self.setup_ui()
        self.setup_shortcuts()

    def setup_ui(self):
        main_layout = QVBoxLayout(self.parent)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        header = QLabel(" 🛠️ 做轨迹文档模块")
        header.setStyleSheet("""
            background-color: #3498db; 
            color: white; 
            font-size: 16px; 
            font-weight: bold; 
            padding: 15px 20px;
            border-bottom: 2px solid #2980b9;
        """)
        main_layout.addWidget(header)

        workspace = QWidget()
        workspace.setStyleSheet("background-color: #ecf0f1;")
        work_layout = QHBoxLayout(workspace)
        work_layout.setContentsMargins(15, 15, 15, 15)
        work_layout.setSpacing(15)
        main_layout.addWidget(workspace, stretch=1)

        # 🟢 左侧主工作台
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        tools_container = QFrame()
        tools_container.setStyleSheet("background-color: #ffffff; border: 1px solid #ced4da; border-radius: 6px;")
        tools_lyt = QVBoxLayout(tools_container)
        tools_lyt.setContentsMargins(15, 10, 15, 10)
        tools_lyt.setSpacing(8)

        search_lyt = QHBoxLayout()
        lbl_search = QLabel("📋 批量单号输入:")
        lbl_search.setStyleSheet("font-weight: bold; color: #34495e; border: none;")
        self.search_var = QLineEdit()
        self.search_var.setStyleSheet(
            "font-family: Consolas; font-size: 13px; padding: 4px; border: 1px solid #adb5bd; border-radius: 3px;")
        self.search_var.textChanged.connect(self.auto_select_by_bl)

        btn_clear_search = self.create_btn("清空", "#6c757d", "#5a6268", self.clear_search_and_selection)
        btn_select_all = self.create_btn("批量选中", "#198754", "#146c43",
                                         lambda: self.auto_select_by_bl(focus_first=True))

        search_lyt.addWidget(lbl_search)
        search_lyt.addWidget(self.search_var, stretch=1)
        search_lyt.addWidget(btn_clear_search)
        search_lyt.addWidget(btn_select_all)
        tools_lyt.addLayout(search_lyt)

        time_lyt = QHBoxLayout()
        lbl_time = QLabel("⏰ 统一设定时间:")
        lbl_time.setStyleSheet("font-weight: bold; color: #c1121f; border: none;")
        self.global_time_var = QLineEdit()
        self.global_time_var.setStyleSheet(
            "font-family: Consolas; font-size: 13px; padding: 4px; border: 1px solid #adb5bd; border-radius: 3px; color: #c1121f; font-weight: bold;")

        btn_clear_time = self.create_btn("清空", "#6c757d", "#5a6268", lambda: self.global_time_var.clear())
        btn_sync = self.create_btn("同步", "#dc3545", "#b02a37", self.apply_global_time_to_all)

        time_lyt.addWidget(lbl_time)
        time_lyt.addWidget(self.global_time_var, stretch=1)
        time_lyt.addWidget(btn_clear_time)
        time_lyt.addWidget(btn_sync)

        tools_lyt.addLayout(time_lyt)
        left_layout.addWidget(tools_container)

        self.table = DropTableWidget(self)
        left_layout.addWidget(self.table, stretch=1)

        lbl_status = QLabel("🛬 支持清关原单直接拖拽入本表格内挂载...")
        lbl_status.setStyleSheet("font-weight: bold; color: #dc3545; font-size: 12px; margin-top: 5px;")
        left_layout.addWidget(lbl_status)

        btn_grid = QGridLayout()
        btn_grid.setSpacing(10)
        stages_config = [
            ("1. 揽收", "#007bff", "#0056b3"), ("2. 入航司仓", "#28a745", "#1e7e34"),
            ("3. 已起飞", "#17a2b8", "#117a8b"),
            ("4. 到达中转机场", "#ffc107", "#d39e00", True), ("5. 中转机场起飞", "#fd7e14", "#d96400"),
            ("6. 到达目的地机场", "#6f42c1", "#542c91")
        ]
        for i, config in enumerate(stages_config):
            name, bg, hover = config[0], config[1], config[2]
            dark_text = len(config) > 3 and config[3]
            btn = QPushButton(name)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            text_color = "#212529" if dark_text else "#ffffff"
            btn.setStyleSheet(f"""
                QPushButton {{ background-color: {bg}; color: {text_color}; font-weight: bold; padding: 10px; border-radius: 5px; border-bottom: 3px solid {hover}; }}
                QPushButton:hover {{ background-color: {hover}; color: #ffffff; }}
                QPushButton:pressed {{ border-bottom: 1px solid {hover}; padding-top: 12px; }}
            """)
            btn.clicked.connect(lambda checked, idx=i + 1: self.trigger_stage(idx))
            btn_grid.addWidget(btn, i // 3, i % 3)

        left_layout.addLayout(btn_grid)
        work_layout.addLayout(left_layout, stretch=1)

        # 🔴 右侧粘贴匹配框
        right_frame = QFrame()
        right_frame.setFixedWidth(260)
        right_frame.setStyleSheet("background-color: #ffffff; border: 1px solid #ced4da; border-radius: 6px;")
        right_lyt = QVBoxLayout(right_frame)
        right_lyt.setContentsMargins(10, 10, 10, 10)
        right_lyt.setSpacing(10)

        lbl_match = QLabel("【匹配框】数据粘贴区")
        lbl_match.setStyleSheet("font-weight: bold; color: #212529; font-size: 14px; border: none;")
        right_lyt.addWidget(lbl_match)

        self.match_text_box = QTextEdit()
        # 优化缩进尺寸，防止粘贴时自动产生巨大空白
        self.match_text_box.setTabStopDistance(30.0)
        self.match_text_box.setStyleSheet(
            "font-family: Consolas; font-size: 12px; border: 1px solid #ced4da; border-radius: 4px; background-color: #f8f9fa;")
        self.match_text_box.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        right_lyt.addWidget(self.match_text_box, stretch=1)

        match_btn_lyt = QHBoxLayout()
        match_btn_lyt.setSpacing(8)

        btn_match = self.create_btn("匹配", "#0d6efd", "#0a58ca", self.parse_match_data)
        btn_clear_match = self.create_btn("清空", "#6c757d", "#5a6268", lambda: self.match_text_box.clear())

        match_btn_lyt.addWidget(btn_match, stretch=1)
        match_btn_lyt.addWidget(btn_clear_match, stretch=1)
        right_lyt.addLayout(match_btn_lyt)

        work_layout.addWidget(right_frame)

    def create_btn(self, text, bg, border, cmd):
        btn = QPushButton(text)
        btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn.setStyleSheet(f"""
            QPushButton {{ background-color: {bg}; color: white; font-weight: bold; padding: 6px 12px; border-radius: 4px; border-bottom: 2px solid {border}; }}
            QPushButton:hover {{ background-color: {border}; }}
            QPushButton:pressed {{ border-bottom: 1px solid {border}; padding-top: 7px; }}
        """)
        if cmd: btn.clicked.connect(cmd)
        return btn

    def setup_shortcuts(self):
        shortcut = QShortcut(QKeySequence("Ctrl+C"), self.table)
        shortcut.activated.connect(self.copy_selected_bl)

    # =====================================================================
    # 🌟 核心业务交互逻辑：重构为“核弹级智能正则解析”
    # =====================================================================

    def apply_global_time_to_all(self):
        global_time = self.global_time_var.text().strip()
        if not global_time: return
        for row in range(self.table.rowCount()):
            time_item = QTableWidgetItem(global_time)
            time_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            self.table.setItem(row, 2, time_item)
            item_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            if item_id in self.main_app.mounted_database:
                self.main_app.mounted_database[item_id]["op_time"] = global_time

    def clear_search_and_selection(self):
        self.search_var.clear()
        self.table.clearSelection()

    def auto_select_by_bl(self, focus_first=False):
        raw_input = self.search_var.text().strip()
        self.table.clearSelection()
        if not raw_input: return
        extracted_bls = re.findall(r'\d{3}-\d{8}|\d{11}', raw_input)
        if not extracted_bls: extracted_bls = [raw_input.lower()]

        matched_rows = []
        for row in range(self.table.rowCount()):
            bl_item = self.table.item(row, 1)
            if not bl_item: continue
            bl_no = bl_item.text().lower()
            if any(target in bl_no for target in extracted_bls): matched_rows.append(row)

        if matched_rows:
            for r in matched_rows: self.table.selectRow(r)
            if focus_first: self.table.scrollToItem(self.table.item(matched_rows[0], 0))

    def parse_match_data(self):
        raw_text = self.match_text_box.toPlainText().strip()
        if not raw_text: return

        # 🌟 智能正则引擎：提取全世界任何格式的单号与时间（无视空格、换行、连字错乱）
        awb_pattern = r'(\d{3}-\d{8}|\b\d{11}\b)'
        time_pattern = r'(\d{4}[-/]\d{1,2}[-/]\d{1,2}\s+\d{1,2}:\d{2}(?::\d{2})?)'

        # 将文本内所有的单号和时间全部独立抽取出来
        awbs = re.findall(awb_pattern, raw_text)
        times = re.findall(time_pattern, raw_text)

        matched_pairs = []

        # 策略 1：如果抽出的单号数量和时间数量完全一致，完美结对！
        if len(awbs) > 0 and len(awbs) == len(times):
            for a, t in zip(awbs, times):
                self.main_app.match_data[a] = t
                matched_pairs.append(f"{a} ➡️ {t}")
        else:
            # 策略 2：如果混入了杂乱数据导致数量不等，退回保守的逐行解析策略
            for line in raw_text.split("\n"):
                line = line.strip()
                if not line: continue
                line_awb = re.findall(awb_pattern, line)
                line_time = re.findall(time_pattern, line)

                # 同一行里既有单号又有时间
                if line_awb and line_time:
                    a, t = line_awb[0], line_time[0]
                    self.main_app.match_data[a] = t
                    matched_pairs.append(f"{a} ➡️ {t}")
                else:
                    # 兼容极老版本的纯 Tab 暴力分割
                    parts = line.split("\t")
                    if len(parts) >= 2:
                        a, t = parts[0].strip(), parts[1].strip()
                        self.main_app.match_data[a] = t
                        matched_pairs.append(f"{a} ➡️ {t}")

        # 🌟 UI 强迫症治愈：将杂乱无章的粘贴文本，瞬间变身绝美整齐清单！
        if matched_pairs:
            clean_display = "\n".join(matched_pairs)
            self.match_text_box.setPlainText(clean_display)

        # 遍历应用到中央表格
        for row in range(self.table.rowCount()):
            bl_item = self.table.item(row, 1)
            if not bl_item: continue
            bl_val = bl_item.text()

            if bl_val in self.main_app.match_data:
                matched_time = self.main_app.match_data[bl_val]

                time_item = QTableWidgetItem(matched_time)
                time_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                self.table.setItem(row, 2, time_item)

                item_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
                if item_id in self.main_app.mounted_database:
                    self.main_app.mounted_database[item_id]["op_time"] = matched_time

    def handle_drop(self, file_paths):
        self.main_app.file_index = 0
        self.main_app.mounted_database.clear()
        self.table.setRowCount(0)

        for p in file_paths:
            if not os.path.isfile(p): continue
            f_name = os.path.basename(p)
            match = re.search(r'\d{3}-\d{8}|\d{8,11}', f_name)
            bl_no = match.group(0) if match else "未知单号"

            self.main_app.file_index += 1
            current_id = str(self.main_app.file_index)

            row = self.table.rowCount()
            self.table.insertRow(row)

            item_seq = QTableWidgetItem(current_id)
            item_seq.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_seq.setData(Qt.ItemDataRole.UserRole, current_id)
            self.table.setItem(row, 0, item_seq)

            item_bl = QTableWidgetItem(bl_no)
            item_bl.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 1, item_bl)

            item_time = QTableWidgetItem("点击右侧应用时间")
            self.table.setItem(row, 2, item_time)

            item_fname = QTableWidgetItem(f_name)
            self.table.setItem(row, 3, item_fname)

            self.main_app.mounted_database[current_id] = {
                "seq": self.main_app.file_index,
                "bl_no": bl_no,
                "op_time": "",
                "file_name": f_name,
                "file_path": p
            }

    def copy_selected_bl(self):
        selected_items = self.table.selectedItems()
        if not selected_items: return
        selected_rows = sorted(list(set(item.row() for item in selected_items)))
        bl_list = [self.table.item(r, 1).text() for r in selected_rows if self.table.item(r, 1)]
        if bl_list: QApplication.clipboard().setText("\n".join(bl_list))

    def trigger_stage(self, stage_num):
        selected_items = self.table.selectedItems()
        if not selected_items:
            QMessageBox.information(self.parent, "提示", "请选择目标行！")
            return

        selected_rows = set(item.row() for item in selected_items)
        selected_files_db = {}
        for r in selected_rows:
            item_id = self.table.item(r, 0).data(Qt.ItemDataRole.UserRole)
            if item_id in self.main_app.mounted_database:
                selected_files_db[item_id] = self.main_app.mounted_database[item_id]

        try:
            if stage_num == 1:
                from modules.Trajectory.Stages.stage1_pickup import Stage1PickupApp
                Stage1PickupApp(self.parent, selected_files_db=selected_files_db)
            elif stage_num == 2:
                from modules.Trajectory.Stages.stage2_airline_inbound import Stage2AirlineInboundApp
                Stage2AirlineInboundApp(self.parent, selected_files_db=selected_files_db)
            elif stage_num == 3:
                from modules.Trajectory.Stages.stage3_takeoff import Stage3TakeoffApp
                Stage3TakeoffApp(self.parent, selected_files_db=selected_files_db)
            elif stage_num == 4:
                from modules.Trajectory.Stages.stage4_transit_arrive import Stage4TransitArriveApp
                Stage4TransitArriveApp(self.parent, selected_files_db=selected_files_db)
            elif stage_num == 5:
                from modules.Trajectory.Stages.stage5_transit_depart import Stage5TransitDepartApp
                Stage5TransitDepartApp(self.parent, selected_files_db=selected_files_db)
            elif stage_num == 6:
                from modules.Trajectory.Stages.stage6_destination_arrive import Stage6DestinationArriveApp
                Stage6DestinationArriveApp(self.parent, selected_files_db=selected_files_db)
        except Exception as e:
            QMessageBox.critical(self.parent, "模块加载异常",
                                 f"无法启动阶段 {stage_num}，请确保该子模块代码已适配 PyQt。\n错误信息: {str(e)}")