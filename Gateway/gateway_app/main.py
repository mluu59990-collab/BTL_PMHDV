from gateway_app.app import create_app
from gateway_app.config import Settings

app = create_app(Settings())
