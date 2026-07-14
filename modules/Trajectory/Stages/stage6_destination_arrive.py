import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import pandas as pd
import datetime

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton, QProgressBar, QMessageBox, QFrame, QComboBox, QListView)
from PyQt6.QtCore import Qt, QObject, pyqtSignal
from PyQt6.QtGui import QFont, QCursor

# 尝试加载写盘引擎
try:
    import xlsxwriter

    HAS_XLSXWRITER = True
except ImportError:
    HAS_XLSXWRITER = False

import warnings

warnings.filterwarnings('ignore')


# =====================================================================
# 🌟 线程安全通讯器 (保护 UI 不被后台运算搞崩溃)
# =====================================================================
class DestinationArriveUpdater(QObject):
    progress_sig = pyqtSignal(int, int)  # current, total
    finish_sig = pyqtSignal(int, list)  # success_count, error_msgs


class Stage6DestinationArriveApp(QDialog):
    def __init__(self, parent, selected_files_db):
        # 🌟 传入 None 彻底切断绑定，获得独立任务栏图标
        super().__init__(None)
        self._keep_alive = self  # 防止被Python垃圾回收
        self.selected_files_db = selected_files_db

        self.setWindowTitle("📦 到达目的地机场操作")
        self.setFixedSize(450, 420)  # 容纳 5 个完美对齐的输入项

        # 🌟 核心控制：绝对置顶 + 允许用户独立缩小到任务栏 + 激活关闭 X 键
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        self.setStyleSheet("background-color: #f0f2f5;")

        # 初始化安全通讯器
        self.updater = DestinationArriveUpdater()
        self.updater.progress_sig.connect(self._update_progress_ui_slot)
        self.updater.finish_sig.connect(self._finish_ui_slot)

        self.setup_ui()
        self.show()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. 顶部横幅 (目的地机场专属紫色主题)
        header = QLabel("录入 到达目的地机场 信息")
        header.setStyleSheet("""
            background-color: #6f42c1; 
            color: white; 
            font-size: 15px; 
            font-weight: bold; 
            padding: 12px;
        """)
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(header)

        # 2. 核心容器
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(20, 15, 20, 15)
        content_layout.setSpacing(12)

        # ==================== 3. 完美对齐的表单输入区 ====================
        input_frame = QFrame()
        input_lyt = QVBoxLayout(input_frame)
        input_lyt.setContentsMargins(15, 0, 15, 0)
        input_lyt.setSpacing(10)

        # (1) 时区下拉框
        row_tz = QHBoxLayout()
        lbl_tz = QLabel("时区:")
        lbl_tz.setFixedWidth(100)
        lbl_tz.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lbl_tz.setStyleSheet("font-size: 12px; font-weight: bold; color: #333333;")
        row_tz.addWidget(lbl_tz)

        self.tz_combo = QComboBox()
        self.tz_combo.setView(QListView())  # 强行启动标准滚动视图
        self.tz_combo.setMaxVisibleItems(10)  # 强行限制高度为10项，功能完美适配滚轮
        tz_list = [f"GMT{'+' if i >= 0 else '-'}{abs(i):02d}:00" for i in range(-12, 15)]
        self.tz_combo.addItems(tz_list)
        self.tz_combo.setCurrentText("GMT+08:00")
        self.tz_combo.setStyleSheet("""
            QComboBox {
                font-family: Arial; font-size: 13px; font-weight: bold;
                padding: 5px; border: 2px solid #ced4da; border-radius: 4px;
                background-color: white;
            }
            QComboBox:focus { border: 2px solid #6f42c1; }
            QListView { background-color: white; font-size: 13px; outline: none; }
        """)
        row_tz.addWidget(self.tz_combo)
        input_lyt.addLayout(row_tz)

        # 辅助生成输入框的通用函数，全面防御输入死循环
        def create_input_row(label_text, mode):
            row_lyt = QHBoxLayout()
            lbl = QLabel(label_text)
            lbl.setFixedWidth(100)
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            lbl.setStyleSheet("font-size: 12px; font-weight: bold; color: #333333;")
            row_lyt.addWidget(lbl)

            entry = QLineEdit()
            entry.setStyleSheet("""
                QLineEdit {
                    font-family: Arial; font-size: 13px; font-weight: bold;
                    padding: 6px; border: 2px solid #ced4da; border-radius: 4px;
                    background-color: white;
                }
                QLineEdit:focus { border: 2px solid #6f42c1; }
            """)
            entry.textChanged.connect(lambda text, e=entry, m=mode: self.auto_format(e, text, m))
            row_lyt.addWidget(entry)
            input_lyt.addLayout(row_lyt)
            return entry

        # (2)-(5) 挂载各类正则过滤防线
        self.entry_loc = create_input_row("操作地点(EN):", 'EN_SPACE')
        self.entry_country = create_input_row("国家(仅中文):", 'CN_ONLY')
        self.entry_airport = create_input_row("机场三字码:", 'EN_ONLY')
        self.entry_flight = create_input_row("航班号:", 'FLIGHT')

        content_layout.addWidget(input_frame)
        self.entry_loc.setFocus()

        # ==================== 4. 进度条区 ====================
        self.progress_frame = QFrame()
        prog_lyt = QVBoxLayout(self.progress_frame)
        prog_lyt.setContentsMargins(0, 0, 0, 0)
        prog_lyt.setSpacing(5)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(15)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar { border: 1px solid #ced4da; border-radius: 4px; background-color: #e9ecef; }
            QProgressBar::chunk { background-color: #6f42c1; border-radius: 3px; }
        """)
        prog_lyt.addWidget(self.progress_bar)

        self.progress_lbl = QLabel("准备就绪")
        self.progress_lbl.setStyleSheet("font-size: 11px; font-weight: bold; color: #6c757d;")
        self.progress_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        prog_lyt.addWidget(self.progress_lbl)

        self.progress_bar.setValue(0)
        content_layout.addWidget(self.progress_frame)

        # ==================== 5. 生成按钮 (固定尺寸防文字压折) ====================
        self.gen_btn = QPushButton("一键生成轨迹")
        self.gen_btn.setFixedSize(180, 42)
        self.gen_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.gen_btn.setStyleSheet("""
            QPushButton {
                background-color: #0d6efd;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 0px; 
                border-radius: 6px;
                border: 1px solid #0a58ca;
                border-bottom: 3px solid #084298;
            }
            QPushButton:hover { background-color: #0b5ed7; }
            QPushButton:pressed { border-bottom: 1px solid #084298; padding-top: 12px; }
            QPushButton:disabled { background-color: #6c757d; border-color: #5a6268; border-bottom: 3px solid #495057; color: #e9ecef;}
        """)
        self.gen_btn.clicked.connect(self.start_generation_threads)

        btn_lyt = QHBoxLayout()
        btn_lyt.addStretch()
        btn_lyt.addWidget(self.gen_btn)
        btn_lyt.addStretch()
        content_layout.addLayout(btn_lyt)

        # 6. 底部状态
        content_layout.addStretch()
        self.status_lbl = QLabel(f"已选中 {len(self.selected_files_db)} 个文件待处理")
        self.status_lbl.setStyleSheet("font-size: 11px; color: #6c757d;")
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(self.status_lbl)

        main_layout.addLayout(content_layout)

    # =====================================================================
    # 🌟 严密正则控制机制
    # =====================================================================
    def auto_format(self, widget, text, mode):
        if mode == 'EN_SPACE':
            cleaned = re.sub(r'[^a-zA-Z\s]', '', text).upper()
        elif mode == 'CN_ONLY':
            cleaned = re.sub(r'[^\u4e00-\u9fa5]', '', text)
        elif mode == 'EN_ONLY':
            cleaned = re.sub(r'[^a-zA-Z]', '', text).upper()[:3]
        elif mode == 'FLIGHT':
            cleaned = re.sub(r'[^a-zA-Z0-9]', '', text).upper()
        else:
            cleaned = text

        if text != cleaned:
            pos = widget.cursorPosition()
            diff = len(text) - len(cleaned)
            widget.blockSignals(True)
            widget.setText(cleaned)
            widget.setCursorPosition(max(0, pos - diff))
            widget.blockSignals(False)

    def parse_op_time(self, raw_time):
        if not raw_time or "点击右侧应用时间" in raw_time:
            return None
        try:
            raw_time = str(raw_time).strip()
            if "/" in raw_time:
                dt = datetime.datetime.strptime(raw_time, "%Y/%m/%d %H:%M")
            else:
                dt = datetime.datetime.strptime(raw_time, "%Y-%m-%d %H:%M:%S")
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return None

    def start_generation_threads(self):
        timezone = self.tz_combo.currentText().strip()
        location = self.entry_loc.text().strip()
        country = self.entry_country.text().strip()
        airport = self.entry_airport.text().strip()
        flight = self.entry_flight.text().strip()

        if not all([timezone, location, country, airport, flight]):
            QMessageBox.warning(self, "提示", "所有带框的字段均不能为空！")
            return

        # 锁定表单
        for widget in [self.tz_combo, self.entry_loc, self.entry_country, self.entry_airport, self.entry_flight]:
            widget.setEnabled(False)

        self.gen_btn.setEnabled(False)
        self.gen_btn.setText("Running...")
        self.status_lbl.hide()

        total_files = len(self.selected_files_db)
        self.progress_bar.setMaximum(total_files)
        self.progress_bar.setValue(0)

        threading.Thread(target=self._run_multithreading, args=(timezone, location, country, airport, flight),
                         daemon=True).start()

    def _run_multithreading(self, timezone, location, country, airport, flight):
        success_count = 0
        error_msgs = []
        completed = 0
        total_files = len(self.selected_files_db)

        update_threshold = max(1, total_files // 20)

        with ThreadPoolExecutor(max_workers=os.cpu_count() or 8) as executor:
            future_to_file = {
                executor.submit(self._giant_table_worker, file_data, timezone, location, country, airport,
                                flight): file_data
                for item_id, file_data in self.selected_files_db.items()
            }

            for future in as_completed(future_to_file):
                file_data = future_to_file[future]
                bl_no = file_data.get("bl_no", "未知")
                try:
                    success, error_detail = future.result()
                    if success:
                        success_count += 1
                    else:
                        error_msgs.append(f"{bl_no}: {error_detail}")
                except Exception as e:
                    error_msgs.append(f"{bl_no}: {str(e)[:15]}")

                completed += 1
                if completed % update_threshold == 0 or completed == total_files:
                    self.updater.progress_sig.emit(completed, total_files)

        self.updater.finish_sig.emit(success_count, error_msgs)

    def _giant_table_worker(self, file_data, timezone, location, country, airport, flight):
        source_path = file_data.get("file_path", "")
        bl_no = file_data.get("bl_no", "未知单号")
        raw_time = file_data.get("op_time", "")

        formatted_time = self.parse_op_time(raw_time)
        if not formatted_time:
            return False, "时间未设置"

        airline = flight[:2].upper()

        try:
            if source_path.lower().endswith('.csv'):
                try:
                    df = pd.read_csv(source_path, usecols=["包裹号"], engine='c', encoding='utf-8', low_memory=False)
                except UnicodeDecodeError:
                    df = pd.read_csv(source_path, usecols=["包裹号"], engine='c', encoding='gbk', low_memory=False)
                except ValueError:
                    return False, "无[包裹号]列"
            else:
                try:
                    df = pd.read_excel(source_path, usecols=["包裹号"], engine="calamine")
                except Exception:
                    df = pd.read_excel(source_path, usecols=["包裹号"])

            unique_pkgs = df["包裹号"].dropna().astype(str).unique()
            pkg_count = len(unique_pkgs)
            if pkg_count == 0:
                return False, "包裹号为空"

            source_dir = os.path.dirname(source_path)
            output_folder = os.path.join(source_dir, "-6-到达目的地机场-")
            os.makedirs(output_folder, exist_ok=True)

            output_filepath = os.path.join(output_folder, f"{bl_no} 到达目的地机场--{pkg_count}.xlsx")

            if HAS_XLSXWRITER:
                workbook = xlsxwriter.Workbook(output_filepath, {'constant_memory': True})
                worksheet = workbook.add_worksheet()

                headers = ["包裹号", "包裹对应提单号", "头程轨迹上传类型", "包裹二级状态",
                           "轨迹描述", "操作时间", "时区", "操作地点", "地点经度",
                           "地点纬度", "国家", "机场三字码", "机场类型", "航空公司", "航班号"]

                for col_num, title in enumerate(headers):
                    worksheet.write_string(0, col_num, title)

                for row_num, pkg in enumerate(unique_pkgs, 1):
                    worksheet.write_string(row_num, 0, pkg)
                    worksheet.write_string(row_num, 1, bl_no)
                    worksheet.write_string(row_num, 2, "空运运力轨迹")
                    worksheet.write_string(row_num, 3, "到达目的地机场")
                    worksheet.write_string(row_num, 4, "Arrived at the Destination Airport")
                    worksheet.write_string(row_num, 5, formatted_time)

                    worksheet.write_string(row_num, 6, timezone)
                    worksheet.write_string(row_num, 7, location)
                    worksheet.write_string(row_num, 10, country)
                    worksheet.write_string(row_num, 11, airport)

                    worksheet.write_string(row_num, 12, "目的机场")  # 固定值修改点
                    worksheet.write_string(row_num, 13, airline)
                    worksheet.write_string(row_num, 14, flight)

                workbook.close()
            else:
                return False, "缺少生成环境"

            return True, "成功"

        except Exception as e:
            return False, f"处理出错: {str(e)[:15]}"

    # =====================================================================
    # 🌟 槽函数与完整报错处理逻辑
    # =====================================================================
    def _update_progress_ui_slot(self, current, total):
        self.progress_bar.setValue(current)
        percent = int((current / total) * 100)
        self.progress_lbl.setText(f"已完成: {percent}%")

    def _finish_ui_slot(self, success_count, error_msgs):
        if error_msgs:
            error_text = "\n".join(error_msgs[:6]) + ("\n......" if len(error_msgs) > 6 else "")
            msg = f"成功: {success_count} 份\n失败: {len(error_msgs)} 份\n\n原因:\n{error_text}\n\n是否立即打开生成的文件夹？"
            title = "部分完成"
        else:
            msg = f"成功生成 {success_count} 份文件！\n\n是否立即打开文件夹查看？"
            title = "处理完成"

        if success_count > 0:
            reply = QMessageBox.question(self, title, msg,
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self._open_output_folder()
        else:
            error_text_all = "\n".join(error_msgs[:6]) + ("\n......" if len(error_msgs) > 6 else "")
            QMessageBox.warning(self, "全部失败", f"生成失败，原因:\n{error_text_all}")

        self.accept()

    def closeEvent(self, event):
        self._keep_alive = None
        event.accept()

    def _open_output_folder(self):
        try:
            first_file = list(self.selected_files_db.values())[0]
            target_dir = os.path.join(os.path.dirname(first_file["file_path"]), "-6-到达目的地机场-")
            if os.path.exists(target_dir):
                os.startfile(target_dir)
        except Exception:
            pass