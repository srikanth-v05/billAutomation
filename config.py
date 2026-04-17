import os
import certifi
import dotenv

dotenv.load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess-secret-key-12345'

    # TiDB / MySQL Connection URI
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # SSL Configuration for TiDB Cloud
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
        "connect_args": {
            "ssl": {
                "ca": certifi.where(),
            }
        }
    }

    # Groq API Key (replaces Gemini)
    GROQ_API_KEY = os.environ.get('GROQ_API_KEY')

    # Upload folder
    UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
