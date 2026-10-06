import base64
import hashlib
import hmac
import json
import os
import time
import urllib.parse
from typing import Any, Dict, List, Optional, Union

import requests

FATSECRET_API_BASE_URL = "https://platform.fatsecret.com/rest"
