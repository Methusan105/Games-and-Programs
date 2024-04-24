import os
release_file_path = r"C:\Users\Methu\Documents\SM2\Spider-Man.2.PC.Port.7z"

# Assuming you want to iterate from 1 to 12
for i in range(1, 48):
    file_number = f"{i:03d}"  # Format the number with leading zeros
    file_path = f'{release_file_path}.{file_number}'
    
    command = f'gh release upload SM2PC "{file_path}" --clobber'
    
    # Execute the command
    os.system(command)