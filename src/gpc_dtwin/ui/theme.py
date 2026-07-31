"""Application themes."""

from __future__ import annotations


def stylesheet(theme: str = "dark") -> str:
    dark = theme.lower() != "light"
    colors = {
        "bg": "#0a1020" if dark else "#f3f6fb",
        "panel": "#10192b" if dark else "#ffffff",
        "panel2": "#162238" if dark else "#f7f9fc",
        "sidebar": "#080f1d" if dark else "#111827",
        "border": "#263650" if dark else "#dce3ee",
        "text": "#edf3ff" if dark else "#172033",
        "muted": "#93a4be" if dark else "#68758a",
        "accent": "#4f9cff",
        "accent_hover": "#3189f5",
        "success": "#2dc98c",
        "warning": "#ffb84d",
        "danger": "#ff667a",
        "selection": "#17345c" if dark else "#dcecff",
        "disabled": "#64748b" if dark else "#9aa6b8",
    }
    return f"""
    * {{ font-family: 'Segoe UI', Arial; font-size: 10pt; color: {colors['text']}; }}
    QMainWindow, QWidget#AppRoot {{ background: {colors['bg']}; }}
    QWidget {{ background: transparent; }}
    QDialog, QMessageBox {{ background: {colors['panel']}; }}
    QMenuBar {{ background: {colors['panel']}; border-bottom: 1px solid {colors['border']}; padding: 3px; }}
    QMenuBar::item {{ padding: 5px 9px; border-radius: 5px; }}
    QMenuBar::item:selected, QMenu::item:selected {{ background: {colors['selection']}; }}
    QMenu {{ background: {colors['panel']}; border: 1px solid {colors['border']}; padding: 5px; }}
    QMenu::item {{ padding: 7px 28px 7px 10px; border-radius: 5px; }}
    QStatusBar {{ background: {colors['panel']}; border-top: 1px solid {colors['border']}; }}
    QStatusBar QLabel {{ color: {colors['muted']}; padding: 0 4px; }}

    QFrame#Sidebar {{ background: {colors['sidebar']}; border-right: 1px solid {colors['border']}; }}
    QLabel#BrandMark {{ background: {colors['accent']}; color: white; border-radius: 11px; font-weight: 800; font-size: 11pt; }}
    QLabel#BrandTitle {{ color: white; font-size: 15pt; font-weight: 750; }}
    QLabel#BrandSubtitle {{ color: #9fb0c8; font-size: 9pt; }}
    QPushButton#NavButton {{ text-align: left; min-height: 22px; padding: 11px 12px; border: 0; border-radius: 9px; color: #b5c3d8; font-weight: 600; }}
    QPushButton#NavButton:hover {{ background: rgba(79,156,255,0.12); color: white; }}
    QPushButton#NavButton:checked {{ background: rgba(79,156,255,0.20); color: white; border-left: 3px solid {colors['accent']}; }}
    QPushButton#SidebarToggle {{ background: transparent; border: 0; color: #c6d2e4; font-size: 14pt; padding: 6px; }}
    QPushButton#SidebarToggle:hover {{ background: rgba(79,156,255,0.14); }}

    QFrame#TopBar {{ background: {colors['panel']}; border-bottom: 1px solid {colors['border']}; }}
    QLabel#PageTitle {{ font-size: 19pt; font-weight: 760; }}
    QLabel#PageSubtitle, QLabel#SectionDescription, QLabel#Muted {{ color: {colors['muted']}; }}
    QLabel#SectionTitle {{ font-size: 15pt; font-weight: 720; }}

    QFrame#Card, QFrame#MetricCard, QFrame#InfoCard {{ background: {colors['panel']}; border: 1px solid {colors['border']}; border-radius: 12px; }}
    QFrame#InfoCard {{ border-left: 3px solid {colors['accent']}; }}
    QFrame#MetricCard:hover {{ border-color: {colors['accent']}; }}
    QLabel#MetricIcon {{ background: {colors['panel2']}; border: 1px solid {colors['border']}; border-radius: 10px; font-size: 15pt; }}
    QLabel#MetricValue {{ font-size: 20pt; font-weight: 780; }}
    QLabel#MetricLabel {{ font-weight: 650; }}

    QPushButton {{ background: {colors['panel2']}; border: 1px solid {colors['border']}; border-radius: 8px; padding: 8px 13px; min-height: 18px; font-weight: 600; }}
    QPushButton:hover {{ border-color: {colors['accent']}; }}
    QPushButton:focus {{ border: 1px solid {colors['accent']}; }}
    QPushButton:pressed {{ background: {colors['selection']}; }}
    QPushButton:disabled {{ color: {colors['disabled']}; border-color: {colors['border']}; }}
    QPushButton#PrimaryButton {{ background: {colors['accent']}; border-color: {colors['accent']}; color: white; }}
    QPushButton#PrimaryButton:hover {{ background: {colors['accent_hover']}; }}
    QPushButton#DangerButton {{ background: rgba(255,102,122,0.14); border-color: {colors['danger']}; color: {colors['danger']}; }}

    QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {{ background: {colors['panel2']}; border: 1px solid {colors['border']}; border-radius: 7px; padding: 7px 9px; selection-background-color: {colors['accent']}; min-height: 18px; }}
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{ border-color: {colors['accent']}; }}
    QComboBox QAbstractItemView {{ background: {colors['panel']}; border: 1px solid {colors['border']}; selection-background-color: {colors['selection']}; }}

    QTableView, QTableWidget, QListWidget {{ background: {colors['panel']}; alternate-background-color: {colors['panel2']}; border: 1px solid {colors['border']}; border-radius: 9px; gridline-color: {colors['border']}; selection-background-color: {colors['selection']}; }}
    QListWidget::item {{ padding: 6px; border-radius: 5px; }}
    QListWidget::item:hover {{ background: {colors['selection']}; }}
    QCheckBox {{ spacing: 8px; }}
    QHeaderView::section {{ background: {colors['panel2']}; border: 0; border-right: 1px solid {colors['border']}; border-bottom: 1px solid {colors['border']}; padding: 8px; font-weight: 650; }}

    QTabWidget::pane {{ border: 1px solid {colors['border']}; border-radius: 10px; background: {colors['panel']}; top: -1px; }}
    QTabBar::tab {{ background: {colors['panel2']}; border: 1px solid {colors['border']}; padding: 9px 16px; margin-right: 4px; border-top-left-radius: 8px; border-top-right-radius: 8px; }}
    QTabBar::tab:selected {{ background: {colors['panel']}; color: {colors['accent']}; border-bottom-color: {colors['panel']}; }}

    QScrollArea {{ border: 0; background: transparent; }}
    QScrollBar:vertical {{ background: transparent; width: 12px; margin: 2px; }}
    QScrollBar::handle:vertical {{ background: {colors['border']}; min-height: 32px; border-radius: 5px; }}
    QScrollBar::handle:vertical:hover {{ background: {colors['accent']}; }}
    QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 2px; }}
    QScrollBar::handle:horizontal {{ background: {colors['border']}; min-width: 32px; border-radius: 5px; }}
    QScrollBar::handle:horizontal:hover {{ background: {colors['accent']}; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
    QSplitter::handle {{ background: {colors['border']}; width: 2px; height: 2px; }}
    QSplitter::handle:hover {{ background: {colors['accent']}; }}
    QToolTip {{ background: {colors['panel']}; color: {colors['text']}; border: 1px solid {colors['border']}; padding: 5px; }}
    QProgressBar {{ border: 1px solid {colors['border']}; border-radius: 6px; background: {colors['panel2']}; text-align: center; }}
    QProgressBar::chunk {{ background: {colors['accent']}; border-radius: 5px; }}
    QLabel#ValuePill {{ border-radius: 10px; padding: 4px 9px; background: {colors['panel2']}; border: 1px solid {colors['border']}; font-weight: 650; }}
    QLabel#ValuePill[tone='success'] {{ color: {colors['success']}; border-color: {colors['success']}; }}
    QLabel#ValuePill[tone='warning'] {{ color: {colors['warning']}; border-color: {colors['warning']}; }}
    QLabel#ValuePill[tone='danger'] {{ color: {colors['danger']}; border-color: {colors['danger']}; }}
    """
