import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="omni-test-")
os.environ.update(OMNI_DATA=os.path.join(_tmp, "data"), OMNI_DEMO=os.path.join(_tmp, "demo"),
                  GEMINI_MODE="fake", OMNI_TELEMETRY_DELAY="0")
