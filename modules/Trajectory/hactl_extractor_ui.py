import os
import sys
import json
import time
import threading
import traceback
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                             QLabel, QFrame, QTextEdit, QTableWidget, QTableWidgetItem,
                             QMessageBox, QWidget, QApplication, QHeaderView)
from PyQt6.QtCore import Qt, QObject, pyqtSignal
from PyQt6.QtGui import QFont, QCursor


# =====================================================================
# 🌟 原生核心工具库 (100% 字节级保留您的算法逻辑)
# =====================================================================
def get_browser_config():
    """实时读取用户在 UI 界面配置的路径 - 增加强风控校验"""
    config_path = "browser_config.json"
    # 🌟 严格尊照核心指示：斩断盲猜的 D 盘保底路径，只在当前工作目录下探测 json 资产
    if not os.path.exists(config_path):
        return None
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            chrome = cfg.get("CHROME_PATH", "")
            driver = cfg.get("DRIVER_PATH", "")
            # 强风控：如果任何一个字段为空，直接触发不全判定
            if not chrome or not driver:
                return None
            return chrome, driver, cfg.get("USER_DATA_DIR", "")
    except:
        return None


def parse_hactl_json_time(raw_time_str):
    """将 JSON 中的 30061104 转换为 2026/6/30 11:04"""
    if not raw_time_str or len(str(raw_time_str)) != 8:
        return "-"
    try:
        d = int(raw_time_str[0:2])
        m = int(raw_time_str[2:4])
        h = int(raw_time_str[4:6])
        mn = raw_time_str[6:8]
        y = datetime.now().year
        return f"{y}/{m}/{d} {h}:{mn}"
    except:
        return raw_time_str


def format_flight_date(flt_no, flt_date):
    """将 MP9412 和 3006 组合成 MP9412 / 30Jun"""
    if not flt_no or flt_no == "-": return "-"
    if not flt_date or len(str(flt_date)) != 4: return flt_no
    months = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    try:
        d = int(flt_date[0:2])
        m = int(flt_date[2:4])
        return f"{flt_no} / {d:02d}{months[m]}"
    except:
        return f"{flt_no} / {flt_date}"


# =====================================================================
# 🌟 线程安全通讯器 (完全替代 Toplevel 里的 win.after 时序调度)
# =====================================================================
class HactlUpdater(QObject):
    row_sig = pyqtSignal(tuple)  # 动态吐入行数据的信号
    status_sig = pyqtSignal(str, str)  # 更新底部就绪状态 (文本, 颜色)
    finish_sig = pyqtSignal(str, str)  # 流程完毕通知 (提示信息, 颜色)


# =====================================================================
# 🌟 统一调用入口
# =====================================================================
def open_hactl_extractor(*args, **kwargs):
    # 🌟 核心第一闸门：触发接口前死等检测，找不到或配置不全当场拦截弹窗，绝不默认盲猜
    cfg_test = get_browser_config()
    if cfg_test is None:
        QMessageBox.critical(
            None, "配置缺失",
            "错误：未能在系统根目录下检测到有效的 'browser_config.json' 或配置项残缺！\n\n请先前往【时间节点设置】界面完整配置并保存浏览器与驱动路径！"
        )
        return

    win = HactlExtractorDialog()
    win.show()


class HactlExtractorDialog(QDialog):
    def __init__(self):
        super().__init__(None)
        self._keep_alive = self  # 独立进程实体保活护盾

        self.setWindowTitle("HACTL 货站信息提取器")
        self.resize(950, 680)

        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        self.setStyleSheet("background-color: #f0f2f5;")

        # 核心定义列（对齐上一款大列宽旗舰排版布局）
        self.cols = ["提单号", "类型", "起始地", "目的地", "状态", "件数", "重量(kg)", "航班", "时间"]

        self.updater = HactlUpdater()
        self.updater.row_sig.connect(self._row_slot)
        self.updater.status_sig.connect(self._status_slot)
        self.updater.finish_sig.connect(self._finish_slot)

        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)

        # 1. 输入区域
        lbl_input = QLabel("1. 输入 HACTL 提单号 (支持批量，一行一个):")
        lbl_input.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        lbl_input.setStyleSheet("color: #333;")
        main_layout.addWidget(lbl_input)

        self.txt_input = QTextEdit()
        self.txt_input.setFont(QFont("Consolas", 11))
        self.txt_input.setStyleSheet("background-color: white; border: 1px solid #bdc3c7; border-radius: 3px;")
        self.txt_input.setFixedHeight(120)
        main_layout.addWidget(self.txt_input)

        # 2. 控制按钮栏排版
        btn_widget = QWidget()
        btn_layout = QHBoxLayout(btn_widget)
        btn_layout.setContentsMargins(0, 5, 0, 5)
        btn_layout.setSpacing(10)

        self.btn_extract = QPushButton(" ⚡ 内存 API 极速提取 ")
        self.btn_clear = QPushButton(" 🗑 清空 ")
        self.btn_copy = QPushButton(" 📋 一键复制结果 ")

        # 配色调教
        self.btn_extract.setStyleSheet(
            "QPushButton { background-color: #198754; color: white; border-radius: 4px; border: none; }")
        self.btn_clear.setStyleSheet(
            "QPushButton { background-color: #6c757d; color: white; border-radius: 4px; border: none; }")
        self.btn_copy.setStyleSheet(
            "QPushButton { background-color: #0d6efd; color: white; border-radius: 4px; border: none; }")

        for btn in [self.btn_extract, self.btn_clear, self.btn_copy]:
            btn.setFixedHeight(40)
            btn.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.btn_extract.setFixedWidth(200)
        self.btn_clear.setFixedWidth(100)
        self.btn_copy.setFixedWidth(160)

        self.btn_extract.clicked.connect(self.start_extraction)
        self.btn_clear.clicked.connect(self.clear_all)
        self.btn_copy.clicked.connect(self.copy_results)

        self.lbl_status = QLabel("准备就绪")
        self.lbl_status.setFont(QFont("Microsoft YaHei", 10))
        self.lbl_status.setStyleSheet("color: #6c757d;")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        btn_layout.addWidget(self.btn_extract)
        btn_layout.addWidget(self.btn_clear)
        btn_layout.addStretch(1)
        btn_layout.addWidget(self.lbl_status)
        btn_layout.addWidget(self.btn_copy)
        main_layout.addWidget(btn_widget)

        # 3. 结果明细看板 (大列宽旗舰排版微调)
        self.table = QTableWidget()
        self.table.setColumnCount(len(self.cols))
        self.table.setHorizontalHeaderLabels(self.cols)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)

        # 隔行变色
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
        self.table.verticalHeader().setVisible(True)  # 侧边栏

        # 重新调配列宽
        col_widths = [120, 80, 80, 80, 160, 60, 80, 120]
        for idx, width in enumerate(col_widths):
            self.table.setColumnWidth(idx, width)

        # 智能拉伸最后一列（时间），吃满死白区域
        self.table.horizontalHeader().set漲LastSectionBounded = True
        self.table.horizontalHeader().setSectionResizeMode(len(self.cols) - 1, QHeaderView.ResizeMode.Stretch)

        main_layout.addWidget(self.table)

    # ================= UI 辅助交互槽函数 =================
    def clear_all(self):
        self.txt_input.clear()
        self.table.setRowCount(0)
        self.lbl_status.setText("已清空")
        self.lbl_status.setStyleSheet("color: #6c757d;")

    def copy_results(self):
        row_count = self.table.rowCount()
        if row_count == 0: return

        text_data = "\t".join(self.cols) + "\n"
        for r in range(row_count):
            row_vals = []
            for c in range(len(self.cols)):
                item = self.table.item(r, c)
                row_vals.append(item.text() if item else "")
            text_data += "\t".join(row_vals) + "\n"

        QApplication.clipboard().setText(text_data)
        QMessageBox.information(self, "成功", "已完整复制结果，可直接粘贴到 Excel！")

    def start_extraction(self):
        raw_text = self.txt_input.toPlainText().strip()
        if not raw_text: return

        # 🌟 核心安全盾：使用 splitlines() 彻底斩断换行符中的 \r 毒素，防止单号带毒
        awb_list = [line.strip() for line in raw_text.splitlines() if line.strip()]
        if not awb_list: return

        self.btn_extract.setEnabled(False)
        self.btn_extract.setText("⏳ 正在黑入货站底层...")
        self.table.setRowCount(0)

        threading.Thread(target=self.run_api_hijack, args=(awb_list,), daemon=True).start()

    # ================= 信号异步更新槽函数 =================
    def _row_slot(self, data_tuple):
        row_idx = self.table.rowCount()
        self.table.insertRow(row_idx)
        for col_idx, text in enumerate(data_tuple):
            item = QTableWidgetItem(str(text))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)  # 规整全列居中
            self.table.setItem(row_idx, col_idx, item)

    def _status_slot(self, status_text, color_hex):
        self.lbl_status.setText(status_text)
        self.lbl_status.setStyleSheet(f"color: {color_hex};")

    def _finish_slot(self, msg, color_hex):
        self.btn_extract.setEnabled(True)
        self.btn_extract.setText("⚡ 内存 API 极速提取")
        self.lbl_status.setText(msg)
        self.lbl_status.setStyleSheet(f"color: {color_hex};")
        QMessageBox.information(self, "完成", msg)

    # =====================================================================
    # 🌟 核心黑客劫持引擎 (100% 还原异步 JavaScript Fetch 全景注入)
    # =====================================================================
    def run_api_hijack(self, awb_list):
        # 走到这一步，外面已经拦截并校验过，cfg 绝对100%安全且完整
        CHROME_PATH, DRIVER_PATH, USER_DATA_DIR = get_browser_config()

        options = Options()
        options.binary_location = CHROME_PATH
        options.add_argument('--headless=new')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument(
            'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

        service = Service(executable_path=DRIVER_PATH)
        driver = None

        try:
            driver = webdriver.Chrome(service=service, options=options)
            driver.set_script_timeout(15)

            self.updater.status_sig.emit("正在获取合法通行证...", "#0d6efd")
            driver.get("https://cargo.hactl.com/site/en-US/overview.html?mode=ct")
            time.sleep(2)

            total = len(awb_list)
            for idx, awb in enumerate(awb_list, 1):
                clean_awb = awb.replace("-", "").strip()
                if len(clean_awb) < 11:
                    self.updater.row_sig.emit((awb, "-", "-", "-", "单号格式错误", "-", "-", "-", "-"))
                    continue

                prefix, suffix = clean_awb[:3], clean_awb[-8:]
                self.updater.status_sig.emit(f"正在解析 {awb} ({idx}/{total})...", "#0d6efd")

                js_fetch = """
                var prefix = arguments[0];
                var suffix = arguments[1];
                var callback = arguments[2];

                fetch("https://cplus.hactl.com/cplusservice/hacnetdata/public/cargoTrackingFasSvc", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json;charset=UTF-8"
                    },
                    body: JSON.stringify({
                        "jsonrpc":"2.0",
                        "method":"findHactlCargo",
                        "id":1,
                        "params":[{"awbPrefix": prefix, "awbSuffix": suffix}]
                    })
                })
                .then(res => res.json())
                .then(data => callback(JSON.stringify(data)))
                .catch(err => callback(JSON.stringify({error: err.message})));
                """

                raw_json_str = driver.execute_async_script(js_fetch, prefix, suffix)
                res_json = json.loads(raw_json_str)

                # 深入执行你原汁原味的 JSON 大字典业务切片
                if "result" in res_json and res_json["result"]:
                    result = res_json["result"]

                    flow = result.get("flow", "-")
                    type_str = "Export" if flow == "E" else ("Import" if flow == "I" else flow)
                    orig = result.get("origin", "-")
                    dest = result.get("destination", "-")
                    dep_lines = result.get("departureLines", [])

                    if not dep_lines:
                        rcv_pcs = result.get("totalReceivedPcs", "-")
                        rcv_wt = result.get("totalReceivedWt", "-")
                        self.updater.row_sig.emit(
                            (awb, type_str, orig, dest, "Accepted(无航班明细)", rcv_pcs, rcv_wt, "-", "-"))
                    else:
                        for line in dep_lines:
                            status_code = line.get("departedStatus", "")
                            status_str = "Departed" if status_code == "D" else (
                                "Awaiting Departure" if status_code == "A" else status_code)

                            pcs = line.get("departedPcs", "-")
                            wt = line.get("departedWt", "-")
                            flt_no = line.get("departedFltNo", "-")
                            flt_date = line.get("departedFltDate", "")
                            raw_time = line.get("departedFltActualTime", "")

                            flt_info = format_flight_date(flt_no, flt_date)
                            fmt_time = parse_hactl_json_time(raw_time)

                            self.updater.row_sig.emit(
                                (awb, type_str, orig, dest, status_str, pcs, wt, flt_info, fmt_time))

                elif "error" in res_json:
                    self.updater.row_sig.emit(
                        (awb, "-", "-", "-", f"劫持失败: {res_json['error']}", "-", "-", "-", "-"))
                else:
                    self.updater.row_sig.emit((awb, "-", "-", "-", "无数据或仍被拦截 (返回 null)", "-", "-", "-", "-"))

            self.updater.finish_sig.emit("✅ HACTL数据解析提取完毕！", "#198754")

        except Exception as e:
            err_msg = str(e).strip()[:50]
            self.updater.finish_sig.emit(f"劫持崩溃: {err_msg}", "#dc3545")
            print(traceback.format_exc())
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass

    def closeEvent(self, event):
        self._keep_alive = None
        event.accept()