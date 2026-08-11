import urllib.request
import ssl

url = "https://raw.githubusercontent.com/intel-iot-devkit/sample-videos/master/person-bicycle-car-detection.mp4"
output = "sample_video.mp4"

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

print("Downloading video...")
urllib.request.urlretrieve(url, output, context=ctx)
print("Saved to", output)
