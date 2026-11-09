class DeliveryError(Exception):
    """A credential-free failure code suitable for durable delivery history."""
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)
