class DeskObstructionException(Exception):
    pass

class DeskTimeoutException(Exception):
    pass

class DeskConnectionException(Exception):
    pass

class Desk():
    """
    Gets the desk height in mm
    """
    def get_height_mm() -> int:
        return 0


    def goto_height_mm(height_mm: int):
        return
