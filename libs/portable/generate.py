#!/usr/bin/env python3

import os
import optparse
import subprocess
import sys
from hashlib import md5
import brotli
import datetime

# 4GB maximum
length_count = 4
# encoding
encoding = 'utf-8'

# output: {path: (compressed_data, file_md5)}


def generate_md5_table(folder: str, level) -> dict:
    res: dict = dict()
    curdir = os.curdir
    os.chdir(folder)
    total_files = 0
    total_size = 0
    for root, _, files in os.walk('.'):
        # remove ./
        for f in files:
            md5_generator = md5()
            full_path = os.path.join(root, f)
            print(f"Processing {full_path}...")
            f = open(full_path, "rb")
            content = f.read()
            content_compressed = brotli.compress(
                content, quality=level)
            md5_generator.update(content)
            md5_code = md5_generator.hexdigest().encode(encoding=encoding)
            res[full_path] = (content_compressed, md5_code)
            total_files += 1
            total_size += len(content)
            f.close()
    os.chdir(curdir)
    print(f"=== MD5 table generation complete: {total_files} files, {total_size} bytes ===")
    return res


def write_package_metadata(md5_table: dict, output_folder: str, exe: str):
    output_path = os.path.join(output_folder, "data.bin")
    print("=== Writing package metadata ===")
    print("Output path: " + output_path)
    print("Number of files: " + str(len(md5_table)))
    total_uncompressed = 0
    total_compressed = 0
    for path in md5_table.keys():
        (compressed_data, md5_code) = md5_table[path]
        total_uncompressed += len(compressed_data)
        md5_table_entry = md5_table[path]
        total_compressed += len(md5_table_entry[0])
    print(f"Total uncompressed: {total_uncompressed} bytes")
    print(f"Total compressed: {total_compressed} bytes")
    print(f"Compression ratio: {total_uncompressed / max(total_compressed, 1):.2f}x")
    with open(output_path, "wb") as f:
        f.write("LUODA".encode(encoding=encoding))
        for path in md5_table.keys():
            (compressed_data, md5_code) = md5_table[path]
            data_length = len(compressed_data)
            path = path.encode(encoding=encoding)
            # path length & path
            f.write((len(path)).to_bytes(length=length_count, byteorder='big'))
            f.write(path)
            # data length & compressed data
            f.write(data_length.to_bytes(
                length=length_count, byteorder='big'))
            f.write(compressed_data)
            # md5 code
            f.write(md5_code)
        # end
        f.write("LUODA".encode(encoding=encoding))
        # executable
        f.write(exe.encode(encoding='utf-8'))
    file_size = os.path.getsize(output_path)
    print(f"Metadata has been written to {output_path} ({file_size} bytes)")
    if file_size < 1000:
        print("WARNING: data.bin is very small, likely incorrect!")

def write_app_metadata(output_folder: str):
    output_path = os.path.join(output_folder, "app_metadata.toml")
    with open(output_path, "w") as f:
        f.write(f"timestamp = {int(datetime.datetime.now().timestamp() * 1000)}\n")
    print(f"App metadata has been written to {output_path}")

def build_portable(output_folder: str, target: str):
    os.chdir(output_folder)
    cmd = ["cargo", "build", "--release"]
    if target:
        cmd += ["--target", target]
    print("=== Building portable packer ===")
    print("Working dir: " + os.getcwd())
    print("Command: " + " ".join(cmd))
    print("cargo version: ", end="")
    subprocess.run(["cargo", "--version"], check=False)
    sys.stdout.flush()
    ret = subprocess.run(cmd)
    if ret.returncode != 0:
        print("=== CARGO BUILD FAILED with exit code " + str(ret.returncode) + " ===")
        sys.exit(ret.returncode)
    print("=== Portable packer build complete ===")

# Linux: python3 generate.py -f ../luoda-portable-packer/test -o . -e ./test/main.py
# Windows: python3 .\generate.py -f ..\luoda\flutter\build\windows\runner\Debug\ -o . -e ..\luoda\flutter\build\windows\runner\Debug\luoda.exe


if __name__ == '__main__':
    parser = optparse.OptionParser()
    parser.add_option("-f", "--folder", dest="folder",
                      help="folder to compress")
    parser.add_option("-o", "--output", dest="output_folder",
                      help="the root of portable packer project, default is './'")
    parser.add_option("-e", "--executable", dest="executable",
                      help="specify startup file in --folder, default is luoda.exe")
    parser.add_option("-t", "--target", dest="target",
                      help="the target used by cargo")
    parser.add_option("-l", "--level", dest="level", type="int",
                      help="compression level, default is 11, highest", default=11)
    (options, args) = parser.parse_args()
    folder = options.folder or './luoda'
    output_folder = os.path.abspath(options.output_folder or './')

    if not options.executable:
        options.executable = 'luoda.exe'
    if not options.executable.startswith(folder):
        options.executable = folder + '/' + options.executable
    exe: str = os.path.abspath(options.executable)
    if not exe.startswith(os.path.abspath(folder)):
        print("The executable must locate in source folder")
        exit(-1)
    exe = '.' + exe[len(os.path.abspath(folder)):]
    print("Executable path: " + exe)
    print("Compression level: " + str(options.level))
    md5_table = generate_md5_table(folder, options.level)
    write_package_metadata(md5_table, output_folder, exe)
    write_app_metadata(output_folder)
    build_portable(output_folder, options.target)
