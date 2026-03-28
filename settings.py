from dotenv import load_dotenv
import os

load_dotenv()

URL = os.getenv("URL", "https://merchant.onewayqueue.com/queuedept.aspx?i=HV8AuMI4EQWIG5Yu64zc9H7FJxxtJexAbirIpoQ9nM")
NAME = os.getenv("NAME", "")
PHONE = os.getenv("PHONE", "")
ADULTS = int(os.getenv("ADULTS", "2"))
CHILDREN = int(os.getenv("CHILDREN", "0"))
PIN_START = int(os.getenv("PIN_START", "1"))
PIN_END = int(os.getenv("PIN_END", "10000"))
DELAY = float(os.getenv("DELAY", "0.05"))
