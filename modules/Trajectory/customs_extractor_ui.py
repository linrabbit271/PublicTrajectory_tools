import os
import re
import gc
import email
from email import policy
from email.utils import parsedate_to_datetime

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QFrame, QTextEdit, QTableWidget,
                             QTableWidgetItem, QHeaderView, QFileDialog, QMessageBox, QWidget, QApplication,
                             QListWidget)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QCursor


# =====================================================================
# 🌟 统一调用入口（主程序专用）
# =====================================================================
def open_customs_extractor(main_app):
    """主程序组件库点击事件绑定的外部调用入口"""
    win = CustomsDataExtractorCoreApp()
    win.show()


# =====================================================================
# 🌟 支持原生拖拽的 Foxmail 邮件挂载队列
# =====================================================================
class DropEmlListWidget(QListWidget):
    def __init__(self, parent_window):
        super().__init__()
        self.parent_window = parent_window
        self.setAcceptDrops(True)
        self.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.setStyleSheet("""
            QListWidget {
                background-color: #f0fcf0;
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                font-family: 'Microsoft YaHei';
                font-size: 13px;
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
        files = [url.toLocalFile() for url in event.mimeData().urls()]
        self.parent_window.handle_drop_files(files)


# =====================================================================
# 🌟 报关自动提取系统主窗体
# =====================================================================
class CustomsDataExtractorCoreApp(QDialog):
    def __init__(self):
        super().__init__(None)
        self._keep_alive = self  # 🌟 强力护盾防内存回收秒退

        self.setWindowTitle("国际货运报关资料自动提取系统")
        self.setFixedSize(1366, 730)

        # 🌟 独立窗口控制（已去除强制置顶，完美恢复自由层级）
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        self.setStyleSheet("background-color: #f8f9fa;")

        # 核心数据缓存
        self.loaded_files = set()
        self.extracted_results = {}
        self.attachments_cache = []

        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 12, 15, 15)
        main_layout.setSpacing(10)

        # ================= 顶部：标准操作向导与重置区 =================
        top_frame = QFrame()
        top_frame.setStyleSheet("background-color: #F0F4F9; border-radius: 4px;")
        top_lyt = QHBoxLayout(top_frame)
        top_lyt.setContentsMargins(15, 6, 15, 6)

        self.lbl_tips = QLabel("操作向导：1. 拖入邮件 ➔ 2. (可选) 输入对账单号 ➔ 3. 复制数据或导出附件。")
        self.lbl_tips.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        self.lbl_tips.setStyleSheet("color: #0055b3; background: transparent;")
        top_lyt.addWidget(self.lbl_tips)
        top_lyt.addStretch()

        btn_global_clear = QPushButton(" 🧹 清空重置 ")
        btn_global_clear.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_global_clear.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        btn_global_clear.setStyleSheet("""
            QPushButton { background-color: #ffe6e6; color: #cc0000; padding: 5px 15px; border: 1px solid #ffcccc; border-radius: 4px; }
            QPushButton:hover { background-color: #ffcccc; }
        """)
        btn_global_clear.clicked.connect(self.manual_clear_all)
        top_lyt.addWidget(btn_global_clear)
        main_layout.addWidget(top_frame)

        # ================= 主体区域：三栏式线性作业工作流 =================
        workspace = QWidget()
        work_lyt = QHBoxLayout(workspace)
        work_lyt.setContentsMargins(0, 0, 0, 0)
        work_lyt.setSpacing(12)

        # ----------- 🟢 【左栏：邮件数据源拖入卡片】 -----------
        left_card = QFrame()
        left_card.setFixedWidth(260)
        left_card.setStyleSheet("background-color: white; border: 1px solid #dee2e6; border-radius: 6px;")
        left_lyt = QVBoxLayout(left_card)
        left_lyt.setContentsMargins(12, 12, 12, 12)
        left_lyt.setSpacing(6)

        lbl_l = QLabel(" 1. 拖入邮件区 ")
        lbl_l.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        lbl_l.setStyleSheet("color: #2c3e50; border: none;")
        left_lyt.addWidget(lbl_l)

        lbl_drop_hint = QLabel("请将 Foxmail 邮件拖入下方：")
        lbl_drop_hint.setFont(QFont("Microsoft YaHei", 9))
        lbl_drop_hint.setStyleSheet("color: blue; border: none;")
        left_lyt.addWidget(lbl_drop_hint)

        self.file_listbox = DropEmlListWidget(self)
        left_lyt.addWidget(self.file_listbox)
        work_lyt.addWidget(left_card)

        # ----------- 🔵 【中栏：标准单号顺序比对卡片】 -----------
        mid_card = QFrame()
        mid_card.setFixedWidth(240)
        mid_card.setStyleSheet("background-color: white; border: 1px solid #dee2e6; border-radius: 6px;")
        mid_lyt = QVBoxLayout(mid_card)
        mid_lyt.setContentsMargins(12, 12, 12, 12)
        mid_lyt.setSpacing(6)

        lbl_m = QLabel(" 2. 对账单号队列 ")
        lbl_m.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        lbl_m.setStyleSheet("color: #2c3e50; border: none;")
        mid_lyt.addWidget(lbl_m)

        lbl_input_hint = QLabel("输入预期的提单号进行对账：\n(支持换行或空格分隔)")
        lbl_input_hint.setFont(QFont("Microsoft YaHei", 9))
        lbl_input_hint.setStyleSheet("color: #1A73E8; border: none;")
        mid_lyt.addWidget(lbl_input_hint)

        self.target_bl_area = QTextEdit()
        self.target_bl_area.setFont(QFont("Consolas", 10))
        self.target_bl_area.setStyleSheet("background-color: #F0F4F9; border: 1px solid #ced4da; border-radius: 4px;")
        mid_lyt.addWidget(self.target_bl_area)

        # 匹配与清空双拼组合按钮
        mid_btn_frame = QWidget()
        mid_btn_frame.setStyleSheet("border: none;")
        mid_btn_lyt = QHBoxLayout(mid_btn_frame)
        mid_btn_lyt.setContentsMargins(0, 0, 0, 0)
        mid_btn_lyt.setSpacing(8)

        self.btn_sort = QPushButton("匹配")
        self.btn_sort.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_sort.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        self.btn_sort.setStyleSheet(
            "QPushButton { background-color: #1A73E8; color: white; padding: 8px; border-radius: 4px; }")
        self.btn_sort.clicked.connect(self.sort_and_compare)
        mid_btn_lyt.addWidget(self.btn_sort)

        self.btn_clear_mid = QPushButton("清空")
        self.btn_clear_mid.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_clear_mid.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        self.btn_clear_mid.setStyleSheet(
            "QPushButton { background-color: #6c757d; color: white; padding: 8px; border-radius: 4px; }")
        self.btn_clear_mid.clicked.connect(lambda: self.target_bl_area.clear())
        mid_btn_lyt.addWidget(self.btn_clear_mid)
        mid_lyt.addWidget(mid_frame_widget := mid_btn_frame)
        work_lyt.addWidget(mid_card)

        # ----------- 🟣 【右栏：综合数据解析看板】 -----------
        right_card = QFrame()
        right_card.setStyleSheet("background-color: white; border: 1px solid #dee2e6; border-radius: 6px;")
        right_lyt = QVBoxLayout(right_card)
        right_lyt.setContentsMargins(12, 12, 12, 12)
        right_lyt.setSpacing(10)

        lbl_r = QLabel(" 3. 数据结果及附件导出 ")
        lbl_r.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        lbl_r.setStyleSheet("color: #2c3e50; border: none;")
        right_lyt.addWidget(lbl_r)

        # 现代数据结果表格组件
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(
            ["序号", "提单号", "服务器接收时间(Received)", "件数", "包裹数", "总毛重", "总体积", "附件状态"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setFont(QFont("Microsoft YaHei", 9))
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setStyleSheet("""
            QTableWidget { background-color: white; border: 1px solid #dee2e6; }
            QHeaderView::section { background-color: #f8f9fa; font-weight: bold; border: 1px solid #dee2e6; padding: 6px; }
        """)
        right_lyt.addWidget(self.table)

        # 底部数据与管理操作组合按钮
        right_btn_frame = QWidget()
        right_btn_frame.setStyleSheet("border: none;")
        right_btn_lyt = QHBoxLayout(right_btn_frame)
        right_btn_lyt.setContentsMargins(0, 0, 0, 0)
        right_btn_lyt.setSpacing(12)

        self.btn_copy = QPushButton("📋 复制表格数据 (可直接粘贴到 Excel)")
        self.btn_copy.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_copy.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        self.btn_copy.setStyleSheet(
            "QPushButton { background-color: #2e7d32; color: white; padding: 10px; border-radius: 5px; }")
        self.btn_copy.clicked.connect(self.copy_to_clipboard)
        right_btn_lyt.addWidget(self.btn_copy, stretch=1)

        self.btn_save_files = QPushButton("💾 批量下载报关附件")
        self.btn_save_files.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_save_files.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        self.btn_save_files.setStyleSheet(
            "QPushButton { background-color: #1565c0; color: white; padding: 10px; border-radius: 5px; }")
        self.btn_save_files.clicked.connect(self.save_attachments)
        right_btn_lyt.addWidget(self.btn_save_files, stretch=1)
        right_lyt.addWidget(right_btn_frame)

        work_lyt.addWidget(right_card, stretch=1)
        main_layout.addWidget(workspace, stretch=1)

    def parse_file_paths(self, data_str):
        paths = re.findall(r'\{(.*?)\}|([^{}\s]+)', data_str)
        cleaned_paths = [p[0].strip() if p[0] else p[1].strip() for p in paths]
        return [p.rstrip(',').rstrip('}').strip() for p in cleaned_paths if p.strip()]

    def handle_drop_files(self, file_paths):
        self.clear_all_silent()
        eml_files = [p for p in file_paths if p.lower().endswith('.eml')]

        if not eml_files:
            QMessageBox.warning(self, "格式不支持", "请拖入正确的 .eml 邮件文件。")
            return

        for path in eml_files:
            self.loaded_files.add(path)
            self.file_listbox.addItem(os.path.basename(path))

        for path in eml_files:
            self.process_single_eml(path)

        self.refresh_table_display()
        self.lbl_tips.setText(f"✅ 刷新成功！当前导入有效邮件: {len(self.loaded_files)} 封。")

    def process_single_eml(self, file_path):
        try:
            with open(file_path, "rb") as f:
                msg = email.message_from_binary_file(f, policy=policy.default)

            mail_date_str = "未知时间"
            received_headers = msg.get_all('Received')
            if received_headers:
                latest_received = received_headers[0]
                if ';' in latest_received:
                    date_part = re.sub(r'\s+', ' ', latest_received.split(';')[-1].strip())
                    try:
                        mail_date_str = parsedate_to_datetime(date_part).strftime("%Y-%m-%d %H:%M:%S")
                    except Exception:
                        pass

            if mail_date_str == "未知时间" and 'Date' in msg:
                try:
                    mail_date_str = parsedate_to_datetime(msg['Date']).strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    mail_date_str = str(msg['Date']).strip()

            body = ""
            body_part = msg.get_body(preferencelist=('plain', 'html'))
            if body_part:
                body = body_part.get_content()
            else:
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_content()
                        break

            bl_match = re.search(r"提单号.*?([\w-]+)", body)
            box_match = re.search(r"大箱个数.*?(\d+)", body)
            pkg_match = re.search(r"包裹个数.*?(\d+)", body)
            weight_match = re.search(r"提单总毛重.*?(\d+(?:\.\d+)?)", body)
            volume_match = re.search(r"总体积.*?(\d+(?:\.\d+)?)", body)

            bl_no = bl_match.group(1).strip() if bl_match else ""
            if not bl_no:
                subject = msg['subject']
                bl_no = subject.split()[
                    0] if subject and subject.split() else f"未知单号({os.path.basename(file_path)[:10]})"

            if bl_no in self.extracted_results and mail_date_str != "未知时间":
                exist_time_str = self.extracted_results[bl_no]["time"]
                if exist_time_str != "未知时间" and mail_date_str <= exist_time_str:
                    return

            boxes = box_match.group(1) if box_match else "0"
            pkgs = pkg_match.group(1) if pkg_match else "0"
            weight = weight_match.group(1) if weight_match else "0"
            volume = volume_match.group(1) if volume_match else "0"

            has_attachments = False
            attach_names = []
            self.attachments_cache = [item for item in self.attachments_cache if item['bl_no'] != bl_no]

            for part in msg.walk():
                if part.get_content_disposition() == 'attachment':
                    filename = part.get_filename()
                    if filename:
                        filename = email.header.decode_header(filename)[0][0]
                        if isinstance(filename, bytes):
                            filename = filename.decode('utf-8', errors='ignore')

                        file_bytes = part.get_payload(decode=True)
                        self.attachments_cache.append({
                            'bl_no': bl_no, 'filename': filename, 'bytes': file_bytes
                        })
                        attach_names.append(filename)
                        has_attachments = True

            attach_status_desc = f"含 {len(attach_names)} 个文件" if has_attachments else "无附件"

            self.extracted_results[bl_no] = {
                "bl_no": bl_no, "time": mail_date_str, "boxes": boxes, "pkgs": pkgs,
                "weight": weight, "volume": volume, "attach_status": attach_status_desc
            }

        except Exception as e:
            err_name = os.path.basename(file_path)
            self.extracted_results[f"IO_ERROR_{err_name}"] = {
                "bl_no": f"错误({err_name})", "time": "ERROR", "boxes": "0", "pkgs": "0",
                "weight": "0", "volume": "0", "attach_status": "异常"
            }

    def refresh_table_display(self, ordered_bl_list=None):
        self.table.setRowCount(0)
        if not self.extracted_results: return

        if not ordered_bl_list:
            ordered_bl_list = list(self.extracted_results.keys())

        for idx, bl in enumerate(ordered_bl_list, 1):
            row = self.table.rowCount()
            self.table.insertRow(row)

            if bl in self.extracted_results:
                res = self.extracted_results[bl]
                vals = [str(idx), res["bl_no"], res["time"], res["boxes"], res["pkgs"], res["weight"], res["volume"],
                        res["attach_status"]]
                for col_idx, val in enumerate(vals):
                    item = QTableWidgetItem(val)
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignCenter if col_idx < 7 else Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                    self.table.setItem(row, col_idx, item)
            else:
                vals = [str(idx), bl, "⚠️ 缺失数据", "0", "0", "0", "0", "无附件"]
                for col_idx, val in enumerate(vals):
                    item = QTableWidgetItem(val)
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignCenter if col_idx < 7 else Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                    item.setForeground(Qt.GlobalColor.red)
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                    self.table.setItem(row, col_idx, item)

    def sort_and_compare(self):
        raw_input = self.target_bl_area.toPlainText().strip()
        if not raw_input:
            QMessageBox.warning(self, "对账提示", "对账队列为空，请输入预期的提单号序列。")
            return

        if not self.extracted_results:
            QMessageBox.warning(self, "对账提示", "当前无提取结果，请先投递邮件数据源。")
            return

        target_bls = [bl.strip() for bl in re.split(r'[\n,，\s\t]+', raw_input) if bl.strip()]

        extracted_bls_set = set(self.extracted_results.keys())
        target_bls_set = set(target_bls)
        extra_bls = list(extracted_bls_set - target_bls_set)

        final_show_list = target_bls + extra_bls
        self.refresh_table_display(final_show_list)

        missing_count = len(target_bls_set - extracted_bls_set)
        alert_msg = f"应收单号：{len(target_bls_set)} 个\n实收单号：{len(extracted_bls_set & target_bls_set)} 个"
        if missing_count > 0: alert_msg += f"\n❌ 缺失单号：{missing_count} 个"
        if extra_bls: alert_msg += f"\n➕ 计划外多出：{len(extra_bls)} 个"

        QMessageBox.information(self, "对账报告", alert_msg)

    def copy_to_clipboard(self):
        rows = ["序号\t提单号\t服务器接收时间\t件数\t包裹数\t总毛重\t总体积\t附件状态"]
        for row in range(self.table.rowCount()):
            row_vals = []
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                row_vals.append(item.text() if item else "")
            rows.append("\t".join(row_vals))

        if len(rows) <= 1:
            QMessageBox.warning(self, "拷贝终止", "结果看板无有效数据。")
            return

        QApplication.clipboard().setText("\n".join(rows))
        QMessageBox.information(self, "成功", "数据已成功复制，可以直接去 Excel 粘贴！")

    def save_attachments(self):
        if not self.attachments_cache:
            QMessageBox.information(self, "提示", "未找到任何可导出的报关附件。")
            return

        target_dir = QFileDialog.getExistingDirectory(self, "选择保存路径")
        if not target_dir: return

        success_save = 0
        for item in self.attachments_cache:
            original_name = item['filename']
            file_bytes = item['bytes']

            safe_name = f"[{item['bl_no']}]_{original_name}"
            safe_name = re.sub(r'[\/:*?"<>|]', '_', safe_name)

            final_path = os.path.join(target_dir, safe_name)
            try:
                with open(final_path, 'wb') as out_f:
                    out_f.write(file_bytes)
                success_save += 1
            except Exception:
                pass

        QMessageBox.information(self, "完成", f"成功保存 {success_save} 个报关文件！")

    def clear_all_silent(self):
        self.loaded_files.clear()
        self.file_listbox.clear()
        self.extracted_results.clear()
        self.attachments_cache.clear()
        self.table.setRowCount(0)
        gc.collect()

    def manual_clear_all(self):
        self.clear_all_silent()
        self.target_bl_area.clear()
        self.lbl_tips.setText("操作向导：1. 拖入邮件 ➔ 2. (可选) 输入对账单号 ➔ 3. 复制数据或导出附件。")
        QMessageBox.information(self, "成功", "数据已全部清空重置。")

    def closeEvent(self, event):
        self._keep_alive = None
        event.accept()