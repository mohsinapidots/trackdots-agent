import platform
import time
import uuid
from agent.config import SCREENSHOT_DIR
from agent.utils.logger import get_logger

log = get_logger("screenshot")


def capture_screenshot():
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    ts   = int(time.time())
    name = f"{ts}_{uuid.uuid4().hex}.webp"
    path = SCREENSHOT_DIR / name

    try:
        from PIL import Image

        if platform.system() == "Darwin":
            import Quartz

            image = Quartz.CGWindowListCreateImage(
                Quartz.CGRectInfinite,
                Quartz.kCGWindowListOptionOnScreenOnly,
                Quartz.kCGNullWindowID,
                Quartz.kCGWindowImageDefault,
            )
            if image is None:
                log.error("CGWindowListCreateImage returned None")
                return None

            width  = Quartz.CGImageGetWidth(image)
            height = Quartz.CGImageGetHeight(image)
            bpr    = Quartz.CGImageGetBytesPerRow(image)
            bpp    = Quartz.CGImageGetBitsPerPixel(image)
            provider = Quartz.CGImageGetDataProvider(image)
            raw_data = bytes(Quartz.CGDataProviderCopyData(provider))

            if bpp == 32:
                img = Image.frombytes('RGBA', (width, height), raw_data, 'raw', 'BGRA', bpr, 1)
                img = img.convert('RGB')
            elif bpp == 24:
                img = Image.frombytes('RGB', (width, height), raw_data, 'raw', 'BGR', bpr, 1)
            else:
                img = Image.frombytes('RGBA', (width, height), raw_data, 'raw', 'BGRA', bpr, 1)
                img = img.convert('RGB')

        elif platform.system() == "Windows":
            import mss
            with mss.mss() as sct:
                monitor = sct.monitors[0]  # full virtual desktop
                sct_img = sct.grab(monitor)
                img = Image.frombytes('RGB', sct_img.size, sct_img.bgra, 'raw', 'BGRX')

        else:
            # Linux
            import mss
            with mss.mss() as sct:
                monitor = sct.monitors[0]
                sct_img = sct.grab(monitor)
                img = Image.frombytes('RGB', sct_img.size, sct_img.bgra, 'raw', 'BGRX')

        img.thumbnail((1600, 1000), Image.LANCZOS)
        img.save(path, format='WEBP', quality=70, method=6)

        log.info("Screenshot saved: %s (%d bytes)", path, path.stat().st_size)
        return {"path": str(path), "size": path.stat().st_size, "format": "webp"}

    except Exception as e:
        log.error("Screenshot capture failed: %s", e)
        return None
