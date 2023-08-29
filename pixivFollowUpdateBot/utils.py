import shutil
import os
from PIL import Image
import io


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
    return tags


def compress_image_if_needed(image_bytes, max_size=1024*1024*9.5):
    image = Image.open(io.BytesIO(image_bytes))

    if len(image_bytes) <= max_size:
        return image_bytes

    # Calculate the compression ratio
    compression_ratio = max_size / len(image_bytes)

    # Resize the image using the compression ratio
    new_width = int(image.width * compression_ratio)
    new_height = int(image.height * compression_ratio)
    resized_image = image.resize((new_width, new_height))

    # Save the resized image to a bytes object
    output = io.BytesIO()
    resized_image.save(output, "png")
    compressed_bytes = output.getvalue()
    output.close()

    return compressed_bytes
