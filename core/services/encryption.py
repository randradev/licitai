import os
from cryptography.fernet import Fernet
from django.conf import settings


class EncryptionService:
    """
    Servicio para cifrar y descifrar datos sensibles (como el Ticket API)
    utilizando algoritmos simétricos (Fernet/AES).
    """

    def __init__(self):
        # Obtener1 la llave desde el .env a través de settings
        key = os.getenv('ENCRYPTION_KEY')
        if not key:
            raise ValueError("No se encontró ENCRYPTION_KEY en las variables de entorno.")
        self.fernet = Fernet(key.encode())

    def encrypt(self, plain_text: str) -> str:
        """Cifra un texto plano y lo devuelve como string."""
        if not plain_text:
            return ""
        return self.fernet.encrypt(plain_text.encode()).decode()

    def decrypt(self, encrypted_text: str) -> str:
        """Descifra un texto cifrado y lo devuelve como texto plano."""
        if not encrypted_text:
            return ""
        return self.fernet.decrypt(encrypted_text.encode()).decode()