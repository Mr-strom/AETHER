"""Security and cryptography service stub for offline data protection."""

import secrets
from cryptography.fernet import Fernet


class SecurityService:
    """Handles hashing, encryption, and secure local file operations."""

    @staticmethod
    def generate_key() -> str:
        """Generate a random Fernet key."""
        return Fernet.generate_key().decode()

    @staticmethod
    def encrypt_data(data: bytes, key: str) -> bytes:
        """Encrypt bytes payload using key."""
        fernet = Fernet(key.encode())
        return fernet.encrypt(data)

    @staticmethod
    def decrypt_data(token: bytes, key: str) -> bytes:
        """Decrypt bytes token using key."""
        fernet = Fernet(key.encode())
        return fernet.decrypt(token)


security_service = SecurityService()
