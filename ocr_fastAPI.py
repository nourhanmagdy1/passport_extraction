# !pip --q install passporteye
# !pip --q install easyocr
# !pip --q install tesseract-ocr
# !pip --q install libtesseract-dev

import os
import string as st
from dateutil import parser
import matplotlib.image as mpimg
import cv2
from passporteye import read_mrz
import json
import easyocr
import warnings
from datetime import datetime
from dateutil.relativedelta import relativedelta
warnings.filterwarnings('ignore')
from fastapi import FastAPI, Request
import uvicorn
from PIL import Image, ImageOps
from fastapi.responses import JSONResponse
import pytesseract
pytesseract.pytesseract.tesseract_cmd = './Tesseract-OCR/tesseract.exe'


def parse_date(string):
    date = parser.parse(string, yearfirst=True).date()
    return date.strftime('%d/%m/%Y')

def clean(string):
    return ''.join(i for i in string if i.isalnum()).upper()

def get_country_name(country_code):
    with open('./country_codes.json') as f:
        country_codes = json.load(f)
    country_name = ''
    for country in country_codes:
        if country['alpha-3'] == country_code:
            country_name = country['name']
            return country_name.upper()
    return country_code

def get_sex(code):
    if code in ['M', 'm', 'F', 'f']:
        sex = code.upper()
    elif code == '0':
        sex = 'M'
    else:
        sex = 'F'
    return sex

def get_data(img_name):
    user_info = {}
    new_im_path = 'tmp.png'
    im_path = img_name
    # Crop image to Machine Readable Zone(MRZ)
    mrz = read_mrz(im_path, save_roi=True)
    try:
        if mrz:
            mpimg.imsave(new_im_path, mrz.aux['roi'], cmap='gray')

            img = cv2.imread(new_im_path)
            img = cv2.resize(img, (1110, 140))

            allowlist = st.ascii_letters+st.digits+'< '
            reader=easyocr.Reader(lang_list=['en'], gpu=False)
            code = reader.readtext(img, paragraph=False, detail=0, allowlist=allowlist)
            a, b = code[0].upper(), code[1].upper()

            if len(a) < 44:
                a = a + '<'*(44 - len(a))
            if len(b) < 44:
                    b = '<'*(44 - len(b))+ b

            surname_names = a[5:44].split('<', 1)
            if len(surname_names) < 2:
                surname_names += ['']
            surname, names = surname_names
            names=names[1:]
            user_info['surname'] = surname.replace('<', ' ').strip().upper()
            user_info['name'] = names.replace('<', ' ').strip().upper()
            if '   ' in user_info['name']:
                user_info['name'], _ =user_info['name'].split('   ', 1)
            user_info['sex'] = get_sex(clean(b[20]))
            user_info['date_of_birth'] = parse_date(b[13:19])
            user_info['nationality'] = get_country_name(a[2:5])
            if user_info['date_of_birth'] >= "01/01/2025" :
                user_info['date_of_birth']=user_info['date_of_birth'].replace('/20','/19')
            if user_info['nationality'] == "U54" :
                user_info['nationality']=user_info['nationality'].replace('54','SA')
            if user_info['nationality'] == "U5A" :
                user_info['nationality']=user_info['nationality'].replace('5A','SA')
            if user_info['nationality'] == "US4" :
                user_info['nationality']=user_info['nationality'].replace('S4','SA')
            if user_info['nationality'] == "U4" :
                user_info['nationality']=user_info['nationality'].replace('4','SA')
            if user_info['nationality'] == "U5" :
                user_info['nationality']=user_info['nationality'].replace('5','SA')
            if user_info['nationality'] == "US" :
                user_info['nationality']=user_info['nationality'].replace('S','SA')
            if user_info['nationality'] == "UA" :
                user_info['nationality']=user_info['nationality'].replace('A','SA')
            user_info['passport_type'] = clean(a[0:2])
            user_info['passport_number']  = clean(b[0:9])
            if len(user_info['passport_number']) != 9:
                user_info['passport_number']=''
            user_info['issuing_country'] = get_country_name(clean(a[2:5]))
            user_info['expiration_date'] = parse_date(b[21:27])
            dtObj = datetime.strptime(user_info['expiration_date'], '%d/%m/%Y')
            user_info['issue_date']= dtObj - relativedelta(years=10, days=-1)
            user_info['issue_date'] = user_info['issue_date'].strftime("%d/%m/%Y")
            user_info['personal_number'] = clean(b[28:42])
            os.remove(new_im_path)
            return user_info
    except:
        os.remove(new_im_path)
        return {"Status:": 'Machine cannot read this image.'}


app = FastAPI()

@app.get("/send")
async def extract_passport_info(image: str):
    try:
        imgg = Image.open(image)
        img = imgg.convert('RGB')
        im = ImageOps.exif_transpose(img)
        im.save('ima.jpg')
        data = get_data('ima.jpg')
        os.remove('ima.jpg')
        return JSONResponse(content=data)
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})


if __name__ == "__main__":
    uvicorn.run(app)

