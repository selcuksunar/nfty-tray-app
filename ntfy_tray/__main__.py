def main():
    import sys

    if "--version" in sys.argv:
        from ntfy_tray.__version__ import __version__
        print(__version__)
    else:
        from ntfy_tray.gui import start_gui
        start_gui()


if __name__ == "__main__":
    main()
