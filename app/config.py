import os

from dotenv import load_dotenv


load_dotenv()


GROQ_API_KEY = os.getenv("GROQ_API_KEY")

GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-120b"
)

VECTORSTORE_PATH = os.getenv(
    "VECTORSTORE_PATH",
    "vectorstore"
)

DATABASE_PATH = os.getenv(
    "DATABASE_PATH",
    "priorauth.db"
)


if not GROQ_API_KEY:
    raise ValueError(
        "GROQ_API_KEY is missing. Add it to your .env file."
    )
