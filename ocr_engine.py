import easyocr
import numpy as np 


#Reads text from images

#OCR model intialization 
reader=easyocr.Reader(['en', 'hi'], gpu=False)

def run_ocr(images):
    text_blocks=[]
    for img in images:
        img_np =np.array(img)
        result = reader.readtext(img_np, detail=0)
        text_blocks.append(" ".join(result) )
    return "\n".join(text_blocks)


    

    
def clean_text(raw_text):
    raw_text=raw_text.lower()
    raw_text=raw_text.replace("\n", " ")
    raw_text=" ".join (raw_text.split())
    return raw_text


  