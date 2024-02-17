import requests
import time

AUDIO_URL = ""
API_KEY = ""

HEADERS = {
    'authorization': API_KEY,
    'content-type': 'application/json'
}

URL = ''

res = requests.post(URL,
    json={'audio_url': AUDIO_URL},
    headers=HEADERS)

transcript_id = res.json()['id']

while True:
    polling_endpoint = URL + '/' + transcript_id
    res = requests.get(polling_endpoint,headers=HEADERS)
    
    if res.json()['status'] == 'completed':
        filename = transcript_id + '.txt'
        with open(filename, 'w') as f:
            f.write(res.json()['text'])

        break
    else:
        time.sleep(60)
