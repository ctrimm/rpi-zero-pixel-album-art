# network_helper.py — WiFi connection and HTTP utilities for Matrix Portal M4
import time
import rtc

try:
    import wifi
    import socketpool
    import ssl
    import adafruit_requests
    _NATIVE_WIFI = True
except ImportError:
    # Fallback for M4 with ESP32 SPI co-processor
    import board
    import busio
    import digitalio
    from adafruit_esp32spi import adafruit_esp32spi
    import adafruit_esp32spi.adafruit_esp32spi_socket as socket
    import adafruit_requests
    _NATIVE_WIFI = False


class NetworkHelper:
    """Handles WiFi connection and HTTP requests for both M4 (ESP32 SPI) and S3 boards."""

    def __init__(self, ssid, password, timezone_offset=0, debug=False):
        self.ssid = ssid
        self.password = password
        self.timezone_offset = timezone_offset
        self.debug = debug
        self.requests = None
        self._connected = False

    def connect(self, retries=3):
        for attempt in range(retries):
            try:
                if _NATIVE_WIFI:
                    self._connect_native()
                else:
                    self._connect_spi()
                self._connected = True
                print(f"WiFi connected: {self.ssid}")
                return True
            except Exception as e:
                print(f"WiFi attempt {attempt + 1} failed: {e}")
                time.sleep(2)
        return False

    def _connect_native(self):
        import wifi
        import socketpool
        import ssl
        import adafruit_requests

        wifi.radio.connect(self.ssid, self.password)
        pool = socketpool.SocketPool(wifi.radio)
        self.requests = adafruit_requests.Session(pool, ssl.create_default_context())

    def _connect_spi(self):
        esp32_cs = digitalio.DigitalInOut(board.ESP_CS)
        esp32_ready = digitalio.DigitalInOut(board.ESP_BUSY)
        esp32_reset = digitalio.DigitalInOut(board.ESP_RESET)
        spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
        esp = adafruit_esp32spi.ESP_SPIcontrol(spi, esp32_cs, esp32_ready, esp32_reset)
        socket.set_interface(esp)

        while not esp.is_connected:
            try:
                esp.connect_AP(self.ssid, self.password)
            except RuntimeError as e:
                print(f"ESP32 connect error: {e}, retrying...")
                time.sleep(1)

        self.requests = adafruit_requests.Session(socket, None)

    def sync_time(self):
        """Sync RTC via worldtimeapi.org."""
        if not self._connected:
            return False
        try:
            url = "http://worldtimeapi.org/api/ip"
            resp = self.get_json(url)
            if resp and "unixtime" in resp:
                import adafruit_datetime as adt
                epoch = resp["unixtime"] + (self.timezone_offset * 3600)
                t = time.localtime(epoch)
                rtc.RTC().datetime = t
                print(f"Time synced: {t.tm_hour:02d}:{t.tm_min:02d}")
                return True
        except Exception as e:
            print(f"Time sync failed: {e}")
        return False

    def get_json(self, url, headers=None, retries=2):
        if not self.requests:
            return None
        for attempt in range(retries):
            try:
                resp = self.requests.get(url, headers=headers)
                data = resp.json()
                resp.close()
                return data
            except Exception as e:
                print(f"GET JSON failed ({url}): {e}")
                if attempt < retries - 1:
                    time.sleep(1)
        return None

    def post_json(self, url, json_data=None, headers=None):
        if not self.requests:
            return None
        try:
            resp = self.requests.post(url, json=json_data, headers=headers)
            data = resp.json()
            resp.close()
            return data
        except Exception as e:
            print(f"POST JSON failed ({url}): {e}")
        return None

    def get_bytes(self, url, headers=None, retries=2):
        if not self.requests:
            return None
        for attempt in range(retries):
            try:
                resp = self.requests.get(url, headers=headers)
                data = resp.content
                resp.close()
                return data
            except Exception as e:
                print(f"GET bytes failed ({url}): {e}")
                if attempt < retries - 1:
                    time.sleep(1)
        return None

    def save_url_to_file(self, url, filepath, headers=None):
        """Stream a URL response to a file (memory-efficient for images)."""
        if not self.requests:
            return False
        try:
            resp = self.requests.get(url, headers=headers)
            with open(filepath, "wb") as f:
                for chunk in resp.iter_content(chunk_size=64):
                    f.write(chunk)
            resp.close()
            return True
        except Exception as e:
            print(f"Save URL to file failed: {e}")
        return False

    @property
    def connected(self):
        return self._connected
