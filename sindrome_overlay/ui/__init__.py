__all__ = ["OverlayWindow", "SettingsDialog"]


def __getattr__(name: str):
    if name == "OverlayWindow":
        from .virtualized_overlay import OverlayWindow

        return OverlayWindow
    if name == "SettingsDialog":
        from .settings_dialog import SettingsDialog

        return SettingsDialog
    raise AttributeError(name)
