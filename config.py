import os
import certifi
import dotenv

dotenv.load_dotenv()
class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess-secret-key-12345'
    
    # TiDB / MySQL Connection URI
    # Automatically handled by app.py patch for pymysql
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    # SQLALCHEMY_DATABASE_URI = "mysql://2L8B6JDP3yKQqPk.root:l1uPemqZNpiygbmg@gateway01.ap-southeast-1.prod.aws.tidbcloud.com:4000/test"
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
