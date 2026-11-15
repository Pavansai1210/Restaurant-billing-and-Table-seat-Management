import base64
import io

import qrcode


def qr_data_url(text):
    """A QR code of the text, as a picture that can be placed inside a page."""
    image = qrcode.make(text)
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(buffer.getvalue()).decode()