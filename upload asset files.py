import os
filepath = input("Enter file Path: ")
release_file_path = rf"{filepath}"
release_tag = str(input("Enter Release Tag: "))
files=int(input("How many files: "))
startnum=int(input("Where to start: "))
# Assuming you want to iterate from 2 to 29
for i in range(startnum, files+1):
    file_number = f"{i:01d}"  # Format the number with leading zeros
    file_path = f'{release_file_path}-{file_number}.bin'
    
    command = f'gh release upload {release_tag} "{file_path}" --clobber'
    
    # Execute the command
    os.system(command)
