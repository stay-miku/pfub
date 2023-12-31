import shutil
import os
from PIL import Image
import io
from typing import List
import html


special_char_to_blank = ["-", "(", ")", "（", "）", "'", "“", "\"", "・", "/", "\\", ".", "+"]
special_char_to_underline = [" "]


def replace_text(text: str) -> str:
    return html.escape(text)


def replace_special_char(tags: List[str]) -> List[str]:
    for char in special_char_to_underline:
        tags = [i.replace(char, "_") for i in tags]
    for char in special_char_to_blank:
        tags = [i.replace(char, "") for i in tags]

    return tags


# rm -rf ./*
def delete_files_in_folder(folder_path):
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        if os.path.isfile(file_path):
            os.remove(file_path)
        elif os.path.isdir(file_path):
            shutil.rmtree(file_path)


def get_tags(meta):
    tag_list = meta["tags"]["tags"]
    tags = []
    for tag in tag_list:
        if "translation" in tag and "en" in tag["translation"]:
            tags.append("#" + tag["translation"]["en"])
        else:
            tags.append("#" + tag["tag"])
    return replace_special_char(tags)


def compress_image_if_needed(image_bytes, max_size=1024*1024*4):
    result = True
    while result:
        image_bytes, result = compress_image(image_bytes, max_size)

    return image_bytes


def get_image_format(byte_data):
    if byte_data.startswith(b'\x89PNG'):
        return 'png'
    elif byte_data.startswith(b'\xff\xd8'):
        return 'jpeg'
    else:
        raise Exception("未知的文件格式")


def compress_image(image_bytes, max_size=1024*1024*9.5):
    image = Image.open(io.BytesIO(image_bytes))

    if len(image_bytes) >= max_size:
        compression_ratio = max_size / len(image_bytes) * 0.8
    elif (image.width + image.height) >= 10000:
        compression_ratio = 10000 / (image.width + image.height) * 0.8
    else:
        return image_bytes, False

    image_format = get_image_format(image_bytes)

    # Resize the image using the compression ratio
    new_width = int(image.width * compression_ratio)
    new_height = int(image.height * compression_ratio)
    resized_image = image.resize((new_width, new_height))

    # Save the resized image to a bytes object
    output = io.BytesIO()
    resized_image.save(output, image_format)
    compressed_bytes = output.getvalue()
    output.close()

    return compressed_bytes, len(compressed_bytes) >= max_size or resized_image.height + resized_image.width >= 10000
