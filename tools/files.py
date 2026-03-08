import os
import time


def read_file(path):

    print(f"\nReading file: {path}")

    start = time.time()

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    end = time.time()

    print(f"Read time: {round(end-start,2)} seconds\n")

    return content


def write_file(path, content):

    print(f"\nWriting file: {path}")

    start = time.time()

    os.makedirs(os.path.dirname(path), exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    end = time.time()

    print(f"Write time: {round(end-start,2)} seconds\n")


def list_files(directory):

    print(f"\nScanning directory: {directory}")

    start = time.time()

    files = []

    for root, dirs, filenames in os.walk(directory):
        for name in filenames:
            files.append(os.path.join(root, name))

    end = time.time()

    print(f"Scan time: {round(end-start,2)} seconds")
    print(f"Files found: {len(files)}\n")

    return files