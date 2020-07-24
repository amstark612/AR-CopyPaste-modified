import io
import os
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from PIL import Image
import numpy as np
import time
import screenpoint
from datetime import datetime
import pyscreenshot
import requests
import logging
import argparse
from shutil import copyfile
import ps

logging.basicConfig(level=logging.INFO)

parser = argparse.ArgumentParser()
parser.add_argument('--basnet_service_ip', required=True, help="The BASNet service IP address")
parser.add_argument('--basnet_service_host', help="Optional, the BASNet service host")
args = parser.parse_args()

max_view_size = 700
max_screenshot_size = 400

# Initialize the Flask application.
app = Flask(__name__)
CORS(app)


# Simple probe.
@app.route('/', methods=['GET'])
def hello():
    return 'Hello AR Cut Paste!'

# Ping to wake up the BASNet service.
@app.route('/ping', methods=['GET'])
def ping():
    logging.info('ping')
    r = requests.get(args.basnet_service_ip, headers={'Host': args.basnet_service_host})
    logging.info(f'pong: {r.status_code} {r.content}')
    return 'pong'

# Called when a user wants to keep an image
@app.route('/keep',methods=['GET'])
def keep():
    now = datetime.today().strftime('%Y-%m-%d_%H-%M-%S')
    copyfile('cut_current.png','IMAGES/' + now + '.png')
    logging.info("hello")
    return 'saved'
    
# The cut endpoints performs the salience detection / background removal.
# And store a copy of the result to be pasted later.
@app.route('/cut', methods=['POST'])
def save():
    start = time.time()
    logging.info(' CUT')

    # Convert string of image data to uint8.
    if 'data' not in request.files:
        return jsonify({
            'status': 'error',
            'error': 'missing file param `data`'
        }), 400
    data = request.files['data'].read()
    if len(data) == 0:
        return jsonify({'status:': 'error', 'error': 'empty image'}), 400

    # Save debug locally.
    with open('cut_received.jpg', 'wb') as f:
        f.write(data)

    # Send to BASNet service.
    logging.info(' > sending to BASNet...')
    headers = {}
    if args.basnet_service_host is not None:
        headers['Host'] = args.basnet_service_host
    files= {'data': open('cut_received.jpg', 'rb')}
    res = requests.post(args.basnet_service_ip, headers=headers, files=files )
    # logging.info(res.status_code)

    # Save mask locally.
    logging.info(' > saving results...')
    with open('cut_mask.png', 'wb') as f:
        f.write(res.content)
        # shutil.copyfileobj(res.raw, f)

    # resize and save mask
    logging.info(' > opening and resizing mask...')
    mask = Image.open('cut_mask.png')
    mask = mask.resize((256,256))

    logging.info(' > saving resized mask...')
    mask.save('cut_mask.png')
    
    logging.info(' > opening mask...')
    mask = Image.open('cut_mask.png').convert("L")


    # Convert string data to PIL Image.
    logging.info(' > compositing final image...')
    ref = Image.open(io.BytesIO(data))
    empty = Image.new("RGBA", ref.size, 0)
    img = Image.composite(ref, empty, mask)

    # TODO: currently hack to manually scale up the images. Ideally this would
    # be done respective to the view distance from the screen.
    img_scaled = img.resize((img.size[0] * 3, img.size[1] * 3))

    # Save locally.
    logging.info(' > saving final image...')
    img_scaled.save('cut_current.png')
    
    # img_scaled.save('cut_current.png')

    # Save to buffer
    buff = io.BytesIO()
    img.save(buff, 'PNG')
    buff.seek(0)

    # Print stats
    logging.info(f'Completed in {time.time() - start:.2f}s')

    # Return data
    return send_file(buff, mimetype='image/png')

if __name__ == '__main__':
    os.environ['FLASK_ENV'] = 'development'
    port = int(os.environ.get('PORT', 3000))
    app.run(debug=True, host='0.0.0.0', port=port)
