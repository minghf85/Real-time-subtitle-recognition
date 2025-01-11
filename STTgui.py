import sys
import pyaudio
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QComboBox, QPushButton, QLabel,
                            QFrame, QGraphicsDropShadowEffect, QProgressBar,
                            QDoubleSpinBox, QCheckBox, QGroupBox, QSpinBox,
                            QColorDialog, QMessageBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QPoint, QTimer
from PyQt6.QtGui import QColor
from RealtimeSTT import AudioToTextRecorder
import re
import ollama
import time
from queue import Queue, Empty
from threading import Thread

class StyleHelper:
    # 磨砂质感配色
    MAIN_BG = "rgba(28, 28, 35, 0.95)"
    CARD_BG = "rgba(40, 40, 50, 0.8)"
    ACCENT = "#7C76F2"
    TEXT = "#FFFFFF"
    SUBTEXT = "rgba(255, 255, 255, 0.7)"
    
    @staticmethod
    def get_button_style(primary=False):
        if primary:
            return """
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                                              stop:0 #7C76F2, stop:1 #A5A1FF);
                    color: white;
                    border: none;
                    border-radius: 8px;
                    padding: 12px 24px;
                    font-weight: bold;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                                              stop:0 #8E88FF, stop:1 #B3B0FF);
                }
            """
        else:
            return """
                QPushButton {
                    background-color: rgba(255, 255, 255, 0.1);
                    color: white;
                    border: 1px solid rgba(255, 255, 255, 0.2);
                    border-radius: 8px;
                    padding: 12px 24px;
                    font-weight: bold;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background-color: rgba(255, 255, 255, 0.15);
                }
            """

    @staticmethod
    def get_combo_style():
        return """
            QComboBox {
                background-color: rgba(255, 255, 255, 0.1);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 8px;
                padding: 8px 12px;
                min-width: 150px;
            }
            QComboBox::drop-down {
                border: none;
                padding-right: 20px;
            }
            QComboBox::down-arrow {
                image: none;
            }
            QComboBox QListView {
                background-color: rgb(40, 40, 50);
                color: white;
                border-radius: 8px;
                outline: none;
            }
            QComboBox QListView::item:selected {
                background-color: rgba(124, 118, 242, 0.6);
            }
        """

    @staticmethod
    def get_spinbox_style():
        return """
            QDoubleSpinBox {
                background-color: rgba(255, 255, 255, 0.1);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 8px;
                padding: 8px 12px;
                min-height: 20px;
            }
            QDoubleSpinBox::up-button {
                width: 20px;
                background-color: transparent;
                subcontrol-position: right top;
                margin-top: 2px;
                margin-right: 2px;
            }
            QDoubleSpinBox::down-button {
                width: 20px;
                background-color: transparent;
                subcontrol-position: right bottom;
                margin-bottom: 2px;
                margin-right: 2px;
            }
        """

    @staticmethod
    def get_checkbox_style():
        return """
            QCheckBox {
                color: white;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 1px solid rgba(255, 255, 255, 0.2);
                background: rgba(255, 255, 255, 0.1);
            }
            QCheckBox::indicator:checked {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                                          stop:0 #7C76F2, stop:1 #A5A1FF);
            }
        """

    @staticmethod
    def get_group_box_style():
        return """
            QGroupBox {
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 8px;
                margin-top: 12px;
                font-weight: bold;
                padding: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 5px;
            }
        """

class GlassCard(QFrame):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {StyleHelper.CARD_BG};
                border-radius: 16px;
                border: 1px solid rgba(255, 255, 255, 0.1);
            }}
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(0, 0, 0, 40))
        shadow.setOffset(0, 8)
        self.setGraphicsEffect(shadow)

class SubtitleWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # 设置默认大小和位置
        screen = QApplication.primaryScreen().geometry()
        self.resize(screen.width() // 2, 150)  # 减小高度以适应两行
        self.move(screen.width() // 4, screen.height() - 200)
        
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)  # Remove layout margins
        
        # 创建字幕卡片
        self.card = QWidget()  # Change from GlassCard to QWidget for no background
        self.card_layout = QVBoxLayout(self.card)
        self.card_layout.setContentsMargins(0, 0, 0, 0)  # Remove card layout margins
        
        # 创建文本标签
        self.label = QLabel()
        self.label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 28px;
                padding: 0;
                background-color: transparent;
                border: none;
                qproperty-wordWrap: true;
            }
        """)
        self.label.setWordWrap(True)  # 允许文字换行
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setMinimumHeight(80)  # 设置最小高度
        self.label.setMaximumHeight(150)  # 设置最大高度限制两行
        self.card_layout.addWidget(self.label)
        
        # 添加调整大小的控件
        self.resize_handle = QWidget(self)
        self.resize_handle.setStyleSheet("""
            QWidget {
                background-color: rgba(124, 118, 242, 0.3);
                border-radius: 4px;
            }
            QWidget:hover {
                background-color: rgba(124, 118, 242, 0.5);
            }
        """)
        self.resize_handle.setFixedSize(10, 10)
        self.resize_handle.setCursor(Qt.CursorShape.SizeFDiagCursor)
        self.resize_handle.mousePressEvent = self.start_resize
        self.resize_handle.mouseMoveEvent = self.do_resize
        
        # 添加设置按钮
        self.settings_button = QPushButton("⚙")
        self.settings_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: rgba(255, 255, 255, 0.5);
                border: none;
                font-size: 16px;
                padding: 5px;
            }
            QPushButton:hover {
                color: white;
            }
        """)
        self.settings_button.clicked.connect(self.show_settings)
        self.settings_button.setFixedSize(30, 30)
        
        # 创建设置面板
        self.settings_panel = QWidget(self)
        self.settings_panel.setStyleSheet("""
            QWidget {
                background-color: rgba(40, 40, 50, 0.95);
                border-radius: 10px;
                border: 1px solid rgba(255, 255, 255, 0.1);
            }
        """)
        self.settings_panel.hide()
        
        settings_layout = QVBoxLayout(self.settings_panel)
        
        # 透明度调节
        opacity_layout = QHBoxLayout()
        opacity_label = QLabel("透明度:")
        opacity_label.setStyleSheet("color: white;")
        self.opacity_spin = QDoubleSpinBox()
        self.opacity_spin.setRange(0.1, 1.0)
        self.opacity_spin.setSingleStep(0.1)
        self.opacity_spin.setValue(1.0)
        self.opacity_spin.valueChanged.connect(self.update_opacity)
        opacity_layout.addWidget(opacity_label)
        opacity_layout.addWidget(self.opacity_spin)
        settings_layout.addLayout(opacity_layout)
        
        # 字体大小调节
        font_size_layout = QHBoxLayout()
        font_size_label = QLabel("字体大小:")
        font_size_label.setStyleSheet("color: white;")
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(12, 48)
        self.font_size_spin.setValue(28)
        self.font_size_spin.valueChanged.connect(self.update_font_size)
        font_size_layout.addWidget(font_size_label)
        font_size_layout.addWidget(self.font_size_spin)
        settings_layout.addLayout(font_size_layout)
        
        # 边框颜色选择
        border_color_layout = QHBoxLayout()
        border_color_label = QLabel("边框颜色:")
        border_color_label.setStyleSheet("color: white;")
        self.border_color_button = QPushButton()
        self.border_color_button.setFixedSize(30, 30)
        self.border_color_button.clicked.connect(self.choose_border_color)
        self.current_border_color = QColor(255, 255, 255, 25)
        self.update_border_color_button()
        border_color_layout.addWidget(border_color_label)
        border_color_layout.addWidget(self.border_color_button)
        settings_layout.addLayout(border_color_layout)
        
        # 边框宽度调节
        border_width_layout = QHBoxLayout()
        border_width_label = QLabel("边框宽度:")
        border_width_label.setStyleSheet("color: white;")
        self.border_width_spin = QSpinBox()
        self.border_width_spin.setRange(0, 10)
        self.border_width_spin.setValue(2)
        self.border_width_spin.valueChanged.connect(self.update_border_width)
        border_width_layout.addWidget(border_width_label)
        border_width_layout.addWidget(self.border_width_spin)
        settings_layout.addLayout(border_width_layout)
        
        # 添加拖动提示标签
        drag_hint = QLabel("(点击任意位置拖动)")
        drag_hint.setStyleSheet("color: rgba(255, 255, 255, 0.5); font-size: 12px;")
        drag_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        settings_layout.addWidget(drag_hint)
        
        self.layout.addWidget(self.card)
        self.setLayout(self.layout)
        
        # 拖动相关
        self.dragging = False
        self.resizing = False
        self.offset = None
        
    def process_text(self, text):
        """处理文本以限制显示行数"""
        # 按句号或问号分割文本
        sentences = re.split('[。.？?!！]', text)
        # 过滤掉空字符串
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if len(sentences) > 0:
            # 如果只有一个句子，直接显示
            if len(sentences) == 1:
                return sentences[0]
            # 如果有多个句子，只显示最后两个
            else:
                return '\n'.join(sentences[-2:])

    def update_text(self, text):
        self.label.setText(self.process_text(text))

    def show_settings(self):
        if self.settings_panel.isHidden():
            # 显示设置面板在字幕窗口右侧
            panel_pos = self.mapToGlobal(QPoint(self.width(), 0))
            self.settings_panel.move(panel_pos)
            self.settings_panel.show()
        else:
            self.settings_panel.hide()

    def update_font_size(self, size):
        style = self.label.styleSheet()
        style = re.sub(r'font-size:\s*\d+px;', f'font-size: {size}px;', style)
        self.label.setStyleSheet(style)

    def choose_border_color(self):
        color = QColorDialog.getColor(self.current_border_color, self, "选择边框颜色", 
                                    QColorDialog.ColorDialogOption.ShowAlphaChannel)
        if color.isValid():
            self.current_border_color = color
            self.update_border_color_button()
            self.update_border_style()

    def update_border_color_button(self):
        self.border_color_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.current_border_color.name()};
                border: 1px solid white;
                border-radius: 4px;
            }}
        """)

    def update_border_width(self, width):
        self.update_border_style()

    def update_border_style(self):
        style = self.label.styleSheet()
        border_color = self.current_border_color.name(QColor.NameFormat.HexArgb)
        border_width = self.border_width_spin.value()
        style = re.sub(r'border:.*?;', f'border: {border_width}px solid {border_color};', style)
        self.label.setStyleSheet(style)

    def update_opacity(self, value):
        self.setWindowOpacity(value)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = True
            self.offset = event.pos()

    def mouseMoveEvent(self, event):
        if self.dragging and self.offset:
            new_pos = event.globalPosition().toPoint() - self.offset
            self.move(new_pos)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False
            self.offset = None

    def start_resize(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.resizing = True
            self.resize_start_pos = event.globalPosition().toPoint()
            self.resize_start_size = self.size()

    def do_resize(self, event):
        if self.resizing:
            diff = event.globalPosition().toPoint() - self.resize_start_pos
            new_size = QSize(
                self.resize_start_size.width() + diff.x(),
                self.resize_start_size.height() + diff.y()
            )
            self.resize(new_size)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False
            self.resizing = False

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 更新调整大小控件的位置
        self.resize_handle.move(
            self.width() - self.resize_handle.width() - 5,
            self.height() - self.resize_handle.height() - 5
        )
        # 更新设置按钮的位置
        self.settings_button.move(5, 5)

class STTThread(QThread):
    text_signal = pyqtSignal(str)
    model_ready_signal = pyqtSignal()

    def __init__(self, config):
        super().__init__()
        # 添加实时转录相关配置
        self.config = config.copy()
        self.config.update({
            'on_realtime_transcription_update': self.process_text  # 实时转录回调
        })
        self.running = True
        self.recorder = None
        self.paused = True
        self.last_text = ""

    def run(self):
        try:
            if not self.recorder:
                # 创建录音器
                self.recorder = AudioToTextRecorder(**self.config)
                
                # 等待 recorder.is_running 变为 True
                while not self.recorder.is_running:
                    if not self.running:
                        return
                    self.msleep(100)
                
                # 发送模型就绪信号
                self.model_ready_signal.emit()

            # 开始录音和识别循环
            while self.running:
                if not self.paused:
                    # 不再需要传递回调函数，因为已经在配置中设置了
                    self.recorder.text()
                else:
                    self.msleep(100)
                
        except Exception as e:
            print(f"Error in STT Thread: {e}")

    def process_text(self, text):
        """处理实时转录的文本"""
        if not self.running or self.paused:
             return
        if text != self.last_text and self.running:
            self.last_text = text
            # 发送文本用于显示
            if text:
                self.text_signal.emit(text)

    def pause(self):
        """暂停录音"""
        if self.recorder:
            self.paused = True
            self.recorder.stop()

    def resume(self):
        """恢复录音"""
        self.paused = False

    def stop(self):
        """停止线程"""
        self.running = False
        if self.recorder:
            self.recorder.stop()
        self.wait()

class TranslateThread(QThread):
    translation_signal = pyqtSignal(str)
    
    def __init__(self, model_name, target_lang):
        super().__init__()
        self.translation_threshold = 0.8  # Translation threshold to prevent overload
        self.model_name = model_name
        self.target_lang = target_lang
        self.queue = Queue()
        self.running = True
        self.last_translation_time = 0
        
    def run(self):
        while self.running:
            try:
                text = self.queue.get(timeout=0.5)
                if text:
                    # Check if enough time has passed since last translation
                    current_time = time.time()
                    if current_time - self.last_translation_time >= self.translation_threshold:
                        self.translate_text(text)
                        self.last_translation_time = current_time
            except Empty:
                continue
                
    def translate_text(self, text):
        try:
            prompt = f"""Translate the following text to {self.target_lang}.
Only output the translation, no explanations.

Text to translate: {text}"""
            
            # Use streaming generation for translation
            stream = ollama.Client().generate(
                model=self.model_name,
                prompt=prompt,
                stream=True
            )
            
            translated_text = ""
            for chunk in stream:
                if not self.running:
                    break
                if "response" in chunk:
                    translated_text += chunk["response"]
                    self.translation_signal.emit(translated_text)
                    
        except Exception as e:
            print(f"Translation error: {e}")
            
    def add_text(self, text):
        """Add text to the translation queue"""
        self.queue.put(text)
        
    def stop(self):
        """Stop the translation thread"""
        self.running = False
        self.wait()

class MainWindow(QMainWindow):
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("实时语音识别翻译工具")
        self.setMinimumSize(500, 400)  # 最小窗口大小
        self.setStyleSheet(f"background-color: {StyleHelper.MAIN_BG};")
        self.resize(1200, 800)  # 设置默认窗口大小

        # 初始化 PyAudio
        self.pa = pyaudio.PyAudio()
        
        # 初始化 Ollama 客户端
        self.translation_thread = None
        self.translation_running = False

        
        # 初始化 PyAudio
        self.pa = pyaudio.PyAudio()
        
        # 创建主窗口部件和布局
        main_widget = QWidget()
        main_layout = QHBoxLayout()  # 设置为横向布局
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # 左侧内容布局
        left_layout = QVBoxLayout()
        left_layout.setSpacing(20)

        # # 标题
        # title_label = QLabel("实时语音识别翻译工具")
        # title_label.setStyleSheet(f"""
        #     color: {StyleHelper.TEXT};
        #     font-size: 24px;
        #     font-weight: bold;
        # """)
        # left_layout.addWidget(title_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # 设置卡片
        settings_card = GlassCard()
        settings_layout = QVBoxLayout(settings_card)
        settings_layout.setSpacing(20)
        settings_layout.setContentsMargins(20, 20, 20, 20)

        # 基础设置组
        basic_group = QGroupBox("语音识别设置")
        basic_group.setStyleSheet(StyleHelper.get_group_box_style())
        basic_layout = QVBoxLayout(basic_group)

        # 麦克风选择
        mic_layout = QHBoxLayout()
        mic_label = QLabel("麦克风设备:")
        mic_label.setStyleSheet(f"color: {StyleHelper.TEXT};")
        self.mic_combo = QComboBox()
        input_devices = []
        for i in range(self.pa.get_device_count()):
            device_info = self.pa.get_device_info_by_index(i)
            if device_info['maxInputChannels'] > 0:
                input_devices.append(f"{i}: {device_info['name']}")
        self.mic_combo.addItems(input_devices)
        self.mic_combo.setStyleSheet(StyleHelper.get_combo_style())
        mic_layout.addWidget(mic_label)
        mic_layout.addWidget(self.mic_combo)
        basic_layout.addLayout(mic_layout)

        # 语言选择
        lang_layout = QHBoxLayout()
        lang_label = QLabel("识别语言:")
        lang_label.setStyleSheet(f"color: {StyleHelper.TEXT};")
        self.language_combo = QComboBox()
        self.language_combo.addItems(["en", "zh", "ja", "ko", "de", "fr"])
        self.language_combo.setStyleSheet(StyleHelper.get_combo_style())
        lang_layout.addWidget(lang_label)
        lang_layout.addWidget(self.language_combo)
        basic_layout.addLayout(lang_layout)

        # 模型选择
        model_layout = QHBoxLayout()
        model_label = QLabel("模型大小:")
        model_label.setStyleSheet(f"color: {StyleHelper.TEXT};")
        self.model_combo = QComboBox()
        self.model_combo.addItems(["tiny", "tiny.en", "base", "base.en", "small", "small.en", 
                                 "medium", "medium.en", "large-v1", "large-v2","large-v3","large-v3 turbo"])
        self.model_combo.setStyleSheet(StyleHelper.get_combo_style())
        model_layout.addWidget(model_label)
        model_layout.addWidget(self.model_combo)
        basic_layout.addLayout(model_layout)

        # 在基础设置组中添加唤醒词设置
        wake_word_layout = QHBoxLayout()
        wake_word_label = QLabel("唤醒词:")
        wake_word_label.setStyleSheet(f"color: {StyleHelper.TEXT};")
        self.wake_word_combo = QComboBox()
        self.wake_word_combo.addItems(["你好","hello","begin"])
        self.wake_word_combo.setStyleSheet(StyleHelper.get_combo_style())
        self.wake_word_combo.setEnabled(False)  # 默认禁用
        wake_word_layout.addWidget(wake_word_label)
        wake_word_layout.addWidget(self.wake_word_combo)
        basic_layout.addLayout(wake_word_layout)

        # 添加启用唤醒词复选框
        self.enable_wake_word = QCheckBox("启用唤醒词")
        self.enable_wake_word.setStyleSheet(StyleHelper.get_checkbox_style())
        self.enable_wake_word.toggled.connect(self.toggle_wake_word)
        basic_layout.addWidget(self.enable_wake_word)

        settings_layout.addWidget(basic_group)
        
        # 翻译设置组
        translate_group = QGroupBox("翻译设置")
        translate_group.setStyleSheet(StyleHelper.get_group_box_style())
        translate_layout = QVBoxLayout(translate_group)

        # 启用翻译复选框
        self.enable_translate = QCheckBox("启用翻译")
        self.enable_translate.setStyleSheet(StyleHelper.get_checkbox_style())
        translate_layout.addWidget(self.enable_translate)

        # Ollama模型选择
        ollama_model_layout = QHBoxLayout()
        ollama_model_label = QLabel("Ollama模型:")
        ollama_model_label.setStyleSheet(f"color: {StyleHelper.TEXT};")
        self.ollama_model_combo = QComboBox()
        self.ollama_model_combo.setStyleSheet(StyleHelper.get_combo_style())
        try:
            models = ollama.list()
            model_names = [model['model'] for model in models['models']]
            self.ollama_model_combo.addItems(model_names)
        except Exception as e:
            print(f"Failed to get Ollama models: {e}")
            self.ollama_model_combo.addItem("No models found")
        ollama_model_layout.addWidget(ollama_model_label)
        ollama_model_layout.addWidget(self.ollama_model_combo)
        translate_layout.addLayout(ollama_model_layout)

        # 目标语言选择
        target_lang_layout = QHBoxLayout()
        target_lang_label = QLabel("目标语言:")
        target_lang_label.setStyleSheet(f"color: {StyleHelper.TEXT};")
        self.target_lang_combo = QComboBox()
        self.target_lang_combo.addItems(["zh","en", "ja", "ko", "de", "fr", "es"])
        self.target_lang_combo.setStyleSheet(StyleHelper.get_combo_style())
        target_lang_layout.addWidget(target_lang_label)
        target_lang_layout.addWidget(self.target_lang_combo)
        translate_layout.addLayout(target_lang_layout)

        settings_layout.addWidget(translate_group)

        left_layout.addWidget(settings_card)  # 将设置卡片添加到内容布局
        main_layout.addLayout(left_layout)  # 添加左侧布局
        
        # 右侧内容布局
        right_layout = QVBoxLayout()
        right_layout.setSpacing(20)

        # 模型控制组（新增）
        model_control_group = QGroupBox("模型控制")
        model_control_group.setStyleSheet(StyleHelper.get_group_box_style())
        model_control_layout = QVBoxLayout(model_control_group)

        button_layout = QHBoxLayout()
        
        self.load_model_button = QPushButton("加载模型")
        self.load_model_button.setStyleSheet(StyleHelper.get_button_style(primary=True))
        self.load_model_button.clicked.connect(self.load_model)
        model_buttons_layout = QHBoxLayout()
        model_buttons_layout.addWidget(self.load_model_button)
        
        self.unload_model_button = QPushButton("卸载模型")
        self.unload_model_button.setStyleSheet(StyleHelper.get_button_style())
        self.unload_model_button.clicked.connect(self.unload_model)
        self.unload_model_button.setEnabled(False)
        model_buttons_layout.addWidget(self.unload_model_button)
        
        model_control_layout.addLayout(model_buttons_layout)
        right_layout.addWidget(model_control_group)

        # VAD 设置组
        vad_group = QGroupBox("语音检测设置")
        vad_group.setStyleSheet(StyleHelper.get_group_box_style())
        vad_layout = QVBoxLayout(vad_group)

        # Silero 灵敏度
        silero_layout = QHBoxLayout()
        silero_layout.setContentsMargins(0, 10, 0, 10)
        
        # 创建一个容器来包含标签和值
        silero_container = QWidget()
        silero_container_layout = QHBoxLayout(silero_container)
        silero_container_layout.setContentsMargins(0, 0, 0, 0)
        silero_container_layout.setSpacing(10)
        
        silero_label = QLabel("Silero灵敏度:")
        silero_label.setStyleSheet(f"color: {StyleHelper.TEXT};")
        
        self.silero_sensitivity = QDoubleSpinBox()
        self.silero_sensitivity.setRange(0, 1)
        self.silero_sensitivity.setSingleStep(0.1)
        self.silero_sensitivity.setValue(0.2)
        self.silero_sensitivity.setFixedHeight(36)
        self.silero_sensitivity.setStyleSheet(StyleHelper.get_spinbox_style())
        
        silero_container_layout.addWidget(silero_label)
        silero_container_layout.addWidget(self.silero_sensitivity)
        silero_layout.addWidget(silero_container)
        vad_layout.addLayout(silero_layout)

        # 使用ONNX
        self.silero_onnx = QCheckBox("使用ONNX加速")
        self.silero_onnx.setStyleSheet(StyleHelper.get_checkbox_style())
        vad_layout.addWidget(self.silero_onnx)

        right_layout.addWidget(vad_group)

        # 添加输出文本显示
        output_group = QGroupBox("识别结果")
        output_group.setStyleSheet(StyleHelper.get_group_box_style())
        output_layout = QVBoxLayout(output_group)
        
        self.output_text = QLabel()
        self.output_text.setStyleSheet(f"""
            color: {StyleHelper.TEXT};
            font-size: 16px;
            padding: 10px;
            background-color: rgba(0, 0, 0, 0.2);
            border-radius: 8px;
            min-height: 60px;
        """)
        self.output_text.setWordWrap(True)
        self.output_text.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        output_layout.addWidget(self.output_text)
        
        right_layout.addWidget(output_group)  # 添加到右侧布局中

        # 添加开始/停止按钮和字幕按钮
        control_group = QGroupBox("控制")
        control_group.setStyleSheet(StyleHelper.get_group_box_style())
        control_layout = QVBoxLayout(control_group)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        self.start_button = QPushButton("开始识别")
        self.start_button.setStyleSheet(StyleHelper.get_button_style(primary=True))
        self.start_button.clicked.connect(self.toggle_recording)
        self.start_button.setEnabled(False)  # 默认禁用
        button_layout.addWidget(self.start_button)

        self.subtitle_button = QPushButton("显示字幕")
        self.subtitle_button.setStyleSheet(StyleHelper.get_button_style())
        self.subtitle_button.clicked.connect(self.toggle_subtitle)
        button_layout.addWidget(self.subtitle_button)

        control_layout.addLayout(button_layout)
        right_layout.addWidget(control_group)

        main_layout.addLayout(right_layout)  # 添加右侧布局

        # 设置主窗口的布局
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

        # 初始化字幕窗口和STT线程
        self.subtitle_window = SubtitleWindow()
        self.stt_thread = None
        self.is_recording = False
        self.subtitle_visible = False
        self.model_loaded = False
        self.loading_timer = QTimer()  # 添加定时器
        self.loading_timer.timeout.connect(self.handle_loading_timeout)
        self.loading_timer.setSingleShot(True)  # 设置为单次触发

    def start_translation_thread(self):
        """Start the translation thread"""
        if self.translation_thread is None:
            self.translation_thread = TranslateThread(
                self.ollama_model_combo.currentText(),
                self.target_lang_combo.currentText()
            )
            self.translation_thread.translation_signal.connect(self.update_translation_ui)
            self.translation_thread.start()

    def stop_translation_thread(self):
        """Stop the translation thread"""
        if self.translation_thread:
            self.translation_thread.stop()
            self.translation_thread = None

    def update_translation_ui(self, text):
        if self.enable_translate.isChecked():
            # 更新主窗口的输出文本
            self.output_text.setText(text)
            # 如果字幕窗口可见，也更新字幕
            if self.subtitle_visible:
                self.subtitle_window.update_text(text)
    def toggle_recording(self):
        if not self.model_loaded:
            print("请先加载模型")
            return
            
        if not self.is_recording:
            self.stt_thread.resume()
            self.start_button.setText("停止识别")
            self.is_recording = True
            
            # 禁用设置控件
            self.mic_combo.setEnabled(False)
            self.language_combo.setEnabled(False)
            self.model_combo.setEnabled(False)
            self.silero_sensitivity.setEnabled(False)
            self.silero_onnx.setEnabled(False)
            self.load_model_button.setEnabled(False)
            self.unload_model_button.setEnabled(False)
        else:
            self.stt_thread.pause()
            self.start_button.setText("开始识别")
            self.is_recording = False
            
            # 启用设置控件
            self.mic_combo.setEnabled(True)
            self.language_combo.setEnabled(True)
            self.model_combo.setEnabled(True)
            self.silero_sensitivity.setEnabled(True)
            self.silero_onnx.setEnabled(True)
            self.unload_model_button.setEnabled(True)

    def toggle_subtitle(self):
        if not self.subtitle_visible:
            self.subtitle_window.show()
            self.subtitle_button.setText("隐藏字幕")
            self.subtitle_visible = True
        else:
            self.subtitle_window.hide()
            self.subtitle_button.setText("显示字幕")
            self.subtitle_visible = False

    def closeEvent(self, event):
        self.stop_translation_thread()  # 停止翻译线程
        if self.stt_thread:
            self.stt_thread.stop()  # 完全停止并清理
            self.stt_thread = None
        self.pa.terminate()
        event.accept()

    def load_model(self):
        if not self.model_loaded:
            config = {
                'language': self.language_combo.currentText(),
                'model': self.model_combo.currentText(),
                'device': "cuda",  # 确保使用显卡
                'silero_sensitivity': self.silero_sensitivity.value(),
                'silero_use_onnx': self.silero_onnx.isChecked(),
                'input_device_index': int(self.mic_combo.currentText().split(':')[0]),
                'enable_realtime_transcription': True,  # 启用实时转录
                "webrtc_sensitivity":3,
                "post_speech_silence_duration":0.4, 
                "min_length_of_recording":0.3, 
                "realtime_processing_pause" : 0.01, 
                "realtime_model_type" : "tiny"
            }
            
            # 添加唤醒词配置
            if self.enable_wake_word.isChecked():
                config.update({
                    'wake_words': self.wake_word_combo.currentText(),
                    'wake_words_sensitivity': 0.5
                })
            
            self.stt_thread = STTThread(config)
            self.stt_thread.text_signal.connect(self.update_subtitle)
            self.stt_thread.model_ready_signal.connect(self.on_model_ready)
            
            # 更新按钮文本并禁用相关控件
            self.load_model_button.setText("加载中...")
            self.load_model_button.setEnabled(False)
            
            # 禁用所有设置控件
            self.mic_combo.setEnabled(False)
            self.language_combo.setEnabled(False)
            self.model_combo.setEnabled(False)
            self.wake_word_combo.setEnabled(False)
            self.enable_wake_word.setEnabled(False)
            self.silero_sensitivity.setEnabled(False)
            self.silero_onnx.setEnabled(False)
            
            # 启动加载超时计时器 (60秒)
            self.loading_timer.start(360000)
            
            self.stt_thread.start()
            # 启动翻译线程
            self.start_translation_thread()

    def handle_loading_timeout(self):
        """处理模型加载超时"""
        if not self.model_loaded:
            # 停止加载
            if self.stt_thread:
                self.stt_thread.stop()
                self.stt_thread = None
            
            # 恢复界面状态
            self.load_model_button.setText("加载模型")
            self.load_model_button.setEnabled(True)
            self.mic_combo.setEnabled(True)
            self.language_combo.setEnabled(True)
            self.model_combo.setEnabled(True)
            self.wake_word_combo.setEnabled(True)
            self.enable_wake_word.setEnabled(True)
            self.silero_sensitivity.setEnabled(True)
            self.silero_onnx.setEnabled(True)
            
            # 显示错误信息
            QMessageBox.critical(self, "错误", "模型加载超时(60s)，请重试")

    def on_model_ready(self):
        # 停止超时计时器
        self.loading_timer.stop()
        self.model_loaded = True
        self.load_model_button.setText("加载完成")  # 更改为"加载完成"
        self.unload_model_button.setEnabled(True)
        self.start_button.setEnabled(True)

    def unload_model(self):
        if self.stt_thread and self.stt_thread.recorder:
            self.stt_thread.recorder.shutdown()  # 使用 shutdown() 方法
            self.stt_thread = None
            self.is_recording = False
            self.model_loaded = False
            
            # 启用所有设置控件
            self.mic_combo.setEnabled(True)
            self.language_combo.setEnabled(True)
            self.model_combo.setEnabled(True)
            self.wake_word_combo.setEnabled(True)
            self.enable_wake_word.setEnabled(True)
            self.silero_sensitivity.setEnabled(True)
            self.silero_onnx.setEnabled(True)
            
            # 更新按钮状态
            self.load_model_button.setText("加载模型")
            self.load_model_button.setEnabled(True)
            self.unload_model_button.setEnabled(False)
            self.start_button.setEnabled(False)

    def toggle_wake_word(self, enabled):
        """启用/禁用唤醒词"""
        self.wake_word_combo.setEnabled(enabled)

    def update_subtitle(self, text):
        if not self.enable_translate.isChecked():
            # 更新主窗口的输出文本
            self.output_text.setText(text)
            # 如果字幕窗口可见，也更新字幕
            if self.subtitle_visible:
                self.subtitle_window.update_text(text)
        else:
            # 将文本加入翻译队列
            self.translation_thread.add_text(text)

            

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec()) 