from dotenv import find_dotenv, dotenv_values
import pathlib

file_path = pathlib.Path().cwd()
static_dir = str(pathlib.Path(pathlib.Path().cwd(), "static"))
config = dotenv_values(find_dotenv(f"{file_path}/.env"))

DATABASE_URL = config.get("DATABASE_URL")
