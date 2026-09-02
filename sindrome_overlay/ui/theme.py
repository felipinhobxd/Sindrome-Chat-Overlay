from __future__ import annotations

from ..settings import Settings


def _alpha(percent: int) -> int:
    return round(max(0, min(100, percent)) * 2.55)


def _scaled_alpha(base_alpha: int, percent: int) -> int:
    return round(base_alpha * max(0, min(100, percent)) / 100)


def build_stylesheet(settings: Settings) -> str:
    panel_alpha = _alpha(settings.background_opacity)
    panel_border_alpha = _scaled_alpha(36, settings.background_opacity)
    header_alpha = _scaled_alpha(225, settings.background_opacity)
    header_border_alpha = _scaled_alpha(26, settings.background_opacity)
    empty_alpha = _scaled_alpha(95, settings.background_opacity)
    empty_border_alpha = _scaled_alpha(45, settings.background_opacity)
    card_alpha = _alpha(settings.card_opacity)
    return f"""
        QWidget {{
            color: #F6F8FC;
            font-family: "Segoe UI", "Inter", sans-serif;
            font-size: {settings.font_size}px;
        }}
        QFrame#OverlayRoot {{
            background-color: rgba(8, 11, 19, {panel_alpha});
            border: 1px solid rgba(255, 255, 255, {panel_border_alpha});
            border-radius: 16px;
        }}
        QFrame#Header {{
            background-color: rgba(14, 19, 31, {header_alpha});
            border-bottom: 1px solid rgba(255, 255, 255, {header_border_alpha});
            border-top-left-radius: 15px;
            border-top-right-radius: 15px;
        }}
        QLabel#AppTitle {{
            color: #FFFFFF;
            font-size: 14px;
            font-weight: 700;
        }}
        QLabel#DragHandle {{
            color: #C8D1E2;
            background: rgba(3, 6, 11, 185);
            border: 1px solid rgba(255, 255, 255, 38);
            border-radius: 5px;
            min-width: 24px;
            max-width: 24px;
            padding: 0 3px 1px 3px;
            font-size: 14px;
            font-weight: 700;
        }}
        QLabel#StatusLabel {{
            color: #AAB5CB;
            font-size: 11px;
        }}
        QPushButton#HeaderButton {{
            background: rgba(255, 255, 255, 15);
            border: 1px solid rgba(255, 255, 255, 22);
            border-radius: 7px;
            min-width: 28px;
            min-height: 26px;
            padding: 0;
        }}
        QPushButton#HeaderButton:hover {{
            background: rgba(255, 255, 255, 34);
        }}
        QPushButton#CloseButton {{
            background: transparent;
            border: none;
            border-radius: 7px;
            min-width: 28px;
            min-height: 26px;
        }}
        QPushButton#CloseButton:hover {{
            background: #D84356;
        }}
        QScrollArea, QScrollArea > QWidget > QWidget {{
            background: transparent;
            border: none;
        }}
        QScrollBar:vertical {{
            background: transparent;
            width: 8px;
            margin: 4px 1px;
        }}
        QScrollBar::handle:vertical {{
            background: rgba(255, 255, 255, 65);
            border-radius: 4px;
            min-height: 28px;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0;
        }}
        QFrame#ChatCard {{
            background: transparent;
            border: none;
        }}
        QFrame#MessageBubble {{
            background-color: rgba(3, 5, 9, {card_alpha});
            border: none;
            border-radius: 6px;
        }}
        QLabel#MessageText {{
            color: #F5F7FB;
            background: transparent;
        }}
        QLabel#MetaText {{
            color: #9BA8BE;
            background: transparent;
            font-size: {max(10, settings.font_size - 3)}px;
        }}
        QLabel#EmptyState {{
            color: #C3CBDA;
            background: rgba(8, 11, 19, {empty_alpha});
            border: 1px dashed rgba(255, 255, 255, {empty_border_alpha});
            border-radius: 12px;
            padding: 22px;
        }}
        QDialog {{
            background: #101521;
        }}
        QGroupBox {{
            border: 1px solid #30384B;
            border-radius: 9px;
            margin-top: 13px;
            padding: 12px 9px 9px 9px;
            font-weight: 600;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px;
        }}
        QFrame#YouTubeStatusCard {{
            background: #151D2B;
            border: 1px solid #34425A;
            border-radius: 8px;
        }}
        QFrame#YouTubeStatusCard[statusKind="official"] {{
            background: #13271F;
            border-color: #2F7658;
        }}
        QFrame#YouTubeStatusCard[statusKind="warning"] {{
            background: #2A2117;
            border-color: #8A6636;
        }}
        QLabel#YouTubeStatusTitle, QLabel#AdvancedFieldTitle {{
            color: #F7F9FD;
            background: transparent;
            font-weight: 650;
        }}
        QLabel#YouTubeStatusDetail, QLabel#AdvancedHelpText {{
            color: #AAB5CB;
            background: transparent;
            font-size: 12px;
        }}
        QPushButton#AdvancedSettingsButton {{
            color: #C9D2E3;
            background: transparent;
            border: none;
            padding: 7px 3px;
            text-align: left;
            font-weight: 600;
        }}
        QPushButton#AdvancedSettingsButton:hover {{
            color: #FFFFFF;
            background: #171E2D;
            border-radius: 6px;
        }}
        QFrame#YouTubeAdvancedPanel {{
            background: #121925;
            border: 1px solid #303A50;
            border-radius: 8px;
        }}
        QToolButton#RevealKeyButton {{
            background: #20293B;
            border: 1px solid #3A4760;
            border-radius: 7px;
            min-width: 35px;
            min-height: 33px;
            padding: 0;
        }}
        QToolButton#RevealKeyButton:hover,
        QToolButton#RevealKeyButton:checked {{
            background: #6542DD;
            border-color: #7A57EB;
        }}
        QLineEdit, QSpinBox {{
            background: #171E2D;
            border: 1px solid #354057;
            border-radius: 7px;
            padding: 7px;
            selection-background-color: #7047EB;
        }}
        QLineEdit:focus, QSpinBox:focus {{
            border-color: #8B68F2;
        }}
        QTabWidget::pane {{
            border: 1px solid #30384B;
            border-radius: 8px;
            top: -1px;
        }}
        QTabBar::tab {{
            background: #171E2D;
            padding: 9px 16px;
            border: 1px solid #30384B;
        }}
        QTabBar::tab:selected {{
            background: #6D46E8;
        }}
        QDialogButtonBox QPushButton, QPushButton#ActionButton {{
            background: #6542DD;
            border: none;
            border-radius: 7px;
            padding: 8px 14px;
            min-width: 80px;
        }}
        QDialogButtonBox QPushButton:hover, QPushButton#ActionButton:hover {{
            background: #7A57EB;
        }}
        QToolTip {{
            background: #151B29;
            color: white;
            border: 1px solid #3A455C;
            padding: 5px;
        }}
    """
