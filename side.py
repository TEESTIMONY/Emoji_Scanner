import requests

def download_file(file_url):
    response = requests.get(file_url)
    if response.status_code == 200:
        return response.content
    else:
        raise Exception("Failed to download file")
    

cal_cunc =download_file('https://dd.dexscreener.com/ds-data/tokens/sui/0xcd86f675b4bfbf415c094ffb231b52b880edffebf4ba0ad6d5d8119ca224eaff::sdrag::sdrag.png')
