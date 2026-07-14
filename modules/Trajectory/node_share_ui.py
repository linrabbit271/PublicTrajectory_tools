import sys
import re
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QTextEdit, QPushButton, QFrame, QTableWidget,
                             QTableWidgetItem, QHeaderView, QMenu, QMessageBox, QApplication)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QCursor, QKeySequence


def init_node_share_panel(main_app, parent):
    """
    接入主系统的总入口
    parent 此时是主系统传过来的 QWidget 容器
    """
    # 建立布局并挂载当前 PyQt6 界面
    layout = parent.layout()
    if not layout:
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(0, 0, 0, 0)

    # 清理历史残余组件，防止界面重叠
    while layout.count():
        child = layout.takeAt(0)
        if child.widget():
            child.widget().deleteLater()

    panel = NodeShareApp(parent)
    layout.addWidget(panel)


class NodeShareApp(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        # 整体纵向大布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- 顶栏 Header ---
        header = QLabel(" 📊 节点四：更新共享表 (提单一致性比对)")
        header.setFont(QFont("Microsoft YaHei", 15, QFont.Weight.Bold))
        header.setStyleSheet("""
            background-color: #e67e22; 
            color: white; 
            padding: 15px 20px;
            border: none;
        """)
        main_layout.addWidget(header)

        # --- 核心工作区卡片 ---
        content_frame = QFrame()
        content_frame.setStyleSheet("background-color: #ecf0f1;")
        content_layout = QHBoxLayout(content_frame)
        content_layout.setContentsMargins(25, 20, 25, 20)
        content_layout.setSpacing(20)

        # ==================== 左侧：输入区域 ====================
        left_layout = QVBoxLayout()
        left_layout.setSpacing(15)

        # 左上：提单管理页面混乱文本
        web_card = QFrame()
        web_card.setStyleSheet("background-color: white; border: 1px solid #bdc3c7; border-radius: 4px;")
        web_card_layout = QVBoxLayout(web_card)
        web_card_layout.setContentsMargins(10, 8, 10, 10)

        lbl_web = QLabel("1. 粘贴【提单管理页面】的混乱文本:")
        lbl_web.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        lbl_web.setStyleSheet("color: #e74c3c; border: none;")
        web_card_layout.addWidget(lbl_web)

        self.web_text = QTextEdit()
        self.web_text.setFont(QFont("Consolas", 10))
        self.web_text.setStyleSheet("background-color: #fdfefe; border: 1px solid #dcdde1;")
        web_card_layout.addWidget(self.web_text)
        left_layout.addWidget(web_card, stretch=1)

        # 左下：用户共享表提单号
        user_card = QFrame()
        user_card.setStyleSheet("background-color: white; border: 1px solid #bdc3c7; border-radius: 4px;")
        user_card_layout = QVBoxLayout(user_card)
        user_card_layout.setContentsMargins(10, 8, 10, 10)

        lbl_user = QLabel("2. 粘贴【共享表】中的标准提单号 (每行一个):")
        lbl_user.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        lbl_user.setStyleSheet("color: #2980b9; border: none;")
        user_card_layout.addWidget(lbl_user)

        self.user_text = QTextEdit()
        self.user_text.setFont(QFont("Consolas", 11))
        self.user_text.setStyleSheet("background-color: #f8f9fa; border: 1px solid #dcdde1;")
        user_card_layout.addWidget(self.user_text)
        left_layout.addWidget(user_card, stretch=1)

        content_layout.addLayout(left_layout, stretch=1)

        # ==================== 右侧：操作与结果区域 ====================
        right_layout = QVBoxLayout()
        right_layout.setSpacing(15)

        # 执行比对卡片
        action_card = QFrame()
        action_card.setStyleSheet("background-color: white; border: 1px solid #bdc3c7; border-radius: 4px;")
        action_card_layout = QVBoxLayout(action_card)
        action_card_layout.setContentsMargins(15, 12, 15, 15)

        lbl_action = QLabel("3. 执行比对")
        lbl_action.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        lbl_action.setStyleSheet("color: #2c3e50; border: none;")
        action_card_layout.addWidget(lbl_action)

        lbl_tip = QLabel("💡 规则: 提单管理页面的提单号绝不允许比共享表多。")
        lbl_tip.setFont(QFont("Microsoft YaHei", 9))
        lbl_tip.setStyleSheet("color: #7f8c8d; border: none;")
        action_card_layout.addWidget(lbl_tip)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.btn_compare = QPushButton("🔍 开始比对")
        self.btn_compare.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        self.btn_compare.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_compare.setStyleSheet("""
            QPushButton { background-color: #d35400; color: white; border-radius: 4px; padding: 8px; }
            QPushButton:hover { background-color: #e67e22; }
        """)
        self.btn_compare.clicked.connect(self.run_comparison)
        btn_layout.addWidget(self.btn_compare)

        self.btn_clear = QPushButton("🗑 清空所有")
        self.btn_clear.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        self.btn_clear.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_clear.setStyleSheet("""
            QPushButton { background-color: #bdc3c7; color: #2c3e50; border-radius: 4px; padding: 8px; }
            QPushButton:hover { background-color: #cacfda; }
        """)
        self.btn_clear.clicked.connect(self.clear_all)
        btn_layout.addWidget(self.btn_clear)

        action_card_layout.addLayout(btn_layout)
        right_layout.addWidget(action_card)

        # 结果输出区卡片
        result_card = QFrame()
        result_card.setStyleSheet("background-color: white; border: 1px solid #bdc3c7; border-radius: 4px;")
        result_card_layout = QVBoxLayout(result_card)
        result_card_layout.setContentsMargins(15, 12, 15, 15)

        self.result_title = QLabel("比对结果 (等待执行...)")
        self.result_title.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        self.result_title.setStyleSheet("color: #2c3e50; border: none;")
        result_card_layout.addWidget(self.result_title)

        # 明显的比对状态大字报
        self.status_lbl = QLabel("")
        self.status_lbl.setFont(QFont("Microsoft YaHei", 16, QFont.Weight.Bold))
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_lbl.setStyleSheet("border: none;")
        result_card_layout.addWidget(self.status_lbl)

        # 替代 Tkinter Treeview 的 PyQt6 原生表格组件
        self.table = QTableWidget()
        self.table.setColumnCount(1)
        self.table.setHorizontalHeaderLabels(["差异提单号 (属于提单管理多出的)"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setFont(QFont("Consolas", 11))
        self.table.setStyleSheet("""
            QTableWidget { background-color: white; border: 1px solid #dcdde1; }
            QHeaderView::section { background-color: #f2f2f2; font-weight: bold; border: 1px solid #dcdde1; padding: 5px; }
        """)
        # 允许自由多选，禁止编辑
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        # 绑定复制快捷键 Ctrl+C 与 右键菜单
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_table_menu)
        result_card_layout.addWidget(self.table)

        # 一键复制底部操作区
        copy_all_layout = QHBoxLayout()
        copy_all_layout.addStretch()

        self.btn_copy_all = QPushButton("📋 一键复制所有差异单号")
        self.btn_copy_all.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        self.btn_copy_all.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_copy_all.setStyleSheet("""
            QPushButton { background-color: #16a085; color: white; border-radius: 4px; padding: 6px 15px; }
            QPushButton:hover { background-color: #1abc9c; }
        """)
        self.btn_copy_all.clicked.connect(self.copy_all_from_table)
        copy_all_layout.addWidget(self.btn_copy_all)

        result_card_layout.addLayout(copy_all_layout)
        right_layout.addWidget(result_card, stretch=1)

        content_layout.addLayout(right_layout, stretch=1)
        main_layout.addWidget(content_frame, stretch=1)

    # ================= 快捷键重写 =================
    def keyPressEvent(self, event):
        if event.matches(QKeySequence.StandardKey.Copy):
            self.copy_from_table()
            event.accept()
        else:
            super().keyPressEvent(event)

    # ================= 业务核心逻辑 =================
    def extract_awbs_from_text(self, text):
        """正则匹配提取标准的 11 位提单号 (xxx-xxxxxxxx)"""
        pattern = r'\d{3}-\d{8}'
        matches = re.findall(pattern, text)
        return set(matches)

    def run_comparison(self):
        web_raw = self.web_text.toPlainText().strip()
        user_raw = self.user_text.toPlainText().strip()

        if not web_raw:
            QMessageBox.warning(self, "提示", "请先粘贴提单管理页面的文本！")
            return

        # 1. 提取网页文本中的所有标准提单号
        web_awb_set = self.extract_awbs_from_text(web_raw)

        # 2. 提取用户输入的提单号进行二次过滤清洗
        user_awb_list = [line.strip() for line in user_raw.split('\n') if line.strip()]
        user_awb_set = self.extract_awbs_from_text('\n'.join(user_awb_list))

        # 清空现有的表格数据
        self.table.setRowCount(0)

        # 3. 核心差集运算：找出【在网页里有，但用户表里没有】的单号
        diff_awbs = web_awb_set - user_awb_set

        if not diff_awbs:
            # 无差异
            self.status_lbl.setText("✅ 对比无差异，提单提取完毕")
            self.status_lbl.setStyleSheet("color: #27ae60; border: none; font-weight: bold;")
            self.result_title.setText(f"比对结果 (网页共解析到 {len(web_awb_set)} 个单号)")
        else:
            # 有差异
            self.status_lbl.setText("❌ 对比有差异！")
            self.status_lbl.setStyleSheet("color: #c0392b; border: none; font-weight: bold;")
            self.result_title.setText(f"提单管理 (发现 {len(diff_awbs)} 个异常单号)")

            # 将多出来的单号装填入表格
            for row_idx, awb in enumerate(sorted(list(diff_awbs))):
                self.table.insertRow(row_idx)
                item = QTableWidgetItem(awb)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row_idx, 0, item)

    def clear_all(self):
        self.web_text.clear()
        self.user_text.clear()
        self.table.setRowCount(0)
        self.status_lbl.setText("")
        self.result_title.setText("比对结果 (等待执行...)")

    # ================= 复制功能支持 =================
    def show_table_menu(self, pos):
        # 创建右键菜单
        menu = QMenu(self)
        copy_action = menu.addAction("📋 复制选中的提单号")
        copy_action.triggered.connect(self.copy_from_table)
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def copy_from_table(self):
        selected_ranges = self.table.selectedRanges()
        if not selected_ranges:
            return

        copy_values = []
        for rg in selected_ranges:
            for row in range(rg.topRow(), rg.bottomRow() + 1):
                item = self.table.item(row, 0)
                if item:
                    copy_values.append(item.text())

        if copy_values:
            copy_str = '\n'.join(copy_values)
            QApplication.clipboard().setText(copy_str)
            QMessageBox.information(self, "复制成功", f"已成功复制 {len(copy_values)} 个选中提单号！")

    def copy_all_from_table(self):
        row_count = self.table.rowCount()
        if row_count == 0:
            QMessageBox.warning(self, "提示", "当前没有差异单号可以复制！")
            return

        copy_values = []
        for row in range(row_count):
            item = self.table.item(row, 0)
            if item:
                copy_values.append(item.text())

        if copy_values:
            copy_str = '\n'.join(copy_values)
            QApplication.clipboard().setText(copy_str)
            QMessageBox.information(self, "复制成功", f"✅ 已成功复制全部 {len(copy_values)} 个差异提单号！")