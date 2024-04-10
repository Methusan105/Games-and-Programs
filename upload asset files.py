import os
release_file_path = r"C:\Users\Methu\Downloads\Compressed\Update.1.3.6.zip"

# Assuming you want to iterate from 1 to 12
for i in range(1, 6):
    file_number = f"{i:03d}"  # Format the number with leading zeros
    file_path = f'{release_file_path}.{file_number}'
    
    command = f'gh release upload SM2PC "{file_path}" --clobber'
    
    # Execute the command
    os.system(command)