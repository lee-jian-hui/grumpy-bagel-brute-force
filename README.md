# grumpy-bagel-brute-force

Automated PIN brute-forcer for the Grumpy Bagels OneWayQueue table reservation page.

## Setup

1. Copy the example env file and fill in your details:
   ```bash
   cp .env.example .env
   ```

3. Edit `.env`:
   ```
   URL=https://merchant.onewayqueue.com/queuedept.aspx?i=HV8AuMI4EQWIG5Yu64zc9H7FJxxtJexAbirIpoQ9nM
   NAME=Your Name
   PHONE=+601XXXXXXXX
   ADULTS=2
   CHILDREN=0
   PIN_START=1
   PIN_END=10000
   DELAY=0.05
   ```

## Run

```bash
uv run main.py
```

The script will:
1. Fetch the page and print all discovered form fields
2. Try each PIN from `PIN_START` to `PIN_END`
3. Print the PIN and stop as soon as a successful login is detected

## Configuration

| Key | Description | Default |
|---|---|---|
| `URL` | Queue page URL | pre-filled |
| `NAME` | Your name | |
| `PHONE` | Your mobile number (e.g. `+601XXXXXXXX`) | |
| `ADULTS` | Number of adults | `2` |
| `CHILDREN` | Number of children | `0` |
| `PIN_START` | First PIN to try | `1` |
| `PIN_END` | Last PIN to try | `10000` |
| `DELAY` | Seconds between requests | `0.05` |

## User Agent

The default user agent is `UserAgent.ANDROID`. To change it, edit the bottom of `main.py`:

```python
SESSION.headers.update({
    "User-Agent": UserAgent.ANDROID,  # or UserAgent.IOS / UserAgent.DESKTOP
    ...
})
```
