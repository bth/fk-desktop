from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from fk.core.abstract_settings import AbstractSettings
from fk.core.path_resolver import resolve_path


class Application(QApplication):
    _settings: AbstractSettings
    
    def __init__(self, args: [str], settings: AbstractSettings):
        super().__init__(args)
        self._settings = settings

        # Quit app on close
        quit_on_close = (settings.get('Application.quit_on_close') == 'True')
        self.setQuitOnLastWindowClosed(quit_on_close)

    def on_settings_change(self):
        pass

    def initialize_fonts(self) -> (QFont, QFont, QFont, QFont):
        fh: QFont | None = None
        fm: QFont | None = None

        fh_default = QFont()
        fh_default.setPointSize(24)
        fm_default = QFont()

        use_custom_fonts = (s.get('Application.use_custom_fonts') == 'True')
        if use_custom_fonts:
            font_file_header = resolve_path("res/font/OpenSans-Light.ttf")
            font_index_header: int = QFontDatabase.addApplicationFont(font_file_header)
            if font_index_header >= 0:
                font_family_header = "Open Sans Light"  # QFontDatabase.applicationFontFamilies(font_index_header)[0]
                fh = QFont(font_family_header, 24)
                print(f"Loaded custom header font: {font_family_header}")
            else:
                print(f"Warning - Cannot load custom font {font_file_header}. Falling back to default system font.")

            font_file_main = resolve_path("res/font/OpenSans-Variable.ttf")
            font_index_main: int = QFontDatabase.addApplicationFont(font_file_main)
            if font_index_main >= 0:
                font_family_main = "Open Sans"  # QFontDatabase.applicationFontFamilies(font_index_main)[0]
                fm = QFont(font_family_main, 11)
                print(f"Loaded custom main font: {font_family_main}")
            else:
                print(f"Warning - Cannot load custom font {font_file_main}. Falling back to default system font.")

        if fh is None:
            fh = fh_default

        if fm is None:
            fm = fm_default

        print(f'Header font: {fh.family()}')
        print(f'Main font: {fm.family()}')

        return fm, fh, fm_default, fh_default

    def set_font(self):
        # TODO: Set from a setting
        font_main, font_header, default_font_main, default_font_header = initialize_fonts(settings)
        self.setFont(font_main)

    def set_theme(self, theme: str):
        # TODO: Set from a setting
        # Apply CSS
        with open(resolve_path(f"res/{theme}/style.qss"), "r") as f:
            self.setStyleSheet(f.read())

