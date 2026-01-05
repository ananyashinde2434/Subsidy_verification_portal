#Takes a file path
#Checks: PDF or image
#Converts PDF → images
#Returns images
import os
from pdf2image import convert_from_path
from PIL import Image

 
def normalize_to_images(file_path):
    _,ext=os.path.splitext(file_path)
    ext=ext.lower()

    if ext == ".pdf":
        return convert_from_path(file_path)
    elif ext in [".jpg", ".jpeg", ".png"]:
        return [Image.open(file_path)]
    else:
        raise ValueError("Unsuported file type")