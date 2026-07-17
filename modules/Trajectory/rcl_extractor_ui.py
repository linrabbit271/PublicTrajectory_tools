import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import pandas as pd
import pdfplumber

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                             QLabel, QFrame, QTextEdit, QTableWidget,
                             QTableWidgetItem, QHeaderView, QFileDialog, QMessageBox, QWidget, QApplication)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QCursor


# =====================================================================
# 🌟 底层解析算法：速度狂飙，仅读取首页解析
# =====================================================================
def extract_awb_from_filename(file_path):
    filename = os.path.basename(file_path)
    match = re.search(r"(\d{3})[- ]?(\d{4})[- ]?(\d{4})", filename)
    if match:
        return f"{match.group(1)}-{match.group(2)}{match.group(3)}"
    return "未知单号"


def get_earliest_time(t1_str, t2_str):
    def parse_dt(ts):
        try:
            return datetime.strptime(ts, "%Y/%m/%d %H:%M")
        except:
            return None

    dt1 = parse_dt(t1_str)
    dt2 = parse_dt(t2_str)
    if dt1 and dt2:
        return t1_str if dt1 < dt2 else t2_str
    elif dt1:
        return t1_str
    elif dt2:
        return t2_str
    else:
        return t1_str


def parse_single_pdf(file_path):
    awb_no = extract_awb_from_filename(file_path)
    filename = os.path.basename(file_path)

    months_map = {
        "JAN": "01", "FEB": "02", "MAR": "03", "APR": "04", "MAY": "05", "JUN": "06",
        "JUL": "07", "AUG": "08", "SEP": "09", "OCT": "10", "NOV": "11", "DEC": "12"
    }
    try:
        with pdfplumber.open(file_path) as pdf:
            if not pdf.pages: return {"awb": awb_no, "time": "文件损坏", "filename": filename}

            # 🚀 性能优化：只提取第 1 页进行解析，速度大幅度提档
            full_text = pdf.pages[0].extract_text() or ""
            if not full_text.strip(): return {"awb": awb_no, "time": "图片PDF/需人工", "filename": filename}

            results = {}
            if "AWB Information" in full_text and "RCL Date Time" in full_text:
                awb_matches = list(re.finditer(r"\b(\d{3})[- ]?(\d{4})[- ]?(\d{4})\b", full_text))
                time_matches = list(re.finditer(r"\b(\d{2})([A-Za-z]{3})\s+(\d{4})\b", full_text))
                for am in awb_matches:
                    awb_str = f"{am.group(1)}-{am.group(2)}{am.group(3)}"
                    best_time, min_dist = None, float('inf')
                    for tm in time_matches:
                        if tm.start() > am.end():
                            dist = tm.start() - am.end()
                            if dist < 250 and dist < min_dist:
                                min_dist = dist
                                d, m_str, ht = tm.groups()
                                mon = months_map.get(m_str.upper())
                                if mon:
                                    h, mn = ht[:2], ht[2:]
                                    if int(h) < 24 and int(mn) < 60:
                                        y = datetime.now().year
                                        best_time = f"{y}/{mon}/{d} {h}:{mn}"
                    if best_time:
                        if awb_str in results:
                            results[awb_str] = get_earliest_time(results[awb_str], best_time)
                        else:
                            results[awb_str] = best_time
                if results:
                    first_awb = list(results.keys())[0]
                    return {"awb": first_awb, "time": results[first_awb], "filename": filename}

            awb_match = re.search(r"(?:AWB\s*No[.:]*|提单号码|AWB)[\s\S]{0,80}?(\d{3})[- ]?(\d{4})[- ]?(\d{4})",
                                  full_text, re.IGNORECASE)
            if not awb_match: awb_match = re.search(r"\b(\d{3})[- ]?(\d{4})[- ]?(\d{4})\b", full_text)
            if awb_match: awb_no = f"{awb_match.group(1)}-{awb_match.group(2)}{awb_match.group(3)}"

            date_dg = re.search(r"(?:Received Date|接收日期)[\s\S]{0,100}?(\d{4})[-/.](\d{2})[-/.](\d{2})", full_text,
                                re.IGNORECASE)
            time_dg = re.search(r"(?:Received Time|接收时间)[\s\S]{0,100}?(\d{2})[:.](\d{2})(?:[:.]\d{2})?\b",
                                full_text, re.IGNORECASE)
            if date_dg and time_dg:
                y, m, d = date_dg.groups()
                hr, mn = time_dg.groups()
                if int(hr) < 24 and int(mn) < 60:
                    return {"awb": awb_no, "time": f"{y}/{m}/{d} {hr}:{mn}", "filename": filename}

            dt_aat = re.search(r"RCL Date/Time:[\s\S]{0,50}?(\d{2})([A-Za-z]{3})(\d{2})\s+(\d{2}:\d{2})", full_text)
            if dt_aat:
                d, m_str, y, t = dt_aat.groups()
                mon = months_map.get(m_str.upper())
                if mon: return {"awb": awb_no, "time": f"20{y}/{mon}/{d} {t}", "filename": filename}

            dt_cathay = re.search(r"RCL Date & Time[\s\S]{0,50}?(\d{2})([A-Za-z]{3})(\d{2})\s+(\d{2}:\d{2})", full_text,
                                  re.IGNORECASE)
            if dt_cathay:
                d, m_str, y, t = dt_cathay.groups()
                mon = months_map.get(m_str.upper())
                if mon: return {"awb": awb_no, "time": f"20{y}/{mon}/{d} {t}", "filename": filename}

            matches_hactl = []
            for m in re.finditer(r"\b(\d{2})([A-Za-z]{3})\s+(\d{2})(\d{2})\b", full_text):
                d, m_str, h, mn = m.groups()
                mon = months_map.get(m_str.upper())
                if mon and int(h) < 24 and int(mn) < 60:
                    year = datetime.now().year
                    matches_hactl.append((m.end(), f"{year}/{mon}/{d} {h}:{mn}"))
            if matches_hactl:
                anchor_pattern = r"(RCL Date Time|RCL Date/Time|RCL\s*No)"
                anchor_positions = [m.end() for m in re.finditer(anchor_pattern, full_text, re.IGNORECASE)]
                if anchor_positions:
                    best_date, min_dist = matches_hactl[-1][1], float('inf')
                    for date_pos, date_str in matches_hactl:
                        for anchor_pos in anchor_positions:
                            dist = abs(date_pos - anchor_pos)
                            if dist < min_dist: min_dist = dist; best_date = date_str
                    datetime_str = best_date
                else:
                    datetime_str = matches_hactl[-1][1]
                return {"awb": awb_no, "time": datetime_str, "filename": filename}
            return {"awb": awb_no, "time": "未提取到时间", "filename": filename}
    except Exception:
        return {"awb": awb_no, "time": "解析出错", "filename": filename}


# =====================================================================
# 🌟 空间拖放面板组件
# =====================================================================
class DropLabel(QLabel):
    def __init__(self, parent_window):
        super().__init__()
        self.parent_window = parent_window
        self.setAcceptDrops(True)
        self.setText("\n📂 拖拽 PDF 到此处\n(每次拖入自动清空上次记录)")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("""
            QLabel {
                font-family: 'Microsoft YaHei'; font-size: 13px; font-weight: bold;
                color: #0d6efd; background-color: #e9ecef;
                border: 2px dashed #bdc3c7; border-radius: 6px; padding: 20px;
            }
        """)

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
        files = [url.toLocalFile() for url in event.mimeData().urls() if url.toLocalFile().lower().endswith('.pdf')]
        self.parent_window.handle_drop_files(files)


# =====================================================================
# 🌟 RCL 主窗体入口
# =====================================================================
_rcl_alive_pool = []


def open_rcl_extractor(main_app=None, *args, **kwargs):
    if main_app is None:
        main_app = QApplication.instance()
    win = RclExtractorApp()
    win.show()
    global _rcl_alive_pool
    _rcl_alive_pool.append(win)


class RclExtractorApp(QDialog):
    def __init__(self):
        super().__init__(None)
        self._keep_alive = self
        self.setWindowTitle("RCL 极简提取器 (高吞吐拉伸版)")

        # 允许自由放大，限制最小安全尺寸
        self.setMinimumSize(950, 620)
        self.resize(1050, 700)

        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowMinMaxButtonsHint |
            Qt.WindowType.WindowCloseButtonHint
        )

        self.setStyleSheet("background-color: #f4f6f9;")
        self.file_paths = []
        self.result_list = []
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 15, 20, 15)
        main_layout.setSpacing(12)

        # 1. 顶层表单区
        top_layout = QHBoxLayout()
        top_layout.setSpacing(15)

        left_box = QWidget()
        left_lyt = QVBoxLayout(left_box)
        left_lyt.setContentsMargins(0, 0, 0, 0)
        lbl_t1 = QLabel("1. 拖入 PDF 文件")
        lbl_t1.setStyleSheet("font-weight: bold; color: #34495e; font-size: 13px;")
        left_lyt.addWidget(lbl_t1)
        self.lbl_drop = DropLabel(self)
        left_lyt.addWidget(self.lbl_drop, stretch=1)
        self.lbl_status = QLabel("待导入...")
        self.lbl_status.setStyleSheet("font-weight: bold; color: #6c757d; font-size: 11px;")
        left_lyt.addWidget(self.lbl_status)
        top_layout.addWidget(left_box, stretch=1)

        right_box = QWidget()
        right_lyt = QVBoxLayout(right_box)
        right_lyt.setContentsMargins(0, 0, 0, 0)
        lbl_t2 = QLabel("2. 提单号排序 (可选填)")
        lbl_t2.setStyleSheet("font-weight: bold; color: #34495e; font-size: 13px;")
        right_lyt.addWidget(lbl_t2)
        self.txt_orders = QTextEdit()
        self.txt_orders.setStyleSheet(
            "background-color: white; border: 1px solid #cbd5e1; border-radius: 4px; font-family: 'Consolas';")
        right_lyt.addWidget(self.txt_orders)
        top_layout.addWidget(right_box, stretch=1)
        main_layout.addLayout(top_layout, stretch=2)

        # 2. 中层工具栏
        toolbar = QHBoxLayout()
        toolbar.setSpacing(15)

        self.btn_import = QPushButton(" 📁 导入 PDF ")
        self.btn_import.clicked.connect(self.select_files)
        self.btn_clear = QPushButton(" 🧹 清空 ")
        self.btn_clear.clicked.connect(self.clear_all)
        self.btn_process = QPushButton(" 🚀 提取数据 ")
        self.btn_process.setEnabled(False)
        self.btn_process.clicked.connect(self.process_data)

        self.btn_import.setStyleSheet("""
            QPushButton { background-color: #cbd5e1; color: #333333; border: 1px solid #b1bfc1; border-radius: 4px; border-bottom: 3px solid #94a3b8; }
            QPushButton:hover { background-color: #b2bec3; }
            QPushButton:pressed { border-bottom: 1px solid #94a3b8; padding-top: 8px; }
        """)
        self.btn_clear.setStyleSheet("""
            QPushButton { background-color: #6c757d; color: white; border: 1px solid #5a6268; border-radius: 4px; border-bottom: 3px solid #545b62; }
            QPushButton:hover { background-color: #5a6268; }
            QPushButton:pressed { border-bottom: 1px solid #545b62; padding-top: 8px; }
        """)
        self.btn_process.setStyleSheet("""
            QPushButton { background-color: #198754; color: white; border: 1px solid #157347; border-radius: 4px; border-bottom: 3px solid #146c43; }
            QPushButton:hover { background-color: #157347; }
            QPushButton:pressed { border-bottom: 1px solid #146c43; padding-top: 8px; }
            QPushButton:disabled { background-color: #e2e8f0; color: #94a3b8; border: none; border-bottom: none; }
        """)

        for btn in [self.btn_import, self.btn_clear, self.btn_process]:
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
            btn.setFixedWidth(130)
            btn.setFixedHeight(38)

        toolbar.addWidget(self.btn_import)
        toolbar.addWidget(self.btn_clear)
        toolbar.addWidget(self.btn_process)
        toolbar.addStretch()
        main_layout.addLayout(toolbar)

        # 3. 数据表格展示区 (🌟 重构列配置，将文件名置于最后一列)
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["提单号", "接收时间", "关联文件名预览"])

        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget { 
                border: 1px solid #ced4da; 
                alternate-background-color: #f9f9f9; 
                background-color: white;
                gridline-color: #e2e8f0;
            } 
            QTableWidget::item { padding: 5px; }
            QHeaderView::section { 
                background-color: #f1f2f6; 
                font-weight: bold; 
                font-size: 13px;
                color: #2c3e50;
                border: 1px solid #dcdde1;
                border-top: none;
                border-left: none;
                padding: 6px;
            }
        """)

        self.table.verticalHeader().setDefaultSectionSize(28)
        self.table.verticalHeader().setVisible(True)
        self.table.verticalHeader().setStyleSheet(
            "QHeaderView::section { background-color: #f1f2f6; color: #7f8c8d; text-align: center; font-weight: normal; font-size: 11px; padding: 0 8px; }")

        # 🌟 自适应调教：前两列(提单号/时间)固定比例交互，第三列(文件名)享受最大化自动拉伸
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 160)
        self.table.setColumnWidth(1, 180)

        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.itemClicked.connect(self.on_table_click)

        main_layout.addWidget(self.table, stretch=5)

        # 4. 底层操作输出栏
        action_bar = QHBoxLayout()
        action_bar.setSpacing(15)

        self.btn_copy_awb = self.create_bottom_btn("📄 复制全列单号", "#198754", "#157347", "#146c43", self.copy_awbs)
        self.btn_copy_tab = self.create_bottom_btn("📋 复制完整表", "#0d6efd", "#0b5ed7", "#0a58ca", self.copy_table)
        self.btn_excel = self.create_bottom_btn("📊 导出 Excel", "#ffc107", "#ffca2c", "#e0a800", self.export_excel,
                                                dark_text=True)

        action_bar.addWidget(self.btn_copy_awb)
        action_bar.addWidget(self.btn_copy_tab)
        action_bar.addWidget(self.btn_excel)
        main_layout.addLayout(action_bar)

    def create_bottom_btn(self, text, color, hover_color, press_color, cmd, dark_text=False):
        btn = QPushButton(text)
        btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        btn.setFixedHeight(40)
        tc = "#333333" if dark_text else "white"

        btn.setStyleSheet(f"""
            QPushButton {{ background-color: {color}; color: {tc}; border: 1px solid {hover_color}; border-radius: 4px; border-bottom: 3px solid {press_color}; }}
            QPushButton:hover {{ background-color: {hover_color}; }}
            QPushButton:pressed {{ border-bottom: 1px solid {press_color}; padding-top: 12px; }}
        """)
        btn.clicked.connect(cmd)
        return btn

    def on_table_click(self, item):
        row = item.row()
        awb_item = self.table.item(row, 0)
        if awb_item:
            QApplication.clipboard().setText(awb_item.text())
            self.lbl_status.setText(f"📋 已自动复制提单号: {awb_item.text()}")
            self.lbl_status.setStyleSheet("color: #0d6efd; font-weight: bold;")

    def handle_drop_files(self, files):
        if files:
            self.file_paths = list(set(files))
            self.lbl_status.setText(f"已就绪: {len(self.file_paths)} 份 PDF")
            self.lbl_status.setStyleSheet("color: #198754; font-weight: bold;")
            self.lbl_drop.setText(f"\n✅ 成功接收 {len(self.file_paths)} 份\n")
            self.lbl_drop.setStyleSheet(
                "QLabel { color: #198754; background-color: #e8f5e9; border: 2px dashed #2e7d32; border-radius: 6px; }")
            self.btn_process.setEnabled(True)

    def select_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "选择PDF", "", "PDF Files (*.pdf)")
        if files:
            self.table.setRowCount(0)
            self.handle_drop_files(files)

    def clear_all(self):
        self.file_paths.clear()
        self.result_list.clear()
        self.txt_orders.clear()
        self.table.setRowCount(0)
        self.lbl_status.setText("待导入...")
        self.lbl_status.setStyleSheet("color: #6c757d;")
        self.lbl_drop.setText("\n📂 拖拽 PDF 到此处\n(每次拖入自动清空上次记录)")
        self.lbl_drop.setStyleSheet("""
            QLabel { font-family: 'Microsoft YaHei'; font-size: 13px; font-weight: bold; color: #0d6efd; background-color: #e9ecef; border: 2px dashed #bdc3c7; border-radius: 6px; }
        """)
        self.btn_process.setEnabled(False)

    def process_data(self):
        self.btn_process.setEnabled(False)
        self.btn_process.setText("处理中...")
        QApplication.processEvents()

        self.table.setRowCount(0)
        pdf_data = {}

        # 🚀 24线程全开并发
        with ThreadPoolExecutor(max_workers=24) as executor:
            for res in executor.map(parse_single_pdf, self.file_paths):
                if not res: continue
                awb = res["awb"]
                time_str = res["time"]
                fname = res["filename"]

                if awb not in pdf_data:
                    pdf_data[awb] = {"time": time_str, "filename": fname}
                else:
                    old_time = pdf_data[awb]["time"]
                    new_time = get_earliest_time(old_time, time_str)
                    if new_time == time_str:
                        pdf_data[awb] = {"time": new_time, "filename": fname}

        # 2. 读取可选填排序单号
        orders = [x.strip() for x in self.txt_orders.toPlainText().replace(",", "\n").split() if x.strip()]
        self.result_list.clear()

        if orders:
            parsed_awbs = set(pdf_data.keys())
            for awb in orders:
                meta = pdf_data.get(awb, {"time": "文件未导入", "filename": "—"})
                self.result_list.append({"提单号": awb, "文件名": meta["filename"], "接收时间": meta["time"]})
            for awb in (parsed_awbs - set(orders)):
                self.result_list.append(
                    {"提单号": awb, "文件名": pdf_data[awb]["filename"], "接收时间": pdf_data[awb]["time"]})
        else:
            for awb, meta in pdf_data.items():
                self.result_list.append({"提单号": awb, "文件名": meta["filename"], "接收时间": meta["time"]})

        # 3. 前台表格自适应渲染 (行内容对应新顺序)
        now = datetime.now()
        for item in self.result_list:
            t_str = item["接收时间"]
            is_alert = any(k in t_str for k in ["未", "需", "错", "损"])
            if not is_alert and t_str:
                try:
                    if (now - datetime.strptime(t_str, "%Y/%m/%d %H:%M")).total_seconds() / 3600.0 > 24.0:
                        is_alert = True
                except:
                    pass

            row = self.table.rowCount()
            self.table.insertRow(row)

            i1 = QTableWidgetItem(item["提单号"])
            i2 = QTableWidgetItem(t_str)  # 索引 1: 接收时间
            i3 = QTableWidgetItem(item["文件名"])  # 索引 2: 文件名

            # 排版美化：单号和时间居中，文件名靠左贴边
            i1.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            i2.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            i3.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

            if is_alert:
                for i in [i1, i2, i3]:
                    i.setForeground(Qt.GlobalColor.red)
                    font = i.font()
                    font.setBold(True)
                    i.setFont(font)

            self.table.setItem(row, 0, i1)
            self.table.setItem(row, 1, i2)
            self.table.setItem(row, 2, i3)

        self.btn_process.setEnabled(True)
        self.btn_process.setText(" 🚀 提取数据 ")
        self.lbl_status.setText(f"🎯 提取完成，共获取 {len(pdf_data)} 个不重复单号")
        self.lbl_status.setStyleSheet("color: #198754; font-weight: bold;")

    def copy_awbs(self):
        if not self.result_list: return
        awbs = [item['提单号'] for item in self.result_list]
        QApplication.clipboard().setText("\n".join(awbs))
        QMessageBox.information(self, "成功", "已复制所有提单号，可直接去系统核对！")

    def copy_table(self):
        if not self.result_list: return
        text = "序号\t提单号\t接收时间\t关联文件名\n"
        for idx, item in enumerate(self.result_list, 1):
            text += f"{idx}\t{item['提单号']}\t{item['接收时间']}\t{item['文件名']}\n"
        QApplication.clipboard().setText(text)
        QMessageBox.information(self, "成功", "已复制完整表格，可直接粘贴到 Excel")

    def export_excel(self):
        if not self.result_list: return
        path, _ = QFileDialog.getSaveFileName(self, "导出Excel", "", "Excel Files (*.xlsx)")
        if path:
            df_out = pd.DataFrame(self.result_list)
            df_out.insert(0, "序号", range(1, len(df_out) + 1))
            # 重新调整 DataFrame 输出列的顺序
            df_out = df_out[["序号", "提单号", "接收时间", "文件名"]]
            df_out.to_excel(path, index=False)
            QMessageBox.information(self, "成功", "带原生文件名的报表导出完毕！")

    def closeEvent(self, event):
        self._keep_alive = None
        event.accept()