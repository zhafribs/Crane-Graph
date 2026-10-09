"""Dark engineering theme for Crane Graph."""

STYLE = """
QWidget {
    background-color: #1b212c;
    color: #dfe6f0;
    font-family: "DejaVu Sans", "Noto Sans", sans-serif;
    font-size: 13px;
}
QMainWindow, QDialog {
    background-color: #161b24;
}
QGroupBox {
    border: 1px solid #2c3547;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 8px;
    font-weight: bold;
    color: #8fb7ff;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    background-color: #1b212c;
}
QLabel { background: transparent; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit, QPlainTextEdit {
    background-color: #232b3a;
    border: 1px solid #34405a;
    border-radius: 4px;
    padding: 4px 6px;
    selection-background-color: #2f6fbf;
    selection-color: #ffffff;
}
QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus, QSpinBox:focus {
    border: 1px solid #5cb3ff;
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
QComboBox QAbstractItemView {
    background-color: #232b3a;
    border: 1px solid #34405a;
    selection-background-color: #2f6fbf;
}
QPushButton {
    background-color: #2a5c9e;
    color: #ffffff;
    border: 1px solid #23508c;
    border-radius: 4px;
    padding: 6px 14px;
    font-weight: bold;
}
QPushButton:hover { background-color: #306bc0; }
QPushButton:pressed { background-color: #1f4a82; }
QPushButton:disabled { background-color: #2a3347; color: #6b7488; }
QPushButton#danger {
    background-color: #8a3a3a;
    border: 1px solid #6f2f2f;
}
QPushButton#danger:hover { background-color: #a33f3f; }
QPushButton#preset {
    background-color: #2a3347;
    border: 1px solid #34405a;
    padding: 4px 8px;
    font-weight: normal;
}
QPushButton#preset:hover { background-color: #34405a; }
QCheckBox { background: transparent; spacing: 8px; }
QCheckBox::indicator {
    width: 14px; height: 14px;
    border: 1px solid #34405a;
    border-radius: 3px;
    background-color: #232b3a;
}
QCheckBox::indicator:checked {
    background-color: #2f6fbf;
    border: 1px solid #5cb3ff;
}
QRadioButton { background: transparent; spacing: 8px; }
QRadioButton::indicator {
    width: 14px; height: 14px;
    border: 1px solid #34405a;
    border-radius: 8px;
    background-color: #232b3a;
}
QRadioButton::indicator:checked {
    background-color: #5cb3ff;
    border: 1px solid #5cb3ff;
}
QRadioButton::indicator:checked {
    image: none;
}
QScrollArea {
    border: none;
    background: transparent;
}
QScrollBar:vertical { background: #161b24; width: 12px; }
QScrollBar::handle:vertical {
    background: #34405a; border-radius: 5px; min-height: 24px;
}
QScrollBar::handle:vertical:hover { background: #40547a; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; }
QScrollBar:horizontal { background: #161b24; height: 12px; }
QScrollBar::handle:horizontal {
    background: #34405a; border-radius: 5px; min-width: 24px;
}
QScrollBar::add-line, QScrollBar::sub-line { width: 0; }
QStatusBar { background-color: #161b24; color: #8fa3c0; }
QMessageBox { background-color: #1b212c; }
QFrame#panel {
    background-color: #1b212c;
    border: 1px solid #2c3547;
    border-radius: 6px;
}
QLabel#hint { color: #8fa3c0; font-size: 11px; }
"""
