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
PIN_PRIORITY_START = os.getenv("PIN_PRIORITY_START")
PIN_PRIORITY_END = os.getenv("PIN_PRIORITY_END")
PRIORITY_RANGE = (
    range(int(PIN_PRIORITY_START), int(PIN_PRIORITY_END) + 1)
    if PIN_PRIORITY_START and PIN_PRIORITY_END else None
)
DELAY = float(os.getenv("DELAY", "0.05"))
PROXIES = [p.strip() for p in os.getenv("PROXIES", "").split(",") if p.strip()]
