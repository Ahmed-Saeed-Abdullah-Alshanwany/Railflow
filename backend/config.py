import os
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

class Config:
    # Database Configuration
    DB_NAME = os.getenv("DB_NAME", "railflow_db")
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "railflow_secure_password_2026")
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5435")

    # Transitland Configuration
    TRANSITLAND_API_KEY = os.getenv("TRANSITLAND_API_KEY")
    DEFAULT_OPERATOR_ID = os.getenv("DEFAULT_OPERATOR_ID", "o-u33-s~bahnberlingmbh")

    # Groq API Configuration
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
    GROQ_API_URL = os.getenv("GROQ_API_URL", "https://api.groq.com/openai/v1")
    GROQ_TEMPERATURE = float(os.getenv("GROQ_TEMPERATURE", "0.15"))
    GROQ_MAX_TOKENS = int(os.getenv("GROQ_MAX_TOKENS", "1200"))

    @classmethod
    def validate(cls):
        """Validates that critical configurations are present."""
        errors = []
        if not cls.GROQ_API_KEY or cls.GROQ_API_KEY == "gsk_placeholder_replace_with_your_key":
            errors.append("GROQ_API_KEY is not configured or is using the default placeholder.")
        
        if errors:
            print(f"Warning: Configuration checks failed:\n" + "\n".join(errors))
            return False
        return True
