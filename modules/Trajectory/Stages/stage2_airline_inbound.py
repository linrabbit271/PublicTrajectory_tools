import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import pandas as pd
import datetime

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton, QProgressBar, QMessageBox, QFrame)
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
class InboundUpdater(QObject):
    progress_sig = pyqtSignal(int, int)  # current, total
    finish_sig = pyqtSignal(int, list)  # success_count, error_msgs


class Stage2AirlineInboundApp(QDialog):
    def __init__(self, parent, selected_files_db):
        super().__init__(None)  # 🌟 修改点1：传入 None，彻底切断与主界面的绑定，获得独立任务栏图标！
        self._keep_alive = self  # 🌟 修改点2：加上这行，防止独立窗口被Python垃圾回收瞬间秒杀！
        self.selected_files_db = selected_files_db

        self.setWindowTitle("📦 入航司仓操作")
        self.setFixedSize(450, 240)

        # =====================================================================
        # 🌟 核心升级：绝对置顶，同时强制唤醒系统的最小化和关闭按钮！
        # =====================================================================
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        self.setStyleSheet("background-color: #f0f2f5;")

        # 初始化安全通讯器
        self.updater = InboundUpdater()
        self.updater.progress_sig.connect(self._update_progress_ui_slot)
        self.updater.finish_sig.connect(self._finish_ui_slot)

        self.setup_ui()
        self.show()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. 顶部横幅 (绿色主题)
        header = QLabel("请输入航班号")
        header.setStyleSheet("""
            background-color: #28a745; 
            color: white; 
            font-size: 14px; 
            font-weight: bold; 
            padding: 12px;
        """)
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(header)

        # 2. 核心容器
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(20, 20, 20, 15)
        content_layout.setSpacing(15)

        # 3. 输入区
        input_frame = QFrame()
        input_lyt = QHBoxLayout(input_frame)
        input_lyt.setContentsMargins(30, 0, 30, 0)

        lbl_flight = QLabel("航班号:")
        lbl_flight.setStyleSheet("font-size: 12px; font-weight: bold; color: #333333;")
        lbl_flight.setFixedWidth(60)
        lbl_flight.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        input_lyt.addWidget(lbl_flight)

        self.entry_flight = QLineEdit()
        self.entry_flight.setStyleSheet("""
            QLineEdit {
                font-family: Arial;
                font-size: 14px;
                font-weight: bold;
                padding: 6px;
                border: 2px solid #ced4da;
                border-radius: 4px;
                background-color: white;
            }
            QLineEdit:focus { border: 2px solid #80bdff; }
        """)
        self.entry_flight.textChanged.connect(self.auto_format)
        input_lyt.addWidget(self.entry_flight)
        content_layout.addWidget(input_frame)

        # 4. 进度条区
        self.progress_frame = QFrame()
        prog_lyt = QVBoxLayout(self.progress_frame)
        prog_lyt.setContentsMargins(0, 0, 0, 0)
        prog_lyt.setSpacing(5)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(15)
        self.progress_bar.setTextVisible(False)
        # 进度条使用和按钮匹配的蓝色主题
        self.progress_bar.setStyleSheet("""
            QProgressBar { border: 1px solid #ced4da; border-radius: 4px; background-color: #e9ecef; }
            QProgressBar::chunk { background-color: #0d6efd; border-radius: 3px; }
        """)
        prog_lyt.addWidget(self.progress_bar)

        self.progress_lbl = QLabel("准备就绪")
        self.progress_lbl.setStyleSheet("font-size: 11px; font-weight: bold; color: #6c757d;")
        self.progress_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        prog_lyt.addWidget(self.progress_lbl)

        self.progress_bar.setValue(0)
        content_layout.addWidget(self.progress_frame)

        # 5. 生成按钮 (蓝色主题)
        self.gen_btn = QPushButton("一键生成轨迹")
        self.gen_btn.setFixedSize(180, 42)  # 🌟 修改点3：强行规定按钮尺寸，足够放下所有文字！
        self.gen_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.gen_btn.setStyleSheet("""
            QPushButton {
                background-color: #0d6efd; /* 此处保留你原文件各自的按钮颜色即可 */
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 0px;  /* 🌟 修改点4：彻底清空内边距，把空间全让给文字 */
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

        self.entry_flight.setFocus()

    def auto_format(self, text):
        """实时转大写并剔除非字母数字及空格字符 (PyQt 安全防死循环版)"""
        cleaned = re.sub(r'[^a-zA-Z0-9\s]', '', text).upper()
        if text != cleaned:
            pos = self.entry_flight.cursorPosition()
            diff = len(text) - len(cleaned)

            self.entry_flight.blockSignals(True)
            self.entry_flight.setText(cleaned)
            self.entry_flight.setCursorPosition(max(0, pos - diff))
            self.entry_flight.blockSignals(False)

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
        flight = self.entry_flight.text().strip()
        if not flight:
            QMessageBox.warning(self, "提示", "航班号不能为空！")
            return

        self.entry_flight.setEnabled(False)
        self.gen_btn.setEnabled(False)
        self.gen_btn.setText("Running...")
        self.status_lbl.hide()

        total_files = len(self.selected_files_db)
        self.progress_bar.setMaximum(total_files)
        self.progress_bar.setValue(0)

        threading.Thread(target=self._run_multithreading, args=(flight,), daemon=True).start()

    def _run_multithreading(self, flight):
        success_count = 0
        error_msgs = []
        completed = 0
        total_files = len(self.selected_files_db)

        update_threshold = max(1, total_files // 20)

        with ThreadPoolExecutor(max_workers=os.cpu_count() or 8) as executor:
            future_to_file = {
                executor.submit(self._giant_table_worker, file_data, flight): file_data
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

    def _giant_table_worker(self, file_data, flight):
        source_path = file_data.get("file_path", "")
        bl_no = file_data.get("bl_no", "未知单号")
        raw_time = file_data.get("op_time", "")

        formatted_time = self.parse_op_time(raw_time)
        if not formatted_time:
            return False, "时间未设置"

        location = "HONG KONG"
        airline = flight.replace(" ", "")[:2].upper()

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
                except ValueError:
                    return False, "无[包裹号]列"
                except ImportError:
                    return False, "缺少处理环境"

            unique_pkgs = df["包裹号"].dropna().astype(str).unique()
            pkg_count = len(unique_pkgs)
            if pkg_count == 0:
                return False, "包裹号为空"

            source_dir = os.path.dirname(source_path)
            output_folder = os.path.join(source_dir, "-2-入航司仓-")
            os.makedirs(output_folder, exist_ok=True)

            output_filepath = os.path.join(output_folder, f"{bl_no} 入航司仓--{pkg_count}.xlsx")

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
                    worksheet.write_string(row_num, 2, "空运货站轨迹")
                    worksheet.write_string(row_num, 3, "入航司仓")
                    worksheet.write_string(row_num, 4, "Inbound by airline")
                    worksheet.write_string(row_num, 5, formatted_time)
                    worksheet.write_string(row_num, 6, "GMT+08:00")
                    worksheet.write_string(row_num, 7, location)
                    worksheet.write_string(row_num, 10, "中国")
                    worksheet.write_string(row_num, 11, "HKG")
                    worksheet.write_string(row_num, 12, "始发机场")
                    worksheet.write_string(row_num, 13, airline)
                    worksheet.write_string(row_num, 14, flight)

                workbook.close()
            else:
                return False, "缺少 xlsxwriter"

            return True, "成功"

        except Exception as e:
            return False, f"处理出错: {str(e)[:15]}"

    # =====================================================================
    # 🌟 槽函数区
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
            QMessageBox.warning(self, "全部失败", f"生成失败，原因:\n{error_text}")

        self.accept()

    def _open_output_folder(self):
        try:
            first_file = list(self.selected_files_db.values())[0]
            target_dir = os.path.join(os.path.dirname(first_file["file_path"]), "-2-入航司仓-")
            if os.path.exists(target_dir):
                os.startfile(target_dir)
        except Exception:
            pass
# 🌟 修改点5：在文件最末尾添加关闭事件拦截，释放内存
    def closeEvent(self, event):
        self._keep_alive = None
        event.accept()