from gui import LPJKScraperApp


def main():
    app = LPJKScraperApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()


if __name__ == "__main__":
    main()
