import sys
import os
import time
import requests

# 🌟 核心绝杀：强行咬合 PyInstaller 单文件虚拟解压路径，彻底阻断动态组件闪退
if getattr(sys, 'frozen', False):
    # 如果是打包后的 EXE 运行环境，强制将解压的临时根目录追加进全局搜索路径
    bundle_dir = sys._MEIPASS
    sys.path.append(bundle_dir)
    sys.path.append(os.path.join(bundle_dir, "modules"))
else:
    # 如果是日常在 PyCharm 等编辑器的开发环境
    sys.path.append(os.path.abspath(os.path.dirname(__file__)))



from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QFrame,
                             QStackedWidget, QMessageBox, QDialog, QTextEdit,
                             QGridLayout, QSizePolicy, QSplashScreen, QProgressBar)
from PyQt6.QtCore import Qt, QVariantAnimation, QUrl
from PyQt6.QtGui import QFont, QColor, QPixmap, QDesktopServices  # 🌟 引入系统桌面服务


# =====================================================================
# 🌟 PyQt6 纯血原生高级动态进度条闪屏 (圆汇同款丝滑升级版)
# =====================================================================
class LoadingSplashScreen(QSplashScreen):
    def __init__(self):
        pixmap = QPixmap(420, 240)
        pixmap.fill(QColor("#2c3e50"))
        super().__init__(pixmap)

        self.label = QLabel(" ✈️ 轨迹工具箱运行环境初始化... ", self)
        self.label.setGeometry(20, 135, 380, 25)
        self.label.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        self.label.setStyleSheet("color: #ffffff; background: transparent;")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.progressBar = QProgressBar(self)
        self.progressBar.setGeometry(20, 175, 380, 18)
        self.progressBar.setRange(0, 100)
        self.progressBar.setValue(0)
        # 🌟 隐藏百分比数字，只看流畅推进，更具高级感
        self.progressBar.setTextVisible(False)
        self.progressBar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #34495e;
                border-radius: 6px;
                background-color: #34495e;
            }
            QProgressBar::chunk {
                background-color: #1abc9c; 
                border-radius: 5px;
            }
        """)

        self.title_label = QLabel(" 轨迹专用工具箱 ", self)
        self.title_label.setGeometry(20, 45, 380, 45)
        self.title_label.setFont(QFont("Microsoft YaHei", 18, QFont.Weight.Bold))
        self.title_label.setStyleSheet("color: #1abc9c; background: transparent;")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def setProgress(self, value, text):
        self.progressBar.setValue(value)
        self.label.setText(text)
        # 🌟 核心绝杀：强行刷新 Qt 事件循环，拒绝任何卡顿假死
        QApplication.processEvents()


# =====================================================================
# 🌟 核心接入点：导入前台所有 PyQt6 UI 模块
# =====================================================================
from modules.Trajectory.trajectory_checker_ui import init_node_time_panel
from modules.Trajectory.trajectory_ui import init_node_doc_panel
from modules.Trajectory.file_dashboard_ui import init_node_dashboard_panel
from modules.Trajectory.node_upload_ui import init_node_upload_panel
from modules.Trajectory.node_share_ui import init_node_share_panel
# 🌟 绝杀点：在这里直接明写强引
from modules.Trajectory.rcl_extractor_ui import open_rcl_extractor
CURRENT_VERSION = "v2.014"

# =====================================================================
# 🌟 全局高级立体美化样式表 (QSS)
# =====================================================================
GLOBAL_STYLE = """
QWidget {
    font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
    color: #2c3e50;
}
QDialog { background-color: #f5f7fa; }
QTextEdit {
    background-color: #ffffff;
    border: 1px solid #dcdfe6;
    border-radius: 8px;
    padding: 12px;
    font-size: 13px;
    line-height: 1.6;
    border-bottom: 2px solid #e4e7ed;
}
QFrame#Sidebar {
    background-color: #2c3e50;
    border-right: 1px solid #11171d;
}
QPushButton#NavButton {
    background-color: transparent;
    color: #b2bec3;
    font-weight: bold;
    font-size: 14px;
    text-align: left;
    padding: 14px 20px;
    border: none;
    border-left: 4px solid transparent;
}
QPushButton#NavButton:hover {
    background-color: #34495e;
    color: #ffffff;
    border-left: 4px solid #1abc9c;
}
QPushButton#NavButton:checked {
    background-color: #1ea896;
    color: #ffffff;
    border-left: 4px solid #ffffff;
}
QLabel#EmptyCard {
    background-color: #f8f9fa;
    color: #95a5a6;
    font-size: 13px;
    border: 1px dashed #bdc3c7;
    border-radius: 8px;
}
QPushButton#BtnAgree {
    background-color: #1abc9c; 
    color: #ffffff;            
    font-weight: bold;
    font-size: 14px;
    padding: 8px 25px;
    border-radius: 6px;
    border: 1px solid #16a085;
    border-bottom: 3px solid #117a65; 
}
QPushButton#BtnAgree:hover { background-color: #16a085; }
QPushButton#BtnAgree:pressed { border-bottom: 1px solid #117a65; padding-top: 10px; }

QPushButton#BtnDisagree {
    background-color: #e74c3c; 
    color: #ffffff;            
    font-weight: bold;
    font-size: 14px;
    padding: 8px 20px;
    border-radius: 6px;
    border: 1px solid #c0392b;
    border-bottom: 3px solid #922b21;
}
QPushButton#BtnDisagree:hover { background-color: #c0392b; }
QPushButton#BtnDisagree:pressed { border-bottom: 1px solid #922b21; padding-top: 10px; }

QPushButton#BtnGitHub {
    background-color: #e67e22; 
    color: #ffffff;
    font-weight: bold;
    font-size: 12px; 
    padding: 10px 5px;
    border-radius: 6px;
    border: 1px solid #d35400;
    border-bottom: 3px solid #a04000;
}
QPushButton#BtnGitHub:hover { background-color: #d35400; }
QPushButton#BtnGitHub:pressed { border-bottom: 1px solid #a04000; padding-top: 12px; }
"""


# =====================================================================
# 🌟 动态组件卡片类
# =====================================================================
class AnimatedComponentCard(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setObjectName("ComponentCard")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.ani = QVariantAnimation(self)
        self.ani.setDuration(250)
        self.ani.setStartValue(QColor("#ffffff"))
        self.ani.setEndValue(QColor("#e8edf3"))
        self.ani.valueChanged.connect(self.flush_animated_style)

        self.static_qss = """
            QPushButton {
                color: #2c3e50;
                font-weight: bold;
                font-size: 14px;
                border: 1px solid #dcdfe6;
                border-radius: 8px;
                padding: 15px;
                border-bottom: 3px solid #b2bec3; 
            }
            QPushButton:pressed {
                background-color: #dcdfe6;        
                border-bottom: 1px solid #bdc3c7; 
                padding-top: 18px;                
            }
        """
        self.flush_animated_style(QColor("#ffffff"))

    def flush_animated_style(self, color):
        self.setStyleSheet(f"QPushButton {{ background-color: {color.name()}; }} {self.static_qss}")

    def enterEvent(self, event):
        self.ani.setDirection(QVariantAnimation.Direction.Forward)
        self.ani.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.ani.setDirection(QVariantAnimation.Direction.Backward)
        self.ani.start()
        super().leaveEvent(event)


# =====================================================================
# 🌟 核心授权防线
# =====================================================================
def check_remote_license(splash_widget=None):
    gitee_url = "https://raw.giteeusercontent.com/rabbit_14_0/toolbox-license/raw/master/auth.json"
    github_url = "https://raw.githubusercontent.com/linrabbit271/toolbox-license/refs/heads/main/auth.json"

    if splash_widget:
        # 顺滑推进到 45%
        smooth_progress_to(splash_widget, 31, 45, " 🔐 正在建立双节点安全授权连接... ")

    auth_data = None
    try:
        response = requests.get(gitee_url, timeout=2)
        response.raise_for_status()
        auth_data = response.json()
    except requests.exceptions.RequestException:
        if splash_widget:
            smooth_progress_to(splash_widget, 45, 65, " 🌐 主节点无响应，切入国际备用节点... ")
        try:
            response = requests.get(github_url, timeout=4)
            response.raise_for_status()
            auth_data = response.json()
        except requests.exceptions.RequestException:
            pass

    if auth_data is None:
        if splash_widget: splash_widget.close()
        QMessageBox.critical(None, "网络异常", "无法连接到系统授权服务器，请检查网络后重试。")
        sys.exit(0)

    if auth_data.get("status") != "active":
        if splash_widget: splash_widget.close()
        error_msg = auth_data.get("msg", "系统安全授权已失效，拒绝启动。")
        QMessageBox.critical(None, "授权到期", error_msg)
        sys.exit(0)


# =====================================================================
# 🌟 免责声明弹窗
# =====================================================================
class DisclaimerDialog(QDialog):
    def __init__(self):
        super().__init__()
        import qtawesome as qta
        self.setWindowIcon(qta.icon('fa5s.balance-scale', color='#e74c3c'))
        self.setWindowTitle("软件使用授权与免责声明")
        self.setFixedSize(680, 580)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        banner = QLabel(" ⚠️ 软件最终用户许可协议与技术免责声明 ")
        banner.setStyleSheet("""
            background-color: #e74c3c;
            color: white; 
            padding: 15px; 
            font-weight: bold; 
            font-size: 16px;
            border-bottom: 2px solid #c0392b;
        """)
        banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(banner)

        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(25, 20, 25, 10)
        content_layout.setSpacing(15)

        text_area = QTextEdit()
        text_area.setReadOnly(True)

        disclaimer_text = (
            "欢迎使用本自动化工具箱。在进入系统前，请务必仔细阅读并理解以下条款。点击“我同意并进入系统”即代表您及您代表的机构自愿接受以下所有约束：\n\n"
            "1. 版权归属与个人自研声明\n"
            "本插件（包括但不限于所有底层架构、图形识别算法及核心代码）属于原开发者个人独立自研的技术资产，其完整版权、所有权及最终解释权永久归属原作者个人所有。本插件未与任何机构或雇主签署排他性交付协议。原作者当前仅以技术交流与模拟测试目的，授予使用者临时的、非排他性的使用许可。原作者保留在任何时间，无条件收回、终止或撤销授权的绝对权利。\n\n"
            "2. 技术资产保护与禁止滥用\n"
            "未经原作者书面明确授权，任何组织或个人对本插件进行破解、反编译、逆向工程、篡改或将其用于商业售卖。本插件仅供技术学习与个人日常办公效能提升之用，任何机构或个人不得将本插件用于非合规的大规模高频轰炸或恶意扰乱第三方系统运行的场景。\n\n"
            "3. 业务风险与第三方平台变动完全免责\n"
            "本插件作为纯个人研究项目，按“现状（AS-IS）”提供，原作者不对其功能的稳定性、绝对无错性做任何技术担保。因第三方圆汇客户端更新升级、界面UI像素调整导致插件失效，或因使用者日常操作不当、误操作引发的任何业务纠纷、数据清洗偏差、经济损失或平台风控处罚，全部风险与法律责任均由使用者自行承担，原开发者不承担任何直接或连带的赔偿责任。\n\n"
            "4. 无技术支持义务与永久责任豁免\n"
            "作为个人自研的免费技术试验品，原作者没有义务对本插件提供长期的技术支持、缺陷修复、版本更新或环境维护。无论在何种时间、何种运行环境下，由本插件引发的任何形式的技术故障、工作延误或业务流转异常，原作者均享有永久、完全且无条件的民事与刑事责任豁免权。"
        )
        text_area.setText(disclaimer_text)
        content_layout.addWidget(text_area)
        main_layout.addLayout(content_layout)

        btn_frame = QFrame()
        btn_layout = QHBoxLayout(btn_frame)
        btn_layout.setContentsMargins(25, 10, 25, 25)
        btn_layout.setSpacing(15)
        btn_layout.addStretch()

        btn_agree = QPushButton(" 我同意并进入系统 ")
        btn_agree.setObjectName("BtnAgree")
        btn_agree.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_agree.clicked.connect(self.accept)

        btn_disagree = QPushButton(" 不同意并退出 ")
        btn_disagree.setObjectName("BtnDisagree")
        btn_disagree.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_disagree.clicked.connect(self.reject)

        btn_layout.addWidget(btn_agree)
        btn_layout.addWidget(btn_disagree)

        main_layout.addWidget(btn_frame)

    def closeEvent(self, event):
        self.reject()


# =====================================================================
# 🌟 主程序界面
# =====================================================================
class LogisticsToolboxApp(QMainWindow):
    def __init__(self):
        super().__init__()
        import qtawesome as qta
        self.setWindowIcon(qta.icon('fa5s.plane', color='#1abc9c'))
        self.setWindowTitle(f"物流轨迹集成工具箱 {CURRENT_VERSION}")
        self.resize(1200, 750)
        self.center_window()

        self.match_data = {}
        self.file_index = 0
        self.mounted_database = {}

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.setup_sidebar(main_layout)

        self.container = QStackedWidget()
        self.container.setStyleSheet("background-color: #ecf0f1; border-left: 1px solid #dcdfe6;")
        main_layout.addWidget(self.container, stretch=1)

        self.pages = {}
        self.nav_buttons = {}

        self.create_pages()
        self.show_page("node1")

    def center_window(self):
        qr = self.frameGeometry()
        cp = self.screen().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    def setup_sidebar(self, layout):
        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(190)

        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 15)
        sidebar_layout.setSpacing(0)

        lbl_title = QLabel("工作节点导航")
        lbl_title.setStyleSheet("""
            color: #ffffff; 
            font-weight: bold; 
            font-size: 15px; 
            padding: 22px 20px;
            background-color: #212f3d;
            border-bottom: 1px solid #1a252f;
        """)
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        sidebar_layout.addWidget(lbl_title)
        sidebar_layout.addSpacing(10)

        self.nav_layout = sidebar_layout
        layout.addWidget(self.sidebar)

    def create_nav_button(self, text, page_id, is_extension=False):
        btn = QPushButton(text)
        btn.setObjectName("NavButton")
        btn.setCheckable(True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)

        if is_extension:
            btn.setStyleSheet("""
                QPushButton#NavButton {
                    background-color: #2980b9; color: white; font-size: 14px; padding: 14px 20px; border:none;
                }
                QPushButton#NavButton:hover { background-color: #3449db; }
                QPushButton#NavButton:checked { background-color: #1a5276; font-weight: bold;}
            """)

        btn.clicked.connect(lambda: self.show_page(page_id))
        self.nav_layout.addWidget(btn)
        self.nav_buttons[page_id] = btn
        return btn

    def create_pages(self):
        nodes_config = [
            ("node1", "1、查时间", self.init_node_time),
            ("node2", "2、做轨迹文档", self.init_node_doc),
            ("node3", "3、上传文档", self.init_node_upload),
            ("node4", "4、更新共享表", self.init_node_share),
            ("node5", "5、文件看板", self.init_node_dashboard)
        ]

        for page_id, btn_text, init_func in nodes_config:
            self.create_nav_button(btn_text, page_id)
            page_widget = QWidget()
            init_func(page_widget)
            self.pages[page_id] = page_widget
            self.container.addWidget(page_widget)

        self.nav_layout.addSpacing(15)

        self.create_nav_button("🧩 扩展组件库", "components", is_extension=True)
        comp_page = QWidget()
        self.init_node_components(comp_page)
        self.pages["components"] = comp_page
        self.container.addWidget(comp_page)

        self.nav_layout.addStretch()

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("background-color: #455a64; margin: 10px 15px;")
        self.nav_layout.addWidget(line)

        lbl_version = QLabel(f"当前版本: {CURRENT_VERSION}")
        lbl_version.setStyleSheet("color: #7f8c8d; font-size: 11px; margin-bottom: 5px;")
        lbl_version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.nav_layout.addWidget(lbl_version)

        update_wrap = QWidget()
        update_wrap_layout = QVBoxLayout(update_wrap)
        update_wrap_layout.setContentsMargins(15, 0, 15, 10)

        btn_github = QPushButton("🌐 前往 GitHub 下载")
        btn_github.setObjectName("BtnGitHub")
        btn_github.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_github.clicked.connect(self.visit_github_repository)

        update_wrap_layout.addWidget(btn_github)
        self.nav_layout.addWidget(update_wrap)

    def show_page(self, page_id):
        self.container.setCurrentWidget(self.pages[page_id])
        for p_id, btn in self.nav_buttons.items():
            btn.setChecked(p_id == page_id)

    def visit_github_repository(self):
        repo_url = "https://github.com/linrabbit271/PublicTrajectory_tools"
        QDesktopServices.openUrl(QUrl(repo_url))

    def init_node_time(self, parent_widget):
        init_node_time_panel(self, parent_widget)

    def init_node_doc(self, parent_widget):
        init_node_doc_panel(self, parent_widget)

    def init_node_upload(self, parent_widget):
        init_node_upload_panel(self, parent_widget)

    def init_node_share(self, parent_widget):
        init_node_share_panel(self, parent_widget)

    def init_node_dashboard(self, parent_widget):
        init_node_dashboard_panel(self, parent_widget)

    def init_node_components(self, parent_widget):
        layout = QVBoxLayout(parent_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QLabel("  🧩 扩展组件库面板")
        header.setStyleSheet("""
            background-color: #34495e; 
            color: white; 
            font-size: 16px; 
            font-weight: bold; 
            padding: 15px 20px;
            border-bottom: 2px solid #2c3e50;
        """)
        layout.addWidget(header)

        grid_container = QWidget()
        grid_layout = QGridLayout(grid_container)
        grid_layout.setContentsMargins(30, 30, 30, 30)
        grid_layout.setSpacing(20)
        layout.addWidget(grid_container, stretch=1)

        buttons_config = [
            ("✈️\n国泰160提取", lambda: __import__("modules.Trajectory.cathay_160_ui", fromlist=["open_cathay_160"]).open_cathay_160(self)),
            ("✈️\n994提取", lambda: __import__("modules.Trajectory.airzeta_994_ui", fromlist=["open_airzeta_994"]).open_airzeta_994(self)),
            ("✈️\n297提取", lambda: __import__("modules.Trajectory.china_airlines_297_ui", fromlist=["open_china_airlines_297"]).open_china_airlines_297(self)),
            ("🧾\n爱德文提单提取", lambda: __import__("modules.Trajectory.bill_info_extractor_ui", fromlist=["open_bill_info_extractor"]).open_bill_info_extractor(self)),
            ("🏢\n圆汇提单信息", lambda: __import__("modules.Trajectory.yuanhui_extractor_ui", fromlist=["open_yuanhui_extractor"]).open_yuanhui_extractor(self)),
            ("🛒\nTemu运单提取", lambda: __import__("modules.Trajectory.temu_scraper_ui", fromlist=["open_temu_scraper"]).open_temu_scraper(self)),
            ("📄\n报关资料提取", lambda: __import__("modules.Trajectory.customs_extractor_ui", fromlist=["open_customs_extractor"]).open_customs_extractor(self)),
            ("📦\n扣件分流", lambda: __import__("modules.Trajectory.customs_detention_ui", fromlist=["open_customs_detention"]).open_customs_detention(self)),
            ("📦\n按箱扣件", lambda: __import__("modules.Trajectory.carton_detention_worker", fromlist=["open_carton_detention"]).open_carton_detention(self)),
            ("⏱️\n装货时间提取", lambda: __import__("modules.Trajectory.loading_time_extractor_ui", fromlist=["open_loading_time_extractor"]).open_loading_time_extractor(self)),
            ("⏱️\nRCL提取器", lambda: open_rcl_extractor(self)),
            ("📧\n邮件转换器", lambda: __import__("modules.Trajectory.email_converter_ui", fromlist=["open_email_converter"]).open_email_converter(self)),
            ("🖼️\n图片分发", lambda: __import__("modules.Trajectory.image_copier_ui", fromlist=["open_image_copier"]).open_image_copier(self)),
            ("✈️\nHACTL", lambda: __import__("modules.Trajectory.hactl_extractor_ui", fromlist=["open_hactl_extractor"]).open_hactl_extractor(self)),
            ("📦\nOCR提取", lambda: __import__("modules.Trajectory.ocr_extractor_ui", fromlist=["open_ocr_extractor"]).open_ocr_extractor(self)),
            ("📁\n工作舱初始化", lambda: __import__("modules.Trajectory.folder_initializer_ui", fromlist=["open_folder_initializer"]).open_folder_initializer(self)),
        ]

        for i in range(20):
            row, col = i // 4, i % 4
            grid_layout.setRowStretch(row, 1)
            grid_layout.setColumnStretch(col, 1)

            if i < len(buttons_config):
                text, cmd = buttons_config[i]
                btn = AnimatedComponentCard(text)
                btn.clicked.connect(cmd)
                grid_layout.addWidget(btn, row, col)
            else:
                lbl = QLabel("➕\n待添入组件")
                lbl.setObjectName("EmptyCard")
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                grid_layout.addWidget(lbl, row, col)


# =====================================================================
# 🌟 进度条顺滑渐进器（圆汇同款：不假死、超流畅、不卡顿）
# =====================================================================
def smooth_progress_to(splash_widget, start_val, end_val, text_info, step_delay=0.012):
    """
    通过 Qt 事件循环无感刷新，将进度条从 start_val 极度丝滑地推送到 end_val
    """
    if not splash_widget:
        return
    for val in range(start_val, end_val + 1):
        splash_widget.setProgress(val, text_info)
        time.sleep(step_delay)


# =====================================================================
# 🌟 主系统总控入口
# =====================================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(GLOBAL_STYLE)

    # 1. 初始化闪屏
    splash = LoadingSplashScreen()
    splash.show()

    # 2. 丝滑运行环境装载（第一阶段：0% -> 30%）
    smooth_progress_to(splash, 0, 15, " ⚙️ 正在挂载全局核心总线... ")
    smooth_progress_to(splash, 16, 30, " 📂 正在索引外部轨迹扩展资产... ")

    # 3. 双节点安全授权检查（第二阶段：30% -> 80% 会在 check_remote_license 内部接力推送）
    check_remote_license(splash)

    # 4. 授权通过，完成最后装箱（第三阶段：80% -> 100%）
    smooth_progress_to(splash, 81, 95, " 🔒 远程安全防线匹配通过... ")
    smooth_progress_to(splash, 96, 100, " 🎉 初始化就绪 ")
    time.sleep(0.15)

    # 5. 阻断弹出个人自研法律协议
    disclaimer = DisclaimerDialog()
    if disclaimer.exec() == QDialog.DialogCode.Accepted:
        main_window = LogisticsToolboxApp()
        splash.finish(main_window)
        main_window.show()
        sys.exit(app.exec())
    else:
        sys.exit(0)