"""gui/theme.py -- modern dark mode stylesheet for the whole app."""

DARK_STYLESHEET = """
QWidget {
    background-color: #121417;
    color: #E6E8EB;
    font-family: 'Segoe UI', sans-serif;
    font-size: 13px;
}
QMainWindow, QDialog {
    background-color: #121417;
}
QLabel#Header {
    font-size: 20px;
    font-weight: 600;
    color: #F5F6F7;
}
QLabel#SubHeader {
    font-size: 13px;
    color: #9AA1AA;
}
QFrame#Card {
    background-color: #1B1F24;
    border-radius: 10px;
    border: 1px solid #262B32;
}
QPushButton {
    background-color: #2A2F37;
    border: 1px solid #383F49;
    border-radius: 6px;
    padding: 8px 16px;
    color: #E6E8EB;
}
QPushButton:hover {
    background-color: #343B45;
}
QPushButton#Approve {
    background-color: #1F7A4C;
    border: none;
    color: white;
    font-weight: 600;
}
QPushButton#Approve:hover {
    background-color: #24915B;
}
QPushButton#Reject {
    background-color: #7A2323;
    border: none;
    color: white;
    font-weight: 600;
}
QPushButton#Reject:hover {
    background-color: #912828;
}
QProgressBar {
    background-color: #262B32;
    border-radius: 6px;
    text-align: center;
    color: #E6E8EB;
}
QProgressBar::chunk {
    background-color: #3A82F6;
    border-radius: 6px;
}
QListWidget, QTableWidget {
    background-color: #1B1F24;
    border: 1px solid #262B32;
    border-radius: 8px;
}
QTabWidget::pane {
    border: 1px solid #262B32;
    border-radius: 8px;
}
QTabBar::tab {
    background: #1B1F24;
    padding: 8px 18px;
    color: #9AA1AA;
}
QTabBar::tab:selected {
    background: #2A2F37;
    color: #F5F6F7;
}
"""
