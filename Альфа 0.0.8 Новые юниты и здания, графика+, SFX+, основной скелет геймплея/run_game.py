from civlite.app import GameApp

if __name__ == "__main__":
    try:
        GameApp().run()
    except Exception:
        import traceback
        traceback.print_exc()
        input("\nПроизошла ошибка! Нажмите Enter для выхода...")

       