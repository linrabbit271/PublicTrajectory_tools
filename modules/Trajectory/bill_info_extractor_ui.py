import os
import re
import time
import datetime
import threading
import pandas as pd

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                             QLabel, QFrame, QTextEdit, QTableWidget, QTableWidgetItem,
                             QFileDialog, QMessageBox, QWidget, QApplication, QHeaderView)
from PyQt6.QtCore import Qt, QObject, pyqtSignal
from PyQt6.QtGui import QFont, QCursor


# =====================================================================
# 🌟 线程安全通讯器
# =====================================================================
class ExtractorUpdater(QObject):
    finish_sig = pyqtSignal(bool, str, list)


# =====================================================================
# 🌟 统一调用入口
# =====================================================================
def open_bill_info_extractor(main_app):
    win = BillInfoExtractorDialog()
    win.show()


class BillInfoExtractorDialog(QDialog):
    def __init__(self):
        super().__init__(None)
        self._keep_alive = self

        self.setWindowTitle("提单信息提取更新器 (多仓智能融合版) v2.9")
        self.resize(1200, 780)

        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        self.setStyleSheet("background-color: #ecf0f1;")

        self.updater = ExtractorUpdater()
        self.updater.finish_sig.connect(self._process_finish_slot)

        # 核心字段矩阵
        self.cols = [
            "提单号", "地面服务商", "运力服务商", "提货仓库", "资源编码", "航空路由",
            "航班号", "计划起飞时间", "发货时间"
        ]
        self.current_df = pd.DataFrame(columns=self.cols)

        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # ----------------- 布局：上方三个输入框 -----------------
        input_widget = QWidget()
        input_layout = QHBoxLayout(input_widget)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(10)

        def create_input_card(title):
            box = QFrame()
            box.setStyleSheet("background-color: white; border: 1px solid #bdc3c7; border-radius: 4px;")
            box_lyt = QVBoxLayout(box)
            box_lyt.setContentsMargins(10, 8, 10, 8)
            box_lyt.setSpacing(5)

            lbl = QLabel(title)
            lbl.setFont(QFont("Microsoft YaHei", 9, QFont.Weight.Bold))
            lbl.setStyleSheet("color: #2c3e50; border: none;")
            box_lyt.addWidget(lbl)

            txt = QTextEdit()
            txt.setFont(QFont("Consolas", 10))
            txt.setStyleSheet("background-color: #f8f9fa; border: 1px solid #ced4da;")
            box_lyt.addWidget(txt)
            return box, txt

        card_manage, self.txt_manage = create_input_card("1. 提单管理 (抓基础路由/时间/服务商):")
        card_board, self.txt_board = create_input_card("2. 提单在途看板 (抓发货时间/提货仓库):")
        card_transit, self.txt_transit_manage = create_input_card("3. 提单在途管理 (只抓提货仓库):")

        input_layout.addWidget(card_manage)
        input_layout.addWidget(card_board)
        input_layout.addWidget(card_transit)
        main_layout.addWidget(input_widget, stretch=4)

        # ----------------- 布局：中间控制按钮 -----------------
        btn_widget = QWidget()
        btn_layout = QHBoxLayout(btn_widget)
        btn_layout.setContentsMargins(0, 5, 0, 5)
        btn_layout.setSpacing(15)

        self.btn_extract = QPushButton(" 🚀 立即提取并合并数据 ")
        self.btn_clear = QPushButton(" 🧹 清空所有输入与结果 ")
        self.btn_copy_all = QPushButton(" 📋 一键复制全部表格结果 ")
        self.btn_export = QPushButton(" 📂 导出为 Excel 文件 ")

        self.btn_extract.setStyleSheet(
            "QPushButton { background-color: #ff6600; color: white; border-radius: 4px; border: none; }")
        self.btn_clear.setStyleSheet(
            "QPushButton { background-color: #666666; color: white; border-radius: 4px; border: none; }")
        self.btn_copy_all.setStyleSheet(
            "QPushButton { background-color: #007bff; color: white; border-radius: 4px; border: none; }")
        self.btn_export.setStyleSheet(
            "QPushButton { background-color: #28a745; color: white; border-radius: 4px; border: none; }")

        for btn in [self.btn_extract, self.btn_clear, self.btn_copy_all, self.btn_export]:
            btn.setFixedHeight(40)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
            btn_layout.addWidget(btn)

        self.btn_extract.clicked.connect(self.process_data)
        self.btn_clear.clicked.connect(self.clear_all)
        self.btn_copy_all.clicked.connect(self.copy_all_to_clipboard)
        self.btn_export.clicked.connect(self.export_to_excel)
        main_layout.addWidget(btn_widget)

        # ----------------- 布局：下方结果区域 (大列宽旗舰优化) -----------------
        res_card = QFrame()
        res_card.setStyleSheet("background-color: white; border: 1px solid #bdc3c7; border-radius: 4px;")
        res_lyt = QVBoxLayout(res_card)
        res_lyt.setContentsMargins(10, 10, 10, 10)

        lbl_res = QLabel(" 📋 提取合并明细看板 (数据已按计划起飞时间升序规整) ")
        lbl_res.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        lbl_res.setStyleSheet("color: #2c3e50; border: none;")
        res_lyt.addWidget(lbl_res)

        self.table = QTableWidget()
        self.table.setColumnCount(len(self.cols))
        self.table.setHorizontalHeaderLabels(self.cols)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)

        # 开启斑马线
        self.table.setAlternatingRowColors(True)

        self.table.setStyleSheet("""
            QTableWidget { 
                border: 1px solid #ced4da; 
                alternate-background-color: #f9f9f9; 
                background-color: white;
                gridline-color: #e2e8f0;
            } 
            QTableWidget::item {
                padding: 5px;
            }
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

        # 🌟 黄金比例宽度重新划配
        # 列索引分别对应：[提单号(0), 地服(1), 运力(2), 提货仓(3), 资源编码(4), 航空路由(5), 航班号(6), 起飞时间(7), 发货时间(8)]
        col_widths = [115, 110, 110, 120, 220, 100, 95, 135, 160]
        for idx, width in enumerate(col_widths):
            self.table.setColumnWidth(idx, width)

        # 🌟 旗舰拉伸机制：由大幅拓宽后的“发货时间”在最后兜底拉满，吃掉所有右侧空白
        self.table.horizontalHeader().set漲LastSectionBounded = True
        self.table.horizontalHeader().setSectionResizeMode(len(self.cols) - 1, QHeaderView.ResizeMode.Stretch)

        res_lyt.addWidget(self.table)
        main_layout.addWidget(res_card, stretch=6)

    # =====================================================================
    # 🌟 解析原生文本工具库
    # =====================================================================
    def clean_val(self, val):
        if not val: return ""
        val = val.strip()
        return "" if val in ["-", "暂无数据", "暂无"] else val

    def format_time_style(self, time_str):
        if not time_str or time_str.strip() == "": return ""
        time_str = time_str.strip()
        try:
            dt = datetime.datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
            return f"{dt.year}/{dt.month}/{dt.day} {dt.strftime('%H:%M')}"
        except:
            try:
                dt = datetime.datetime.strptime(time_str, "%Y-%m-%d %H:%M")
                return f"{dt.year}/{dt.month}/{dt.day} {dt.strftime('%H:%M')}"
            except:
                return time_str

    def parse_manage(self, text):
        results = []
        if not text.strip(): return results

        if "序号提单号资源编码" in text:
            text = text.split("序号提单号资源编码", 1)[1]
        if "全部提单" in text:
            text = text.split("全部提单", 1)[1]

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        blocks = []
        current_block = []
        start_tracking = False

        for line in lines:
            if re.match(r"^\d+$", line):
                if current_block: blocks.append(current_block)
                current_block = []
                start_tracking = True
            if start_tracking: current_block.append(line)
        if current_block: blocks.append(current_block)

        for b in blocks:
            bill_no = ""
            for item in b[0:5]:
                if re.match(r"^\d{3}-\d+$", item):
                    bill_no = self.clean_val(item)
                    break
            if not bill_no: continue

            route = ""
            for item in b:
                if re.match(r"^[A-Z]{3}(-[A-Z]{3})+$", item):
                    route = item
                    break

            resource_code = ""
            for item in b:
                if item.upper().startswith("YS") or item.upper().startswith("YH"):
                    resource_code = item
                    break

            flight = ""
            for item in b:
                if "一程：" in item:
                    flight = item.replace("一程：", "").strip()
                    break
            if not flight:
                for item in b:
                    if re.match(r"^[A-Z]{2,3}\d[A-Z0-9]*$|^[A-Z]\d[A-Z0-9]+$", item):
                        if item != route and not item.upper().startswith("YS") and not item.upper().startswith("YH"):
                            flight = item
                            break

            valid_times = []
            first_time_idx = -1
            for idx, item in enumerate(b):
                if any(k in item for k in ["原计划:", "提前原因:", "提前时长:", "延误原因:"]):
                    continue
                if re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", item) or re.match(
                        r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}", item):
                    if first_time_idx == -1:
                        first_time_idx = idx
                    valid_times.append(item)

            ground_sp = ""
            capacity_sp = ""
            if first_time_idx >= 2:
                capacity_sp = b[first_time_idx - 1]
                ground_sp = b[first_time_idx - 2]
                if "拆段" in capacity_sp or capacity_sp in ["是", "否", "日运力变更"]: capacity_sp = ""
                if "拆段" in ground_sp or ground_sp in ["是", "否", "日运力变更"]: ground_sp = ""

            takeoff_time = ""
            if len(valid_times) >= 2:
                takeoff_time = valid_times[1]
            elif len(valid_times) == 1:
                takeoff_time = valid_times[0]

            results.append({
                "提单号": bill_no, "资源编码": resource_code, "航空路由": route, "航班号": flight,
                "地面服务商": ground_sp, "运力服务商": capacity_sp,
                "计划起飞时间": self.format_time_style(takeoff_time)
            })
        return results

    def parse_board(self, text):
        results = []
        if not text.strip(): return results

        if "自定义列" in text:
            text = text.split("自定义列", 1)[1]

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        for i, line in enumerate(lines):
            if re.match(r"^\d{3}-\d+$", line):
                bill_no = self.clean_val(line)
                send_time = ""
                warehouse = ""

                for j in range(i + 1, len(lines)):
                    if re.match(r"^\d{3}-\d+$", lines[j]):
                        break
                    if re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", lines[j]):
                        if j - 1 >= 0 and re.match(r"^[A-Z]{3}(-[A-Z]{3})+$", lines[j - 1]):
                            send_time = lines[j]
                    if "仓" in lines[j] and not warehouse:
                        warehouse = lines[j]

                results.append({
                    "提单号": bill_no,
                    "发货时间": self.format_time_style(send_time),
                    "提货仓库": warehouse
                })
        return results

    def parse_transit_manage(self, text):
        results = []
        if not text.strip(): return results

        if "计划提货时间计划起飞时间计划到达时间" in text:
            text = text.split("计划提货时间计划起飞时间计划到达时间", 1)[1]

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        for i, line in enumerate(lines):
            if re.match(r"^\d{3}-\d+$", line):
                bill_no = self.clean_val(line)
                warehouse = ""
                for j in range(i + 1, len(lines)):
                    if re.match(r"^\d{3}-\d+$", lines[j]):
                        break
                    if "仓" in lines[j]:
                        warehouse = lines[j]
                        break
                results.append({"提单号": bill_no, "提货仓库": warehouse})
        return results

    # =====================================================================
    # 🌟 异步业务核心
    # =====================================================================
    def process_data(self):
        raw_manage = self.txt_manage.toPlainText()
        raw_board = self.txt_board.toPlainText()
        raw_transit = self.txt_transit_manage.toPlainText()

        self.btn_extract.setEnabled(False)
        self.btn_extract.setText(" ⏳ 数据融合智能清洗中... ")

        def task(txt_m, txt_b, txt_t):
            try:
                list_manage = self.parse_manage(txt_m)
                list_board = self.parse_board(txt_b)
                list_transit = self.parse_transit_manage(txt_t)

                if not list_manage and not list_board and not list_transit:
                    self.updater.finish_sig.emit(False, "未检测到任何有效的提单数据！", [])
                    return

                all_bill_nos = set()
                if list_manage: all_bill_nos.update([x["提单号"] for x in list_manage])
                if list_board: all_bill_nos.update([x["提单号"] for x in list_board])
                if list_transit: all_bill_nos.update([x["提单号"] for x in list_transit])

                data_map = {b_no: {c: "" for c in self.cols} for b_no in all_bill_nos}

                for item in list_manage:
                    b_no = item["提单号"]
                    if item.get("资源编码"): data_map[b_no]["资源编码"] = item["资源编码"]
                    if item.get("航空路由"): data_map[b_no]["航空路由"] = item["航空路由"]
                    if item.get("航班号"): data_map[b_no]["航班号"] = item["航班号"]
                    if item.get("地面服务商"): data_map[b_no]["地面服务商"] = item["地面服务商"]
                    if item.get("运力服务商"): data_map[b_no]["运力服务商"] = item["运力服务商"]
                    if item.get("计划起飞时间"): data_map[b_no]["计划起飞时间"] = item["计划起飞时间"]

                for item in list_transit:
                    b_no = item["提单号"]
                    if item.get("提货仓库"): data_map[b_no]["提货仓库"] = item["提货仓库"]

                for item in list_board:
                    b_no = item["提单号"]
                    if item.get("发货时间"): data_map[b_no]["发货时间"] = item["发货时间"]
                    if item.get("提货仓库"):
                        existing_wh = data_map[b_no]["提货仓库"]
                        if not existing_wh:
                            data_map[b_no]["提货仓库"] = item["提货仓库"]
                        elif existing_wh != item["提货仓库"]:
                            data_map[b_no]["提货仓库"] = f"{existing_wh}/{item['提货仓库']}"

                final_list = []
                for b_no in all_bill_nos:
                    m_item = data_map[b_no]
                    m_item["提单号"] = b_no
                    final_list.append(m_item)

                self.updater.finish_sig.emit(True, "", final_list)
            except Exception as e:
                self.updater.finish_sig.emit(False, str(e), [])

        threading.Thread(target=task, args=(raw_manage, raw_board, raw_transit), daemon=True).start()

    def _process_finish_slot(self, success, error_msg, result_data):
        self.btn_extract.setEnabled(True)
        self.btn_extract.setText(" 🚀 立即提取并合并数据 ")

        if not success:
            QMessageBox.warning(self, "提示", error_msg)
            return

        final_df = pd.DataFrame(result_data)
        for col in self.cols:
            if col not in final_df.columns: final_df[col] = ""
            final_df[col] = final_df[col].apply(
                lambda x: "" if pd.isna(x) or str(x).strip().lower() == "none" else str(x).strip())

        final_df = final_df.sort_values(by="计划起飞时间").reset_index(drop=True)
        self.current_df = final_df[self.cols]

        # 刷新渲染表格
        self.table.setRowCount(0)
        for _, row in self.current_df.iterrows():
            row_idx = self.table.rowCount()
            self.table.insertRow(row_idx)
            for col_idx, col_name in enumerate(self.cols):
                item = QTableWidgetItem(str(row[col_name]))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row_idx, col_idx, item)

    def clear_all(self):
        self.txt_manage.clear()
        self.txt_board.clear()
        self.txt_transit_manage.clear()
        self.table.setRowCount(0)
        self.current_df = pd.DataFrame(columns=self.cols)

    def copy_all_to_clipboard(self):
        if self.current_df.empty:
            QMessageBox.warning(self, "提示", "当前没有合并的数据可以复制！")
            return
        lines = ["\t".join(self.cols)]
        for _, row in self.current_df.iterrows():
            values = [str(row[col]) if row[col] else "" for col in self.cols]
            lines.append("\t".join(values))

        QApplication.clipboard().setText("\n".join(lines))
        QMessageBox.information(self, "成功", f"已成功复制全部 {len(self.current_df)} 条规整结果！可直接去 Excel 粘贴。")

    def export_to_excel(self):
        if self.current_df.empty:
            QMessageBox.warning(self, "提示", "当前没有数据，无法导出！")
            return
        default_name = f"TMS提单精准合并表_{datetime.datetime.now().strftime('%m%d_%H%M%S')}.xlsx"
        filepath, _ = QFileDialog.getSaveFileName(
            self, "选择要保存 Excel 的位置", default_name, "Excel 文件 (*.xlsx);;所有文件 (*.*)"
        )
        if not filepath: return
        try:
            self.current_df.to_excel(filepath, index=False)
            QMessageBox.information(self, "成功", f"文件已成功保存，共计 {len(self.current_df)} 条数据。")
        except Exception as e:
            QMessageBox.critical(self, "失败", f"文件导出失败: {str(e)}")